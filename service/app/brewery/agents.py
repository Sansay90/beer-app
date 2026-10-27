"""Агенты пользователей и их токены.

Агент шлёт токен в заголовке Authorization, подключаясь к /api/agent; в базе — только его SHA-256.
Привязка по короткому коду с сайта — этап 2 (docs/roadmap.md), а пока токен выдаёт команда сервиса:
python -m app agents new (cli.py).
"""
import hashlib
import secrets

from sqlmodel import select

from ..db import session
from ..models import Agent, User, utcnow

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


def of_user(user_id):
    with session() as s:
        return s.exec(select(Agent).where(Agent.user_id == user_id).order_by(Agent.created_at)).all()


def owner(email=None):
    """Чей агент: пользователь по почте, а без неё — единственный. LookupError с подсказкой, если не найти."""
    with session() as s:
        if email:
            u = s.exec(select(User).where(User.email == email.strip().lower())).first()
            if u is None:
                raise LookupError(f"нет пользователя с почтой {email}")
            return u.id
        users = s.exec(select(User).limit(2)).all()
    if not users:
        raise LookupError("пользователей ещё нет — зарегистрируйтесь в интерфейсе")
    if len(users) > 1:
        raise LookupError("пользователей несколько — укажите --email")
    return users[0].id
