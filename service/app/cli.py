"""Команды сервиса — из папки brewapp/service (.venv) или в контейнере:

    python -m app [serve] [--host H] [--port P] [--lan]   запустить сервис (--lan — доступ из домашней сети)
    python -m app agents new [название] [--email почта]    новый агент — токен печатается один раз
    python -m app agents list [--email почта]              агенты пользователя и когда были на связи
    python -m app vapid                                    новый ключ Web Push — строка для .env
    python -m app openapi [путь]                           OpenAPI-схема для типов интерфейса (../web/openapi.json)

--email — чей агент; без неё — единственного пользователя.
"""
import argparse
import json
import logging
import os
import sys

from .config import SERVICE_DIR, Settings


def serve(args, settings):
    import uvicorn

    from .main import create_app

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    uvicorn.run(create_app(settings), host="0.0.0.0" if args.lan else args.host or settings.service_host,
                port=args.port or settings.service_port, log_level="warning",
                proxy_headers=True, forwarded_allow_ips=settings.forwarded_allow_ips)


def agents(args, settings):
    from . import db
    from .brewery import agents as tokens

    if not settings.database_url:
        raise SystemExit("не задан DATABASE_URL (переменная окружения или service/.env)")
    db.configure(settings.database_url)
    db.migrate()
    try:
        owner = tokens.owner(args.email)
    except LookupError as e:
        raise SystemExit(str(e)) from None
    if args.action == "new":
        print(tokens.create(owner, args.name))
        return
    for a in tokens.of_user(owner):
        seen = a.last_seen_at.astimezone().strftime("%d.%m.%Y %H:%M") if a.last_seen_at else "ещё не подключался"
        print(f"{a.name} · {seen}")


def vapid(args, settings):
    from .push.pusher import new_private_key

    print(f"VAPID_PRIVATE_KEY={new_private_key()}")


def openapi(args, settings):
    from .main import create_app

    path = args.path or os.path.join(os.path.dirname(SERVICE_DIR), "web", "openapi.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(create_app(settings).openapi(), f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(path)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0].startswith("-"):
        argv = ["serve", *argv]
    p = argparse.ArgumentParser(prog="python -m app", description="brewapp — сервис рецептов и пивоварен")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("serve", help="запустить сервис")
    s.add_argument("--host", help="адрес, где слушать (SERVICE_HOST, по умолчанию 127.0.0.1)")
    s.add_argument("--port", type=int, help="порт (SERVICE_PORT, по умолчанию 8000)")
    s.add_argument("--lan", action="store_true", help="слушать домашнюю сеть — то же, что --host 0.0.0.0")
    s.set_defaults(run=serve)

    a = sub.add_parser("agents", help="агенты у пивоварен и их токены")
    a.set_defaults(run=agents)
    actions = a.add_subparsers(dest="action", required=True)
    new = actions.add_parser("new", help="новый агент — напечатать токен")
    new.add_argument("name", nargs="?", default="Агент")
    new.add_argument("--email", help="чей агент (без неё — единственного пользователя)")
    ls = actions.add_parser("list", help="агенты пользователя")
    ls.add_argument("--email")

    sub.add_parser("vapid", help="новый ключ Web Push").set_defaults(run=vapid)
    o = sub.add_parser("openapi", help="выгрузить OpenAPI-схему")
    o.add_argument("path", nargs="?")
    o.set_defaults(run=openapi)

    args = p.parse_args(argv)
    args.run(args, Settings())
