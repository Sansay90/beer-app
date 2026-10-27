"""Пивоварня пользователя: состояние и поток SSE, команды, история варок, профиль оборудования;
WebSocket для агентов (hub.py)."""
import asyncio
import json

from fastapi import APIRouter, Request, WebSocket
from fastapi.responses import StreamingResponse

from ..auth.dependencies import CurrentUser
from ..deps import DevicesDep, HubDep, JournalDep, StreamsDep
from ..schemas import Ok
from .control import UserBrewery, ViewerBrewery
from .schemas import (
    BrewDetail,
    BrewEvent,
    BrewSummary,
    Equipment,
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
            summary="SSE: `state` — Snapshot, `event` — BrewEvent",
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


# ── история варок ─────────────────────────────────────────────────────────────
@router.get("/brews", response_model=list[BrewSummary], tags=["история"], summary="Варки, новые первыми")
def list_brews(user: CurrentUser, journal: JournalDep, recipe: str | None = None):
    """recipe — только варки по этому рецепту."""
    return journal.brews(user.id, recipe)


@router.get("/brews/{bid}", response_model=BrewDetail, tags=["история"],
            summary="Варка: рецепт, температура [время, °C, цель] и события")
def get_brew(bid: str, user: CurrentUser, journal: JournalDep):
    return journal.brew(user.id, bid)


# ── оборудование ──────────────────────────────────────────────────────────────
@router.get("/equipment", response_model=Equipment, tags=["оборудование"], summary="Профиль оборудования")
def get_equipment(brewery: UserBrewery, devices: DevicesDep):
    return Equipment.model_validate(devices.equipment(brewery.device_id))


@router.put("/equipment", response_model=Equipment, tags=["оборудование"], summary="Сохранить профиль оборудования")
def put_equipment(body: Equipment, brewery: UserBrewery, devices: DevicesDep):
    devices.set_equipment(brewery.device_id, body.model_dump())
    return body
