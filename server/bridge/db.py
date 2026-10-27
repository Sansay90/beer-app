"""Postgres: подключение, миграции при старте и первичное наполнение (владелец, пивоварня)."""
import json
import logging
import os
from contextlib import contextmanager

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlmodel import Session, select

from .models import Device, User

log = logging.getLogger("brewapp.db")

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))      # brewapp/server


def env(name, default=None):
    """Переменная окружения или строка из server/.env — для запуска из .venv без Docker."""
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
    raise RuntimeError("не задан DATABASE_URL (переменная окружения или server/.env)")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


@contextmanager
def session():
    with Session(engine, expire_on_commit=False) as s:
        yield s


def migrate():
    cfg = Config(os.path.join(APP_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(APP_DIR, "migrations"))
    command.upgrade(cfg, "head")


def seed(devices_file):
    """Владелец и пивоварня из devices.json. Возвращает (user_id, device_id)."""
    with session() as s:
        owner = s.exec(select(User).order_by(User.created_at)).first()
        if owner is None:
            owner = User(name="Владелец")
            s.add(owner)
            s.commit()
            log.info("создан пользователь-владелец")

        device = _seed_device(s, owner, devices_file)
        return owner.id, device.id


def _seed_device(s, owner, devices_file):
    keyed = []
    if os.path.exists(devices_file):
        with open(devices_file, encoding="utf-8") as f:
            keyed = [d for d in json.load(f) if d.get("key")]
    for d in keyed:
        row = s.exec(select(Device).where(Device.tuya_id == d["id"])).first()
        if row is None:
            row = Device(user_id=owner.id, tuya_id=d["id"], name=d.get("name") or "Пивоварня", local_key=d["key"],
                         address=d.get("ip") or None, protocol=d.get("version") or None)
            s.add(row)
            log.info("пивоварня %s заведена в базе", row.name)
        elif row.local_key != d["key"]:                # пивоварню переподключили к Smart Life — ключ сменился
            row.local_key = d["key"]
            log.info("ключ пивоварни %s обновлён из devices.json", row.name)
    s.commit()

    devices = s.exec(select(Device).where(Device.user_id == owner.id)).all()
    if len(devices) != 1:
        raise RuntimeError(f"у владельца {len(devices)} пивоварен — нужна ровно одна (заведите ключи в devices.json)")
    return devices[0]

