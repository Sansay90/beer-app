"""Журнал пивоварен в Postgres: температура, события, варки с пивоварни. Варки глазами пивовара — logbook.py."""
import logging
import queue
import threading
from datetime import timedelta

from sqlmodel import select

from ..access import PUBLIC
from ..db import session
from ..models import Brew, Equipment, Event, Reading, Recipe, from_unix, parse_id, unix, utcnow
from .logbook import DEVICE, batch_recipe, event_view, plan_of

log = logging.getLogger("brewapp.journal")

EVENT_FIELDS = ("kind", "text", "at")


class Journal:
    """Запись — отдельным потоком через очередь: медленная или упавшая база не тормозит приём от агентов
    (записи тогда теряются с предупреждением). Чтение — сразу. on_brew(id пользователя, id варки) — варка
    изменилась и это уже в базе (Streams.brew): запись возвращает, о каких варках сказать."""

    QUEUE_MAX = 10_000

    def __init__(self, on_brew=None):
        self.on_brew = on_brew
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
                    changed = write(s)
                    s.commit()
            except Exception:
                log.exception("запись в базу не удалась")
                continue
            for user_id, brew_id in changed or ():
                if self.on_brew is not None:
                    self.on_brew(user_id, brew_id)

    # ── запись (от агентов) ───────────────────────────────────────────────────
    def reading(self, device_id, brew_id, at, temp, target, step, status):
        row = Reading(device_id=device_id, brew_id=parse_id(brew_id) if brew_id else None, at=from_unix(at),
                      temp=temp, target=target, step=step, status=status)
        self._submit(lambda s: s.add(row))

    def event(self, device_id, brew_id, ev):
        extra = {k: v for k, v in ev.items() if k not in EVENT_FIELDS}
        row = Event(device_id=device_id, brew_id=parse_id(brew_id) if brew_id else None, at=from_unix(ev["at"]),
                    kind=ev["kind"], text=ev["text"], data=extra or None)

        def write(s):
            s.add(row)
            if row.brew_id is not None:                 # шаг, подсказка, конец — у варки сменилось «сейчас»
                user_id = s.exec(select(Brew.user_id).where(Brew.id == row.brew_id)).first()
                return [(user_id, row.brew_id)] if user_id else None
        self._submit(write)

    def start_brew(self, device_id, user_id, brew_id, name, recipe_id, recipe, at):
        """Повтор после переподключения агента варку не задваивает. Программа от «Сварить» несёт id партии —
        варка идёт в неё: партия становится варкой с пивоварни. Иначе варка новая: рецепт привязывается, если он
        свой или опубликован (по нему считается «сколько раз варили»; из него — рецепт партии под оборудование
        пивоварни и план варки); id чужого личного агент не подставит."""
        bid = parse_id(brew_id)
        if bid is None:
            return

        def write(s):
            equipment = s.exec(select(Equipment).where(Equipment.device_id == device_id)).first()
            if (b := s.get(Brew, bid)) is not None:
                if b.user_id == user_id and b.device_id is None:        # партия от «Сварить» — теперь на пивоварне
                    b.device_id, b.source, b.status, b.ended_at = device_id, DEVICE, "running", None
                    b.recipe, b.started_at = recipe or {}, from_unix(at)
                    b.equipment_id = equipment.id if equipment else None
                    return [(user_id, bid)]
                return None
            r = s.get(Recipe, rid) if (rid := parse_id(recipe_id)) else None
            if r is not None and r.user_id != user_id and r.visibility != PUBLIC:
                r = None
            snapshot = batch_recipe(r.data, equipment) if r else None
            s.add(Brew(id=bid, user_id=user_id, device_id=device_id, equipment_id=equipment.id if equipment else None,
                       name=name, recipe_id=r.id if r else None, recipe=recipe or {}, snapshot=snapshot,
                       plan=plan_of(snapshot) if snapshot else None, started_at=from_unix(at)))
            return [(user_id, bid)]
        self._submit(write)

    def finish_brew(self, brew_id, status, energy_wh, at=None):
        ended = from_unix(at) if at else utcnow()

        def write(s):
            b = s.get(Brew, bid) if (bid := parse_id(brew_id)) else None
            if b is not None and b.status == "running":
                b.status, b.ended_at, b.energy_wh = status, ended, energy_wh
                return [(b.user_id, b.id)]
            return None
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
            closed = []
            for b in s.exec(select(Brew).where(Brew.device_id == device_id, Brew.status == "running")).all():
                if str(b.id) not in keep:
                    b.status, b.ended_at = "stopped", at
                    closed.append((b.user_id, b.id))
            return closed
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
        return [event_view(e) for e in rows]
