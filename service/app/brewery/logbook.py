"""Журнал варок пивовара: варки с пивоварни и записанные вручную, а в каждой — лента записей.

«Сварить» заводит партию по рецепту, который видно (свой или опубликованный): сегодня — варочный день идёт,
задним числом — уже сварено. На подключённой пивоварне программа партии запускается с её id — варка с пивоварни
идёт в эту партию (journal.py). Без «Сварить» варка с пивоварни появляется сама. У варки — рецепт партии
(snapshot): рецепт, пересчитанный под объём и эффективность оборудования на момент варки (recipes/scale.py),
с его испарением — правка оригинала его не трогает; и план по нему: OG, FG, крепость, объём, эффективность, этапы
брожения и сухое охмеление по дням. Записи: замеры (плотность — в SG, pH, объём — л, температура — °C), вехи
(задача дрожжей, сухое охмеление, холодное осветление, розлив), переходы к шагам и этапам и заметки.

Фаза партии (phase): варочный день (brewday) → брожение (fermenting) → разлито (packaged); вылитая (dumped) —
с любой фазы, история остаётся. Варочный день кончается задачей дрожжей, «закончить» или «вылито», брошенный — сам
через полтора суток (brewday.py); удалили запись, которая его закончила, — день снова идёт. Конец программы
пивоварни или её выключение день не заканчивают — охлаждение и дрожжи ещё впереди. status — исход программы пивоварни
(у партии без неё — идёт ли день). Начальная и конечная плотность варки, объём в ферментере — последние такие
замеры, крепость — по ним. Брожение отсчитывается от задачи дрожжей (нет такой записи, но в плане есть брожение —
от конца варочного дня; нет и плана — брожения не видно: это могла быть проверка пивоварни на воде) и идёт
до розлива; напоминания по плану — reminders.py. Варку видит и ведёт только её пивовар; другим — только счёт
«сварили N раз»: сваренной считается разлитая и не вылитая партия, от одного пивовара по рецепту — не больше одной
в день, ручными записями его не накрутить.
"""
from datetime import timedelta

from sqlalchemy import exists, func
from sqlmodel import select

from ..access import can_view
from ..db import session
from ..errors import Conflict, Invalid, NotFound
from ..models import Brew, BrewEntry, Equipment, Event, Reading, Recipe, from_unix, parse_id, unix, utcnow
from ..recipes.calc import abv_of
from ..recipes.program import ru_num
from ..recipes.scale import scale_recipe
from .brewday import end_day, progress, reopen_day, steps_of
from .equipment import main_of, own
from .kinds import is_system

MANUAL, DEVICE = "manual", "device"
BREWDAY, FERMENTING, PACKAGED, DUMPED = "brewday", "fermenting", "packaged", "dumped"   # фазы партии
# замеры: вид → единица; вехи и заметка — без значения
MEASURES = {
    "first_wort": "sg", "preboil_gravity": "sg", "og": "sg", "gravity": "sg", "fg": "sg",
    "ph": "ph",
    "preboil_volume": "l", "postboil_volume": "l", "fermenter_volume": "l",
    "mash_temp": "c", "pitch_temp": "c", "temp": "c",   # затора; сусла при задаче дрожжей; брожения
}
MILESTONES = ("pitch", "dry_hop", "cold_crash", "package", "dumped")
NOTE = "note"
STAGE = "stage"                          # переход к этапу брожения по факту: value — его номер в плане с нуля (≥ 1)
STEP = "step"                            # переход к шагу варочного дня (brewday.py): value — номер шага с нуля
# переходы: самый малый номер и что сказать, если номера нет; номер у записи не меняется
TRANSITIONS = {STAGE: (1, "укажите номер этапа брожения"), STEP: (0, "укажите номер шага варочного дня")}
KINDS = (*MEASURES, *MILESTONES, NOTE, STAGE, STEP)
RANGES = {"sg": (0.98, 1.2), "ph": (2.0, 9.0), "l": (0.1, 2000.0), "c": (-5.0, 110.0)}
TEXT_MAX = 2000
ENTRIES_MAX = 500
LIST_MAX = 200
EARLIEST = from_unix(946684800)          # 2000-01-01: раньше варок не записывают
AHEAD = timedelta(days=1)                # запас на часовые пояса: «сегодня» у пивовара может быть завтра по UTC
SUMMARY = ("og", "fg", "fermenter_volume")   # из этих замеров — итог варки
MARKS = ("pitch", "package", "dumped")       # первая такая веха — начало брожения, розлив, вылито
DAY_ENDS = ("pitch", "dumped")               # эти вехи заканчивают варочный день


def dry_hops_of(data):
    """Сухое охмеление рецепта: [{day, gravity, items: ["Citra 100 г", …]}] — по плотности (день — примерный)
    или по дню брожения. По дню (у плотности — примерному) — раньше выше; только по плотности — после них, выше
    плотность — раньше; без дня и плотности — в конце. Отметки «заложил» сопоставляются по составу, не по месту."""
    groups = {}
    for h in data.get("hops") or []:
        if h.get("use") == "dry_hop":
            amount = f" {ru_num(h['amount'])} г" if h.get("amount") else ""
            groups.setdefault((h.get("gravity"), h.get("day")), []).append((h.get("name") or "Хмель") + amount)

    def order(key):
        gravity, day = key
        return (day is None and gravity is None, day is None, day or 0, -(gravity or 0))
    return [{"day": day, "gravity": gravity, "items": items}
            for (gravity, day), items in sorted(groups.items(), key=lambda x: order(x[0]))]


def plan_of(data):
    """План варки из рецепта (JSONB recipes.data): что задумано — для «факт против плана» и брожения."""
    t, b = data.get("targets") or {}, data.get("batch") or {}
    stages = [{"name": st.get("name"), "temp": st.get("temp"), "days": st.get("days") or 0,
               "until": st.get("until") or "days", "gravity": st.get("gravity")}
              for st in data.get("fermentation") or [] if st.get("days") or (st.get("until") or "days") != "days"]
    plan = {"og": t.get("og"), "fg": t.get("fg"), "abv": t.get("abv") or abv_of(t.get("og"), t.get("fg")),
            "volume": b.get("volume"), "efficiency": b.get("efficiency"),
            "fermentation": stages or None, "dryHops": dry_hops_of(data) or None}
    if plan["og"] is None and not plan["fermentation"] and not plan["dryHops"]:
        return None                                   # ни показателей, ни брожения — плана нет (объём — ещё не план)
    return {k: v for k, v in plan.items() if v is not None}


def batch_recipe(data, equipment):
    """Рецепт партии: рецепт (JSONB recipes.data) под объём и эффективность оборудования, с его испарением — по нему
    вода на варку; оборудования нет — как есть."""
    if equipment is None:
        return scale_recipe(data, None, None)
    r = scale_recipe(data, equipment.volume, equipment.efficiency)
    r["batch"]["evaporation"] = equipment.evaporation
    return r


def event_view(e):
    """Событие пивоварни для API (BrewEvent)."""
    return {**(e.data or {}), "kind": e.kind, "text": e.text, "at": unix(e.at)}


def summary_of(rows):
    """{вид: последнее значение замера SUMMARY или время первой вехи MARKS} по записям (kind, value, at) по времени."""
    last = {}
    for kind, value, at in rows:
        if kind in MARKS:
            last.setdefault(kind, at)
        elif kind in SUMMARY:
            last[kind] = value
    return last


def has_entry(*kinds):
    """Условие для запроса по Brew: у варки есть запись одного из видов kinds."""
    return exists().where(BrewEntry.brew_id == Brew.id, BrewEntry.kind.in_(kinds))


def ended_by(b, at):
    """Веха со временем at закончила варочный день b: день кончился в её время, и это не день начала (записанная
    задним числом варка кончается в день начала)."""
    return at is not None and b.day_ended_at == at != b.started_at


def fermenting(plan):
    """Есть ли в плане варки брожение — этапы или сухое охмеление."""
    return bool(plan and (plan.get("fermentation") or plan.get("dryHops")))


def brews_total(s, ids):
    """{id рецепта: сколько раз его сварили все пивовары}: сваренная — разлитая и не вылитая партия; от одного
    пивовара — не больше одной в день; кто варил, не раскрывается."""
    if not ids:
        return {}
    days = (select(Brew.recipe_id, Brew.user_id, func.date_trunc("day", Brew.started_at).label("day"))
            .where(Brew.recipe_id.in_(ids), has_entry("package"), ~has_entry("dumped")).distinct().subquery())
    return dict(s.exec(select(days.c.recipe_id, func.count()).group_by(days.c.recipe_id)).all())


def check_at(t, what="дата"):
    """unix-время из запроса → datetime; None — сейчас. Не раньше 2000 года и не в будущем."""
    if t is None:
        return utcnow()
    at = from_unix(t)
    if at < EARLIEST or at > utcnow() + AHEAD:
        raise Invalid(f"{what} — не раньше 2000 года и не в будущем")
    return at


def check_entry(kind, value, text):
    """Запись по виду: у замера — значение в своих пределах, у заметки — текст; текст — до TEXT_MAX."""
    if kind not in KINDS:
        raise Invalid("неизвестный вид записи")
    text = (text or "").strip() or None
    if text and len(text) > TEXT_MAX:
        raise Invalid(f"текст длиннее {TEXT_MAX} знаков — сократите")
    if kind in TRANSITIONS:
        low, missing = TRANSITIONS[kind]
        if value is None or value != int(value) or value < low:
            raise Invalid(missing)
        return float(value), text
    unit = MEASURES.get(kind)
    if unit is None:
        if kind == NOTE and not text:
            raise Invalid("напишите текст заметки")
        return None, text
    if value is None:
        raise Invalid("укажите значение замера")
    low, high = RANGES[unit]
    if not low <= value <= high:
        raise Invalid("значение замера вне разумных пределов — проверьте единицы")
    return float(value), text


class Logbook:
    """Варки пользователя user (не None). NotFound — варки, записи или рецепта не видно."""

    def __init__(self, user):
        self.user = user

    # ── варки ─────────────────────────────────────────────────────────────────
    def list(self, recipe_id=None, phase=None, limit=LIST_MAX):
        """Новые первыми; recipe_id — только по этому рецепту, phase — только в этой фазе."""
        q = select(Brew).where(Brew.user_id == self.user.id)
        # фаза — как в _summary: вылито важнее «разлито», дальше — идёт ли варочный день
        if phase == DUMPED:
            q = q.where(has_entry("dumped"))
        elif phase == PACKAGED:
            q = q.where(~has_entry("dumped"), has_entry("package"))
        elif phase in (BREWDAY, FERMENTING):
            day = Brew.day_ended_at.is_(None) if phase == BREWDAY else Brew.day_ended_at.is_not(None)
            q = q.where(~has_entry("dumped", "package"), day)
        if recipe_id:
            if (rid := parse_id(recipe_id)) is None:
                return []
            q = q.where(Brew.recipe_id == rid)
        with session() as s:
            brews = s.exec(q.order_by(Brew.started_at.desc()).limit(limit)).all()
            ids = [b.id for b in brews]
            counts = dict(s.exec(select(BrewEntry.brew_id, func.count()).where(BrewEntry.brew_id.in_(ids))
                                 .group_by(BrewEntry.brew_id)).all()) if ids else {}
            last = self._summary_measures(s, ids)
            used = {b.equipment_id for b in brews if b.equipment_id}
            names = dict(s.exec(select(Equipment.id, Equipment.name)
                                .where(Equipment.id.in_(used))).all()) if used else {}
        return [self._summary(b, last.get(b.id, {}), counts.get(b.id, 0), names) for b in brews]

    def get(self, brew_id):
        with session() as s:
            b = self._brew(s, brew_id)
            entries = s.exec(select(BrewEntry).where(BrewEntry.brew_id == b.id)
                             .order_by(BrewEntry.at, BrewEntry.created_at)).all()
            events = s.exec(select(Event).where(Event.brew_id == b.id).order_by(Event.at)).all()
            eq = s.get(Equipment, b.equipment_id) if b.equipment_id else None
        names = {eq.id: eq.name} if eq else {}
        last = summary_of((e.kind, e.value, e.at) for e in entries)
        steps = steps_of(b.snapshot) if b.snapshot else []
        current, starts, _ = progress(steps, b.started_at, [(e.at, e.kind, e.value) for e in entries],
                                      [(e.at, e.kind, e.data) for e in events])
        for st in steps:
            st["at"] = unix(starts.get(st["index"]))
        return {**self._summary(b, last, len(entries), names), "recipe": b.recipe or None, "snapshot": b.snapshot,
                "plan": b.plan, "brewDay": steps, "currentStep": current,
                "events": [event_view(e) for e in events],
                "entries": [self._entry(e) for e in entries]}

    def readings(self, brew_id):
        """Температура варки с пивоварни: [(unix-время, °C, цель °C)] по времени."""
        with session() as s:
            b = self._brew(s, brew_id)
            rows = s.exec(select(Reading.at, Reading.temp, Reading.target)
                          .where(Reading.brew_id == b.id).order_by(Reading.at)).all()
        return [(unix(at), temp, target) for at, temp, target in rows]

    def snapshot(self, brew_id):
        """(id рецепта, рецепт партии) — для загрузки программы партии в пивоварню; варочный день позади — Conflict."""
        with session() as s:
            b = self._brew(s, brew_id)
            if b.day_ended_at is not None:
                raise Conflict("варочный день этой партии позади")
            return (str(b.recipe_id) if b.recipe_id else None), b.snapshot

    def create(self, recipe_id, started_at=None, equipment_id=None):
        """Сварить: новая партия по рецепту, который пивовару виден, на указанном или основном оборудовании.
        Рецепт партии — пересчитанный под его объём и эффективность (без оборудования — как есть). День
        и оборудование задаются один раз: рецепт партии посчитан под них, ошиблись — удалить и сварить заново."""
        at = check_at(started_at)
        with session() as s:
            r = s.get(Recipe, rid) if (rid := parse_id(recipe_id)) else None
            if r is None or not can_view(self.user, r):
                raise NotFound("рецепт не найден")
            e = self._equipment(s, equipment_id) if equipment_id else main_of(s, self.user.id)
            if e is not None and not is_system(e.kind):
                raise Invalid("варят на варочной системе — кастрюле, котле или пивоварне")
            snapshot = batch_recipe(r.data, e)
            b = Brew(user_id=self.user.id, source=MANUAL, recipe_id=r.id, name=r.data.get("name") or "Варка",
                     equipment_id=e.id if e else None, snapshot=snapshot, plan=plan_of(snapshot),
                     status="running" if started_at is None else "finished", started_at=at,
                     day_ended_at=None if started_at is None else at)
            s.add(b)
            s.commit()
            bid = b.id
        return self.get(bid)

    def finish(self, brew_id):
        """Закончить варочный день — дальше брожение. Пока идёт программа пивоварни, день ведёт она."""
        with session() as s:
            b = self._brew(s, brew_id)
            if b.source != MANUAL and b.status == "running":
                raise Conflict("программа пивоварни ещё идёт — закончить день можно после неё")
            if b.day_ended_at is None:
                end_day(b, utcnow())
                s.add(b)
                s.commit()
        return self.get(brew_id)

    def delete(self, brew_id):
        with session() as s:
            b = self._brew(s, brew_id)
            if b.status == "running" and b.source != MANUAL:
                raise Conflict("варка на пивоварне ещё идёт — удалить можно после её конца")
            s.delete(b)
            s.commit()

    # ── записи ────────────────────────────────────────────────────────────────
    def add_entry(self, brew_id, kind, value=None, text=None, at=None):
        value, text = check_entry(kind, value, text)
        when = check_at(at, "время записи")
        with session() as s:
            b = self._brew(s, brew_id)
            if s.exec(select(func.count()).select_from(BrewEntry).where(BrewEntry.brew_id == b.id)).one() \
                    >= ENTRIES_MAX:
                raise Conflict(f"в журнале варки уже {ENTRIES_MAX} записей")
            if kind in TRANSITIONS:
                text = text or (self._stage_name if kind == STAGE else self._step_name)(b, value)
            if kind == "dumped" and b.source != MANUAL and b.status == "running":
                raise Conflict("программа пивоварни ещё идёт — отметить можно после её конца")
            if kind in DAY_ENDS and b.day_ended_at is None:     # дрожжи заданы или вылито — варочный день позади
                end_day(b, when)
                s.add(b)
            e = BrewEntry(brew_id=b.id, kind=kind, value=value, text=text, at=when)
            s.add(e)
            s.commit()
            return self._entry(e)

    def edit_entry(self, brew_id, entry_id, value=None, text=None, at=None):
        """Вид записи не меняется; время не прислали — остаётся прежним. Запись закончила варочный день — его конец
        переезжает вместе с ней: иначе её удаление день не вернёт."""
        with session() as s:
            e = self._entry_row(s, brew_id, entry_id)
            if e.kind in TRANSITIONS:                         # к какому этапу или шагу — не меняется
                value = e.value
            e.value, e.text = check_entry(e.kind, value, text)
            if at is not None:
                when = check_at(at, "время записи")
                b = s.get(Brew, e.brew_id)
                if e.kind in DAY_ENDS and ended_by(b, e.at):
                    if b.ended_at == b.day_ended_at:
                        b.ended_at = when
                    b.day_ended_at = when
                    s.add(b)
                e.at = when
            s.add(e)
            s.commit()
            return self._entry(e)

    def remove_entry(self, brew_id, entry_id):
        """Удалили запись, которая закончила варочный день («дрожжи заданы», «вылито»), и другой такой нет — день
        снова идёт. Записанная задним числом варка кончилась в день начала — её день не возвращается."""
        with session() as s:
            e = self._entry_row(s, brew_id, entry_id)
            b = s.get(Brew, e.brew_id)
            others = s.exec(select(func.count()).select_from(BrewEntry).where(
                BrewEntry.brew_id == b.id, BrewEntry.kind.in_(DAY_ENDS), BrewEntry.id != e.id)).one()
            if e.kind in DAY_ENDS and ended_by(b, e.at) and not others:
                reopen_day(b, e.at)
                s.add(b)
            s.delete(e)
            s.commit()

    # ── общее ─────────────────────────────────────────────────────────────────
    def _brew(self, s, brew_id):
        b = s.get(Brew, bid) if (bid := parse_id(brew_id)) else None
        if b is None or b.user_id != self.user.id:
            raise NotFound("варка не найдена")
        return b

    @staticmethod
    def _stage_name(b, number):
        """Название этапа плана по номеру; такого нет — Invalid. Первый этап начинается с задачей дрожжей."""
        stages = (b.plan or {}).get("fermentation") or []
        if not 1 <= int(number) < len(stages):
            raise Invalid("такого этапа в плане брожения нет")
        return stages[int(number)].get("name") or f"Этап {int(number) + 1}"

    @staticmethod
    def _step_name(b, number):
        """Название шага варочного дня по номеру; такого нет — Invalid."""
        steps = steps_of(b.snapshot) if b.snapshot else []
        if not 0 <= int(number) < len(steps):
            raise Invalid("такого шага в варочном дне нет")
        return steps[int(number)]["name"]

    def _equipment(self, s, equipment_id):
        return own(s, self.user.id, equipment_id)

    def _entry_row(self, s, brew_id, entry_id):
        b = self._brew(s, brew_id)
        e = s.get(BrewEntry, eid) if (eid := parse_id(entry_id)) else None
        if e is None or e.brew_id != b.id:
            raise NotFound("запись не найдена")
        return e

    @staticmethod
    def _summary_measures(s, ids):
        """{id варки: {вид: последнее значение замера или время первой вехи}} — для итога в списке."""
        if not ids:
            return {}
        rows = {}
        for bid, kind, value, at in s.exec(select(BrewEntry.brew_id, BrewEntry.kind, BrewEntry.value, BrewEntry.at)
                                           .where(BrewEntry.brew_id.in_(ids), BrewEntry.kind.in_(SUMMARY + MARKS))
                                           .order_by(BrewEntry.at, BrewEntry.created_at)).all():
            rows.setdefault(bid, []).append((kind, value, at))
        return {bid: summary_of(r) for bid, r in rows.items()}

    @staticmethod
    def _summary(b, last, entries, equipment_names):
        og, fg = last.get("og"), last.get("fg")
        name = equipment_names.get(b.equipment_id)
        phase = (DUMPED if last.get("dumped") else PACKAGED if last.get("package")
                 else BREWDAY if b.day_ended_at is None else FERMENTING)
        return {"id": str(b.id), "name": b.name, "status": b.status, "phase": phase, "manual": b.source == MANUAL,
                "recipeId": str(b.recipe_id) if b.recipe_id else None,
                "equipment": {"id": str(b.equipment_id), "name": name} if name else None,
                "startedAt": unix(b.started_at), "endedAt": unix(b.ended_at), "energyWh": b.energy_wh,
                "og": og, "fg": fg, "abv": abv_of(og, fg), "volume": last.get("fermenter_volume"),
                # от задачи дрожжей, иначе от конца варочного дня; день ещё идёт — брожение впереди; вылили в
                # варочный день, без дрожжей, — брожения не было
                "fermentStart": unix(last.get("pitch") or (b.day_ended_at if fermenting(b.plan)
                                                           and not ended_by(b, last.get("dumped")) else None)),
                "packagedAt": unix(last.get("package")), "dumpedAt": unix(last.get("dumped")),
                "entries": entries}

    @staticmethod
    def _entry(e):
        return {"id": str(e.id), "at": unix(e.at), "kind": e.kind, "value": e.value, "text": e.text}
