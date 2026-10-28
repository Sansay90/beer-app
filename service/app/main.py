"""Сервис brewapp: HTTP API и поток SSE для интерфейса, WebSocket для агентов у пивоварен.

create_app собирает приложение: настройки (config.py), общие объекты в app.state (зависимости — deps.py),
роутеры разделов и проверку источника запросов. На старте (lifespan) — миграции базы, журнал, связь с агентами
и уведомления. Запуск — python -m app (cli.py). Интерфейс — отдельное приложение (web/), сервис отдаёт только /api.
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db, errors
from .auth.admin import router as admin_router
from .auth.brewers import router as brewers_router
from .auth.router import router as auth_router
from .auth.throttle import AuthLimits
from .brewery.devices import DeviceStore
from .brewery.hub import Hub
from .brewery.journal import Journal
from .brewery.router import router as brewery_router
from .brewery.streams import Streams
from .config import Settings
from .mail import Mailer
from .notifications.router import router as notifications_router
from .push.pusher import Pusher
from .push.router import router as push_router
from .recipes.router import router as recipes_router
from .schemas import Ok
from .security import OwnSiteOnly


@asynccontextmanager
async def lifespan(app: FastAPI):
    state, settings = app.state, app.state.settings
    if not settings.database_url:
        raise RuntimeError("не задан DATABASE_URL (переменная окружения или service/.env)")
    db.configure(settings.database_url)
    await asyncio.to_thread(db.migrate)

    state.journal = Journal()
    state.devices = DeviceStore()
    state.hub = Hub(state.devices, state.journal)
    state.streams = Streams()
    # сообщения пивоварни — открытым вкладкам её владельца
    state.hub.subscribe(lambda device_id, msg: state.streams.publish(state.hub.owner(device_id), msg))
    state.pusher = Pusher(settings.vapid_private_key, settings.vapid_subject)
    state.pusher.watch(state.hub)

    state.journal.start()
    state.pusher.start()
    yield
    await asyncio.to_thread(state.pusher.stop)
    await asyncio.to_thread(state.journal.stop)


def api_router():
    api = APIRouter(prefix="/api")

    @api.get("/health", response_model=Ok, tags=["состояние"],
             summary="Сервис жив — для проверок Docker и мониторинга")
    def health():
        return Ok()

    for router in (auth_router, admin_router, brewers_router, recipes_router, brewery_router, push_router,
                   notifications_router):
        api.include_router(router)
    return api


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="brewapp", version="0.4", lifespan=lifespan)
    app.state.settings = settings
    app.state.mailer = Mailer(settings)
    app.state.limits = AuthLimits()
    errors.install(app)
    app.add_middleware(CORSMiddleware, allow_origin_regex=settings.trusted_origin.pattern, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])
    app.add_middleware(OwnSiteOnly, pattern=settings.trusted_origin)
    app.include_router(api_router())
    return app
