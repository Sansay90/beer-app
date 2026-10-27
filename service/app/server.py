"""Сервис brewapp: HTTP API и поток SSE для интерфейса, WebSocket для агентов у пивоварен.

Запуск из папки brewapp/service:
    .venv\\Scripts\\python -m app.server           только этот ПК (http://127.0.0.1:8000)
    .venv\\Scripts\\python -m app.server --lan     доступ с телефона по домашней сети

Вход — по почте и паролю (auth.py), сессия — httpOnly-cookie. Роли и права — access.py: гость смотрит
опубликованные рецепты, пользователь ведёт свои рецепты и свою пивоварню, администратор ещё и модерирует. Состояние и события идут интерфейсу потоком SSE (/api/stream), команды —
обычными POST; пивоварне их передаёт её агент (hub.py). Если собран интерфейс (../web/.output/public), он
раздаётся тут же, на корне.

Данные — в Postgres: DATABASE_URL (окружение или service/.env); схема — миграции Alembic, применяются при старте.
Переменные окружения: APP_URL — адрес сайта (ссылки в письмах, проверка источника запросов); SMTP_* — письма
(mail.py); BREWAPP_WEB_DIR — сборка интерфейса; VAPID_PRIVATE_KEY, VAPID_SUBJECT — уведомления (push.py);
SERVICE_HOST, SERVICE_PORT — где слушать; FORWARDED_ALLOW_IPS — за reverse proxy: чьим заголовкам
X-Forwarded-* верить (схема https для cookie, настоящий адрес клиента для лимитов).
"""
import argparse
import asyncio
import io
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from typing import Annotated, Optional

import uvicorn
from PIL import Image, ImageOps
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import auth, db, mail
from .access import is_admin
from .hub import AgentLost, AgentOffline, Hub
from .models import User
from .program import build_program, check_boil_items, check_program, program_steps
from .push import Pusher
from .schemas import (AdminUser, BrewDetail, BrewEvent, BrewSummary, Credentials, EmailIn, Equipment, FlowLevel,
                      Limits, ManualMode, Me, Ok, OnOff, Photo, PushEndpoint, PushKey, PushSubscriptionIn, PushTest,
                      Recipe, RecipeDetail, RecipeSummary, ResetIn, RoleIn, SavedRecipe, SettingsUpdate, Snapshot,
                      TokenIn, VisibilityIn)
from .store import DeviceStore, Journal, RecipeStore

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))      # brewapp/service
WEB_DIR = os.environ.get("BREWAPP_WEB_DIR") or os.path.join(os.path.dirname(APP_DIR), "web", ".output", "public")
COMMAND_TIMEOUT_S = 35                # агент сам ждёт пивоварню до 30 с — дольше значит, что агент пропал
SSE_PING_S = 15
SESSION_COOKIE = "brewapp_session"
APP_URL = (db.env("APP_URL") or "").rstrip("/")
# без APP_URL сервис стоит у пивовара дома: интерфейсу из dev-сервера на этом же ПК — можно
LOCAL_ORIGIN = re.compile(r"https?://(localhost|127\.0\.0\.1)(:\d+)?")
TRUSTED_ORIGIN = re.compile(re.escape(APP_URL)) if APP_URL else LOCAL_ORIGIN

log = logging.getLogger("brewapp.server")
clients = {}                          # id пользователя → очереди его подписчиков SSE
state = {}


def broadcast(device_id, msg):
    """Сообщения пивоварни — подписчикам SSE её владельца."""
    for q in list(clients.get(hub().owner(device_id), ())):
        q.put_nowait(msg)


@asynccontextmanager
async def lifespan(app):
    await asyncio.to_thread(db.migrate)
    journal = Journal()
    journal.start()
    devices = DeviceStore()
    hub_ = Hub(devices, journal)
    hub_.subscribe(broadcast)
    pusher = Pusher(db.env("VAPID_PRIVATE_KEY"), db.env("VAPID_SUBJECT", "mailto:brewapp@example.com"))
    pusher.watch(hub_)
    state.update(journal=journal, devices=devices, hub=hub_, pusher=pusher)

    pusher.start()
    yield
    await asyncio.to_thread(pusher.stop)
    await asyncio.to_thread(journal.stop)


app = FastAPI(title="brewapp", version="0.4", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origin_regex=TRUSTED_ORIGIN.pattern, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def own_site_only(request: Request, call_next):
    """Изменяющие запросы — только со своего сайта: cookie браузер приложит и к форме, отправленной с чужой страницы."""
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD", "OPTIONS") and origin and not trusted(origin, request):
        return JSONResponse({"detail": "запрос с чужого сайта"}, status_code=403)
    return await call_next(request)


def trusted(origin, request):
    return origin == f"{request.url.scheme}://{request.headers.get('host', '')}" or bool(TRUSTED_ORIGIN.fullmatch(origin))


def hub() -> Hub:
    return state["hub"]


def optional_user(request: Request) -> Optional[User]:
    """Вошедший пользователь или None — гость."""
    return auth.session_user(request.cookies.get(SESSION_COOKIE))


def current_user(user: Annotated[Optional[User], Depends(optional_user)]) -> User:
    if user is None:
        raise HTTPException(401, "войдите")
    return user


def admin_user(user: Annotated[User, Depends(current_user)]) -> User:
    if not is_admin(user):
        raise HTTPException(403, "нужны права администратора")
    return user


Viewer = Annotated[Optional[User], Depends(optional_user)]
CurrentUser = Annotated[User, Depends(current_user)]
Admin = Annotated[User, Depends(admin_user)]


def device(user):
    """Пивоварня пользователя (пока она у него одна) или None — гость или агент ещё ни разу не подключался."""
    return state["devices"].current(user.id) if user is not None else None


def recipes(viewer):
    """Рецепты глазами этого человека: гостю — опубликованные, пользователю — ещё и свои."""
    return RecipeStore(viewer)


def denied(e):
    return HTTPException(403, str(e))


async def run(user, name, not_found=None, **args):
    """Команда пивоварне через её агента: 400 — неверные данные, 404 — нет такого, 502/504 — пивоварня не
    подтвердила или не ответила, 503 — агента нет на связи."""
    try:
        res = await hub().command(await asyncio.to_thread(device, user), name, COMMAND_TIMEOUT_S, **args)
    except AgentLost:
        raise HTTPException(503, "связь с пивоварней прервалась — команда могла выполниться, проверьте её состояние")
    except AgentOffline:
        raise HTTPException(503, "пивоварня не в сети")
    except TimeoutError:
        raise HTTPException(504, "пивоварня не ответила")
    if not res.get("ok"):
        status = res.get("status") or 502
        raise HTTPException(status, (status == 404 and not_found) or res.get("error") or "пивоварня не подтвердила команду")
    return Ok()


def sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ── вход ──────────────────────────────────────────────────────────────────────
# лимиты по адресу мягче: за NAT провайдера или шлюзом Docker с одного адреса приходят многие люди
failed_by_email = auth.Throttle(10, 15 * 60)         # неудачные входы в одну почту
failed_by_ip = auth.Throttle(50, 15 * 60)            # и с одного адреса
letters_by_email = auth.Throttle(5, 60 * 60)         # писем со ссылками на одну почту в час
letters_by_ip = auth.Throttle(30, 60 * 60)
signups_by_ip = auth.Throttle(30, 60 * 60)


def client_ip(request):
    return f"ip:{request.client.host if request.client else '?'}"


def too_many(wait):
    raise HTTPException(429, f"слишком много попыток — попробуйте через {max(1, round(wait / 60))} мин")


def throttle(*pairs):
    """Засчитать попытку по каждой паре (лимит, ключ); где лимит исчерпан — 429."""
    if wait := max(limiter.wait(key) for limiter, key in pairs):
        too_many(wait)
    for limiter, key in pairs:
        limiter.add(key)


def app_url(request):
    """Адрес сайта для ссылок в письмах. Без APP_URL — только адрес на этом же ПК: иначе подставной заголовок
    отправил бы ссылку сброса пароля на чужой сайт."""
    if APP_URL:
        return APP_URL
    origin = request.headers.get("origin") or str(request.base_url).rstrip("/")
    if LOCAL_ORIGIN.fullmatch(origin):
        return origin
    raise HTTPException(500, "на сервере не задан APP_URL — адрес сайта для ссылок в письмах")


def start_session(request, response, user):
    token = auth.start_session(user.id, request.headers.get("user-agent"))
    response.set_cookie(SESSION_COOKIE, token, max_age=auth.SESSION_DAYS * 86400, httponly=True, samesite="lax",
                        secure=request.url.scheme == "https", path="/")


def send_verify(request, user):
    link = f"{app_url(request)}/verify?token={auth.issue_token(user.id, 'verify')}"
    mail.send(user.email, *mail.verify_letter(user.email, link))


@app.post("/api/auth/register", response_model=Me, tags=["вход"], summary="Зарегистрироваться и войти",
          description="Письмо со ссылкой подтверждения почты уходит сразу; входить можно и до подтверждения.")
def register(body: Credentials, request: Request, response: Response):
    throttle((signups_by_ip, client_ip(request)))
    app_url(request)                                   # до записи: без адреса для ссылки регистрировать нельзя
    try:
        user = auth.register(body.email, body.password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    start_session(request, response, user)
    send_verify(request, user)
    return auth.me(user)


@app.post("/api/auth/login", response_model=Me, tags=["вход"], summary="Войти")
def login(body: Credentials, request: Request, response: Response):
    ip, email = client_ip(request), f"email:{body.email.strip().lower()}"
    if wait := max(failed_by_ip.wait(ip), failed_by_email.wait(email)):
        too_many(wait)
    user = auth.authenticate(body.email, body.password)
    if user is None:                                     # считаются только неудачные попытки
        failed_by_ip.add(ip)
        failed_by_email.add(email)
        raise HTTPException(401, "неверная почта или пароль")
    start_session(request, response, user)
    return auth.me(user)


@app.post("/api/auth/logout", response_model=Ok, tags=["вход"], summary="Выйти")
def logout(request: Request, response: Response):
    auth.end_session(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return Ok()


@app.get("/api/auth/me", response_model=Me, tags=["вход"], summary="Кто вошёл")
def get_me(user: CurrentUser):
    return auth.me(user)


@app.post("/api/auth/verify", response_model=Me, tags=["вход"], summary="Подтвердить почту по ссылке из письма")
def verify(body: TokenIn):
    try:
        return auth.me(auth.verify_email(body.token))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/auth/verify/resend", response_model=Ok, tags=["вход"], summary="Прислать письмо подтверждения ещё раз")
def resend_verify(user: CurrentUser, request: Request):
    if user.email_verified_at is None:
        throttle((letters_by_email, f"email:{user.email}"))
        send_verify(request, user)
    return Ok()


@app.post("/api/auth/forgot", response_model=Ok, tags=["вход"], summary="Прислать ссылку для нового пароля",
          description="Отвечает одинаково, есть такая почта или нет.")
def forgot(body: EmailIn, request: Request):
    email = body.email.strip().lower()
    throttle((letters_by_ip, client_ip(request)), (letters_by_email, f"email:{email}"))
    base = app_url(request)
    user = auth.user_by_email(email)
    if user is not None:
        mail.send(user.email, *mail.reset_letter(f"{base}/reset?token={auth.issue_token(user.id, 'reset')}"))
    return Ok()


@app.post("/api/auth/reset", response_model=Me, tags=["вход"], summary="Задать новый пароль по ссылке и войти",
          description="Прежние входы на всех устройствах закрываются.")
def reset(body: ResetIn, request: Request, response: Response):
    try:
        user = auth.reset_password(body.token, body.password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    start_session(request, response, user)
    return auth.me(user)


@app.get("/api/health", response_model=Ok, tags=["состояние"], summary="Сервис жив — для проверок Docker и мониторинга")
def health():
    return Ok()


# ── агенты ────────────────────────────────────────────────────────────────────
@app.websocket("/api/agent")
async def agent_socket(ws: WebSocket):
    """Агент у пивоварни: токен — в заголовке Authorization, сообщения — agent/README.md, «Протокол»."""
    await hub().serve(ws)


# ── состояние ─────────────────────────────────────────────────────────────────
@app.get("/api/state", response_model=Snapshot, tags=["состояние"])
def get_state(user: CurrentUser):
    return hub().snapshot(device(user))


@app.get("/api/history", response_model=list[tuple[float, float, Optional[float]]], tags=["состояние"],
         summary="Точки графика [unix-время, °C, цель °C]")
def get_history(user: CurrentUser, minutes: int = 360):
    d = device(user)
    return state["journal"].history(d, minutes * 60) if d else []


@app.get("/api/events", response_model=list[BrewEvent], tags=["состояние"], summary="Недавние события, новые первыми")
def get_events(user: CurrentUser):
    d = device(user)
    return state["journal"].recent_events(d) if d else []


@app.get("/api/limits", response_model=Limits, tags=["состояние"],
         summary="Ограничения пивоварни; гостю и без пивоварни — по умолчанию")
def get_limits(viewer: Viewer):
    return hub().limits(device(viewer))


@app.get("/api/stream", tags=["состояние"], response_class=StreamingResponse,
         summary="SSE: `state` — Snapshot, `event` — BrewEvent",
         responses={200: {"content": {"text/event-stream": {}}}})
async def stream(request: Request, user: CurrentUser):
    q = asyncio.Queue()
    clients.setdefault(user.id, set()).add(q)
    first = hub().snapshot(await asyncio.to_thread(device, user))

    async def events():
        try:
            yield "retry: 2000\n\n"
            yield sse("state", first)
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), SSE_PING_S)
                except TimeoutError:
                    if await request.is_disconnected():
                        break
                    yield ": ping\n\n"
                    continue
                yield sse(msg["type"], msg["data"])
        finally:
            clients.get(user.id, set()).discard(q)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── управление ────────────────────────────────────────────────────────────────
@app.post("/api/power", response_model=Ok, tags=["управление"])
async def power(body: OnOff, user: CurrentUser):
    return await run(user, "power", on=body.on)


@app.post("/api/manual", response_model=Ok, tags=["управление"], summary="Задать ручной режим")
async def manual(body: ManualMode, user: CurrentUser):
    return await run(user, "manual", setpoint=body.setpoint, minutes=body.minutes, watts=body.watts)


@app.post("/api/start", response_model=Ok, tags=["управление"], summary="Старт / продолжить")
async def start(user: CurrentUser):
    return await run(user, "run", run=True)


@app.post("/api/pause", response_model=Ok, tags=["управление"])
async def pause(user: CurrentUser):
    return await run(user, "run", run=False)


@app.post("/api/pump", response_model=Ok, tags=["управление"])
async def pump(body: OnOff, user: CurrentUser):
    return await run(user, "pump", on=body.on)


@app.post("/api/flow", response_model=Ok, tags=["управление"])
async def flow(body: FlowLevel, user: CurrentUser):
    return await run(user, "flow", level=body.level)


@app.post("/api/settings", response_model=Ok, tags=["управление"], summary="Калибровка и компенсация кипения")
async def settings(body: SettingsUpdate, user: CurrentUser):
    return await run(user, "settings", calibration=body.calibration, boilCompensation=body.boilCompensation)


@app.post("/api/alert/confirm", response_model=Ok, tags=["управление"], summary="Подтвердить подсказку пивоварни")
async def confirm_alert(user: CurrentUser):
    return await run(user, "confirmAlert")


@app.post("/api/additions/{minutes}/ack", response_model=Ok, tags=["управление"],
          summary="Закладка сделана — снять напоминание")
async def ack_addition(minutes: int, user: CurrentUser):
    return await run(user, "ackAddition", not_found="такой закладки не ждём", minutes=minutes)


# ── рецепты ───────────────────────────────────────────────────────────────────
@app.get("/api/recipes", response_model=list[RecipeSummary], tags=["рецепты"],
         summary="Опубликованные рецепты и свои, недавно изменённые первыми", description="mine — только свои.")
def list_recipes(viewer: Viewer, mine: bool = False):
    if mine and viewer is None:
        raise HTTPException(401, "войдите")
    return recipes(viewer).list(mine)


@app.get("/api/recipes/{rid}", response_model=RecipeDetail, tags=["рецепты"],
         summary="Рецепт: свой или опубликованный; meta — автор и что можно тому, кто спрашивает")
def get_recipe(rid: str, viewer: Viewer):
    try:
        return recipes(viewer).detail(rid)
    except KeyError:
        raise HTTPException(404, "рецепт не найден")


def in_device(device_id, rid):
    """Этот рецепт загружен в пивоварню."""
    return ((hub().snapshot(device_id).get("deviceRecipe") or {}).get("id")) == rid


def check(recipe, device_id):
    """ValueError, если пивоварня программу рецепта не примет. Рецепт без программы сохранить можно (черновик,
    импорт) — загрузить в пивоварню нельзя."""
    check_boil_items(recipe)
    if program_steps(recipe):
        check_program(build_program("", recipe), hub().limits(device_id))


async def save(user, rid, body):
    recipe = body.model_dump(exclude_none=True)
    d = await asyncio.to_thread(device, user)
    try:
        await asyncio.to_thread(check, recipe, d)         # до записи: пивоварня должна принять программу
        saved_id = await asyncio.to_thread(recipes(user).save, rid, recipe)
    except PermissionError as e:
        raise denied(e)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except KeyError:
        raise HTTPException(404, "рецепт не найден")
    if in_device(d, saved_id):                             # агенту — свежие названия шагов и закладок
        await hub().notify(d, {"type": "program", "program": build_program(saved_id, recipe)})
    return {"id": saved_id}


@app.post("/api/recipes", response_model=SavedRecipe, tags=["рецепты"], summary="Создать рецепт")
async def create_recipe(body: Recipe, user: CurrentUser):
    return await save(user, None, body)


@app.put("/api/recipes/{rid}", response_model=SavedRecipe, tags=["рецепты"], summary="Сохранить рецепт")
async def update_recipe(rid: str, body: Recipe, user: CurrentUser):
    return await save(user, rid, body)


@app.delete("/api/recipes/{rid}", response_model=Ok, tags=["рецепты"])
async def delete_recipe(rid: str, user: CurrentUser):
    try:
        await asyncio.to_thread(recipes(user).delete, rid)
    except PermissionError as e:
        raise denied(e)
    except KeyError:
        raise HTTPException(404, "рецепт не найден")
    d = await asyncio.to_thread(device, user)
    if in_device(d, rid):
        await hub().notify(d, {"type": "forget", "forget": rid})
    return Ok()


@app.put("/api/recipes/{rid}/visibility", response_model=Ok, tags=["рецепты"], summary="Опубликовать или снять с публикации",
         description="Автор — в обе стороны, публиковать — с подтверждённой почтой; администратор — снять чужой рецепт.")
def set_visibility(rid: str, body: VisibilityIn, user: CurrentUser):
    try:
        recipes(user).set_visibility(rid, body.visibility)
    except PermissionError as e:
        raise denied(e)
    except KeyError:
        raise HTTPException(404, "рецепт не найден")
    return Ok()


@app.post("/api/recipes/{rid}/upload", response_model=Ok, tags=["рецепты"], summary="Загрузить рецепт в пивоварню",
          description="Свой или опубликованный: варить можно и по чужому рецепту.")
async def upload(rid: str, user: CurrentUser):
    try:
        recipe = await asyncio.to_thread(recipes(user).get, rid)
    except KeyError:
        raise HTTPException(404, "рецепт не найден")
    try:
        await asyncio.to_thread(check, recipe, await asyncio.to_thread(device, user))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return await run(user, "upload", program=build_program(rid, recipe))


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
def list_photos(rid: str, viewer: Viewer):
    try:
        return recipes(viewer).photos(rid)
    except KeyError:
        raise HTTPException(404, "рецепт не найден")


@app.post("/api/recipes/{rid}/photos", response_model=Photo, tags=["рецепты"], summary="Добавить фото пива",
          description="Тело — сама картинка, JPEG, PNG или WebP, до 10 МБ (интерфейс заранее уменьшает её). "
                      "credit — автор и лицензия, если фото чужое.",
          openapi_extra={"requestBody": {"required": True, "content": {
              t: {"schema": {"type": "string", "format": "binary"}} for t in PHOTO_TYPES}}})
async def add_photo(rid: str, request: Request, user: CurrentUser,
                    credit: Optional[str] = Query(None, max_length=300)):
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
        return await asyncio.to_thread(recipes(user).add_photo, rid, kind, bytes(data), thumb, credit,
                                       PHOTOS_PER_RECIPE)
    except PermissionError as e:
        raise denied(e)
    except KeyError:
        raise HTTPException(404, "рецепт не найден")
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.get("/api/photos/{pid}", response_class=Response, tags=["рецепты"], summary="Фото — сама картинка",
         responses={200: {"content": {t: {} for t in PHOTO_TYPES}}})
def get_photo(pid: str, viewer: Viewer,
              thumb: bool = Query(False, description="превью до 480 px вместо полного снимка")):
    try:
        kind, data = recipes(viewer).photo(pid, thumb)
    except KeyError:
        raise HTTPException(404, "фото не найдено")
    # фото не меняется — у нового снимка новый id
    return Response(data, media_type=kind, headers={"Cache-Control": "private, max-age=31536000, immutable",
                                                    "X-Content-Type-Options": "nosniff"})


@app.delete("/api/photos/{pid}", response_model=Ok, tags=["рецепты"], summary="Удалить фото")
def delete_photo(pid: str, user: CurrentUser):
    try:
        recipes(user).delete_photo(pid)
    except PermissionError as e:
        raise denied(e)
    except KeyError:
        raise HTTPException(404, "фото не найдено")
    return Ok()


@app.post("/api/recipe/start", response_model=Ok, tags=["рецепты"], summary="Запустить рецепт пивоварни")
async def start_recipe(user: CurrentUser):
    return await run(user, "startRecipe")


# ── история варок ─────────────────────────────────────────────────────────────
@app.get("/api/brews", response_model=list[BrewSummary], tags=["история"], summary="Варки, новые первыми")
def list_brews(user: CurrentUser, recipe: Optional[str] = None):
    """recipe — только варки по этому рецепту."""
    try:
        return state["journal"].brews(user.id, recipe)
    except KeyError:
        return []


@app.get("/api/brews/{bid}", response_model=BrewDetail, tags=["история"],
         summary="Варка: рецепт, температура [время, °C, цель] и события")
def get_brew(bid: str, user: CurrentUser):
    try:
        return state["journal"].brew(user.id, bid)
    except KeyError:
        raise HTTPException(404, "варка не найдена")


# ── оборудование ──────────────────────────────────────────────────────────────
@app.get("/api/equipment", response_model=Equipment, tags=["оборудование"], summary="Профиль оборудования")
def get_equipment(user: CurrentUser):
    d = device(user)
    return Equipment.model_validate(state["devices"].equipment(d) if d else {})


@app.put("/api/equipment", response_model=Equipment, tags=["оборудование"], summary="Сохранить профиль оборудования")
def put_equipment(body: Equipment, user: CurrentUser):
    d = device(user)
    if d is None:
        raise HTTPException(409, "пивоварня ещё не подключена")
    state["devices"].set_equipment(d, body.model_dump())
    return body


# ── администрирование ─────────────────────────────────────────────────────────
@app.get("/api/admin/users", response_model=list[AdminUser], tags=["администрирование"], summary="Пользователи")
def admin_users(admin: Admin):
    return auth.list_users()


@app.put("/api/admin/users/{uid}/role", response_model=AdminUser, tags=["администрирование"], summary="Сменить роль")
def admin_set_role(uid: str, body: RoleIn, admin: Admin):
    try:
        user = auth.set_role(uid, body.role)
    except KeyError:
        raise HTTPException(404, "пользователь не найден")
    except ValueError as e:
        raise HTTPException(409, str(e))
    return next(u for u in auth.list_users() if u["id"] == str(user.id))


# ── уведомления ───────────────────────────────────────────────────────────────
def pusher() -> Pusher:
    """503, если на сервере не задан VAPID-ключ."""
    p = state["pusher"]
    if not p.enabled:
        raise HTTPException(503, "уведомления не настроены на сервере: нет VAPID_PRIVATE_KEY")
    return p


@app.get("/api/push/key", response_model=PushKey, tags=["уведомления"], summary="Ключ сервера для подписки браузера")
def push_key(user: CurrentUser):
    return {"publicKey": pusher().public_key}


@app.post("/api/push/subscriptions", response_model=Ok, tags=["уведомления"], summary="Подписать браузер")
def push_subscribe(body: PushSubscriptionIn, user: CurrentUser):
    try:
        pusher().subscribe(user.id, body.endpoint, body.keys.p256dh, body.keys.auth, body.userAgent)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return Ok()


@app.delete("/api/push/subscriptions", response_model=Ok, tags=["уведомления"], summary="Отписать браузер")
def push_unsubscribe(body: PushEndpoint, user: CurrentUser):
    pusher().unsubscribe(user.id, body.endpoint)
    return Ok()


@app.post("/api/push/test", response_model=PushTest, tags=["уведомления"], summary="Проверочное уведомление")
def push_test(user: CurrentUser):
    p = pusher()
    p.notify(user.id, {"title": "Уведомления работают", "body": "Так придут подсказки, закладки и конец программы",
                       "tag": "test"})
    return {"devices": p.count(user.id)}


class AppFiles(StaticFiles):
    """Собранный интерфейс: путь страницы (/recipes/<id>) — не файл, ему 200.html: маршрут разберёт само приложение."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 404:
            return await super().get_response("200.html", scope)
        if response.status_code in (307, 308) and path and not path.endswith("/"):
            # у страницы сборка завела папку (recipes/index.html) — отдать её сразу, без лишнего «/» в адресе
            return await super().get_response(f"{path}/index.html", scope)
        return response


if os.path.isdir(WEB_DIR):
    app.mount("/", AppFiles(directory=WEB_DIR, html=True), name="web")


def main():
    p = argparse.ArgumentParser(description="brewapp — сервис: API для интерфейса и связь с агентами пивоварен")
    p.add_argument("--host", default=os.environ.get("SERVICE_HOST", "127.0.0.1"))
    p.add_argument("--lan", action="store_true", help="слушать домашнюю сеть (доступ с телефона) — то же, что --host 0.0.0.0")
    p.add_argument("--port", type=int, default=int(os.environ.get("SERVICE_PORT", 8000)))
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    uvicorn.run(app, host="0.0.0.0" if args.lan else args.host, port=args.port, log_level="warning",
                proxy_headers=True, forwarded_allow_ips=os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1"))


if __name__ == "__main__":
    main()
