"""Postgres: подключение и миграции при старте."""
import os
from contextlib import contextmanager

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlmodel import Session

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))      # brewapp/service


def env(name, default=None):
    """Переменная окружения или строка из service/.env — для запуска из .venv без Docker."""
    if os.environ.get(name):
        return os.environ[name]
    try:
        with open(os.path.join(APP_DIR, ".env"), encoding="utf-8") as f:
            for line in f:
                key, sep, value = line.strip().partition("=")
                if sep and key == name and not key.startswith("#"):
                    return value.strip()
    except OSError:
        pass
    return default


DATABASE_URL = env("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("не задан DATABASE_URL (переменная окружения или service/.env)")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


@contextmanager
def session():
    with Session(engine, expire_on_commit=False) as s:
        yield s


def migrate():
    cfg = Config(os.path.join(APP_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(APP_DIR, "migrations"))
    command.upgrade(cfg, "head")
