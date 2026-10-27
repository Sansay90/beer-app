"""Доступ к данным: рецепты пользователя и журнал пивоварни (варки, события, температура)."""
import logging
import queue
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlmodel import select

from .db import session
from .models import Brew, Device, Event, Reading, Recipe, RecipePhoto, utcnow
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


def excerpt(text, limit=220):
    """Первый абзац описания одной строкой: карточка всё равно обрежет до двух строк."""
    text = " ".join(re.split(r"\n\s*\n", (text or "").strip())[0].split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


class RecipeStore:
    """Рецепты пользователя: рецепт целиком — JSONB data (schemas.Recipe), name — для сортировки и поиска."""

    def __init__(self, user_id):
        self.user_id = user_id

    def list(self):
        with session() as s:
            rows = s.exec(select(Recipe).where(Recipe.user_id == self.user_id).order_by(Recipe.updated_at.desc())).all()
            brewed = {rid: (n, last) for rid, n, last in s.exec(
                select(Brew.recipe_id, func.count(), func.max(Brew.started_at))
                .where(Brew.user_id == self.user_id, Brew.recipe_id.is_not(None)).group_by(Brew.recipe_id)).all()}
            photos = {}
            for rid, pid in s.exec(select(RecipePhoto.recipe_id, RecipePhoto.id)
                                   .where(RecipePhoto.user_id == self.user_id).order_by(RecipePhoto.created_at)).all():
                photos.setdefault(rid, []).append(str(pid))
        out = []
        for r in rows:
            steps = program_steps(r.data)
            n, last = brewed.get(r.id, (0, None))
            out.append({"id": str(r.id), "name": r.name, "style": r.data.get("style"),
                        "targets": r.data.get("targets") or {}, "volume": (r.data.get("batch") or {}).get("volume"),
                        "steps": len(steps), "minutes": sum(int(x["minutes"]) for x in steps),
                        "brews": n, "lastBrewedAt": unix(last), "updatedAt": unix(r.updated_at),
                        "about": excerpt(r.data.get("notes")), "photos": photos.get(r.id, [])})
        return out

    def get(self, rid):
        with session() as s:
            return self._row(s, rid).data

    def save(self, rid, recipe):
        """rid = None — новый рецепт. Возвращает id."""
        with session() as s:
            r = Recipe(user_id=self.user_id, name="") if rid is None else self._row(s, rid)
            r.name, r.data = recipe["name"], recipe
            r.updated_at = utcnow()
            s.add(r)
            s.commit()
            return str(r.id)

    def delete(self, rid):
        with session() as s:
            s.delete(self._row(s, rid))
            s.commit()

    # ── фото пива ─────────────────────────────────────────────────────────────
    def photos(self, rid):
        with session() as s:
            r = self._row(s, rid)
            rows = s.exec(select(RecipePhoto.id, RecipePhoto.credit, RecipePhoto.created_at)
                          .where(RecipePhoto.recipe_id == r.id).order_by(RecipePhoto.created_at)).all()
            return [{"id": str(pid), "credit": credit, "createdAt": unix(at)} for pid, credit, at in rows]

    def add_photo(self, rid, content_type, data, thumb=None, credit=None, limit=None):
        """limit — сколько фото может быть у рецепта; больше — ValueError."""
        with session() as s:
            r = self._row(s, rid)
            if limit and s.exec(select(func.count()).select_from(RecipePhoto).where(RecipePhoto.recipe_id == r.id)).one() >= limit:
                raise ValueError(f"у рецепта уже {limit} фото")
            p = RecipePhoto(recipe_id=r.id, user_id=self.user_id, content_type=content_type, data=data, thumb=thumb,
                            credit=credit)
            s.add(p)
            s.commit()
            return {"id": str(p.id), "credit": p.credit, "createdAt": unix(p.created_at)}

    def photo(self, pid, thumb=False):
        """(content_type, data); thumb — превью (JPEG), если оно есть."""
        with session() as s:
            p = self._photo(s, pid)
            return ("image/jpeg", p.thumb) if thumb and p.thumb else (p.content_type, p.data)

    def delete_photo(self, pid):
        with session() as s:
            s.delete(self._photo(s, pid))
            s.commit()

    def _photo(self, s, pid):
        p = s.get(RecipePhoto, as_uuid(pid))
        if p is None or p.user_id != self.user_id:
            raise KeyError(pid)
        return p

    def _row(self, s, rid):
        r = s.get(Recipe, as_uuid(rid))
        if r is None or r.user_id != self.user_id:
            raise KeyError(rid)
        return r


class Journal:
    """Журнал пивоварни в Postgres. Запись — отдельным потоком через очередь:
    медленная или упавшая база не тормозит связь с пивоварней (записи тогда теряются с предупреждением)."""

    QUEUE_MAX = 10_000

    def __init__(self, device_id, user_id):
        self.device_id = device_id
        self.user_id = user_id
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

    # ── запись (из потока пивоварни) ──────────────────────────────────────────
    def reading(self, temp, target, step, status, brew_id):
        row = Reading(device_id=self.device_id, brew_id=brew_id, at=utcnow(), temp=temp, target=target,
                      step=step, status=status)
        self._submit(lambda s: s.add(row))

    def event(self, ev, brew_id):
        extra = {k: v for k, v in ev.items() if k not in EVENT_FIELDS}
        row = Event(device_id=self.device_id, brew_id=brew_id, at=datetime.fromtimestamp(ev["at"], timezone.utc),
                    kind=ev["kind"], text=ev["text"], data=extra or None)
        self._submit(lambda s: s.add(row))

    def start_brew(self, brew_id, name, recipe_id, recipe):
        row = Brew(id=brew_id, user_id=self.user_id, device_id=self.device_id,
                   recipe_id=as_uuid(recipe_id) if recipe_id else None, name=name, recipe=recipe)
        self._submit(lambda s: s.add(row))

    def finish_brew(self, brew_id, status, energy_wh):
        at = utcnow()

        def write(s):
            b = s.get(Brew, brew_id)
            if b is not None and b.status == "running":
                b.status, b.ended_at, b.energy_wh = status, at, energy_wh
        self._submit(write)

    def update_brew(self, brew_id, **fields):
        def write(s):
            b = s.get(Brew, brew_id)
            if b is not None:
                for k, v in fields.items():
                    setattr(b, k, v)
        self._submit(write)

    def update_device(self, **fields):
        def write(s):
            d = s.get(Device, self.device_id)
            for k, v in fields.items():
                setattr(d, k, v)
        self._submit(write)

    # ── чтение ────────────────────────────────────────────────────────────────
    def device(self):
        with session() as s:
            return s.get(Device, self.device_id)

    def equipment(self):
        with session() as s:
            return s.get(Device, self.device_id).equipment or {}

    def set_equipment(self, data):
        """Сразу в базу, не через очередь журнала: настройку человек ждёт сохранённой."""
        with session() as s:
            d = s.get(Device, self.device_id)
            d.equipment = data
            s.add(d)
            s.commit()

    def open_brew(self):
        """Незакрытая варка этой пивоварни (посредник перезапустили посреди варки): (id, energy_wh) или None."""
        with session() as s:
            return s.exec(select(Brew.id, Brew.energy_wh)
                          .where(Brew.device_id == self.device_id, Brew.status == "running")
                          .order_by(Brew.started_at.desc())).first()

    def history(self, seconds):
        since = utcnow() - timedelta(seconds=seconds)
        with session() as s:
            rows = s.exec(select(Reading.at, Reading.temp, Reading.target)
                          .where(Reading.device_id == self.device_id, Reading.at >= since).order_by(Reading.at)).all()
        return [(unix(at), temp, target) for at, temp, target in rows]

    def recent_events(self, limit=200):
        with session() as s:
            rows = s.exec(select(Event).where(Event.device_id == self.device_id)
                          .order_by(Event.at.desc()).limit(limit)).all()
        return [self._event(e) for e in rows]

    def brews(self, recipe_id=None, limit=200):
        q = select(Brew).where(Brew.user_id == self.user_id)
        if recipe_id:
            q = q.where(Brew.recipe_id == as_uuid(recipe_id))
        with session() as s:
            rows = s.exec(q.order_by(Brew.started_at.desc()).limit(limit)).all()
        return [self._brew(b) for b in rows]

    def brew(self, brew_id):
        with session() as s:
            b = s.get(Brew, as_uuid(brew_id))
            if b is None or b.user_id != self.user_id:
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
