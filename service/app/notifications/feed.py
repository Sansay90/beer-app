"""Уведомления на сайте: кому и о чём сообщить, список, непрочитанные, настройка push.

О новом комментарии узнают автор рецепта (comment) и автор комментария, на который ответили (reply); если это
один человек — одно уведомление, «ответ». О своих комментариях не сообщаем. Уведомление записывается в той же
транзакции, что и комментарий; push уходит после неё — тем, у кого он не выключен (users.push_comments).
Удалили комментарий — уходят и уведомления о нём. Рецепт сняли с публикации — его уведомления не видны тем,
кому не виден он сам (access.py).
"""
from sqlalchemy import func, or_
from sqlmodel import delete, select, update

from ..access import PUBLIC
from ..auth.profile import author
from ..db import session
from ..models import Comment, Notification, Recipe, User, parse_id, unix, utcnow

COMMENT, REPLY = "comment", "reply"
LIST_MAX = 50
EXCERPT = 140                        # сколько текста комментария показать в уведомлении


def excerpt(text, limit=EXCERPT):
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def recipe_path(recipe_id, comment_id):
    """Адрес комментария на странице рецепта — туда ведёт уведомление."""
    return f"/recipes/{recipe_id}#c-{comment_id}"


class Notices:
    """Запись уведомлений об обсуждении. pusher — push на устройства (push/pusher.py; без ключа — выключен)."""

    def __init__(self, pusher=None):
        self.pusher = pusher

    def comment(self, s, c, recipe, replied_to=None):
        """Новый комментарий c к recipe; replied_to — комментарий, на который ответили (до переноса ответа в ветку).
        Уведомления добавляются в сессию s и уходят в базу вместе с комментарием; вернуть отправку push —
        вызвать после commit."""
        to = {}
        if recipe.user_id != c.user_id:
            to[recipe.user_id] = COMMENT
        if replied_to is not None and replied_to.user_id != c.user_id and replied_to.deleted_at is None:
            to[replied_to.user_id] = REPLY
        for uid, kind in to.items():
            s.add(Notification(user_id=uid, kind=kind, actor_id=c.user_id, recipe_id=recipe.id, comment_id=c.id))
        name, text, rid, cid, actor_id = recipe.data.get("name") or "Без названия", c.text, recipe.id, c.id, c.user_id
        return lambda: self._push(to, actor_id, name, text, rid, cid)

    def _push(self, to, actor_id, name, text, rid, cid):
        if not to or self.pusher is None:
            return
        with session() as s:
            actor = s.get(User, actor_id)
            wanting = set(s.exec(select(User.id).where(User.id.in_(to), User.push_comments)).all())
        who = actor.name if actor is not None and actor.name else "Неизвестный пивовар"
        for uid, kind in to.items():
            if uid not in wanting:
                continue
            title = f"Вам ответили в рецепте «{name}»" if kind == REPLY else f"Новый комментарий к рецепту «{name}»"
            self.pusher.notify(uid, {"title": title, "body": f"{who}: {excerpt(text, 100)}", "tag": f"comment-{cid}",
                                     "url": recipe_path(rid, cid)})

    @staticmethod
    def forget(s, comment_id):
        """Комментарий удалён (остался пустым в ветке) — уведомления о нём больше не нужны."""
        s.exec(delete(Notification).where(Notification.comment_id == comment_id))


class Feed:
    """Уведомления пользователя user: новые первыми."""

    def __init__(self, user):
        self.user = user

    def _mine(self):
        """Свои уведомления о рецептах, которые пользователю видны."""
        return (Notification.user_id == self.user.id,
                or_(Recipe.visibility == PUBLIC, Recipe.user_id == self.user.id))

    def list(self, limit=LIST_MAX):
        with session() as s:
            rows = s.exec(select(Notification, Recipe.data["name"].astext, Comment.text,
                                 User.name, User.avatar_version, User.avatar.is_not(None))
                          .join(Recipe, Recipe.id == Notification.recipe_id)
                          .join(Comment, Comment.id == Notification.comment_id)
                          .join(User, User.id == Notification.actor_id)
                          .where(*self._mine())
                          .order_by(Notification.created_at.desc()).limit(limit)).all()
        return [{"id": str(n.id), "kind": n.kind, "createdAt": unix(n.created_at), "read": n.read_at is not None,
                 "actor": author(n.actor_id, name, version, has),
                 "recipe": {"id": str(n.recipe_id), "name": recipe_name or "Без названия"},
                 "commentId": str(n.comment_id), "text": excerpt(text)}
                for n, recipe_name, text, name, version, has in rows]

    def unread(self):
        with session() as s:
            return s.exec(select(func.count()).select_from(Notification)
                          .join(Recipe, Recipe.id == Notification.recipe_id)
                          .where(*self._mine(), Notification.read_at.is_(None))).one()

    def read(self, ids=None):
        """Отметить прочитанными: ids — эти (чужие и непонятные молча пропускаются), None — все."""
        where = [Notification.user_id == self.user.id, Notification.read_at.is_(None)]
        if ids is not None:
            where.append(Notification.id.in_([u for i in ids if (u := parse_id(i))]))
        with session() as s:
            s.exec(update(Notification).where(*where).values(read_at=utcnow()))
            s.commit()

    def settings(self):
        with session() as s:
            return {"pushComments": s.get(User, self.user.id).push_comments}

    def set_settings(self, push_comments):
        with session() as s:
            u = s.get(User, self.user.id)
            u.push_comments = push_comments
            s.add(u)
            s.commit()
            return {"pushComments": u.push_comments}
