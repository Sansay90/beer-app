"""Агенты пользователей и их токены.

Агент шлёт токен в заголовке Authorization, подключаясь к /api/agent; в базе — только его SHA-256.
Привязка по короткому коду с сайта — этап 2 (ARCHITECTURE.md), а пока токен выдаёт команда:

    .venv\\Scripts\\python -m app.agents new [название] [--email почта]   новый агент — токен печатается один раз
    .venv\\Scripts\\python -m app.agents list [--email почта]             агенты и когда были на связи

--email — чей агент; без неё — единственного пользователя.
"""
import argparse
import hashlib
import secrets

from sqlmodel import select

from . import db
from .db import session
from .models import Agent, User, utcnow

TOKEN_BYTES = 32


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def create(user_id, name):
    """Новый агент пользователя → его токен (больше нигде не хранится)."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    with session() as s:
        s.add(Agent(user_id=user_id, name=name, token_hash=token_hash(token)))
        s.commit()
    return token


def by_token(token):
    """Агент по токену или None."""
    if not token:
        return None
    with session() as s:
        return s.exec(select(Agent).where(Agent.token_hash == token_hash(token))).first()


def touch(agent_id):
    with session() as s:
        a = s.get(Agent, agent_id)
        if a is not None:
            a.last_seen_at = utcnow()
            s.add(a)
            s.commit()


def user_id(email):
    """Пользователь по почте, а без неё — единственный. SystemExit с подсказкой, если не найти."""
    with session() as s:
        if email:
            u = s.exec(select(User).where(User.email == email.strip().lower())).first()
            if u is None:
                raise SystemExit(f"нет пользователя с почтой {email}")
            return u.id
        users = s.exec(select(User).limit(2)).all()
    if not users:
        raise SystemExit("пользователей ещё нет — зарегистрируйтесь в интерфейсе")
    if len(users) > 1:
        raise SystemExit("пользователей несколько — укажите --email")
    return users[0].id


def main():
    p = argparse.ArgumentParser(description="агенты brewapp")
    sub = p.add_subparsers(dest="cmd", required=True)
    new = sub.add_parser("new", help="новый агент — напечатать токен")
    new.add_argument("name", nargs="?", default="Агент")
    new.add_argument("--email", help="чей агент (без неё — единственного пользователя)")
    ls = sub.add_parser("list", help="агенты пользователя")
    ls.add_argument("--email")
    args = p.parse_args()
    db.migrate()
    owner = user_id(args.email)
    if args.cmd == "new":
        print(create(owner, args.name))
        return
    with session() as s:
        for a in s.exec(select(Agent).where(Agent.user_id == owner).order_by(Agent.created_at)).all():
            seen = a.last_seen_at.astimezone().strftime("%d.%m.%Y %H:%M") if a.last_seen_at else "ещё не подключался"
            print(f"{a.name} · {seen}")


if __name__ == "__main__":
    main()
