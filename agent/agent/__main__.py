"""Агент brewapp — рядом с пивоварней: связь с ней по домашней сети и с сервисом по WebSocket.

Запуск из папки brewapp/agent:
    .venv\\Scripts\\python -m agent

Настройки — переменные окружения или agent/.env (образец — .env.example):
SERVICE_URL — адрес сервиса для агентов, AGENT_TOKEN — токен агента (выдаёт сервис, README.md);
BREWERY_IP, BREWERY_VERSION — адрес пивоварни и версия протокола вместо автопоиска;
MAX_WATTS — потолок мощности, если модели пивоварни нет в списке (recipe.MODEL_MAX_WATTS);
BREWAPP_DEVICES — ключи пивоварни (devices.json), BREWAPP_STATE — память агента (data/state.json).
"""
import asyncio
import json
import logging
import os

from .brew import Controller
from .device import Brewery
from .link import Link
from .state import Memory

VERSION = "0.1"
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))      # brewapp/agent


def env(name, default=None):
    """Переменная окружения или строка из agent/.env."""
    if os.environ.get(name):
        return os.environ[name]
    try:
        with open(os.path.join(APP_DIR, ".env"), encoding="utf-8") as f:
            for line in f:
                key, sep, value = line.strip().partition("=")
                if sep and key == name and not key.startswith("#"):
                    return value.strip() or default
    except OSError:
        pass
    return default


def load_device(path):
    """Первая пивоварня с ключом из devices.json."""
    try:
        with open(path, encoding="utf-8") as f:
            keyed = [d for d in json.load(f) if d.get("key")]
    except FileNotFoundError:
        raise SystemExit(f"нет {path} — нужны ключи пивоварни (README.md, «Ключи пивоварни»)")
    if not keyed:
        raise SystemExit(f"в {path} нет пивоварни с ключом")
    return keyed[0]


async def serve(controller, brewery, url, token, device):
    link = Link(url, token, controller, device, VERSION)
    brewery.start()
    try:
        await link.run()
    finally:
        await asyncio.to_thread(brewery.stop)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    token = env("AGENT_TOKEN")
    if not token:
        raise SystemExit("не задан AGENT_TOKEN — токен агента выдаёт сервис (README.md, «Запуск»)")
    d = load_device(env("BREWAPP_DEVICES") or os.path.join(APP_DIR, "devices.json"))
    memory = Memory(env("BREWAPP_STATE") or os.path.join(APP_DIR, "data", "state.json"))
    # BREWERY_IP/VERSION перекрывают devices.json — в Docker автопоиск по широковещанию не работает
    brewery = Brewery(d["id"], d["key"], address=env("BREWERY_IP") or d.get("ip") or None,
                      version=env("BREWERY_VERSION") or d.get("version") or None)
    max_watts = env("MAX_WATTS")
    controller = Controller(brewery, memory, int(max_watts) if max_watts else None)
    device = {"tuyaId": d["id"], "name": d.get("name") or "Пивоварня"}
    try:
        asyncio.run(serve(controller, brewery, env("SERVICE_URL", "ws://127.0.0.1:8000/api/agent"), token, device))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
