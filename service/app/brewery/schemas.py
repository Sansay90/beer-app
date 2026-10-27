"""Схемы API пивоварни: состояние и события (их присылает агент), ограничения, команды, история варок,
профиль оборудования."""
from typing import Literal

from pydantic import BaseModel, Field

from ..recipes.schemas import AdditionSlot


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
class BrewSummary(BaseModel):
    id: str
    name: str
    status: Literal["running", "finished", "stopped"]
    recipeId: str | None = Field(None, description="рецепт библиотеки; None — рецепт из Smart Life или удалён")
    startedAt: float = Field(description="unix-время")
    endedAt: float | None = None
    energyWh: float = Field(description="оценка расхода электричества ТЭНом, Вт·ч (±20–30 %)")


class BrewDetail(BrewSummary):
    recipe: DeviceRecipe | None = Field(None, description="рецепт, как он был в пивоварне на момент варки")
    readings: list[tuple[float, float, float | None]] = Field(description="[unix-время, °C, цель °C]")
    events: list[BrewEvent]


# ── оборудование ──────────────────────────────────────────────────────────────
class Equipment(BaseModel):
    """Профиль оборудования пивоварни: эффективность — значение новых рецептов, по испарению считается
    промывочная вода."""
    efficiency: float = Field(75, ge=1, le=100, description="эффективность для новых рецептов, %")
    evaporation: float = Field(3.0, ge=0, le=20, description="испарение при кипячении, л/ч")


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
