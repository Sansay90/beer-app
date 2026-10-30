"""Варочный день партии: шаги из рецепта партии, где партия сейчас и таймеры с напоминаниями для варки без пивоварни.

Варка в кастрюле и на автоматике не отличается ничем, кроме автоматики, — шаги одни: подготовка → нагрев до первой
паузы → засыпать солод → паузы затирания → промывка → кипячение с закладками → охлаждение → задать дрожжи. Что
приготовить на шаге (вода и соли, засыпь, дрожжи), интерфейс считает по рецепту партии сам (web/app/utils/brewday.ts).

Текущий шаг — последний по времени переход (progress): запись пивовара «step» (value — номер шага) или шаг программы
пивоварни по её событиям (brewery_steps). Таймер только напоминает: конец паузы, закладка на кипячении —
уведомление на сайте и push (ticker.py; ключи step-N, add-N-M), если к шагу перешёл пивовар; программа пивоварни
напоминает сама. Варочный день кончается задачей дрожжей или «закончить» (logbook.py, end_day); брошенный — через
DAY_SPAN после начала (close_stale). Конец программы пивоварни — не конец дня: охлаждение, замеры и дрожжи впереди.
"""
from datetime import timedelta

from sqlalchemy import or_
from sqlalchemy.orm import defer
from sqlmodel import select

from ..db import session
from ..models import Brew, BrewEntry, Event, parse_id, utcnow
from ..recipes.program import addition_slots, ru_num
from .ticker import Ticker

DAY_SPAN = timedelta(hours=36)          # столько после начала варки день без дрожжей ещё считается идущим
PROGRESS_EVENTS = ("step", "alert", "alertCleared", "end")   # события пивоварни, по которым видно её шаг
ALERT_STEPS = {"malt": "mash_in", "mashEnd": "sparge"}       # подсказка пивоварни → шаг варочного дня


def steps_of(recipe):
    """Шаги варочного дня из рецепта партии: [{index, key, kind, name, temp, minutes, measures, additions}].
    kind: prepare, heat, mash_in, rest, sparge, boil, chill, pitch. measures — виды замеров на этом шаге."""
    mash = recipe.get("mash") or []
    boil = recipe.get("boil")
    chill_to = next((st.get("temp") for st in recipe.get("fermentation") or [] if st.get("temp") is not None), None)
    steps = [{"kind": "prepare", "name": "Подготовка"}]
    if mash:
        steps.append({"kind": "heat", "name": "Нагрев", "temp": mash[0]["temp"]})
        steps.append({"kind": "mash_in", "name": "Засыпать солод", "measures": ["ph", "mash_temp"]})
    for i, st in enumerate(mash):
        steps.append({"kind": "rest", "name": st.get("name") or f"Пауза {i + 1}", "temp": st["temp"],
                      "minutes": st["minutes"]})
    if mash:
        steps.append({"kind": "sparge", "name": "Промывка",
                      "measures": ["first_wort", "preboil_volume", "preboil_gravity"]})
    if boil:
        steps.append({"kind": "boil", "name": "Кипячение", "minutes": boil["minutes"],
                      "additions": [{"minutes": s["minutes"], "label": s["label"]} for s in addition_slots(recipe)]})
    steps.append({"kind": "chill", "name": "Охлаждение", "temp": chill_to, "measures": ["og", "fermenter_volume"]})
    steps.append({"kind": "pitch", "name": "Задать дрожжи"})
    for i, s in enumerate(steps):
        s.setdefault("measures", [])
        s.setdefault("additions", [])
        s.update({"index": i, "key": f"{s['kind']}-{i}"})
    return steps


def brewery_steps(steps, events):
    """[(когда, номер шага варочного дня)] по событиям программы пивоварни — (когда, вид, data) по времени.
    Программа — паузы затирания, затем кипячение (recipes/program.py): её шаг 1 — нагрев до первой паузы, шаг k —
    k-я пауза, после пауз — кипячение; подсказка «солод» — засыпь, её подтверждение — первая пауза; «конец
    затирания» — промывка; программа закончена — охлаждение."""
    first = {}
    for s in steps:
        first.setdefault(s["kind"], s["index"])
    rests = [s["index"] for s in steps if s["kind"] == "rest"]
    out, alert = [], None
    for at, kind, data in events:
        data = data or {}
        index = None
        if kind == "step" and data.get("step"):
            k = int(data["step"])
            index = first.get("boil") if k > len(rests) else first.get("heat", rests[0]) if k == 1 else rests[k - 1]
        elif kind == "alert":
            alert = data.get("alert")
            index = first.get(ALERT_STEPS.get(alert))
        elif kind == "alertCleared":
            if alert == "malt" and rests:
                index = rests[0]
            alert = None
        elif kind == "end":
            index = first.get("chill")
        if index is not None:
            out.append((at, index))
    return out


def progress(steps, started, entries, events=()):
    """Где партия: (текущий шаг, {шаг: когда начат}, перешёл ли к текущему пивовар сам). entries — записи журнала
    (когда, вид, значение), events — события пивоварни (когда, вид, data), всё по времени. Подготовка — с начала
    варки; дрожжи заданы — все шаги позади, текущий — последний."""
    if not steps:
        return 0, {}, False
    moves = [(at, int(v), True) for at, kind, v in entries
             if kind == "step" and v is not None and 0 <= int(v) < len(steps)]
    moves += [(at, i, False) for at, i in brewery_steps(steps, events)]
    current, starts, manual = 0, {0: started}, True
    for at, i, by_brewer in sorted(moves, key=lambda m: m[0]):
        current, starts[i], manual = i, at, by_brewer
    pitch = next((at for at, kind, _ in entries if kind == "pitch"), None)
    if pitch is not None:
        current, manual = len(steps) - 1, True
        starts[current] = pitch
    return current, starts, manual


def end_day(b, at):
    """Варочный день партии b позади с at — дальше брожение; у варки без пивоварни это и конец статуса."""
    if b.day_ended_at is None:
        b.day_ended_at = at
    if b.source == "manual" and b.status == "running":
        b.status, b.ended_at = "finished", at


def close_stale(now):
    """Брошенные варочные дни — старше DAY_SPAN, программа пивоварни не идёт — к брожению: день кончился, когда
    кончилась программа, иначе — в день варки. Вернуть [(id пользователя, id варки)] закрытых."""
    closed = []
    with session() as s:
        for b in s.exec(select(Brew).options(defer(Brew.snapshot), defer(Brew.recipe))
                        .where(Brew.day_ended_at.is_(None), Brew.started_at < now - DAY_SPAN,
                               or_(Brew.source == "manual", Brew.status != "running"))).all():
            end_day(b, b.ended_at or b.started_at)
            s.add(b)
            closed.append((b.user_id, b.id))
        s.commit()
    return closed


def schedule(steps, index, started):
    """[(ключ, когда, заголовок, текст)] напоминаний текущего шага: конец паузы или кипячения, закладки."""
    if started is None or not 0 <= index < len(steps):
        return []
    step = steps[index]
    out = []
    minutes = step.get("minutes")
    if step["kind"] == "boil" and minutes:
        for a in step["additions"]:
            if 0 <= a["minutes"] <= minutes:
                at = started + timedelta(minutes=minutes - a["minutes"])
                when = "в начале кипячения" if a["minutes"] == minutes else \
                    "в конце кипячения" if a["minutes"] == 0 else f"за {a['minutes']} мин до конца"
                out.append((f"add-{index}-{a['minutes']}", at, f"Закладка: {a['label']}", when))
        out.append((f"step-{index}", started + timedelta(minutes=minutes), "Кипячение закончено",
                    "Дальше — охлаждение, замеры OG и объёма"))
    elif minutes:
        nxt = steps[index + 1] if index + 1 < len(steps) else None
        temp = f" {ru_num(nxt['temp'], 1)} °C" if nxt and nxt.get("temp") is not None else ""
        text = f"Дальше — {nxt['name']}{temp}" if nxt else ""
        out.append((f"step-{index}", started + timedelta(minutes=minutes),
                    f"{step['name']} — {minutes} мин прошло", text))
    return sorted(out, key=lambda r: r[1])


class BrewDayTimers(Ticker):
    """Таймеры шагов, к которым пивовар перешёл сам, раз в 30 с; после записи шага роутер зовёт tick сразу.
    Заодно закрывает брошенные варочные дни."""

    NAME = "brewday"
    TAG = "brewday"
    INTERVAL_S = 30
    LATE = timedelta(hours=2)

    def tick(self, now=None, brew_id=None):
        now = now or utcnow()
        if brew_id is None:
            for user_id, bid in close_stale(now):
                if self.streams is not None:
                    self.streams.brew(user_id, bid)
        return super().tick(now, brew_id)

    def due(self, s, now, brew_id=None):
        q = select(Brew).options(defer(Brew.recipe)).where(
            Brew.day_ended_at.is_(None), Brew.snapshot.is_not(None), Brew.started_at >= now - DAY_SPAN,
            or_(Brew.source == "manual", Brew.status != "running"))     # программа идёт — напоминает пивоварня
        if brew_id is not None:
            q = q.where(Brew.id == parse_id(brew_id))
        brews = s.exec(q).all()
        ids = [b.id for b in brews]
        entries, events = {}, {}
        if ids:
            for bid, at, kind, value in s.exec(select(BrewEntry.brew_id, BrewEntry.at, BrewEntry.kind, BrewEntry.value)
                                               .where(BrewEntry.brew_id.in_(ids), BrewEntry.kind == "step")
                                               .order_by(BrewEntry.at, BrewEntry.created_at)).all():
                entries.setdefault(bid, []).append((at, kind, value))
            for bid, at, kind, data in s.exec(select(Event.brew_id, Event.at, Event.kind, Event.data)
                                              .where(Event.brew_id.in_(ids), Event.kind.in_(PROGRESS_EVENTS))
                                              .order_by(Event.at)).all():
                events.setdefault(bid, []).append((at, kind, data))
        out = []
        for b in brews:
            steps = steps_of(b.snapshot)
            current, starts, manual = progress(steps, b.started_at, entries.get(b.id, []), events.get(b.id, []))
            items = schedule(steps, current, starts.get(current)) if manual else []
            out.append((b, [(*r, False) for r in items if r[1] <= now]))
        return out
