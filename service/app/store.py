"""Доступ к данным: рецепты пользователей, их пивоварни и журнал (варки, события, температура)."""
import logging
import queue
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_
from sqlmodel import select

from .access import PRIVATE, PUBLIC, VISIBILITIES, can_edit, can_moderate, can_publish, can_view
from .db import session
from .models import Brew, Device, Event, Reading, Recipe, RecipePhoto, User, utcnow
from .program import program_steps

log = logging.getLogger("brewapp.store")

EVENT_FIELDS = ("kind", "text", "at")


def as_uuid(value):
    """id из URL → UUID; мусор — KeyError (→ 404), а не 500."""
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except ValueError:
        raise KeyError(value)


def unix(dt):
    return dt.timestamp() if dt else None


def from_unix(t):
    return datetime.fromtimestamp(t, timezone.utc)


def excerpt(text, limit=220):
    """Первый абзац описания одной строкой: карточка всё равно обрежет до двух строк."""
    text = " ".join(re.split(r"\n\s*\n", (text or "").strip())[0].split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


class RecipeStore:
    """Рецепты глазами одного человека: viewer — вошедший пользователь или None (гость). Права — access.py:
    KeyError — рецепта не видно (→ 404), PermissionError — видно, но этого нельзя (→ 403).
    Рецепт целиком — JSONB data (schemas.Recipe), name — для сортировки и поиска."""

    def __init__(self, viewer=None):
        self.viewer = viewer
        self.uid = viewer.id if viewer is not None else None

    def list(self, mine=False):
        """Опубликованные рецепты всех и свои, недавно изменённые первыми; mine — только свои."""
        visible = Recipe.visibility == PUBLIC
        if self.uid is not None:
            visible = or_(visible, Recipe.user_id == self.uid)
        with session() as s:
            q = select(Recipe, User.name).join(User, User.id == Recipe.user_id)
            q = q.where(Recipe.user_id == self.uid) if mine else q.where(visible)
            rows = s.exec(q.order_by(Recipe.updated_at.desc())).all()
            brewed = {}
            if self.uid is not None:                      # варки — свои, чужие никому не видны
                brewed = {rid: (n, last) for rid, n, last in s.exec(
                    select(Brew.recipe_id, func.count(), func.max(Brew.started_at))
                    .where(Brew.user_id == self.uid, Brew.recipe_id.is_not(None)).group_by(Brew.recipe_id)).all()}
            photos = {}
            ids = [r.id for r, _ in rows]
            if ids:
                for rid, pid in s.exec(select(RecipePhoto.recipe_id, RecipePhoto.id)
                                       .where(RecipePhoto.recipe_id.in_(ids)).order_by(RecipePhoto.created_at)).all():
                    photos.setdefault(rid, []).append(str(pid))
        out = []
        for r, author in rows:
            steps = program_steps(r.data)
            n, last = brewed.get(r.id, (0, None))
            out.append({"id": str(r.id), "name": r.name, "style": r.data.get("style"),
                        "targets": r.data.get("targets") or {}, "volume": (r.data.get("batch") or {}).get("volume"),
                        "steps": len(steps), "minutes": sum(int(x["minutes"]) for x in steps),
                        "brews": n, "lastBrewedAt": unix(last), "updatedAt": unix(r.updated_at),
                        "about": excerpt(r.data.get("notes")), "photos": photos.get(r.id, []),
                        "author": author, "mine": r.user_id == self.uid, "visibility": r.visibility,
                        "publishedAt": unix(r.published_at)})
        return out

    def get(self, rid):
        with session() as s:
            return self._view(s, rid).data

    def detail(self, rid):
        """Рецепт и то, что о нём знать интерфейсу: автор, видимость, что можно тому, кто спрашивает."""
        with session() as s:
            r = self._view(s, rid)
            author = s.get(User, r.user_id)
            return {**r.data, "meta": {"author": author.name if author else "", "mine": r.user_id == self.uid,
                                       "visibility": r.visibility, "publishedAt": unix(r.published_at),
                                       "canEdit": can_edit(self.viewer, r), "canModerate": can_moderate(self.viewer, r)}}

    def save(self, rid, recipe):
        """rid = None — новый рецепт (личный, пока автор его не опубликует). Возвращает id."""
        with session() as s:
            if rid is None:
                if self.uid is None:
                    raise PermissionError("войдите, чтобы сохранять рецепты")
                r = Recipe(user_id=self.uid, name="")
            else:
                r = self._view(s, rid)
                if not can_edit(self.viewer, r):
                    raise PermissionError("это чужой рецепт — сохраните себе копию")
            r.name, r.data = recipe["name"], recipe
            r.updated_at = utcnow()
            s.add(r)
            s.commit()
            return str(r.id)

    def delete(self, rid):
        with session() as s:
            r = self._view(s, rid)
            if not (can_edit(self.viewer, r) or can_moderate(self.viewer, r)):
                raise PermissionError("удалить можно только свой рецепт")
            s.delete(r)
            s.commit()

    def set_visibility(self, rid, visibility):
        """Опубликовать или снять с публикации. Автор — в обе стороны (публиковать — с подтверждённой почтой),
        администратор — только снять чужой рецепт с публикации."""
        if visibility not in VISIBILITIES:
            raise ValueError(f"видимость — {' или '.join(VISIBILITIES)}")
        with session() as s:
            r = self._view(s, rid)
            if can_edit(self.viewer, r):
                if visibility == PUBLIC and not can_publish(self.viewer):
                    raise PermissionError("подтвердите почту, чтобы публиковать рецепты")
            elif not (can_moderate(self.viewer, r) and visibility == PRIVATE):
                raise PermissionError("это чужой рецепт")
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
        """limit — сколько фото может быть у рецепта; больше — ValueError."""
        with session() as s:
            r = self._view(s, rid)
            if not can_edit(self.viewer, r):
                raise PermissionError("добавить фото можно только к своему рецепту")
            if limit and s.exec(select(func.count()).select_from(RecipePhoto).where(RecipePhoto.recipe_id == r.id)).one() >= limit:
                raise ValueError(f"у рецепта уже {limit} фото")
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
                raise PermissionError("удалить можно только фото своего рецепта")
            s.delete(p)
            s.commit()

    def _photo(self, s, pid):
        p = s.get(RecipePhoto, as_uuid(pid))
        r = s.get(Recipe, p.recipe_id) if p is not None else None
        if r is None or not can_view(self.viewer, r):
            raise KeyError(pid)
        return p, r

    def _view(self, s, rid):
        r = s.get(Recipe, as_uuid(rid))
        if r is None or not can_view(self.viewer, r):
            raise KeyError(rid)
        return r


class DeviceStore:
    """Пивоварни пользователей: то, что сервису нужно и без агента на связи, — модель, ограничения, профиль."""

    def attach(self, agent, tuya_id, name, model=None, limits=None):
        """Агент сообщил, какую пивоварню обслуживает, — завести её или привязать к нему. Возвращает id пивоварни.
        PermissionError — пивоварня заведена у другого пользователя."""
        with session() as s:
            d = s.exec(select(Device).where(Device.tuya_id == tuya_id)).first()
            if d is None:
                d = Device(user_id=agent.user_id, tuya_id=tuya_id, name=name)
                log.info("пивоварня «%s» заведена", name)
            elif d.user_id != agent.user_id:
                raise PermissionError(f"пивоварня {tuya_id} принадлежит другому пользователю")
            d.agent_id = agent.id
            d.model = model or d.model
            d.limits = limits or d.limits
            s.add(d)
            s.commit()
            return d.id

    def update(self, device_id, **fields):
        """Пустые значения не затирают известные."""
        with session() as s:
            d = s.get(Device, device_id)
            for k, v in fields.items():
                if v is not None:
                    setattr(d, k, v)
            s.add(d)
            s.commit()

    def current(self, user_id):
        """Пивоварня пользователя (пока она у него одна — последняя заведённая) или None."""
        with session() as s:
            return s.exec(select(Device.id).where(Device.user_id == user_id).order_by(Device.created_at.desc())).first()

    def limits(self, device_id):
        with session() as s:
            d = s.get(Device, device_id)
            return d.limits if d else None

    def equipment(self, device_id):
        with session() as s:
            d = s.get(Device, device_id)
            return (d.equipment if d else None) or {}

    def set_equipment(self, device_id, data):
        with session() as s:
            d = s.get(Device, device_id)
            d.equipment = data
            s.add(d)
            s.commit()


class Journal:
    """Журнал пивоварен в Postgres: температура, события, варки. Запись — отдельным потоком через очередь:
    медленная или упавшая база не тормозит приём от агентов (записи тогда теряются с предупреждением)."""

    QUEUE_MAX = 10_000

    def __init__(self):
        self._q = queue.Queue(maxsize=self.QUEUE_MAX)
        self._thread = threading.Thread(target=self._run, name="journal", daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._q.put(None)
        self._thread.join(timeout=5)

    def _submit(self, write):
        try:
            self._q.put_nowait(write)
        except queue.Full:
            log.warning("очередь журнала переполнена — запись пропущена")

    def _run(self):
        while (write := self._q.get()) is not None:
            try:
                with session() as s:
                    write(s)
                    s.commit()
            except Exception:
                log.exception("запись в базу не удалась")

    # ── запись (от агентов) ───────────────────────────────────────────────────
    def reading(self, device_id, brew_id, at, temp, target, step, status):
        row = Reading(device_id=device_id, brew_id=as_uuid(brew_id) if brew_id else None, at=from_unix(at),
                      temp=temp, target=target, step=step, status=status)
        self._submit(lambda s: s.add(row))

    def event(self, device_id, brew_id, ev):
        extra = {k: v for k, v in ev.items() if k not in EVENT_FIELDS}
        row = Event(device_id=device_id, brew_id=as_uuid(brew_id) if brew_id else None, at=from_unix(ev["at"]),
                    kind=ev["kind"], text=ev["text"], data=extra or None)
        self._submit(lambda s: s.add(row))

    def start_brew(self, device_id, user_id, brew_id, name, recipe_id, recipe, at):
        """Повтор после переподключения агента варку не задваивает; чужой рецепт к варке не привязывается."""
        def write(s):
            if s.get(Brew, as_uuid(brew_id)) is not None:
                return
            rid = None
            if recipe_id:
                try:
                    r = s.get(Recipe, as_uuid(recipe_id))
                    rid = r.id if r is not None and r.user_id == user_id else None
                except KeyError:
                    pass
            s.add(Brew(id=as_uuid(brew_id), user_id=user_id, device_id=device_id, recipe_id=rid, name=name,
                       recipe=recipe or {}, started_at=from_unix(at)))
        self._submit(write)

    def finish_brew(self, brew_id, status, energy_wh, at=None):
        ended = from_unix(at) if at else utcnow()

        def write(s):
            b = s.get(Brew, as_uuid(brew_id))
            if b is not None and b.status == "running":
                b.status, b.ended_at, b.energy_wh = status, ended, energy_wh
        self._submit(write)

    def update_brew(self, brew_id, **fields):
        def write(s):
            b = s.get(Brew, as_uuid(brew_id))
            if b is not None:
                for k, v in fields.items():
                    setattr(b, k, v)
        self._submit(write)

    def close_brews(self, device_id, keep=()):
        """Варки пивоварни, о которых её агент уже не знает, не идут — закрыть как прерванные. keep — id варок,
        которые агент ещё ведёт или о которых не дослал записи."""
        at = utcnow()

        def write(s):
            for b in s.exec(select(Brew).where(Brew.device_id == device_id, Brew.status == "running")).all():
                if str(b.id) not in keep:
                    b.status, b.ended_at = "stopped", at
        self._submit(write)

    # ── чтение ────────────────────────────────────────────────────────────────
    def brew_device(self, brew_id):
        """Чья это варка — id пивоварни или None, если такой нет."""
        try:
            bid = as_uuid(brew_id)
        except KeyError:
            return None
        with session() as s:
            return s.exec(select(Brew.device_id).where(Brew.id == bid)).first()

    def history(self, device_id, seconds):
        since = utcnow() - timedelta(seconds=seconds)
        with session() as s:
            rows = s.exec(select(Reading.at, Reading.temp, Reading.target)
                          .where(Reading.device_id == device_id, Reading.at >= since).order_by(Reading.at)).all()
        return [(unix(at), temp, target) for at, temp, target in rows]

    def recent_events(self, device_id, limit=200):
        with session() as s:
            rows = s.exec(select(Event).where(Event.device_id == device_id)
                          .order_by(Event.at.desc()).limit(limit)).all()
        return [self._event(e) for e in rows]

    def brews(self, user_id, recipe_id=None, limit=200):
        q = select(Brew).where(Brew.user_id == user_id)
        if recipe_id:
            q = q.where(Brew.recipe_id == as_uuid(recipe_id))
        with session() as s:
            rows = s.exec(q.order_by(Brew.started_at.desc()).limit(limit)).all()
        return [self._brew(b) for b in rows]

    def brew(self, user_id, brew_id):
        with session() as s:
            b = s.get(Brew, as_uuid(brew_id))
            if b is None or b.user_id != user_id:
                raise KeyError(brew_id)
            readings = s.exec(select(Reading.at, Reading.temp, Reading.target)
                              .where(Reading.brew_id == b.id).order_by(Reading.at)).all()
            events = s.exec(select(Event).where(Event.brew_id == b.id).order_by(Event.at)).all()
        return {**self._brew(b), "recipe": b.recipe,
                "readings": [(unix(at), temp, target) for at, temp, target in readings],
                "events": [self._event(e) for e in events]}

    @staticmethod
    def _brew(b):
        return {"id": str(b.id), "name": b.name, "status": b.status, "recipeId": str(b.recipe_id) if b.recipe_id else None,
                "startedAt": unix(b.started_at), "endedAt": unix(b.ended_at), "energyWh": b.energy_wh}

    @staticmethod
    def _event(e):
        return {**(e.data or {}), "kind": e.kind, "text": e.text, "at": unix(e.at)}
