"""Уведомления на сайте: кому и о чём сообщить, список, непрочитанные, настройка push.

О новом комментарии узнают автор рецепта (comment) и автор комментария, на который ответили (reply); если это
один человек — одно уведомление, «ответ». О своих комментариях не сообщаем. Уведомление записывается в той же
транзакции, что и комментарий; push уходит после неё — тем, у кого он не выключен (users.push_comments).
Удалили комментарий — уходят и уведомления о нём. Рецепт сняли с публикации — его уведомления не видны тем,
кому не виден он сам (access.py). Напоминания о брожении (brew) пишет brewery/reminders.py — со ссылкой на варку;
их push — по users.push_brews.
"""
from sqlalchemy import func, or_
from sqlmodel import delete, select, update

from ..access import PUBLIC
from ..auth.profile import author
from ..db import session
from ..models import Brew, Comment, Notification, Recipe, User, parse_id, unix, utcnow

COMMENT, REPLY, BREW = "comment", "reply", "brew"
LIST_MAX = 50
EXCERPT = 140                        # сколько текста комментария показать в уведомлении


def excerpt(text, limit=EXCERPT):
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def recipe_path(recipe_id, comment_id):
    """Адрес комментария на странице рецепта — туда ведёт уведомление."""
    return f"/recipes/{recipe_id}#c-{comment_id}"


class Notices:
    """Запись уведомлений об обсуждении. pusher — push на устройства (push/pusher.py; без ключа — выключен),
    streams — открытым вкладкам «новое уведомление» (brewery/streams.py)."""

    def __init__(self, pusher=None, streams=None):
        self.pusher = pusher
        self.streams = streams

    def comment(self, s, c, recipe, replied_to=None):
        """Новый комментарий c к recipe; replied_to — комментарий, на который ответили (до переноса ответа в ветку).
        Уведомления добавляются в сессию s и уходят в базу вместе с комментарием; вернуть отправку — вкладкам
        и push — вызвать после commit."""
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
        if self.streams is not None:
            for uid in to:
                self.streams.notice(uid)
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
        """Свои уведомления: о варках — все, об обсуждении — о рецептах, которые пользователю видны."""
        return (Notification.user_id == self.user.id,
                or_(Notification.kind == BREW, Recipe.visibility == PUBLIC, Recipe.user_id == self.user.id))

    def list(self, limit=LIST_MAX):
        with session() as s:
            rows = s.exec(select(Notification, Recipe.data["name"].astext, Comment.text,
                                 User.name, User.avatar_version, User.avatar.is_not(None), Brew.name)
                          .outerjoin(Recipe, Recipe.id == Notification.recipe_id)
                          .outerjoin(Comment, Comment.id == Notification.comment_id)
                          .outerjoin(User, User.id == Notification.actor_id)
                          .outerjoin(Brew, Brew.id == Notification.brew_id)
                          .where(*self._mine())
                          .order_by(Notification.created_at.desc()).limit(limit)).all()
        return [self._view(n, *rest) for n, *rest in rows]

    @staticmethod
    def _view(n, recipe_name, text, name, version, has, brew_name):
        base = {"id": str(n.id), "kind": n.kind, "createdAt": unix(n.created_at), "read": n.read_at is not None}
        if n.kind == BREW:
            data = n.data or {}
            return {**base, "brew": {"id": str(n.brew_id), "name": brew_name}, "title": data.get("title"),
                    "text": data.get("text") or ""}
        return {**base, "actor": author(n.actor_id, name, version, has),
                "recipe": {"id": str(n.recipe_id), "name": recipe_name or "Без названия"},
                "commentId": str(n.comment_id), "text": excerpt(text or "")}

    def unread(self):
        with session() as s:
            return s.exec(select(func.count()).select_from(Notification)
                          .outerjoin(Recipe, Recipe.id == Notification.recipe_id)
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
            u = s.get(User, self.user.id)
            return {"pushComments": u.push_comments, "pushBrews": u.push_brews}

    def set_settings(self, push_comments=None, push_brews=None):
        """Не указанное — как было."""
        with session() as s:
            u = s.get(User, self.user.id)
            if push_comments is not None:
                u.push_comments = push_comments
            if push_brews is not None:
                u.push_brews = push_brews
            s.add(u)
            s.commit()
            return {"pushComments": u.push_comments, "pushBrews": u.push_brews}
