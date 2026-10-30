"""Схемы API пивоварни: состояние и события (их присылает агент), ограничения, команды, история варок,
профиль оборудования."""
from typing import Literal

from pydantic import BaseModel, Field

from ..recipes.schemas import AdditionSlot, Recipe
from .kinds import KIND_IDS


# ── состояние ─────────────────────────────────────────────────────────────────
class Timer(BaseModel):
    minutes: int | None = Field(None, description="DP 6: минуты шага с округлением вверх")
    remaining: float | None = Field(None, description="оценка остатка шага, с")
    counting: bool = Field(description="идёт ли отсчёт (температура шага достигнута)")
    at: float = Field(description="момент оценки, unix-время агента")


class DeviceSettings(BaseModel):
    calibration: float | None = None
    boilCompensation: float | None = None
    unit: str | None = None
    model: str | None = None
    maxWatts: int | None = None


class DeviceStep(BaseModel):
    temp: float
    minutes: int
    watts: int
    additions: list[int] = Field(description="таймеры закладок, мин до конца шага")
    boil: bool
    name: str | None = None


class DeviceRecipe(BaseModel):
    name: str | None = Field(None, description="известно, если рецепт загружен из приложения")
    id: str | None = None
    brewId: str | None = Field(None, description="партия, под которую загружена программа («Сварить»)")
    steps: list[DeviceStep]


Status = Literal["idle", "paused", "running"] | int | None
Mode = Literal["manual", "recipe"] | int | None
Alert = Literal["malt", "mashEnd"] | str | None


class Energy(BaseModel):
    """Оценка расхода электричества ТЭНом (±20–30 %) — energy.py."""
    wh: float = Field(description="Вт·ч с начала текущей программы (варки)")
    watts: int = Field(description="оценка мощности ТЭНа сейчас")


class Snapshot(BaseModel):
    online: bool
    brewId: str | None = Field(None, description="идущая варка пивоварни — её партия")
    power: bool
    running: bool
    status: Status = None
    mode: Mode = None
    temp: float | None = None
    setpoint: float | None = None
    manualMinutes: int | None = None
    manualWatts: int | None = None
    pump: bool
    flow: int | None = None
    step: int
    stepTarget: float | None = None
    timer: Timer
    alert: Alert = None
    error: int
    settings: DeviceSettings
    deviceRecipe: DeviceRecipe | None = None
    additions: list[AdditionSlot]
    additionsPending: list[AdditionSlot] = Field(description="закладки, о которых напомнили, — ждут «Заложил»")
    energy: Energy


EventKind = Literal["alert", "alertCleared", "step", "addition", "added", "end", "powerOff", "error", "offline",
                   "online"]


class BrewEvent(BaseModel):
    kind: EventKind
    text: str
    at: float
    alert: str | None = None
    step: int | None = None
    addition: AdditionSlot | None = None


class Limits(BaseModel):
    """Ограничения пивоварни — сообщает агент (agent/PROTOCOL.md); интерфейс проверяет рецепт по ним же."""
    maxSteps: int
    maxAdditions: int = Field(description="разных времён закладок на кипячение")
    minTemp: float
    maxTemp: float
    boilTemp: float
    minWatts: int
    maxWatts: int | None = Field(None, description="потолок модели; None — модель неизвестна")
    wattsStep: int = Field(100, description="мощность задаётся кратно этому шагу, W")


# ── история варок ─────────────────────────────────────────────────────────────
EntryKind = Literal["first_wort", "preboil_gravity", "og", "gravity", "fg", "ph", "preboil_volume", "postboil_volume",
                    "fermenter_volume", "mash_temp", "temp", "pitch", "dry_hop", "cold_crash", "package", "note",
                    "stage", "step"]


class EquipmentRef(BaseModel):
    """Оборудование, на котором варили."""
    id: str
    name: str


class BrewSummary(BaseModel):
    id: str
    name: str
    status: Literal["running", "finished", "stopped"] = Field(description="исход программы пивоварни: running — "
                                                                         "идёт; у партии без пивоварни — идёт ли "
                                                                         "варочный день")
    phase: Literal["brewday", "fermenting", "packaged"] = Field(description="где партия: варочный день (до задачи "
                                                                          "дрожжей или «закончить»), брожение, "
                                                                          "разлито")
    manual: bool = Field(False, description="записана вручную, без пивоварни")
    recipeId: str | None = Field(None, description="рецепт библиотеки; None — рецепт из Smart Life или удалён")
    equipment: EquipmentRef | None = Field(None, description="на чём варили")
    startedAt: float = Field(description="unix-время")
    endedAt: float | None = None
    energyWh: float = Field(description="оценка расхода электричества ТЭНом, Вт·ч (±20–30 %)")
    og: float | None = Field(None, description="начальная плотность по факту (последний замер OG), SG")
    fg: float | None = Field(None, description="конечная плотность по факту (последний замер FG), SG")
    abv: float | None = Field(None, description="крепость по факту, % об.")
    volume: float | None = Field(None, description="объём в ферментере по факту, л")
    fermentStart: float | None = Field(None, description="начало брожения: задача дрожжей, иначе конец варочного "
                                                       "дня, если в плане есть брожение; unix-время")
    packagedAt: float | None = Field(None, description="розлив — брожение позади; unix-время")
    entries: int = Field(0, description="записей в журнале")


class FermentStage(BaseModel):
    name: str | None = None
    temp: float
    days: float = Field(description="until = days — сколько держать; gravity и fg — примерно сколько дней")
    until: Literal["gravity", "fg", "days"] = Field("days", description="когда к следующему: плотность дошла "
                                                                       "до цели, плотность перестала падать, "
                                                                       "прошли дни")
    gravity: float | None = Field(None, description="until = gravity: цель по рецепту, SG; в партии — от "
                                                    "фактической OG")


class DryHopDay(BaseModel):
    day: int | None = Field(None, description="день брожения; при gravity — примерный; None — не указан")
    gravity: float | None = Field(None, description="при какой плотности, SG; в партии — от фактической OG")
    items: list[str] = Field(description="«Citra 100 г»")


class BrewPlan(BaseModel):
    """Что задумано по рецепту на момент варки."""
    og: float | None = None
    fg: float | None = None
    abv: float | None = None
    volume: float | None = Field(None, description="л после кипячения")
    efficiency: float | None = None
    fermentation: list[FermentStage] | None = Field(None, description="этапы брожения")
    dryHops: list[DryHopDay] | None = Field(None, description="сухое охмеление по дням брожения")


class BrewDayAddition(BaseModel):
    minutes: int = Field(description="минут до конца кипячения")
    label: str = Field(description="«Magnum 26 г, Чиллер»")


class BrewDayStep(BaseModel):
    """Шаг варочного дня из рецепта партии (brewday.py)."""
    index: int
    key: str
    kind: Literal["prepare", "heat", "mash_in", "rest", "sparge", "boil", "chill", "pitch"]
    name: str
    temp: float | None = None
    minutes: int | None = Field(None, description="пауза или кипячение — сколько держать; таймер")
    measures: list[EntryKind] = Field([], description="замеры, которые делают на этом шаге")
    additions: list[BrewDayAddition] = Field([], description="закладки на кипячении, от ранних к поздним")
    at: float | None = Field(None, description="когда начат по факту (последний переход к нему), unix-время")


class BrewEntryOut(BaseModel):
    id: str
    at: float = Field(description="когда это было, unix-время")
    kind: EntryKind
    value: float | None = Field(None, description="замер: плотность — SG, pH, объём — л, температура — °C; "
                                                  "переход к шагу варочного дня — его номер с нуля; "
                                                  "переход к этапу — его номер в плане с нуля: первый "
                                                  "начинается с задачей дрожжей, поэтому 1 и дальше")
    text: str | None = None


class BrewEntryIn(BaseModel):
    kind: EntryKind
    value: float | None = None
    text: str | None = None
    at: float | None = Field(None, description="не указано — сейчас")


class BrewEntryEdit(BaseModel):
    value: float | None = None
    text: str | None = None
    at: float | None = Field(None, description="не указано — прежнее")


class BrewIn(BaseModel):
    recipeId: str
    startedAt: float | None = Field(None, description="день варки, unix-время; не указан — сейчас")
    equipmentId: str | None = Field(None, description="на чём варят; не указано — основное оборудование. Рецепт партии "
                                                      "пересчитывается под его объём и эффективность")


class BrewDetail(BrewSummary):
    recipe: DeviceRecipe | None = Field(None, description="рецепт, как он был в пивоварне на момент варки")
    snapshot: Recipe | None = Field(None, description="рецепт партии: пересчитан под оборудование на момент варки; "
                                                      "правка оригинала его не меняет. У варок до снимков — None")
    plan: BrewPlan | None = Field(None, description="что задумано: показатели и брожение рецепта партии")
    brewDay: list[BrewDayStep] = Field([], description="шаги варочного дня из рецепта партии")
    currentStep: int = Field(0, description="текущий шаг: последний по времени переход — запись step или шаг "
                                            "программы пивоварни по её событиям; дрожжи заданы — последний")
    events: list[BrewEvent]
    entries: list[BrewEntryOut] = []


# ── оборудование ──────────────────────────────────────────────────────────────
EquipmentKind = Literal[KIND_IDS]
PropValue = bool | float | str


class EquipmentIn(BaseModel):
    """Оборудование. У варочной системы — объём и эффективность для новых рецептов, испарение для расчёта воды,
    котёл; у прочего — параметры вида (props). Пределы, точность и средние — по каталогу (GET /api/equipment/kinds);
    чужое для вида или вне пределов — 400."""
    name: str = Field(max_length=60)
    volume: float | None = Field(None, description="система: л после кипячения — партия новых рецептов")
    efficiency: float | None = Field(None, description="система: эффективность для новых рецептов, %; "
                                                       "не указана — средняя из каталога")
    evaporation: float | None = Field(None, description="система: испарение при кипячении без крышки, л/ч; "
                                                        "не указано — среднее из каталога")
    kettle: float | None = Field(None, description="система: объём котла до краёв, л — предупредить, если варка "
                                                   "не влезает")
    props: dict[str, PropValue | None] = Field({}, description="не система: параметры вида по каталогу; пустые "
                                                               "не сохраняются")
    notes: str | None = Field(None, max_length=2000, description="модель, где куплено, особенности")


class EquipmentNew(EquipmentIn):
    kind: EquipmentKind = Field("manual", description="вид из каталога: manual — кастрюля или котёл, easybrew — "
                                                      "Easy Brew Connect, fermenter — ферментер…")


class Equipment(EquipmentNew):
    id: str
    kind: str = Field(description="вид из каталога; вида там уже нет — видно как «Другое» (category other)")
    category: str = Field(description="группа каталога: brew, mill, chill, ferment, measure, yeast, package, other")
    system: bool = Field(description="варочная система: на ней варят, у неё объём, эффективность и испарение")
    props: dict[str, PropValue] = {}
    connected: bool = Field(description="пивоварня привязана к сайту (агент её завёл)")
    controlled: bool = Field(description="пивоварня, которой сейчас управляет сайт: её связь, калибровка, команды")
    main: bool = Field(description="основная варочная система — для новых рецептов и расчётов")


class EquipmentOption(BaseModel):
    value: str
    label: str


class EquipmentField(BaseModel):
    key: str
    label: str
    type: Literal["number", "select", "bool"]
    unit: str | None = None
    min: float | None = None
    max: float | None = None
    step: float | None = None
    digits: int | None = Field(None, description="знаков после запятой")
    prefix: str | None = Field(None, description="перед значением в кратком описании: «котёл 40 л»")
    default: float | None = Field(None, description="у нового")
    short: str | None = Field(None, description="«да/нет»: в кратком описании, если да")
    options: list[EquipmentOption] | None = None
    help: str | None = None


class EquipmentKindInfo(BaseModel):
    id: EquipmentKind
    label: str
    hint: str
    system: bool
    fields: list[EquipmentField]


class EquipmentCategory(BaseModel):
    id: str
    label: str
    kinds: list[EquipmentKindInfo]



# ── команды ───────────────────────────────────────────────────────────────────
class OnOff(BaseModel):
    on: bool


class ManualMode(BaseModel):
    setpoint: float
    minutes: int
    watts: int


class FlowLevel(BaseModel):
    level: int


class SettingsUpdate(BaseModel):
    calibration: float | None = None
    boilCompensation: float | None = None
