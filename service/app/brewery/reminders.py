"""Брожение по плану варки — расписание, «плотность стабильна» и напоминания: следующий этап, сухое охмеление,
конец брожения по плану, «похоже, брожение закончилось» — уведомление на сайте и push (users.push_brews).

Расписание — от начала брожения (задача дрожжей, иначе конец варочного дня — logbook.py): этап начинается через дни
этапов до него — или по факту: запись «переход к этапу» (value — номер этапа с нуля) или «холодное осветление»
(начинает первый этап не теплее COLD); следующие этапы идут уже от него. Сухое охмеление «на N-й день» —
через N − 1 суток от начала. Плотность стабильна — последние замеры на брожении (и FG) за двое суток и больше
расходятся не больше STABLE_SG. Этап, начатый по факту, не напоминается; как и когда уходят напоминания — ticker.py.
Разлитые (веха «розлив»), идущий варочный день и начатые раньше SCAN_DAYS не смотрим.
Тот же расчёт — в интерфейсе (web/app/utils/brewlog.ts: fermentPlan, gravityStable).
"""
from datetime import timedelta

from sqlalchemy import exists, func
from sqlalchemy.orm import defer
from sqlmodel import select

from ..models import Brew, BrewEntry
from ..recipes.calc import plato_from_sg
from ..recipes.program import ru_num
from .ticker import Ticker

SCAN_DAYS = 120
COLD = 8.0                               # °C: этап не теплее — холодное осветление
STABLE_SG = 0.001                        # ≈ 0,25 °P — в пределах ошибки ареометра
STABLE_SPAN = timedelta(days=2)
FACTS = ("pitch", "stage", "cold_crash", "gravity", "fg")   # записи, от которых зависит расписание



def stage_starts(stages, entries):
    """{номер этапа: когда начат по факту} — по записям «переход к этапу» и «холодное осветление»."""
    cold = next((i for i, st in enumerate(stages) if i and st["temp"] <= COLD), None)
    starts = {}
    for e in entries:
        if e.kind == "stage" and e.value is not None and 1 <= int(e.value) < len(stages):
            starts[int(e.value)] = e.at
        elif e.kind == "cold_crash" and cold is not None:
            starts.setdefault(cold, e.at)
    return starts


def stages_of(plan, start, entries=()):
    """Этапы плана с датами: [(начало, конец, начат ли по факту)]; конец — начало следующего."""
    stages = (plan or {}).get("fermentation") or []
    starts = stage_starts(stages, entries)
    froms = []
    for i in range(len(stages)):
        froms.append(starts.get(i, start if i == 0 else froms[-1] + timedelta(days=stages[i - 1]["days"])))
    out = []
    for i, st in enumerate(stages):
        end = froms[i + 1] if i + 1 < len(stages) else froms[i] + timedelta(days=st["days"])
        out.append((froms[i], max(end, froms[i]), i in starts))
    return out


def stable(entries):
    """(с какого времени, плотность) — если плотность стабильна, иначе None."""
    gravity = [e for e in entries if e.kind in ("gravity", "fg") and e.value is not None]
    if len(gravity) < 2:
        return None
    last = oldest = gravity[-1]
    for e in reversed(gravity[:-1]):
        if abs(e.value - last.value) > STABLE_SG:
            break
        oldest = e
    return (last.at, last.value) if last.at - oldest.at >= STABLE_SPAN else None


def schedule(plan, start, entries=()):
    """[(ключ, когда, заголовок, текст, по факту ли)] по плану брожения и записям журнала (по времени);
    start — начало брожения, entries — записи варки по времени."""
    plan = plan or {}
    stages = plan.get("fermentation") or []
    dated = stages_of(plan, start, entries)
    out = []
    for i, (frm, _, manual) in enumerate(dated):
        if i:
            st = stages[i]
            out.append((f"stage-{i}", frm, f"Пора: {st.get('name') or f'этап {i + 1}'}",
                        f"{ru_num(st['temp'])} °C, {ru_num(st['days'])} дн.", manual))
    if dated:
        out.append(("end", dated[-1][1], "Брожение по плану закончено", "Можно переливать и разливать", False))
    for dh in plan.get("dryHops") or []:
        if dh.get("day"):
            out.append((f"dry-{dh['day']}", start + timedelta(days=dh["day"] - 1), "Сухое охмеление",
                        ", ".join(dh["items"]), False))
    if (calm := stable(entries)) is not None:
        at, sg = calm
        upcoming = next((stages[i].get("name") or f"этап {i + 1}" for i, (frm, _, _) in enumerate(dated)
                         if i and frm > at), None)
        out.append(("stable", at, "Похоже, брожение закончилось",
                    f"Плотность {ru_num(round(sg, 3))} ({ru_num(round(plato_from_sg(sg), 1))} °P) "
                    "не меняется двое суток — "
                    + (f"можно переходить к этапу «{upcoming}»" if upcoming else "можно разливать"), False))
    return sorted(out, key=lambda r: r[1])


class Reminders(Ticker):
    """Напоминания о брожении раз в 5 минут."""

    NAME = "reminders"
    TAG = "brew"
    INTERVAL_S = 300
    LATE = timedelta(hours=12)

    def due(self, s, now, brew_id=None):
        packaged = exists().where(BrewEntry.brew_id == Brew.id, BrewEntry.kind == "package")
        brews = s.exec(select(Brew).options(defer(Brew.snapshot), defer(Brew.recipe))
                       .where(func.jsonb_typeof(Brew.plan) == "object", Brew.day_ended_at.is_not(None),
                              Brew.started_at >= now - timedelta(days=SCAN_DAYS), Brew.started_at <= now,
                              ~packaged)).all()
        facts = {}
        if brews:
            for e in s.exec(select(BrewEntry).where(BrewEntry.brew_id.in_([b.id for b in brews]),
                                                    BrewEntry.kind.in_(FACTS))
                            .order_by(BrewEntry.at, BrewEntry.created_at)).all():
                facts.setdefault(e.brew_id, []).append(e)
        out = []
        for b in brews:
            entries = facts.get(b.id, [])
            pitch = next((e.at for e in entries if e.kind == "pitch"), None)
            out.append((b, [r for r in schedule(b.plan, pitch or b.day_ended_at, entries) if r[1] <= now]))
        return out
