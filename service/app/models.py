"""Таблицы Postgres. Схема меняется только миграциями Alembic (migrations/), не create_all.

users ─┬─ sessions                  входы: cookie-токен — хэшем
       ├─ auth_tokens               одноразовые ссылки из писем: подтверждение почты, сброс пароля
       ├─ agents                    агенты у пивоварен; devices.agent_id — через какой на связи
       ├─ equipment ── devices      оборудование пивовара: без подключения или пивоварня; одно — основное
       ├─ devices ─┬─ readings      температура во времени
       │           ├─ events        события пивоварни
       │           └─ brews         варки с пивоварни (и без неё — записанные вручную)
       ├─ brews ── brew_entries     журнал варки: замеры, вехи и заметки пивовара
       ├─ recipes ─┬─ recipe_photos      рецепт — JSONB; фото пива
       │           ├─ recipe_votes       лайки и дизлайки рецепта
       │           └─ comments ── comment_votes   обсуждение: комментарии и ответы, голоса за них
       ├─ favorites ── recipes      избранное: чужие и свои рецепты, сохранённые без копии
       └─ notifications ─┬─ comments   уведомления на сайте: комментарий к моему рецепту, ответ мне,
                         └─ brews      напоминание о брожении
"""
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import BigInteger, Column, DateTime, Index, LargeBinary
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def utcnow():
    return datetime.now(UTC)


def unix(dt):
    return dt.timestamp() if dt else None


def from_unix(t):
    return datetime.fromtimestamp(t, UTC)


def parse_id(value):
    """id из URL или сообщения → UUID; мусор — None (такого нет), а не ошибка 500."""
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def ts(**kw):
    return Field(default_factory=utcnow, sa_type=DateTime(timezone=True), **kw)


def fk(target, *, nullable=False, ondelete="CASCADE", index=True):
    """Внешний ключ: по умолчанию удаляется вместе с владельцем; nullable — обнуляется."""
    return Field(default=None if nullable else ..., foreign_key=target, ondelete=ondelete,
                 nullable=nullable, index=index)


class User(SQLModel, table=True):
    """Пользователь. Без почты — владелец данных, заведённых до входа: его забирает первая регистрация (auth.py).
    name — ник, его видят все (нет — «Неизвестный пивовар»); почта — только сам пользователь и администратор
    (auth/profile.py)."""
    __tablename__ = "users"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str | None = None
    name_key: str | None = Field(default=None, unique=True)        # ник для сравнения: строчными, «ё» как «е»
    avatar: bytes | None = Field(default=None, sa_type=LargeBinary)  # JPEG 256×256
    avatar_version: int = Field(default=0, sa_column_kwargs={"server_default": "0"})  # в адресе — для кеша
    email: str | None = Field(default=None, unique=True)           # строчными буквами
    password_hash: str | None = None
    email_verified_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    role: str = Field(default="user", sa_column_kwargs={"server_default": "user"})    # user | admin (access.py)
    push_comments: bool = Field(default=True, sa_column_kwargs={"server_default": "true"})  # push о комментариях
    push_brews: bool = Field(default=True, sa_column_kwargs={"server_default": "true"})     # push о брожении
    created_at: datetime = ts()


class UserSession(SQLModel, table=True):
    """Вход пользователя: случайный токен в cookie, здесь — его SHA-256. Продлевается, пока им пользуются."""
    __tablename__ = "sessions"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = fk("users.id")
    token_hash: str = Field(unique=True)
    user_agent: str | None = None
    created_at: datetime = ts()
    last_seen_at: datetime = ts()
    expires_at: datetime = Field(sa_type=DateTime(timezone=True))


class AuthToken(SQLModel, table=True):
    """Одноразовая ссылка из письма: kind — verify (подтвердить почту) или reset (сбросить пароль)."""
    __tablename__ = "auth_tokens"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = fk("users.id")
    kind: str
    token_hash: str = Field(unique=True)
    created_at: datetime = ts()
    expires_at: datetime = Field(sa_type=DateTime(timezone=True))
    used_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


class Recipe(SQLModel, table=True):
    """Рецепт пользователя. data — рецепт целиком (schemas.Recipe), name дублирует data.name для сортировки.
    visibility: private — видит только автор, public — все, и гости тоже (access.py)."""
    __tablename__ = "recipes"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = fk("users.id")
    name: str
    data: dict[str, Any] = Field(default_factory=dict, sa_type=JSONB)
    visibility: str = Field(default="private", index=True, sa_column_kwargs={"server_default": "private"})
    published_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = ts()
    updated_at: datetime = ts()


class Favorite(SQLModel, table=True):
    """Рецепт в избранном у пользователя — ссылка, а не копия: автор правит рецепт, в избранном — свежая версия.
    Рецепт сняли с публикации — из избранного он пропадает вместе с доступом (access.py), запись остаётся."""
    __tablename__ = "favorites"
    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", primary_key=True)
    recipe_id: uuid.UUID = Field(foreign_key="recipes.id", ondelete="CASCADE", primary_key=True, index=True)
    created_at: datetime = ts()


class RecipeVote(SQLModel, table=True):
    """Голос за рецепт: value 1 — нравится, −1 — не нравится; один на человека, за свой рецепт — нельзя."""
    __tablename__ = "recipe_votes"
    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", primary_key=True)
    recipe_id: uuid.UUID = Field(foreign_key="recipes.id", ondelete="CASCADE", primary_key=True, index=True)
    value: int
    created_at: datetime = ts()


class Comment(SQLModel, table=True):
    """Комментарий к рецепту. parent_id — ответ на комментарий (один уровень: ответ на ответ — в ту же ветку).
    Удалённый с ответами остаётся пустым (deleted_at) — ветка не рассыпается; без ответов — удаляется."""
    __tablename__ = "comments"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    recipe_id: uuid.UUID = fk("recipes.id")
    user_id: uuid.UUID = fk("users.id")
    parent_id: uuid.UUID | None = fk("comments.id", nullable=True, ondelete="CASCADE")
    text: str
    created_at: datetime = ts()
    edited_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


class CommentVote(SQLModel, table=True):
    """Голос за комментарий — как за рецепт."""
    __tablename__ = "comment_votes"
    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", primary_key=True)
    comment_id: uuid.UUID = Field(foreign_key="comments.id", ondelete="CASCADE", primary_key=True, index=True)
    value: int
    created_at: datetime = ts()


class Notification(SQLModel, table=True):
    """Уведомление на сайте (notifications/feed.py): kind — comment (к моему рецепту), reply (ответ мне) —
    с actor, recipe и comment; brew — напоминание о брожении (brewery/reminders.py) — с brew и data
    (заголовок, текст). Уходит вместе с комментарием, рецептом, варкой или тем, кто написал."""
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_created", "user_id", "created_at"),)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = fk("users.id", index=False)                # кому; индекс — вместе со временем
    kind: str
    actor_id: uuid.UUID | None = fk("users.id", nullable=True, ondelete="CASCADE")   # кто написал
    recipe_id: uuid.UUID | None = fk("recipes.id", nullable=True, ondelete="CASCADE")
    comment_id: uuid.UUID | None = fk("comments.id", nullable=True, ondelete="CASCADE")
    brew_id: uuid.UUID | None = fk("brews.id", nullable=True, ondelete="CASCADE")
    data: dict[str, Any] | None = Field(default=None, sa_type=JSONB)  # напоминание: title, text
    created_at: datetime = ts()
    read_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


class RecipePhoto(SQLModel, table=True):
    """Фото пива по рецепту: снимок, уже уменьшенный интерфейсом. credit — автор и лицензия, если фото чужое."""
    __tablename__ = "recipe_photos"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    recipe_id: uuid.UUID = fk("recipes.id")
    user_id: uuid.UUID = fk("users.id")
    content_type: str                                 # image/jpeg | image/png | image/webp — по сигнатуре файла
    data: bytes = Field(sa_type=LargeBinary)
    thumb: bytes | None = Field(default=None, sa_type=LargeBinary)   # превью для списков, JPEG до 480 px
    credit: str | None = None
    created_at: datetime = ts()


class Agent(SQLModel, table=True):
    """Агент пользователя — программа рядом с пивоварней (agent/). Токен хранится только хэшем (agents.py)."""
    __tablename__ = "agents"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = fk("users.id")
    name: str
    token_hash: str = Field(unique=True)
    created_at: datetime = ts()
    last_seen_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


class Device(SQLModel, table=True):
    """Пивоварня пользователя. Ключи, адрес и память о программе — у агента; здесь — то, что нужно без него."""
    __tablename__ = "devices"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = fk("users.id")
    agent_id: uuid.UUID | None = fk("agents.id", nullable=True, ondelete="SET NULL")
    tuya_id: str = Field(unique=True)
    name: str
    model: str | None = None                       # DP 109 power_model — сообщает агент
    limits: dict[str, Any] | None = Field(default=None, sa_type=JSONB)      # schemas.Limits — сообщает агент
    created_at: datetime = ts()


class Equipment(SQLModel, table=True):
    """Оборудование пивовара (brewery/equipment.py): manual — без подключения (кастрюля, котёл, любая система),
    easybrew — пивоварня, которой управляют с сайта (device_id — когда агент её завёл). Основное (main) —
    объём, эффективность и испарение для новых рецептов и расчётов; у пользователя одно основное."""
    __tablename__ = "equipment"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = fk("users.id")
    name: str
    kind: str = "manual"
    device_id: uuid.UUID | None = fk("devices.id", nullable=True, ondelete="SET NULL")
    volume: float | None = None                       # л после кипячения — партия новых рецептов
    efficiency: float = 75.0                          # % — для новых рецептов
    evaporation: float = 3.0                          # л/ч кипячения без крышки — для расчёта воды
    kettle: float | None = None                       # л до краёв — предупредить, если варка не влезает
    main: bool = False
    created_at: datetime = ts()


class Brew(SQLModel, table=True):
    """Варка — партия пива (brewery/logbook.py). С пивоварни (source = device) — от запуска программы рецепта
    до её конца, с температурой и событиями; записанная вручную (manual) — без пивоварни. Убрали пивоварню —
    варки остаются. Журнал пивовара — brew_entries."""
    __tablename__ = "brews"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = fk("users.id")
    device_id: uuid.UUID | None = fk("devices.id", nullable=True, ondelete="SET NULL")
    source: str = Field(default="device", sa_column_kwargs={"server_default": "device"})   # device | manual
    recipe_id: uuid.UUID | None = fk("recipes.id", nullable=True, ondelete="SET NULL")
    equipment_id: uuid.UUID | None = fk("equipment.id", nullable=True, ondelete="SET NULL")   # на чём варили
    name: str
    recipe: dict[str, Any] = Field(default_factory=dict, sa_type=JSONB)   # рецепт, как был загружен в пивоварню
    snapshot: dict[str, Any] | None = Field(default=None, sa_type=JSONB)  # рецепт партии: под оборудование на момент
    plan: dict[str, Any] | None = Field(default=None, sa_type=JSONB)      # задумано по рецепту партии: OG, FG, брожение
    reminded: list[str] = Field(default_factory=list, sa_type=JSONB,     # о чём из плана брожения уже напомнили
                                sa_column_kwargs={"server_default": "[]"})
    status: str = "running"                           # running | finished | stopped (программа; без пивоварни — день)
    energy_wh: float = Field(default=0.0, sa_column_kwargs={"server_default": "0"})   # оценка расхода ТЭНа
    started_at: datetime = ts(index=True)
    ended_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    # варочный день позади (дрожжи, «закончить», брошен — brewday.py): дальше брожение; None — день идёт
    day_ended_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


class BrewEntry(SQLModel, table=True):
    """Запись журнала варки (brewery/logbook.py): замер (value — SG, pH, л или °C, по kind), веха или заметка."""
    __tablename__ = "brew_entries"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    brew_id: uuid.UUID = fk("brews.id")
    at: datetime = ts()                               # когда это было — пивовар может указать задним числом
    kind: str
    value: float | None = None
    text: str | None = None
    created_at: datetime = ts()


class Event(SQLModel, table=True):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_device_at", "device_id", "at"),)
    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    device_id: uuid.UUID = fk("devices.id", index=False)
    brew_id: uuid.UUID | None = fk("brews.id", nullable=True)
    at: datetime = ts()
    kind: str
    text: str
    data: dict[str, Any] | None = Field(default=None, sa_type=JSONB)


class Reading(SQLModel, table=True):
    __tablename__ = "readings"
    __table_args__ = (Index("ix_readings_device_at", "device_id", "at"),)
    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    device_id: uuid.UUID = fk("devices.id", index=False)
    brew_id: uuid.UUID | None = fk("brews.id", nullable=True)
    at: datetime = ts()
    temp: float
    target: float | None = None
    step: int | None = None
    status: str | None = None


class PushSubscription(SQLModel, table=True):
    """Подписка браузера на Web Push: одна на устройство пользователя (endpoint уникален)."""
    __tablename__ = "push_subscriptions"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = fk("users.id")
    endpoint: str = Field(unique=True)
    p256dh: str
    auth: str
    user_agent: str | None = None
    created_at: datetime = ts()
    last_seen_at: datetime = ts()
