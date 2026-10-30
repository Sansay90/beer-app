"""Общие объекты сервиса для роутеров — зависимости FastAPI. Создаёт их main.py и кладёт в app.state:
настройки, почта и лимиты — при сборке приложения, остальное — на старте (lifespan)."""
from typing import Annotated

from fastapi import Depends
from starlette.requests import HTTPConnection

from .auth.throttle import AuthLimits
from .brewery.brewday import BrewDayTimers
from .brewery.devices import DeviceStore
from .brewery.hub import Hub
from .brewery.journal import Journal
from .brewery.streams import Streams
from .config import Settings
from .mail import Mailer
from .push.pusher import Pusher


def get_settings(conn: HTTPConnection) -> Settings:
    return conn.app.state.settings


def get_mailer(conn: HTTPConnection) -> Mailer:
    return conn.app.state.mailer


def get_limits(conn: HTTPConnection) -> AuthLimits:
    return conn.app.state.limits


def get_hub(conn: HTTPConnection) -> Hub:
    return conn.app.state.hub


def get_journal(conn: HTTPConnection) -> Journal:
    return conn.app.state.journal


def get_devices(conn: HTTPConnection) -> DeviceStore:
    return conn.app.state.devices


def get_streams(conn: HTTPConnection) -> Streams:
    return conn.app.state.streams


def get_pusher(conn: HTTPConnection) -> Pusher:
    return conn.app.state.pusher


def get_brewday(conn: HTTPConnection) -> BrewDayTimers:
    return conn.app.state.brewday


SettingsDep = Annotated[Settings, Depends(get_settings)]
MailerDep = Annotated[Mailer, Depends(get_mailer)]
LimitsDep = Annotated[AuthLimits, Depends(get_limits)]
HubDep = Annotated[Hub, Depends(get_hub)]
JournalDep = Annotated[Journal, Depends(get_journal)]
DevicesDep = Annotated[DeviceStore, Depends(get_devices)]
StreamsDep = Annotated[Streams, Depends(get_streams)]
PusherDep = Annotated[Pusher, Depends(get_pusher)]
BrewDayDep = Annotated[BrewDayTimers, Depends(get_brewday)]
