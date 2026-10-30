"""Тесты сервиса. Юнит-тесты базы не требуют; сквозные (фикстура service) идут на настоящем Postgres:
TEST_DATABASE_URL, а без неё — база brewapp_test рядом с базой из DATABASE_URL (service/.env), создаётся сама.
Схема — миграциями, перед каждым тестом таблицы очищаются."""
import json
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlmodel import SQLModel

from app import db, models  # noqa: F401 — models регистрирует таблицы
from app.brewery import agents as agent_tokens
from app.config import Settings

from .support import Agent, Service


def database_url_for_tests():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        base = Settings().database_url
        if not base:
            return None
        url = make_url(base).set(database="brewapp_test").render_as_string(hide_password=False)
    if not make_url(url).database.endswith("_test"):
        raise RuntimeError(f"тестовая база должна называться *_test, а не {make_url(url).database}: её очищают")
    return url


def ensure_database(url):
    u = make_url(url)
    admin = create_engine(u.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        if not c.execute(text("select 1 from pg_database where datname = :n"), {"n": u.database}).scalar():
            c.execute(text(f'create database "{u.database}"'))
    admin.dispose()


@pytest.fixture(scope="session")
def database():
    url = database_url_for_tests()
    if url is None:
        pytest.skip("нет базы для тестов: задайте TEST_DATABASE_URL или DATABASE_URL в service/.env")
    ensure_database(url)
    db.configure(url)
    with db.engine().begin() as c:                       # с чистого листа: схема — только миграциями
        c.execute(text("drop schema public cascade; create schema public"))
    db.migrate()
    return url


@pytest.fixture
def clean_db(database):
    tables = ", ".join(f'"{t.name}"' for t in SQLModel.metadata.sorted_tables)
    with db.engine().begin() as c:
        c.execute(text(f"truncate {tables} restart identity cascade"))
    return database


@pytest.fixture
def settings(clean_db):
    return Settings(database_url=clean_db, app_url="", admin_emails="", vapid_private_key="", smtp_host="")


@pytest.fixture
def service_factory():
    """Сервис с особыми настройками: service_factory(settings) → запущенный Service; остановится сам."""
    started = []

    def start(settings):
        svc = Service(settings).start()
        started.append(svc)
        return svc

    yield start
    for svc in started:
        svc.stop()


@pytest.fixture
def service(settings, service_factory):
    return service_factory(settings)


@pytest.fixture
def agents(service, tmp_path):
    """Запускать агентов: agents(token) → Agent; все останавливаются в конце теста."""
    started = []

    def start(token, memory="state.json", brewery=None, url=None):
        a = Agent(url or f"ws://127.0.0.1:{service.port}/api/agent", token, str(tmp_path / memory), brewery).start()
        started.append(a)
        return a

    yield start
    for a in started:
        a.stop()


@pytest.fixture
def recipe():
    """Короткая программа: три паузы по 2 мин и кипячение 3 мин с закладками за 2 и за 1 мин."""
    return json.loads((Path(__file__).parent / "data" / "recipe_short.json").read_text(encoding="utf-8"))


@pytest.fixture
def brewer(service):
    """Вошедший пользователь — первый, значит администратор. me — его данные."""
    c = service.client()
    status, c.me = c.signup("brewer@test.local")
    assert status == 200, c.me
    return c


def new_agent_token(client, name="Тест"):
    return agent_tokens.create(uuid.UUID(client.me["id"]), name)


@pytest.fixture
def pushes(service):
    """Push не уходит наружу, а копится здесь: (кому, уведомление)."""
    sent = []
    service.state.pusher.notify = lambda user_id, note: sent.append((str(user_id), note))
    return sent
