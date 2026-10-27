"""Alembic: схема — метаданные SQLModel (app/models.py), адрес — DATABASE_URL (app/config.py).

Сервис применяет миграции сам при старте (db.migrate) и передаёт своё подключение; из командной строки
(alembic upgrade head / revision --autogenerate) адрес берётся из настроек.
"""
import logging.config
import os
import sys

from alembic import context
from sqlmodel import SQLModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import db, models  # noqa: F401 — models регистрирует таблицы в метаданных
from app.config import Settings

if context.config.config_file_name and not logging.getLogger().handlers:
    logging.config.fileConfig(context.config.config_file_name, disable_existing_loggers=False)

target_metadata = SQLModel.metadata


def run_migrations_online():
    engine = context.config.attributes.get("engine") or db.configure(Settings().database_url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
