"""Рецепты глазами одного человека: что ему видно и что можно (права — access.py)."""
import re

from sqlalchemy import func, or_
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import delete, select

from ..access import PRIVATE, PUBLIC, VISIBILITIES, can_edit, can_moderate, can_publish, can_view
from ..auth.profile import author as author_of
from ..auth.profile import by_nick
from ..db import session
from ..errors import Conflict, Forbidden, Invalid, NotFound
from ..models import Brew, Favorite, Recipe, RecipePhoto, User, parse_id, unix, utcnow
from .program import program_steps


def excerpt(text, limit=220):
    """Первый абзац описания одной строкой: карточка всё равно обрежет до двух строк."""
    text = " ".join(re.split(r"\n\s*\n", (text or "").strip())[0].split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


class RecipeStore:
    """viewer — вошедший пользователь или None (гость). NotFound — рецепта не видно, Forbidden — видно,
    но этого нельзя. Рецепт целиком — JSONB data (recipes/schemas.py, Recipe), name — для сортировки и поиска."""

    def __init__(self, viewer=None):
        self.viewer = viewer
        self.uid = viewer.id if viewer is not None else None

    def list(self, mine=False, favorites=False, author=None):
        """Опубликованные рецепты всех и свои, недавно изменённые первыми; mine — только свои,
        favorites — только избранные (из тех, что видно: снятый с публикации чужой рецепт пропадает),
        author — ник: рецепты этого пивовара (его опубликованные; свои — все)."""
        visible = Recipe.visibility == PUBLIC
        if self.uid is not None:
            visible = or_(visible, Recipe.user_id == self.uid)
        with session() as s:
            q = (select(Recipe, User.name, User.avatar_version, User.avatar.is_not(None))
                 .join(User, User.id == Recipe.user_id))
            q = q.where(Recipe.user_id == self.uid) if mine else q.where(visible)
            if favorites:
                q = q.join(Favorite, (Favorite.recipe_id == Recipe.id) & (Favorite.user_id == self.uid))
            if author is not None:
                brewer = by_nick(s, author)
                if brewer is None:
                    return []
                q = q.where(Recipe.user_id == brewer.id)
            rows = s.exec(q.order_by(Recipe.updated_at.desc())).all()
            brewed, starred = {}, set()
            if self.uid is not None:                      # варки и избранное — свои, чужие никому не видны
                brewed = {rid: (n, last) for rid, n, last in s.exec(
                    select(Brew.recipe_id, func.count(), func.max(Brew.started_at))
                    .where(Brew.user_id == self.uid, Brew.recipe_id.is_not(None)).group_by(Brew.recipe_id)).all()}
                starred = set(s.exec(select(Favorite.recipe_id).where(Favorite.user_id == self.uid)).all())
            photos = {}
            ids = [r.id for r, *_ in rows]
            if ids:
                for rid, pid in s.exec(select(RecipePhoto.recipe_id, RecipePhoto.id)
                                       .where(RecipePhoto.recipe_id.in_(ids)).order_by(RecipePhoto.created_at)).all():
                    photos.setdefault(rid, []).append(str(pid))
        out = []
        for r, name, avatar_version, has_avatar in rows:
            steps = program_steps(r.data)
            n, last = brewed.get(r.id, (0, None))
            out.append({"id": str(r.id), "name": r.name, "style": r.data.get("style"),
                        "targets": r.data.get("targets") or {}, "volume": (r.data.get("batch") or {}).get("volume"),
                        "steps": len(steps), "minutes": sum(int(x["minutes"]) for x in steps),
                        "brews": n, "lastBrewedAt": unix(last), "updatedAt": unix(r.updated_at),
                        "about": excerpt(r.data.get("notes")), "photos": photos.get(r.id, []),
                        "author": author_of(r.user_id, name, avatar_version, has_avatar),
                        "mine": r.user_id == self.uid, "visibility": r.visibility,
                        "publishedAt": unix(r.published_at), "favorite": r.id in starred})
        return out

    def get(self, rid):
        with session() as s:
            return self._view(s, rid).data

    def detail(self, rid):
        """Рецепт и то, что о нём знать интерфейсу: автор, видимость, что можно тому, кто спрашивает."""
        with session() as s:
            r = self._view(s, rid)
            u = s.get(User, r.user_id)
            favorite = self.uid is not None and s.get(Favorite, (self.uid, r.id)) is not None
            meta = {"author": author_of(u.id, u.name, u.avatar_version, u.avatar is not None),
                    "mine": r.user_id == self.uid,
                    "visibility": r.visibility, "publishedAt": unix(r.published_at), "favorite": favorite,
                    "canEdit": can_edit(self.viewer, r), "canModerate": can_moderate(self.viewer, r)}
            return {**r.data, "meta": meta}

    def set_favorite(self, rid, on):
        """В избранное или из него — любой видимый рецепт, свой тоже. Повторное действие ничего не меняет."""
        if self.uid is None:
            raise Forbidden("войдите, чтобы сохранять рецепты в избранное")
        with session() as s:
            r = self._view(s, rid)
            if on:
                s.exec(insert(Favorite).values(user_id=self.uid, recipe_id=r.id, created_at=utcnow())
                       .on_conflict_do_nothing())
            else:
                s.exec(delete(Favorite).where(Favorite.user_id == self.uid, Favorite.recipe_id == r.id))
            s.commit()

    def save(self, rid, recipe):
        """rid = None — новый рецепт (личный, пока автор его не опубликует). Возвращает id."""
        with session() as s:
            if rid is None:
                if self.uid is None:
                    raise Forbidden("войдите, чтобы сохранять рецепты")
                r = Recipe(user_id=self.uid, name="")
            else:
                r = self._view(s, rid)
                if not can_edit(self.viewer, r):
                    raise Forbidden("это чужой рецепт — сохраните себе копию")
            r.name, r.data = recipe["name"], recipe
            r.updated_at = utcnow()
            s.add(r)
            s.commit()
            return str(r.id)

    def delete(self, rid):
        with session() as s:
            r = self._view(s, rid)
            if not (can_edit(self.viewer, r) or can_moderate(self.viewer, r)):
                raise Forbidden("удалить можно только свой рецепт")
            s.delete(r)
            s.commit()

    def set_visibility(self, rid, visibility):
        """Опубликовать или снять с публикации. Автор — в обе стороны (публиковать — с подтверждённой почтой),
        администратор — только снять чужой рецепт с публикации."""
        if visibility not in VISIBILITIES:
            raise Invalid(f"видимость — {' или '.join(VISIBILITIES)}")
        with session() as s:
            r = self._view(s, rid)
            if can_edit(self.viewer, r):
                if visibility == PUBLIC and not can_publish(self.viewer):
                    raise Forbidden("подтвердите почту, чтобы публиковать рецепты")
            elif not (can_moderate(self.viewer, r) and visibility == PRIVATE):
                raise Forbidden("это чужой рецепт")
            if visibility == PUBLIC and r.visibility != PUBLIC:
                r.published_at = utcnow()
            r.visibility = visibility
            s.add(r)
            s.commit()

    # ── фото пива ─────────────────────────────────────────────────────────────
    def photos(self, rid):
        with session() as s:
            r = self._view(s, rid)
            rows = s.exec(select(RecipePhoto.id, RecipePhoto.credit, RecipePhoto.created_at)
                          .where(RecipePhoto.recipe_id == r.id).order_by(RecipePhoto.created_at)).all()
            return [{"id": str(pid), "credit": credit, "createdAt": unix(at)} for pid, credit, at in rows]

    def add_photo(self, rid, content_type, data, thumb=None, credit=None, limit=None):
        """limit — сколько фото может быть у рецепта; больше — Conflict."""
        with session() as s:
            r = self._view(s, rid)
            if not can_edit(self.viewer, r):
                raise Forbidden("добавить фото можно только к своему рецепту")
            if limit and s.exec(select(func.count()).select_from(RecipePhoto)
                                .where(RecipePhoto.recipe_id == r.id)).one() >= limit:
                raise Conflict(f"у рецепта уже {limit} фото")
            p = RecipePhoto(recipe_id=r.id, user_id=self.uid, content_type=content_type, data=data, thumb=thumb,
                            credit=credit)
            s.add(p)
            s.commit()
            return {"id": str(p.id), "credit": p.credit, "createdAt": unix(p.created_at)}

    def photo(self, pid, thumb=False):
        """(content_type, data); thumb — превью (JPEG), если оно есть."""
        with session() as s:
            p, _ = self._photo(s, pid)
            return ("image/jpeg", p.thumb) if thumb and p.thumb else (p.content_type, p.data)

    def delete_photo(self, pid):
        with session() as s:
            p, r = self._photo(s, pid)
            if not (can_edit(self.viewer, r) or can_moderate(self.viewer, r)):
                raise Forbidden("удалить можно только фото своего рецепта")
            s.delete(p)
            s.commit()

    def _photo(self, s, pid):
        p = s.get(RecipePhoto, uid) if (uid := parse_id(pid)) else None
        r = s.get(Recipe, p.recipe_id) if p is not None else None
        if r is None or not can_view(self.viewer, r):
            raise NotFound("фото не найдено")
        return p, r

    def _view(self, s, rid):
        r = s.get(Recipe, uid) if (uid := parse_id(rid)) else None
        if r is None or not can_view(self.viewer, r):
            raise NotFound("рецепт не найден")
        return r
