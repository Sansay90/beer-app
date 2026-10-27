"""Обсуждение рецепта: комментарии с ответами и голоса — за рецепт и за комментарии.

Видно тем, кому виден рецепт (access.py); писать и голосовать — вошедшим; править комментарий — его автору,
удалять — ему и администратору. Голос — 1 (нравится) или −1 (не нравится), один на человека; 0 — снять.
За свой рецепт и свой комментарий не голосуют. Ответ на ответ встаёт в ту же ветку — уровень один.
"""
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import delete, select

from ..access import can_view, is_admin
from ..auth.profile import author
from ..db import session
from ..errors import Forbidden, Invalid, NotFound
from ..models import Comment, CommentVote, Recipe, RecipeVote, User, parse_id, unix, utcnow

TEXT_MAX = 2000
VOTES = (-1, 0, 1)


def check_text(text):
    text = (text or "").strip()
    if not text:
        raise Invalid("напишите текст комментария")
    if len(text) > TEXT_MAX:
        raise Invalid(f"комментарий длиннее {TEXT_MAX} знаков — сократите")
    return text


def check_vote(value):
    if value not in VOTES:
        raise Invalid("голос — 1, −1 или 0")
    return value


def tally(s, model, key, ids):
    """{id: (нравится, не нравится)} по голосам за рецепты или комментарии."""
    if not ids:
        return {}
    col = getattr(model, key)
    rows = s.exec(select(col, func.count().filter(model.value > 0), func.count().filter(model.value < 0))
                  .where(col.in_(ids)).group_by(col)).all()
    return {k: (likes, dislikes) for k, likes, dislikes in rows}


def votes_of(s, model, key, user_id, ids):
    """{id: голос} того, кто спрашивает."""
    if user_id is None or not ids:
        return {}
    col = getattr(model, key)
    return dict(s.exec(select(col, model.value).where(model.user_id == user_id, col.in_(ids))).all())


def comment_counts(s, recipe_ids):
    """{id рецепта: комментариев} — без удалённых."""
    if not recipe_ids:
        return {}
    return dict(s.exec(select(Comment.recipe_id, func.count()).where(Comment.recipe_id.in_(recipe_ids),
                                                                     Comment.deleted_at.is_(None))
                       .group_by(Comment.recipe_id)).all())


class Discussion:
    """Обсуждение глазами viewer (пользователь или None — гость). NotFound — рецепта или комментария не видно."""

    def __init__(self, viewer=None):
        self.viewer = viewer
        self.uid = viewer.id if viewer is not None else None

    # ── комментарии ───────────────────────────────────────────────────────────
    def comments(self, rid):
        """Все комментарии рецепта, старые первыми; ответы — с parentId."""
        with session() as s:
            r = self._recipe(s, rid)
            rows = s.exec(select(Comment, User.name, User.avatar_version, User.avatar.is_not(None))
                          .join(User, User.id == Comment.user_id)
                          .where(Comment.recipe_id == r.id).order_by(Comment.created_at)).all()
            ids = [c.id for c, *_ in rows]
            counts = tally(s, CommentVote, "comment_id", ids)
            mine = votes_of(s, CommentVote, "comment_id", self.uid, ids)
            return [self._view(c, author(c.user_id, name, version, has), counts.get(c.id, (0, 0)), mine.get(c.id, 0))
                    for c, name, version, has in rows]

    def add(self, rid, text, parent_id=None):
        text = check_text(text)
        if self.uid is None:
            raise Forbidden("войдите, чтобы написать комментарий")
        with session() as s:
            r = self._recipe(s, rid)
            parent = None
            if parent_id:
                parent = self._comment(s, parent_id)
                if parent.recipe_id != r.id:
                    raise Invalid("ответ — только на комментарий этого рецепта")
                if parent.parent_id is not None:                  # ответ на ответ — в ту же ветку
                    parent = s.get(Comment, parent.parent_id)
            c = Comment(recipe_id=r.id, user_id=self.uid, parent_id=parent.id if parent else None, text=text)
            s.add(c)
            s.commit()
            u = s.get(User, self.uid)
            return self._view(c, author(u.id, u.name, u.avatar_version, u.avatar is not None), (0, 0), 0)

    def edit(self, cid, text):
        text = check_text(text)
        with session() as s:
            c = self._comment(s, cid)
            if c.user_id != self.uid or c.deleted_at is not None:
                raise Forbidden("изменить можно только свой комментарий")
            c.text, c.edited_at = text, utcnow()
            s.add(c)
            s.commit()
            u = s.get(User, c.user_id)
            counts = tally(s, CommentVote, "comment_id", [c.id]).get(c.id, (0, 0))
            mine = votes_of(s, CommentVote, "comment_id", self.uid, [c.id]).get(c.id, 0)
            return self._view(c, author(u.id, u.name, u.avatar_version, u.avatar is not None), counts, mine)

    def remove(self, cid):
        """Удалить: с ответами — остаётся пустым («комментарий удалён»), без ответов — совсем."""
        with session() as s:
            c = self._comment(s, cid)
            if c.user_id != self.uid and not is_admin(self.viewer):
                raise Forbidden("удалить можно только свой комментарий")
            replies = s.exec(select(func.count()).select_from(Comment).where(Comment.parent_id == c.id)).one()
            if replies:
                c.text, c.deleted_at = "", utcnow()
                s.add(c)
            else:
                s.delete(c)
                parent = s.get(Comment, c.parent_id) if c.parent_id else None
                if parent is not None and parent.deleted_at is not None and s.exec(       # последний ответ
                        select(func.count()).select_from(Comment).where(Comment.parent_id == parent.id,
                                                                        Comment.id != c.id)).one() == 0:
                    s.delete(parent)                                  # пустой удалённый без ответов — не нужен
            s.commit()

    # ── голоса ────────────────────────────────────────────────────────────────
    def vote_recipe(self, rid, value):
        value = check_vote(value)
        with session() as s:
            r = self._recipe(s, rid)
            if r.user_id == self.uid:
                raise Forbidden("за свой рецепт голосовать нельзя")
            self._vote(s, RecipeVote, "recipe_id", r.id, value)
            likes, dislikes = tally(s, RecipeVote, "recipe_id", [r.id]).get(r.id, (0, 0))
            return {"likes": likes, "dislikes": dislikes, "vote": value}

    def vote_comment(self, cid, value):
        value = check_vote(value)
        with session() as s:
            c = self._comment(s, cid)
            if c.user_id == self.uid:
                raise Forbidden("за свой комментарий голосовать нельзя")
            if c.deleted_at is not None:
                raise Invalid("комментарий удалён")
            self._vote(s, CommentVote, "comment_id", c.id, value)
            likes, dislikes = tally(s, CommentVote, "comment_id", [c.id]).get(c.id, (0, 0))
            return {"likes": likes, "dislikes": dislikes, "vote": value}

    def _vote(self, s, model, key, target_id, value):
        if self.uid is None:
            raise Forbidden("войдите, чтобы голосовать")
        col = getattr(model, key)
        if value == 0:
            s.exec(delete(model).where(model.user_id == self.uid, col == target_id))
        else:
            s.exec(insert(model).values(user_id=self.uid, **{key: target_id}, value=value, created_at=utcnow())
                   .on_conflict_do_update(index_elements=["user_id", key], set_={"value": value}))
        s.commit()

    # ── общее ─────────────────────────────────────────────────────────────────
    def _view(self, c, who, counts, mine):
        deleted = c.deleted_at is not None
        own = c.user_id == self.uid
        return {"id": str(c.id), "parentId": str(c.parent_id) if c.parent_id else None,
                "author": None if deleted else who, "text": "" if deleted else c.text,
                "createdAt": unix(c.created_at), "edited": c.edited_at is not None, "deleted": deleted,
                "likes": counts[0], "dislikes": counts[1], "vote": mine,
                "canEdit": own and not deleted, "canDelete": not deleted and (own or is_admin(self.viewer))}

    def _recipe(self, s, rid):
        r = s.get(Recipe, uid) if (uid := parse_id(rid)) else None
        if r is None or not can_view(self.viewer, r):
            raise NotFound("рецепт не найден")
        return r

    def _comment(self, s, cid):
        c = s.get(Comment, uid) if (uid := parse_id(cid)) else None
        r = s.get(Recipe, c.recipe_id) if c is not None else None
        if r is None or not can_view(self.viewer, r):
            raise NotFound("комментарий не найден")
        return c

