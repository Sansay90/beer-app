"""Брожение по плану варки — расписание, где партия сейчас и напоминания (на сайте и push, users.push_brews).

Этап брожения кончается по своему условию (рецепт, FermentationStep.until): «до плотности» — замер дошёл до цели;
«до FG» — плотность перестала падать (стоит двое суток после того, как пошла вниз); «выдержка» — прошли дни.
Цель по плотности в партии — от фактической OG: та же доля сбраживания (target_of). Цель «до плотности» страхуется
замедлением (slowdown): пройдена половина пути от плотности на начало этапа к цели, а плотность падает медленнее
SLOW_SG в сутки — конечная выйдет выше расчётной, пора всё равно. У этапов по плотности дни — прикидка: по ним
даты и график, а прошли они без свежих замеров — «пора замерить». Решает пивовар: напоминание предлагает переход,
этап меняется записью «переход к этапу» (value — номер этапа с нуля) или «холодное осветление» (начинает первый
этап не теплее COLD).

Начало брожения — задача дрожжей, иначе конец варочного дня (logbook.py). Сухое охмеление — при своей плотности
(в партии — от фактической OG; день при ней — когда напомнить замерить) или «на N-й день» — через N − 1 суток
от начала. Этап, начатый по факту, не напоминается; как и когда уходят напоминания — ticker.py. Разлитые,
идущий варочный день и начатые раньше SCAN_DAYS не смотрим. Тот же расчёт — в интерфейсе
(web/app/utils/brewlog.ts: fermentPlan, fermentAdvice, fermentCalm); общие примеры — shared/ferment-cases.json.
"""
from datetime import timedelta

from sqlalchemy import exists, func
from sqlalchemy.orm import defer
from sqlmodel import select

from ..models import Brew, BrewEntry, unix
from ..recipes.calc import plato_from_sg
from ..recipes.program import ru_num
from .ticker import Ticker

SCAN_DAYS = 120
COLD = 8.0                               # °C: этап не теплее — холодное осветление
STABLE_SG = 0.001                        # ≈ 0,25 °P — в пределах ошибки ареометра
STABLE_SPAN = timedelta(days=2)
DROP_SG = 0.005                          # «стоит» — только когда плотность уже пошла вниз (не лаг-фаза)
SLOW_SG = 0.002                          # ≈ 0,5 °P в сутки: медленнее — брожение замедлилось
SLOW_SPAN = timedelta(days=1)            # скорость — по двум замерам не ближе суток: шаг ареометра 0,001 не мешает
FRESH = timedelta(hours=20)              # замер свежее — «пора замерить» не нужно
DAY = timedelta(days=1)
FACTS = ("pitch", "stage", "cold_crash", "og", "gravity", "fg")   # записи, от которых зависит расписание
GRAVITY = ("gravity", "fg")


def target_of(target, plan_og, og):
    """Цель по плотности в партии: та же доля сбраживания от фактической OG; OG или цели нет — как в рецепте."""
    if target is None or not og or not plan_og or plan_og <= 1:
        return target
    return 1 + (target - 1) * (og - 1) / (plan_og - 1)


def gravity_text(sg):
    return f"{ru_num(round(sg, 3))} ({ru_num(round(plato_from_sg(sg), 1))} °P)"


def until_of(st):
    return st.get("until") or "days"


def condition_text(st, target=None):
    """Условие этапа для текста: «до 1,024 (6 °P)» (цель партии, если дана), «до конечной плотности», «3 дн.»."""
    until = until_of(st)
    if until == "gravity":
        return f"до {gravity_text(target if target is not None else st['gravity'])}"
    if until == "fg":
        return "до конечной плотности"
    return f"{ru_num(st['days'])} дн."


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


def stages_of(plan, start, entries=(), now=None):
    """Этапы с датами: [(начало, конец, начат ли по факту)]; конец — начало следующего, у последнего — по дням.
    Идущий этап «до плотности» или «до FG» (следующие не начаты) не кончается раньше now: его дни — прикидка,
    пока условие не наступило, следующие сдвигаются."""
    stages = (plan or {}).get("fermentation") or []
    starts = stage_starts(stages, entries)
    latest = max(starts, default=0)
    out = []
    frm = start
    for i, st in enumerate(stages):
        frm = starts.get(i, frm)
        end = starts.get(i + 1, frm + timedelta(days=st["days"]))
        if i + 1 not in starts and i >= latest and now is not None and frm <= now and until_of(st) != "days":
            end = max(end, now)
        out.append((frm, max(end, frm), i in starts))
        frm = out[-1][1]
    return out


def current_of(dated, now):
    """Номер идущего этапа — последнего, начатого к now; ни один не начат — −1. Этап, который лишь по прикидке
    начинается ровно сейчас (предыдущий «до плотности» продлён до now), ещё не идёт."""
    return max((i for i, (frm, _, manual) in enumerate(dated)
                if now is None or frm < now or (manual and frm <= now)), default=-1)


def stable(entries, top=None):
    """(с какого времени, плотность) — если плотность стабильна, иначе None. top — OG: плотность должна уже
    пойти вниз, иначе лаг-фаза сойдёт за конец брожения."""
    gravity = [e for e in entries if e.kind in GRAVITY and e.value is not None]
    if len(gravity) < 2:
        return None
    last = oldest = gravity[-1]
    if top is not None and last.value > top - DROP_SG:
        return None
    for e in reversed(gravity[:-1]):
        if abs(e.value - last.value) > STABLE_SG:
            break
        oldest = e
    return (last.at, last.value) if last.at - oldest.at >= STABLE_SPAN else None


def slowdown(measures, top, target):
    """Замер, на котором брожение замедлилось до цели: пройдена половина пути от top (плотность на начало этапа)
    к target, а плотность падает медленнее SLOW_SG в сутки (по двум замерам не ближе SLOW_SPAN); иначе None."""
    if top is None or len(measures) < 2:
        return None
    last = measures[-1]
    if last.value > top - (top - target) / 2:
        return None
    prev = next((e for e in reversed(measures[:-1]) if last.at - e.at >= SLOW_SPAN), None)
    if prev is None:
        return None
    rate = (prev.value - last.value) / ((last.at - prev.at) / DAY)
    return last if rate < SLOW_SG else None


class Ferment:
    """Брожение партии на момент now: этапы с датами (dated), цели партии (targets), идущий этап (current, −1 —
    ни один), фактическая OG (og) и замеры плотности по времени (gravity). Считается один раз — им пользуются и
    напоминания, и «пора»."""

    def __init__(self, plan, start, entries=(), now=None):
        self.plan = plan or {}
        self.stages = self.plan.get("fermentation") or []
        self.start = start
        self.dated = stages_of(self.plan, start, entries, now)
        self.current = current_of(self.dated, now)
        self.og = next((e.value for e in reversed(entries) if e.kind == "og" and e.value), None)
        self.gravity = [e for e in entries if e.kind in GRAVITY and e.value is not None]
        self.targets = [target_of(st.get("gravity"), self.plan.get("og"), self.og) if until_of(st) == "gravity"
                        else None for st in self.stages]

    @property
    def top(self):
        """OG: фактическая, иначе по рецепту."""
        return self.og or self.plan.get("og")

    def since(self, i):
        """Замеры плотности с начала этапа i."""
        return [e for e in self.gravity if e.at >= self.dated[i][0]]

    def top_of(self, i):
        """Плотность на начало этапа i: последний замер до него, иначе OG."""
        before = [e for e in self.gravity if e.at <= self.dated[i][0]]
        return before[-1].value if before else self.top

    def advice(self):
        """Пора ли кончать идущий этап «до плотности» или «до FG»: (номер этапа, почему — target | slow | stable,
        замер) или None."""
        i = self.current
        if i < 0 or until_of(self.stages[i]) == "days":
            return None
        since = self.since(i)
        if until_of(self.stages[i]) == "gravity":
            target = self.targets[i]
            reached = next((e for e in since if e.value <= target + 1e-9), None)
            if reached is not None:
                return i, "target", reached
            slow = slowdown(since, self.top_of(i), target)
            return (i, "slow", slow) if slow is not None else None
        calm = stable(since, self.top)
        return (i, "stable", since[-1]) if calm is not None else None

    def calm(self):
        """«Похоже, брожение закончилось»: идёт выдержка (или этапов нет), а плотность с начала этапа стоит двое
        суток — (когда, плотность) или None. У «до плотности» и «до FG» это их собственное «пора»."""
        if self.current >= 0 and until_of(self.stages[self.current]) != "days":
            return None
        measures = self.since(self.current) if self.current >= 0 else self.gravity
        return stable(measures, self.top)

    def view(self):
        """Для общих примеров (shared/ferment-cases.json): то же, что считает интерфейс."""
        a, c = self.advice(), self.calm()
        return {"current": self.current,
                "stages": [{"from": unix(f), "to": unix(t), "target": self.targets[i]}
                           for i, (f, t, _) in enumerate(self.dated)],
                "advice": {"stage": a[0], "why": a[1], "value": a[2].value, "at": unix(a[2].at)} if a else None,
                "calm": {"value": c[1], "at": unix(c[0])} if c else None}


def schedule(plan, start, entries=(), now=None):
    """[(ключ, когда, заголовок, текст, по факту ли)] по плану брожения и записям журнала (по времени);
    start — начало брожения. now нужно этапам по плотности: где партия сейчас и пора ли замерить."""
    f = Ferment(plan, start, entries, now)
    stages, dated = f.stages, f.dated
    out = []

    def transition(i, why=None):
        """Заголовок и текст перехода от этапа i к следующему (или конца плана)."""
        lead = f"{why}. " if why else ""
        if i + 1 >= len(stages):
            return "Брожение по плану закончено", lead + "Можно переливать и разливать"
        nxt = stages[i + 1]
        name = nxt.get("name") or f"этап {i + 2}"
        return f"Пора: {name}", lead + f"{ru_num(nxt['temp'])} °C, {condition_text(nxt, f.targets[i + 1])}"

    reasons = []                                  # зачем замерить: этап по прикидке у конца, сухое по плотности

    def measure(due, text):
        if now is not None and now >= due:
            reasons.append(text)

    hit = f.advice()
    for i, st in enumerate(stages):
        key = f"stage-{i + 1}" if i + 1 < len(stages) else "end"
        silent = i + 1 < len(stages) and dated[i + 1][2]          # следующий уже начат по факту
        if until_of(st) == "days":
            out.append((key, dated[i][1], *transition(i), silent))
        elif i == f.current and hit is not None:
            _, why, e = hit
            text = {"target": f"Плотность {gravity_text(e.value)} — цель достигнута",
                    "slow": f"Брожение замедлилось: плотность {gravity_text(e.value)}, цель не наступила",
                    "stable": f"Плотность {gravity_text(e.value)} не меняется двое суток"}[why]
            out.append((key, e.at, *transition(i, text), silent))
        elif i == f.current and st["days"]:
            measure(dated[i][0] + timedelta(days=st["days"]),
                    f"«{st.get('name') or f'Этап {i + 1}'}» по прикидке подходит к концу — "
                    f"{condition_text(st, f.targets[i])}")

    for n, dh in enumerate(f.plan.get("dryHops") or []):
        items = ", ".join(dh["items"])
        if dh.get("gravity"):
            target = target_of(dh["gravity"], f.plan.get("og"), f.og)
            reached = next((e for e in f.gravity if e.at >= start and e.value <= target + 1e-9), None)
            if reached is not None:
                out.append((f"dry-g{n}", reached.at, "Сухое охмеление",
                            f"{items} — плотность {gravity_text(reached.value)}", False))
            elif dh.get("day"):
                measure(start + timedelta(days=dh["day"] - 1),
                        f"Сухое охмеление ({items}) — при {gravity_text(target)}")
        elif dh.get("day"):
            out.append((f"dry-{dh['day']}", start + timedelta(days=dh["day"] - 1), "Сухое охмеление", items, False))

    # «пора замерить» — одно в сутки брожения, пока нет свежего замера
    if reasons and not any(now - e.at < FRESH for e in f.gravity):
        out.append((f"measure-{int((now - start) / DAY)}", now, "Пора замерить плотность", "; ".join(reasons), False))

    if (calm := f.calm()) is not None:
        at, sg = calm
        nxt = stages[f.current + 1] if f.current + 1 < len(stages) else None
        upcoming = (nxt.get("name") or f"этап {f.current + 2}") if nxt else None
        out.append(("stable", at, "Похоже, брожение закончилось",
                    f"Плотность {gravity_text(sg)} не меняется двое суток — "
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
            out.append((b, [r for r in schedule(b.plan, pitch or b.day_ended_at, entries, now) if r[1] <= now]))
        return out
