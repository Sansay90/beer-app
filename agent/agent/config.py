"""Настройки агента — переменные окружения или agent/.env (образец — .env.example).

Пустая переменная окружения считается незаданной: тогда берётся значение из .env или по умолчанию.
"""
import os
from dataclasses import dataclass

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))      # brewapp/agent
ENV_FILE = os.path.join(AGENT_DIR, ".env")


def env(name, default=None, path=ENV_FILE):
    """Переменная окружения или строка из agent/.env."""
    if os.environ.get(name):
        return os.environ[name]
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                key, sep, value = line.strip().partition("=")
                if sep and key == name and not key.startswith("#"):
                    return value.strip() or default
    except OSError:
        pass
    return default


@dataclass(frozen=True)
class Config:
    service_url: str                  # SERVICE_URL — адрес сервиса для агентов, wss://<сайт>/api/agent
    token: str | None                 # AGENT_TOKEN — выдаёт сервис (README.md, «Запуск»)
    devices: str                      # BREWAPP_DEVICES — ключи пивоварни (devices.json)
    state: str                        # BREWAPP_STATE — память агента (data/state.json)
    brewery_ip: str | None            # BREWERY_IP, BREWERY_VERSION — адрес пивоварни и версия протокола
    brewery_version: str | None       # вместо автопоиска (из Docker широковещание не доходит)
    max_watts: int | None             # MAX_WATTS — потолок мощности, если модели нет в recipe.MODEL_MAX_WATTS

    @classmethod
    def from_env(cls):
        max_watts = env("MAX_WATTS")
        return cls(service_url=env("SERVICE_URL", "ws://127.0.0.1:8000/api/agent"), token=env("AGENT_TOKEN"),
                   devices=env("BREWAPP_DEVICES") or os.path.join(AGENT_DIR, "devices.json"),
                   state=env("BREWAPP_STATE") or os.path.join(AGENT_DIR, "data", "state.json"),
                   brewery_ip=env("BREWERY_IP"), brewery_version=env("BREWERY_VERSION"),
                   max_watts=int(max_watts) if max_watts else None)
