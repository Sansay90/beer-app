"""Схемы API посредника. Из них FastAPI строит OpenAPI, а из OpenAPI генерируются TS-типы интерфейса
(web: npm run api:types) — один источник истины для формы данных."""
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


# ── состояние пивоварни ───────────────────────────────────────────────────────
class Timer(BaseModel):
    minutes: Optional[int] = Field(None, description="DP 6: минуты шага с округлением вверх")
    remaining: Optional[float] = Field(None, description="оценка остатка шага, с")
    counting: bool = Field(description="идёт ли отсчёт (температура шага достигнута)")
    at: float = Field(description="момент оценки, unix-время посредника")


class DeviceSettings(BaseModel):
    calibration: Optional[float] = None
    boilCompensation: Optional[float] = None
    unit: Optional[str] = None
    model: Optional[str] = None
    maxWatts: Optional[int] = None


class DeviceStep(BaseModel):
    temp: float
    minutes: int
    watts: int
    additions: list[int] = Field(description="таймеры закладок, мин до конца шага")
    boil: bool
    name: Optional[str] = None


class DeviceRecipe(BaseModel):
    name: Optional[str] = Field(None, description="известно, если рецепт загружен из приложения")
    id: Optional[str] = None
    steps: list[DeviceStep]


AdditionKind = Literal["hop", "spice", "fining", "water", "adjunct", "sugar", "equipment"]
Unit = Literal["g", "kg", "ml", "pcs", "pkg"]


class Addition(BaseModel):
    """Что заложить в кипячение: хмель, специи, осветлитель, соли, добавка, сахар или оборудование (чиллер)."""
    minutes: int = Field(description="минут до конца кипячения")
    kind: AdditionKind = "hop"
    name: Optional[str] = None
    amount: Optional[float] = Field(None, description="у оборудования не бывает")
    unit: Unit = "g"


class AdditionSlot(BaseModel):
    """Таймер пивоварни и всё, что закладывают по нему: на одну минуту — один писк."""
    minutes: int = Field(description="минут до конца кипячения")
    items: list[Addition] = Field(description="пусто — рецепт загружен не из приложения")
    label: str


Status = Union[Literal["idle", "paused", "running"], int, None]
Mode = Union[Literal["manual", "recipe"], int, None]
Alert = Union[Literal["malt", "mashEnd"], str, None]


class Energy(BaseModel):
    """Оценка расхода электричества ТЭНом (±20–30 %) — energy.py."""
    wh: float = Field(description="Вт·ч с начала текущей программы (варки)")
    watts: int = Field(description="оценка мощности ТЭНа сейчас")


class Snapshot(BaseModel):
    online: bool
    power: bool
    running: bool
    status: Status = None
    mode: Mode = None
    temp: Optional[float] = None
    setpoint: Optional[float] = None
    manualMinutes: Optional[int] = None
    manualWatts: Optional[int] = None
    pump: bool
    flow: Optional[int] = None
    step: int
    stepTarget: Optional[float] = None
    timer: Timer
    alert: Alert = None
    error: int
    settings: DeviceSettings
    deviceRecipe: Optional[DeviceRecipe] = None
    additions: list[AdditionSlot]
    additionsPending: list[AdditionSlot] = Field(description="закладки, о которых напомнили, — ждут «Заложил»")
    energy: Energy


EventKind = Literal["alert", "alertCleared", "step", "addition", "added", "end", "powerOff", "error", "offline", "online"]


class BrewEvent(BaseModel):
    kind: EventKind
    text: str
    at: float
    alert: Optional[str] = None
    step: Optional[int] = None
    addition: Optional[AdditionSlot] = None


class Limits(BaseModel):
    """Ограничения контроллера (PROTOCOL.md) — интерфейс проверяет рецепт по ним же."""
    maxSteps: int
    maxAdditions: int = Field(description="разных времён закладок на кипячение")
    minTemp: float
    maxTemp: float
    boilTemp: float
    minWatts: int
    maxWatts: Optional[int] = Field(None, description="потолок модели; None — модель неизвестна")


# ── история варок ─────────────────────────────────────────────────────────────
class BrewSummary(BaseModel):
    id: str
    name: str
    status: Literal["running", "finished", "stopped"]
    recipeId: Optional[str] = Field(None, description="рецепт библиотеки; None — рецепт из Smart Life или удалён")
    startedAt: float = Field(description="unix-время")
    endedAt: Optional[float] = None
    energyWh: float = Field(description="оценка расхода электричества ТЭНом, Вт·ч (±20–30 %)")


class BrewDetail(BrewSummary):
    recipe: Optional[DeviceRecipe] = Field(None, description="рецепт, как он был в пивоварне на момент варки")
    readings: list[tuple[float, float, Optional[float]]] = Field(description="[unix-время, °C, цель °C]")
    events: list[BrewEvent]


# ── рецепты ───────────────────────────────────────────────────────────────────
# Рецепт описывает пиво (по мотивам BeerJSON). Программа пивоварни — затирание и кипячение — и напоминания
# на кипячении выводятся из него (program.py). Плотность — SG (1.048), цвет — EBC, объём — л, солод — кг, хмель — г.
class StyleRef(BaseModel):
    code: Optional[str] = Field(None, description="стиль BJCP 2021, напр. 5B; None — свой стиль")
    name: str


class Batch(BaseModel):
    volume: Optional[float] = Field(None, description="л сусла после кипячения — к нему считаются OG, IBU и цвет")
    efficiency: Optional[float] = Field(None, description="эффективность, %: экстракт в сусле после кипячения / экстракт засыпи")


class Targets(BaseModel):
    og: Optional[float] = Field(None, description="начальная плотность, SG")
    fg: Optional[float] = Field(None, description="конечная плотность, SG")
    ibu: Optional[float] = None
    ebc: Optional[float] = None


class Fermentable(BaseModel):
    name: str = ""
    kind: Literal["grain", "adjunct", "sugar", "extract"] = "grain"
    amount: Optional[float] = Field(None, description="кг")
    ebc: Optional[float] = None
    use: Literal["mash", "boil", "fermentation"] = "mash"
    minutes: Optional[int] = Field(None, description="кипячение — за сколько минут до конца")


class Hop(BaseModel):
    name: str = ""
    alpha: Optional[float] = Field(None, description="альфа-кислоты, %")
    amount: Optional[float] = Field(None, description="г")
    use: Literal["mash", "first_wort", "boil", "whirlpool", "dry_hop"] = "boil"
    minutes: Optional[int] = Field(None, description="кипячение — за сколько минут до конца; вирпул — сколько стоит")
    day: Optional[int] = Field(None, description="сухое охмеление — день брожения")


class Misc(BaseModel):
    name: str = ""
    kind: Literal["spice", "fining", "adjunct", "equipment"] = "adjunct"
    amount: Optional[float] = Field(None, description="у оборудования не бывает")
    unit: Unit = "g"
    use: Literal["mash", "boil", "whirlpool", "fermentation", "packaging"] = "boil"
    minutes: Optional[int] = Field(None, description="кипячение — за сколько минут до конца")


class WaterProfile(BaseModel):
    """Ионы, мг/л."""
    ca: float = 0
    mg: float = 0
    na: float = 0
    cl: float = 0
    so4: float = 0
    hco3: float = 0


WaterAgent = Literal["cacl2", "cacl2_anhydrous", "gypsum", "nacl", "nahco3", "caco3", "epsom",
                     "lactic80", "lactic88", "other"]


class WaterAddition(BaseModel):
    """Соль (г) или кислота (мл) в заторную или промывочную воду."""
    agent: WaterAgent
    name: str = Field("", description="для agent = other")
    amount: Optional[float] = None
    target: Literal["mash", "sparge"] = "mash"


class Water(BaseModel):
    """Заторная вода = гидромодуль × засыпь; промывочная — остальное до объёма перед кипячением
    с поправкой на дробину (считает интерфейс: испарение — у оборудования, а не в рецепте)."""
    ratio: Optional[float] = Field(None, description="гидромодуль — заторная вода к засыпи, л/кг")
    source: WaterProfile = Field(default_factory=WaterProfile, description="исходная вода; нули — осмос")
    additions: list[WaterAddition] = []


class Yeast(BaseModel):
    name: str = ""
    form: Literal["dry", "liquid"] = "dry"
    amount: Optional[float] = None
    unit: Unit = "pkg"
    attenuation: Optional[float] = Field(None, description="степень сбраживания, %")


class MashStep(BaseModel):
    name: Optional[str] = None
    temp: float
    minutes: int
    watts: int


class Boil(BaseModel):
    minutes: int
    watts: int


class FermentationStep(BaseModel):
    name: Optional[str] = None
    temp: float
    days: float


class Recipe(BaseModel):
    name: str
    style: Optional[StyleRef] = None
    batch: Batch = Field(default_factory=Batch)
    targets: Targets = Field(default_factory=Targets)
    fermentables: list[Fermentable] = []
    hops: list[Hop] = []
    miscs: list[Misc] = []
    yeasts: list[Yeast] = []
    water: Water = Field(default_factory=Water)
    mash: list[MashStep] = []
    boil: Optional[Boil] = None
    fermentation: list[FermentationStep] = []
    notes: str = ""


class RecipeSummary(BaseModel):
    id: str
    name: str
    style: Optional[StyleRef] = None
    targets: Targets
    volume: Optional[float] = Field(None, description="л сусла после кипячения")
    steps: int = Field(description="шагов программы пивоварни")
    minutes: int = Field(description="длительность программы без учёта нагрева")
    brews: int = Field(description="сколько раз варили")
    lastBrewedAt: Optional[float] = None
    updatedAt: float
    about: str = Field("", description="первый абзац описания (notes) — для карточки")
    photos: list[str] = Field([], description="id фото пива, старые первыми — миниатюры на карточке")


class Photo(BaseModel):
    """Фото пива по рецепту; сама картинка — GET /api/photos/{id}."""
    id: str
    credit: Optional[str] = Field(None, description="автор и лицензия, если фото чужое")
    createdAt: float


class SavedRecipe(BaseModel):
    id: str


# ── оборудование ──────────────────────────────────────────────────────────────
class Equipment(BaseModel):
    """Профиль оборудования пивоварни: эффективность — значение новых рецептов, по испарению считается промывочная вода."""
    efficiency: float = Field(75, ge=1, le=100, description="эффективность для новых рецептов, %")
    evaporation: float = Field(3.0, ge=0, le=20, description="испарение при кипячении, л/ч")


# ── команды ───────────────────────────────────────────────────────────────────
class Ok(BaseModel):
    ok: bool = True


class OnOff(BaseModel):
    on: bool


class ManualMode(BaseModel):
    setpoint: float
    minutes: int
    watts: int


class FlowLevel(BaseModel):
    level: int


class SettingsUpdate(BaseModel):
    calibration: Optional[float] = None
    boilCompensation: Optional[float] = None


# ── уведомления ───────────────────────────────────────────────────────────────
class PushKey(BaseModel):
    publicKey: str = Field(description="VAPID-ключ сервера, base64url — applicationServerKey для pushManager.subscribe")


class PushKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionIn(BaseModel):
    """PushSubscription.toJSON() браузера."""
    endpoint: str
    keys: PushKeys
    userAgent: Optional[str] = None


class PushEndpoint(BaseModel):
    endpoint: str


class PushTest(BaseModel):
    devices: int = Field(description="сколько устройств подписано — на столько и отправлено")
