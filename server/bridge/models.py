"""Таблицы Postgres. Схема меняется только миграциями Alembic (migrations/), не create_all.

users ─┬─ devices ─┬─ readings      температура во времени
       │           ├─ events        события пивоварни
       │           └─ brews         варки: рецепт, начало, конец, исход
       └─ recipes ── recipe_photos  рецепт — JSONB; фото пива
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import BigInteger, Column, DateTime, Index, LargeBinary
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def utcnow():
    return datetime.now(timezone.utc)


def ts(**kw):
    return Field(default_factory=utcnow, sa_type=DateTime(timezone=True), **kw)


def fk(target, *, nullable=False, ondelete="CASCADE", index=True):
    """Внешний ключ: по умолчанию удаляется вместе с владельцем; nullable — обнуляется."""
    return Field(default=None if nullable else ..., foreign_key=target, ondelete=ondelete,
                 nullable=nullable, index=index)


class User(SQLModel, table=True):
    __tablename__ = "users"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    email: Optional[str] = Field(default=None, unique=True)
    created_at: datetime = ts()


class Recipe(SQLModel, table=True):
    """Рецепт пользователя. data — рецепт целиком (schemas.Recipe), name дублирует data.name для сортировки."""
    __tablename__ = "recipes"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = fk("users.id")
    name: str
    data: dict[str, Any] = Field(default_factory=dict, sa_type=JSONB)
    created_at: datetime = ts()
    updated_at: datetime = ts()


class RecipePhoto(SQLModel, table=True):
    """Фото пива по рецепту: снимок, уже уменьшенный интерфейсом. credit — автор и лицензия, если фото чужое."""
    __tablename__ = "recipe_photos"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    recipe_id: uuid.UUID = fk("recipes.id")
    user_id: uuid.UUID = fk("users.id")
    content_type: str                                 # image/jpeg | image/png | image/webp — по сигнатуре файла
    data: bytes = Field(sa_type=LargeBinary)
    thumb: Optional[bytes] = Field(default=None, sa_type=LargeBinary)   # превью для списков, JPEG до 480 px
    credit: Optional[str] = None
    created_at: datetime = ts()


class Device(SQLModel, table=True):
    """Пивоварня пользователя. local_key — секрет модуля Tuya."""
    __tablename__ = "devices"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = fk("users.id")
    tuya_id: str = Field(unique=True)
    name: str
    local_key: str
    address: Optional[str] = None                     # None — искать широковещанием
    protocol: Optional[str] = None
    model: Optional[str] = None                       # DP 109 power_model
    max_watts: Optional[int] = None                   # ручной потолок мощности для неизвестной модели
    recipe_raw: Optional[str] = None                  # последний блок DP 128 (в status не приходит)
    heat_capacity: Optional[float] = None             # Дж/К бака с содержимым — последняя оценка (energy.py)
    equipment: Optional[dict[str, Any]] = Field(default=None, sa_type=JSONB)   # профиль оборудования (schemas.Equipment)
    active_recipe_id: Optional[uuid.UUID] = fk("recipes.id", nullable=True, ondelete="SET NULL", index=False)
    created_at: datetime = ts()


class Brew(SQLModel, table=True):
    """Варка: от запуска программы рецепта до её конца."""
    __tablename__ = "brews"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = fk("users.id")
    device_id: uuid.UUID = fk("devices.id")
    recipe_id: Optional[uuid.UUID] = fk("recipes.id", nullable=True, ondelete="SET NULL")
    name: str
    recipe: dict[str, Any] = Field(default_factory=dict, sa_type=JSONB)   # рецепт, как был загружен
    status: str = "running"                           # running | finished | stopped
    energy_wh: float = Field(default=0.0, sa_column_kwargs={"server_default": "0"})   # оценка расхода ТЭНа
    started_at: datetime = ts(index=True)
    ended_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))


class Event(SQLModel, table=True):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_device_at", "device_id", "at"),)
    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    device_id: uuid.UUID = fk("devices.id", index=False)
    brew_id: Optional[uuid.UUID] = fk("brews.id", nullable=True)
    at: datetime = ts()
    kind: str
    text: str
    data: Optional[dict[str, Any]] = Field(default=None, sa_type=JSONB)


class Reading(SQLModel, table=True):
    __tablename__ = "readings"
    __table_args__ = (Index("ix_readings_device_at", "device_id", "at"),)
    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    device_id: uuid.UUID = fk("devices.id", index=False)
    brew_id: Optional[uuid.UUID] = fk("brews.id", nullable=True)
    at: datetime = ts()
    temp: float
    target: Optional[float] = None
    step: Optional[int] = None
    status: Optional[str] = None


class PushSubscription(SQLModel, table=True):
    """Подписка браузера на Web Push: одна на устройство пользователя (endpoint уникален)."""
    __tablename__ = "push_subscriptions"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = fk("users.id")
    endpoint: str = Field(unique=True)
    p256dh: str
    auth: str
    user_agent: Optional[str] = None
    created_at: datetime = ts()
    last_seen_at: datetime = ts()
