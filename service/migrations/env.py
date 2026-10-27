"""Alembic: схема — метаданные SQLModel (app/models.py), адрес — DATABASE_URL."""
import logging.config
import os
import sys

from alembic import context
from sqlmodel import SQLModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import models  # noqa: E402,F401 — регистрирует таблицы в метаданных
from app.db import engine  # noqa: E402

if context.config.config_file_name and not logging.getLogger().handlers:
    logging.config.fileConfig(context.config.config_file_name, disable_existing_loggers=False)

target_metadata = SQLModel.metadata


def run_migrations_online():
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
