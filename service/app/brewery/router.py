"""Пивоварня пользователя: состояние и поток SSE, команды; журнал варок (партии, записи, варочный день);
оборудование; WebSocket для агентов (hub.py)."""
import asyncio
import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, WebSocket
from fastapi.responses import StreamingResponse

from ..auth.dependencies import CurrentUser
from ..deps import BrewDayDep, HubDep, JournalDep, StreamsDep
from ..errors import Invalid
from ..recipes.program import build_program
from ..schemas import Ok
from .control import UserBrewery, ViewerBrewery
from .equipment import EquipmentStore
from .kinds import CATEGORIES
from .logbook import Logbook
from .schemas import (
    BrewDetail,
    BrewEntryEdit,
    BrewEntryIn,
    BrewEntryOut,
    BrewEvent,
    BrewIn,
    BrewSummary,
    Equipment,
    EquipmentCategory,
    EquipmentIn,
    EquipmentNew,
    FlowLevel,
    Limits,
    ManualMode,
    OnOff,
    SettingsUpdate,
    Snapshot,
)

SSE_PING_S = 15

router = APIRouter()


def sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ── агенты ────────────────────────────────────────────────────────────────────
@router.websocket("/agent")
async def agent_socket(ws: WebSocket, hub: HubDep):
    """Агент у пивоварни: токен — в заголовке Authorization, сообщения — agent/README.md, «Протокол»."""
    await hub.serve(ws)


# ── состояние ─────────────────────────────────────────────────────────────────
@router.get("/state", response_model=Snapshot, tags=["состояние"])
def get_state(brewery: UserBrewery):
    return brewery.snapshot()


@router.get("/history", response_model=list[tuple[float, float, float | None]], tags=["состояние"],
            summary="Точки графика [unix-время, °C, цель °C]")
def get_history(brewery: UserBrewery, journal: JournalDep, minutes: int = 360):
    return journal.history(brewery.device_id, minutes * 60)


@router.get("/events", response_model=list[BrewEvent], tags=["состояние"], summary="Недавние события, новые первыми")
def get_events(brewery: UserBrewery, journal: JournalDep):
    return journal.recent_events(brewery.device_id)


@router.get("/limits", response_model=Limits, tags=["состояние"],
            summary="Ограничения пивоварни; гостю и без пивоварни — по умолчанию")
def get_limits(brewery: ViewerBrewery):
    return brewery.limits()


@router.get("/stream", tags=["состояние"], response_class=StreamingResponse,
            summary="SSE: `state` — Snapshot, `event` — BrewEvent, `brew` — {id} варки, которая изменилась, "
                    "`notice` — новое уведомление",
            responses={200: {"content": {"text/event-stream": {}}}})
async def stream(request: Request, user: CurrentUser, brewery: UserBrewery, streams: StreamsDep):
    async def events():
        with streams.subscribe(user.id) as q:
            yield "retry: 2000\n\n"
            yield sse("state", brewery.snapshot())
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), SSE_PING_S)
                except TimeoutError:
                    if await request.is_disconnected():
                        break
                    yield ": ping\n\n"
                    continue
                yield sse(msg["type"], msg["data"])

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── управление ────────────────────────────────────────────────────────────────
@router.post("/power", response_model=Ok, tags=["управление"])
async def power(body: OnOff, brewery: UserBrewery):
    return await brewery.run("power", on=body.on)


@router.post("/manual", response_model=Ok, tags=["управление"], summary="Задать ручной режим")
async def manual(body: ManualMode, brewery: UserBrewery):
    return await brewery.run("manual", setpoint=body.setpoint, minutes=body.minutes, watts=body.watts)


@router.post("/start", response_model=Ok, tags=["управление"], summary="Старт / продолжить")
async def start(brewery: UserBrewery):
    return await brewery.run("run", run=True)


@router.post("/pause", response_model=Ok, tags=["управление"])
async def pause(brewery: UserBrewery):
    return await brewery.run("run", run=False)


@router.post("/pump", response_model=Ok, tags=["управление"])
async def pump(body: OnOff, brewery: UserBrewery):
    return await brewery.run("pump", on=body.on)


@router.post("/flow", response_model=Ok, tags=["управление"])
async def flow(body: FlowLevel, brewery: UserBrewery):
    return await brewery.run("flow", level=body.level)


@router.post("/settings", response_model=Ok, tags=["управление"], summary="Калибровка и компенсация кипения")
async def settings(body: SettingsUpdate, brewery: UserBrewery):
    return await brewery.run("settings", calibration=body.calibration, boilCompensation=body.boilCompensation)


@router.post("/alert/confirm", response_model=Ok, tags=["управление"], summary="Подтвердить подсказку пивоварни")
async def confirm_alert(brewery: UserBrewery):
    return await brewery.run("confirmAlert")


@router.post("/additions/{minutes}/ack", response_model=Ok, tags=["управление"],
             summary="Закладка сделана — снять напоминание")
async def ack_addition(minutes: int, brewery: UserBrewery):
    return await brewery.run("ackAddition", not_found="такой закладки не ждём", minutes=minutes)


@router.post("/recipe/start", response_model=Ok, tags=["рецепты"], summary="Запустить рецепт пивоварни")
async def start_recipe(brewery: UserBrewery):
    return await brewery.run("startRecipe")


# ── журнал варок ──────────────────────────────────────────────────────────────
def user_logbook(user: CurrentUser) -> Logbook:
    return Logbook(user)


UserLogbook = Annotated[Logbook, Depends(user_logbook)]


@router.get("/brews", response_model=list[BrewSummary], tags=["варки"], summary="Свои варки, новые первыми")
def list_brews(logbook: UserLogbook, recipe: str | None = None,
               phase: Literal["brewday", "fermenting", "packaged"] | None = None,
               limit: Annotated[int, Query(ge=1, le=200)] = 200):
    """recipe — только варки по этому рецепту, phase — только в этой фазе (brewday — варочный день идёт)."""
    return logbook.list(recipe, phase, limit)


@router.post("/brews", response_model=BrewDetail, tags=["варки"], summary="Сварить — новая партия по рецепту",
             description="По рецепту, который виден: свой или опубликованный. Партия получает рецепт, "
                         "пересчитанный под объём и эффективность оборудования (snapshot), и план по нему.")
def create_brew(body: BrewIn, logbook: UserLogbook):
    return logbook.create(body.recipeId, body.startedAt, body.equipmentId)


@router.get("/brews/{bid}", response_model=BrewDetail, tags=["варки"],
            summary="Варка: рецепт партии, план, шаги варочного дня, записи журнала и события пивоварни")
def get_brew(bid: str, logbook: UserLogbook):
    return logbook.get(bid)


@router.get("/brews/{bid}/readings", response_model=list[tuple[float, float, float | None]], tags=["варки"],
            summary="Температура варки с пивоварни: [unix-время, °C, цель °C]")
def get_readings(bid: str, logbook: UserLogbook):
    return logbook.readings(bid)


@router.post("/brews/{bid}/upload", response_model=Ok, tags=["варки"], summary="Загрузить программу партии в пивоварню",
             description="Программа рецепта партии с её id: запущенная, она идёт варкой в эту партию.")
async def upload_brew(bid: str, logbook: UserLogbook, brewery: UserBrewery):
    recipe_id, snapshot = await asyncio.to_thread(logbook.snapshot, bid)
    if not snapshot:
        raise Invalid("у этой варки нет рецепта партии")
    await asyncio.to_thread(brewery.check, snapshot)
    return await brewery.run("upload", program=build_program(recipe_id or "", snapshot, bid))


@router.post("/brews/{bid}/finish", response_model=BrewDetail, tags=["варки"], summary="Закончить варочный день",
             description="Дальше брожение. Пока идёт программа пивоварни — нельзя (409): день ведёт она.")
def finish_brew(bid: str, logbook: UserLogbook):
    return logbook.finish(bid)


@router.delete("/brews/{bid}", response_model=Ok, tags=["варки"], summary="Удалить варку",
               description="С журналом, температурой и событиями; идущую на пивоварне — нельзя.")
def delete_brew(bid: str, logbook: UserLogbook):
    logbook.delete(bid)
    return Ok()


@router.post("/brews/{bid}/entries", response_model=BrewEntryOut, tags=["варки"], summary="Запись в журнал варки",
             description="Замер (value: плотность — SG, pH, объём — л, температура — °C), веха или заметка (text).")
async def add_entry(bid: str, body: BrewEntryIn, logbook: UserLogbook, brewday: BrewDayDep):
    entry = await asyncio.to_thread(logbook.add_entry, bid, body.kind, body.value, body.text, body.at)
    if body.kind == "step":                      # закладка «в начале» и прочее, чему пора сразу, — не ждать проверки
        await asyncio.to_thread(brewday.tick, None, bid)
    return entry


@router.patch("/brews/{bid}/entries/{eid}", response_model=BrewEntryOut, tags=["варки"], summary="Изменить запись")
def edit_entry(bid: str, eid: str, body: BrewEntryEdit, logbook: UserLogbook):
    return logbook.edit_entry(bid, eid, body.value, body.text, body.at)


@router.delete("/brews/{bid}/entries/{eid}", response_model=Ok, tags=["варки"], summary="Удалить запись")
def delete_entry(bid: str, eid: str, logbook: UserLogbook):
    logbook.remove_entry(bid, eid)
    return Ok()


# ── оборудование ──────────────────────────────────────────────────────────────
def user_equipment(user: CurrentUser) -> EquipmentStore:
    return EquipmentStore(user)


UserEquipment = Annotated[EquipmentStore, Depends(user_equipment)]


@router.get("/equipment/kinds", response_model=list[EquipmentCategory], tags=["оборудование"],
            summary="Каталог оборудования: группы, виды и их параметры")
def equipment_kinds():
    return CATEGORIES


@router.get("/equipment", response_model=list[Equipment], tags=["оборудование"], summary="Оборудование",
            description="Основное первым.")
def list_equipment(equipment: UserEquipment):
    return equipment.list()


@router.post("/equipment", response_model=Equipment, tags=["оборудование"], summary="Добавить оборудование",
             description="Первая варочная система — основная; не больше 100.")
def create_equipment(body: EquipmentNew, equipment: UserEquipment):
    return equipment.create(body.name, body.kind, body.volume, body.efficiency, body.evaporation, body.kettle,
                            body.props, body.notes)


@router.put("/equipment/{eid}", response_model=Equipment, tags=["оборудование"], summary="Изменить оборудование",
            description="Вид не меняется.")
def update_equipment(eid: str, body: EquipmentIn, equipment: UserEquipment):
    return equipment.update(eid, body.name, body.volume, body.efficiency, body.evaporation, body.kettle,
                            body.props, body.notes)


@router.put("/equipment/{eid}/main", response_model=Equipment, tags=["оборудование"],
            summary="Сделать основным", description="Только варочную систему (400).")
def make_main_equipment(eid: str, equipment: UserEquipment):
    return equipment.make_main(eid)


@router.delete("/equipment/{eid}", response_model=Ok, tags=["оборудование"], summary="Удалить оборудование",
               description="Пивоварню, привязанную к сайту, — нельзя (409).")
def delete_equipment(eid: str, equipment: UserEquipment):
    equipment.delete(eid)
    return Ok()
