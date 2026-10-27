"""Postgres: подключение и миграции. Адрес задаёт configure() — при старте сервиса (main.py) или команды (cli.py)."""
import os
from contextlib import contextmanager

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlmodel import Session

from .config import SERVICE_DIR

_engine = None
_url = None


def configure(url):
    """Подключиться к базе по адресу url (DATABASE_URL); с новым адресом прежнее подключение закрывается."""
    global _engine, _url
    if url != _url:
        if _engine is not None:
            _engine.dispose()
        _engine, _url = create_engine(url, pool_pre_ping=True), url
    return _engine


def engine():
    if _engine is None:
        raise RuntimeError("база не подключена: сначала db.configure(DATABASE_URL)")
    return _engine


@contextmanager
def session():
    with Session(engine(), expire_on_commit=False) as s:
        yield s


def migrate():
    """Схема — до последней миграции (migrations/)."""
    cfg = Config(os.path.join(SERVICE_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(SERVICE_DIR, "migrations"))
    cfg.attributes["engine"] = engine()
    command.upgrade(cfg, "head")
