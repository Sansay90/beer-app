"""Журнал пивоварен в Postgres: температура, события, варки."""
import logging
import queue
import threading
from datetime import timedelta

from sqlmodel import select

from ..access import PUBLIC
from ..db import session
from ..errors import NotFound
from ..models import Brew, Event, Reading, Recipe, from_unix, parse_id, unix, utcnow

log = logging.getLogger("brewapp.journal")

EVENT_FIELDS = ("kind", "text", "at")


class Journal:
    """Запись — отдельным потоком через очередь: медленная или упавшая база не тормозит приём от агентов
    (записи тогда теряются с предупреждением). Чтение — сразу."""

    QUEUE_MAX = 10_000

    def __init__(self):
        self._q = queue.Queue(maxsize=self.QUEUE_MAX)
        self._thread = threading.Thread(target=self._run, name="journal", daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._q.put(None)
        self._thread.join(timeout=5)

    def flush(self, timeout=5):
        """Дождаться, пока записано всё, что поставлено в очередь до этого вызова."""
        done = threading.Event()
        self._submit(lambda s: done.set())
        return done.wait(timeout)

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
        row = Reading(device_id=device_id, brew_id=parse_id(brew_id) if brew_id else None, at=from_unix(at),
                      temp=temp, target=target, step=step, status=status)
        self._submit(lambda s: s.add(row))

    def event(self, device_id, brew_id, ev):
        extra = {k: v for k, v in ev.items() if k not in EVENT_FIELDS}
        row = Event(device_id=device_id, brew_id=parse_id(brew_id) if brew_id else None, at=from_unix(ev["at"]),
                    kind=ev["kind"], text=ev["text"], data=extra or None)
        self._submit(lambda s: s.add(row))

    def start_brew(self, device_id, user_id, brew_id, name, recipe_id, recipe, at):
        """Повтор после переподключения агента варку не задваивает. Рецепт привязывается, если он свой или
        опубликован (по нему считается «сколько раз варили»); id чужого личного агент не подставит."""
        bid = parse_id(brew_id)
        if bid is None:
            return

        def write(s):
            if s.get(Brew, bid) is not None:
                return
            r = s.get(Recipe, rid) if (rid := parse_id(recipe_id)) else None
            s.add(Brew(id=bid, user_id=user_id, device_id=device_id, name=name,
                       recipe_id=r.id if r is not None and (r.user_id == user_id or r.visibility == PUBLIC) else None,
                       recipe=recipe or {}, started_at=from_unix(at)))
        self._submit(write)

    def finish_brew(self, brew_id, status, energy_wh, at=None):
        ended = from_unix(at) if at else utcnow()

        def write(s):
            b = s.get(Brew, bid) if (bid := parse_id(brew_id)) else None
            if b is not None and b.status == "running":
                b.status, b.ended_at, b.energy_wh = status, ended, energy_wh
        self._submit(write)

    def update_brew(self, brew_id, **fields):
        def write(s):
            b = s.get(Brew, bid) if (bid := parse_id(brew_id)) else None
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
        if (bid := parse_id(brew_id)) is None:
            return None
        with session() as s:
            return s.exec(select(Brew.device_id).where(Brew.id == bid)).first()

    def history(self, device_id, seconds):
        if device_id is None:
            return []
        since = utcnow() - timedelta(seconds=seconds)
        with session() as s:
            rows = s.exec(select(Reading.at, Reading.temp, Reading.target)
                          .where(Reading.device_id == device_id, Reading.at >= since).order_by(Reading.at)).all()
        return [(unix(at), temp, target) for at, temp, target in rows]

    def recent_events(self, device_id, limit=200):
        if device_id is None:
            return []
        with session() as s:
            rows = s.exec(select(Event).where(Event.device_id == device_id)
                          .order_by(Event.at.desc()).limit(limit)).all()
        return [self._event(e) for e in rows]

    def brews(self, user_id, recipe_id=None, limit=200):
        q = select(Brew).where(Brew.user_id == user_id)
        if recipe_id:
            if (rid := parse_id(recipe_id)) is None:
                return []
            q = q.where(Brew.recipe_id == rid)
        with session() as s:
            rows = s.exec(q.order_by(Brew.started_at.desc()).limit(limit)).all()
        return [self._brew(b) for b in rows]

    def brew(self, user_id, brew_id):
        with session() as s:
            b = s.get(Brew, bid) if (bid := parse_id(brew_id)) else None
            if b is None or b.user_id != user_id:
                raise NotFound("варка не найдена")
            readings = s.exec(select(Reading.at, Reading.temp, Reading.target)
                              .where(Reading.brew_id == b.id).order_by(Reading.at)).all()
            events = s.exec(select(Event).where(Event.brew_id == b.id).order_by(Event.at)).all()
        return {**self._brew(b), "recipe": b.recipe,
                "readings": [(unix(at), temp, target) for at, temp, target in readings],
                "events": [self._event(e) for e in events]}

    @staticmethod
    def _brew(b):
        return {"id": str(b.id), "name": b.name, "status": b.status,
                "recipeId": str(b.recipe_id) if b.recipe_id else None,
                "startedAt": unix(b.started_at), "endedAt": unix(b.ended_at), "energyWh": b.energy_wh}

    @staticmethod
    def _event(e):
        return {**(e.data or {}), "kind": e.kind, "text": e.text, "at": unix(e.at)}
