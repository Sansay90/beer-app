"""HTTP API + поток SSE для интерфейса.

Запуск из папки brewapp/server:
    .venv\\Scripts\\python -m bridge.server           только этот ПК (http://127.0.0.1:8000)
    .venv\\Scripts\\python -m bridge.server --lan     доступ с телефона по домашней сети

Состояние и события идут интерфейсу потоком SSE (/api/stream), команды — обычными POST.
Если собран интерфейс (../web/.output/public), он раздаётся тут же, на корне.

Данные — в Postgres: DATABASE_URL (окружение или server/.env); схема — миграции Alembic, применяются при старте.
Переменные окружения: BREWAPP_DEVICES — ключи пивоварни для первичного заведения в базе,
BREWAPP_WEB_DIR — сборка интерфейса; VAPID_PRIVATE_KEY, VAPID_SUBJECT — уведомления (push.py);
BREWERY_IP, BREWERY_VERSION — адрес пивоварни и версия протокола вместо автопоиска;
BRIDGE_HOST, BRIDGE_PORT — где слушать.
"""
import argparse
import asyncio
import io
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from PIL import Image, ImageOps
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .brew import Controller
from .device import Brewery
from .push import Pusher
from .schemas import (BrewDetail, BrewEvent, BrewSummary, Equipment, FlowLevel, Limits, ManualMode, Ok, OnOff,
                      Photo, PushEndpoint, PushKey, PushSubscriptionIn, PushTest, Recipe, RecipeSummary, SavedRecipe,
                      SettingsUpdate, Snapshot)
from .store import Journal, RecipeStore

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))      # brewapp/server
DEVICES_FILE = os.environ.get("BREWAPP_DEVICES") or os.path.join(APP_DIR, "devices.json")
WEB_DIR = os.environ.get("BREWAPP_WEB_DIR") or os.path.join(os.path.dirname(APP_DIR), "web", ".output", "public")
COMMAND_TIMEOUT_S = 20                # последовательность «включить → режим → старт» с паузой
SSE_PING_S = 15

log = logging.getLogger("brewapp.server")
clients = set()
state = {}


def broadcast(msg):
    """Из потока пивоварни — в очереди подписчиков SSE."""
    loop = state.get("loop")
    for q in list(clients):
        loop.call_soon_threadsafe(q.put_nowait, msg)


async def ticker(controller):
    while True:
        await asyncio.sleep(1)
        controller.tick()


@asynccontextmanager
async def lifespan(app):
    state["loop"] = asyncio.get_running_loop()
    await asyncio.to_thread(db.migrate)
    user_id, device_id = await asyncio.to_thread(db.seed, DEVICES_FILE)

    journal = Journal(device_id, user_id)
    journal.start()
    recipes = RecipeStore(user_id)
    device = journal.device()
    # BREWERY_IP/VERSION перекрывают базу — в Docker автопоиск по широковещанию не работает
    brewery = Brewery(device.tuya_id, device.local_key,
                      address=os.environ.get("BREWERY_IP") or device.address,
                      version=os.environ.get("BREWERY_VERSION") or device.protocol)
    controller = Controller(brewery, journal, recipes)
    controller.subscribe(broadcast)
    pusher = Pusher(user_id, db.env("VAPID_PRIVATE_KEY"), db.env("VAPID_SUBJECT", "mailto:brewapp@example.com"))
    pusher.watch(controller)
    state.update(controller=controller, journal=journal, recipes=recipes, pusher=pusher)

    pusher.start()
    brewery.start()
    task = asyncio.create_task(ticker(controller))
    yield
    task.cancel()
    await asyncio.to_thread(brewery.stop)
    await asyncio.to_thread(pusher.stop)
    await asyncio.to_thread(journal.stop)


app = FastAPI(title="brewapp bridge", version="0.2", lifespan=lifespan)
# dev-сервер интерфейса может подняться на любом свободном порту
app.add_middleware(CORSMiddleware, allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
                   allow_methods=["*"], allow_headers=["*"])


def ctl() -> Controller:
    return state["controller"]


async def run(fn, *args, **kwargs):
    """Команда пивоварне: 400 — неверные данные, 404 — нет такого, 502/504 — пивоварня не подтвердила."""
    try:
        fut = fn(*args, **kwargs)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except KeyError as e:
        raise HTTPException(404, f"не найдено: {e}")
    try:
        res = await asyncio.wait_for(asyncio.wrap_future(fut), COMMAND_TIMEOUT_S)
    except asyncio.TimeoutError:
        raise HTTPException(504, "пивоварня не ответила")
    if not res.get("ok"):
        raise HTTPException(502, res.get("error") or "пивоварня не подтвердила команду (DP "
                            + ", ".join(res.get("missing", [])) + ")")
    return Ok()


def sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ── состояние ─────────────────────────────────────────────────────────────────
@app.get("/api/state", response_model=Snapshot, tags=["состояние"])
def get_state():
    return ctl().snapshot()


@app.get("/api/history", response_model=list[tuple[float, float, Optional[float]]], tags=["состояние"],
         summary="Точки графика [unix-время, °C, цель °C]")
def get_history(minutes: int = 360):
    return state["journal"].history(minutes * 60)


@app.get("/api/events", response_model=list[BrewEvent], tags=["состояние"], summary="Недавние события, новые первыми")
def get_events():
    return state["journal"].recent_events()


@app.get("/api/limits", response_model=Limits, tags=["состояние"])
def get_limits():
    return ctl().limits()


@app.get("/api/stream", tags=["состояние"], response_class=StreamingResponse,
         summary="SSE: `state` — Snapshot, `event` — BrewEvent",
         responses={200: {"content": {"text/event-stream": {}}}})
async def stream(request: Request):
    q = asyncio.Queue()
    clients.add(q)

    async def events():
        try:
            yield "retry: 2000\n\n"
            yield sse("state", ctl().snapshot())
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), SSE_PING_S)
                except asyncio.TimeoutError:
                    if await request.is_disconnected():
                        break
                    yield ": ping\n\n"
                    continue
                yield sse(msg["type"], msg["data"])
        finally:
            clients.discard(q)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── управление ────────────────────────────────────────────────────────────────
@app.post("/api/power", response_model=Ok, tags=["управление"])
async def power(body: OnOff):
    return await run(ctl().cmd_power, body.on)


@app.post("/api/manual", response_model=Ok, tags=["управление"], summary="Задать ручной режим")
async def manual(body: ManualMode):
    return await run(ctl().cmd_manual, body.setpoint, body.minutes, body.watts)


@app.post("/api/start", response_model=Ok, tags=["управление"], summary="Старт / продолжить")
async def start():
    return await run(ctl().cmd_run, True)


@app.post("/api/pause", response_model=Ok, tags=["управление"])
async def pause():
    return await run(ctl().cmd_run, False)


@app.post("/api/pump", response_model=Ok, tags=["управление"])
async def pump(body: OnOff):
    return await run(ctl().cmd_pump, body.on)


@app.post("/api/flow", response_model=Ok, tags=["управление"])
async def flow(body: FlowLevel):
    return await run(ctl().cmd_flow, body.level)


@app.post("/api/settings", response_model=Ok, tags=["управление"], summary="Калибровка и компенсация кипения")
async def settings(body: SettingsUpdate):
    return await run(ctl().cmd_settings, body.calibration, body.boilCompensation)


@app.post("/api/alert/confirm", response_model=Ok, tags=["управление"], summary="Подтвердить подсказку пивоварни")
async def confirm_alert():
    return await run(ctl().cmd_confirm_alert)


@app.post("/api/additions/{minutes}/ack", response_model=Ok, tags=["управление"],
          summary="Закладка сделана — снять напоминание")
def ack_addition(minutes: int):
    try:
        ctl().ack_addition(minutes)
    except KeyError:
        raise HTTPException(404, "такой закладки не ждём")
    return Ok()


# ── рецепты ───────────────────────────────────────────────────────────────────
@app.get("/api/recipes", response_model=list[RecipeSummary], tags=["рецепты"], summary="Рецепты, недавно изменённые первыми")
def list_recipes():
    return state["recipes"].list()


@app.get("/api/recipes/{rid}", response_model=Recipe, tags=["рецепты"])
def get_recipe(rid: str):
    try:
        return state["recipes"].get(rid)
    except KeyError:
        raise HTTPException(404, "рецепт не найден")


def save(rid, body):
    recipe = body.model_dump(exclude_none=True)
    try:
        ctl().validate_recipe(recipe)                       # до записи: пивоварня должна принять программу
        saved_id = state["recipes"].save(rid, recipe)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except KeyError:
        raise HTTPException(404, "рецепт не найден")
    ctl().on_recipe_saved(saved_id, recipe)
    return {"id": saved_id}


@app.post("/api/recipes", response_model=SavedRecipe, tags=["рецепты"], summary="Создать рецепт")
def create_recipe(body: Recipe):
    return save(None, body)


@app.put("/api/recipes/{rid}", response_model=SavedRecipe, tags=["рецепты"], summary="Сохранить рецепт")
def update_recipe(rid: str, body: Recipe):
    return save(rid, body)


@app.delete("/api/recipes/{rid}", response_model=Ok, tags=["рецепты"])
def delete_recipe(rid: str):
    try:
        state["recipes"].delete(rid)
    except KeyError:
        raise HTTPException(404, "рецепт не найден")
    ctl().on_recipe_deleted(rid)
    return Ok()


@app.post("/api/recipes/{rid}/upload", response_model=Ok, tags=["рецепты"], summary="Загрузить рецепт в пивоварню")
async def upload(rid: str):
    return await run(ctl().cmd_upload, rid)


# ── фото пива ─────────────────────────────────────────────────────────────────
PHOTO_MAX_BYTES = 10 * 1024 * 1024
PHOTOS_PER_RECIPE = 12
PHOTO_TYPES = ("image/jpeg", "image/png", "image/webp")
PHOTO_THUMB_SIDE = 480


def photo_thumb(data: bytes) -> bytes:
    """Превью для списков — JPEG до 480 px; заодно проверка, что картинка открывается (иначе ValueError)."""
    try:
        with Image.open(io.BytesIO(data)) as im:
            im = ImageOps.exif_transpose(im)
            im.thumbnail((PHOTO_THUMB_SIDE, PHOTO_THUMB_SIDE))
            out = io.BytesIO()
            im.convert("RGB").save(out, "JPEG", quality=80, optimize=True)
            return out.getvalue()
    except (OSError, Image.DecompressionBombError) as e:
        raise ValueError("картинка не открывается") from e


def photo_type(data: bytes):
    """Тип картинки по сигнатуре файла — заголовку Content-Type не верим; не картинка — None."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


@app.get("/api/recipes/{rid}/photos", response_model=list[Photo], tags=["рецепты"], summary="Фото пива по рецепту")
def list_photos(rid: str):
    try:
        return state["recipes"].photos(rid)
    except KeyError:
        raise HTTPException(404, "рецепт не найден")


@app.post("/api/recipes/{rid}/photos", response_model=Photo, tags=["рецепты"], summary="Добавить фото пива",
          description="Тело — сама картинка, JPEG, PNG или WebP, до 10 МБ (интерфейс заранее уменьшает её). "
                      "credit — автор и лицензия, если фото чужое.",
          openapi_extra={"requestBody": {"required": True, "content": {
              t: {"schema": {"type": "string", "format": "binary"}} for t in PHOTO_TYPES}}})
async def add_photo(rid: str, request: Request, credit: Optional[str] = Query(None, max_length=300)):
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > PHOTO_MAX_BYTES:
            raise HTTPException(413, "фото больше 10 МБ")
    kind = photo_type(bytes(data))
    try:
        if kind is None:
            raise ValueError
        thumb = await asyncio.to_thread(photo_thumb, bytes(data))
    except ValueError:
        raise HTTPException(415, "нужна картинка JPEG, PNG или WebP")
    try:
        return await asyncio.to_thread(state["recipes"].add_photo, rid, kind, bytes(data), thumb, credit,
                                       PHOTOS_PER_RECIPE)
    except KeyError:
        raise HTTPException(404, "рецепт не найден")
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.get("/api/photos/{pid}", response_class=Response, tags=["рецепты"], summary="Фото — сама картинка",
         responses={200: {"content": {t: {} for t in PHOTO_TYPES}}})
def get_photo(pid: str, thumb: bool = Query(False, description="превью до 480 px вместо полного снимка")):
    try:
        kind, data = state["recipes"].photo(pid, thumb)
    except KeyError:
        raise HTTPException(404, "фото не найдено")
    # фото не меняется — у нового снимка новый id
    return Response(data, media_type=kind, headers={"Cache-Control": "private, max-age=31536000, immutable",
                                                    "X-Content-Type-Options": "nosniff"})


@app.delete("/api/photos/{pid}", response_model=Ok, tags=["рецепты"], summary="Удалить фото")
def delete_photo(pid: str):
    try:
        state["recipes"].delete_photo(pid)
    except KeyError:
        raise HTTPException(404, "фото не найдено")
    return Ok()


@app.post("/api/recipe/start", response_model=Ok, tags=["рецепты"], summary="Запустить рецепт пивоварни")
async def start_recipe():
    return await run(ctl().cmd_start_recipe)


# ── история варок ─────────────────────────────────────────────────────────────
@app.get("/api/brews", response_model=list[BrewSummary], tags=["история"], summary="Варки, новые первыми")
def list_brews(recipe: Optional[str] = None):
    """recipe — только варки по этому рецепту."""
    try:
        return state["journal"].brews(recipe)
    except KeyError:
        return []


@app.get("/api/brews/{bid}", response_model=BrewDetail, tags=["история"],
         summary="Варка: рецепт, температура [время, °C, цель] и события")
def get_brew(bid: str):
    try:
        return state["journal"].brew(bid)
    except KeyError:
        raise HTTPException(404, "варка не найдена")


# ── оборудование ──────────────────────────────────────────────────────────────
@app.get("/api/equipment", response_model=Equipment, tags=["оборудование"], summary="Профиль оборудования")
def get_equipment():
    return Equipment.model_validate(state["journal"].equipment())


@app.put("/api/equipment", response_model=Equipment, tags=["оборудование"], summary="Сохранить профиль оборудования")
def put_equipment(body: Equipment):
    state["journal"].set_equipment(body.model_dump())
    return body


# ── уведомления ───────────────────────────────────────────────────────────────
def pusher() -> Pusher:
    """503, если на сервере не задан VAPID-ключ."""
    p = state["pusher"]
    if not p.enabled:
        raise HTTPException(503, "уведомления не настроены на сервере: нет VAPID_PRIVATE_KEY")
    return p


@app.get("/api/push/key", response_model=PushKey, tags=["уведомления"], summary="Ключ сервера для подписки браузера")
def push_key():
    return {"publicKey": pusher().public_key}


@app.post("/api/push/subscriptions", response_model=Ok, tags=["уведомления"], summary="Подписать браузер")
def push_subscribe(body: PushSubscriptionIn):
    try:
        pusher().subscribe(body.endpoint, body.keys.p256dh, body.keys.auth, body.userAgent)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return Ok()


@app.delete("/api/push/subscriptions", response_model=Ok, tags=["уведомления"], summary="Отписать браузер")
def push_unsubscribe(body: PushEndpoint):
    pusher().unsubscribe(body.endpoint)
    return Ok()


@app.post("/api/push/test", response_model=PushTest, tags=["уведомления"], summary="Проверочное уведомление")
def push_test():
    p = pusher()
    p.notify({"title": "Уведомления работают", "body": "Так придут подсказки, закладки и конец программы",
              "tag": "test"})
    return {"devices": p.count()}


if os.path.isdir(WEB_DIR):
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")


def main():
    p = argparse.ArgumentParser(description="brewapp — посредник между интерфейсом и пивоварней")
    p.add_argument("--host", default=os.environ.get("BRIDGE_HOST", "127.0.0.1"))
    p.add_argument("--lan", action="store_true", help="слушать домашнюю сеть (доступ с телефона) — то же, что --host 0.0.0.0")
    p.add_argument("--port", type=int, default=int(os.environ.get("BRIDGE_PORT", 8000)))
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    uvicorn.run(app, host="0.0.0.0" if args.lan else args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
