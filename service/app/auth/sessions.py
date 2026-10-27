"""Сессии входа и одноразовые ссылки из писем.

Сессия — случайный токен в httpOnly-cookie, в базе — его SHA-256; живёт SESSION_DAYS дней с последнего захода.
Ссылки из писем (подтвердить почту, задать новый пароль) — одноразовые токены auth_tokens со сроком годности.
"""
import hashlib
import secrets
from datetime import timedelta

from sqlmodel import delete, select

from ..db import session
from ..errors import Invalid
from ..models import AuthToken, User, UserSession, utcnow
from .passwords import check_password, hash_password

SESSION_DAYS = 30
SESSION_TOUCH_S = 3600                   # продлевать сессию не чаще раза в час
TOKEN_TTL = {"verify": timedelta(days=2), "reset": timedelta(hours=1)}


def _hash(token):
    return hashlib.sha256((token or "").encode()).hexdigest()


# ── сессии ────────────────────────────────────────────────────────────────────
def start(user_id, user_agent=None):
    """Новый вход → токен для cookie (в базе — только его хэш)."""
    token = secrets.token_urlsafe(32)
    with session() as s:
        s.add(UserSession(user_id=user_id, token_hash=_hash(token), user_agent=(user_agent or "")[:300] or None,
                          expires_at=utcnow() + timedelta(days=SESSION_DAYS)))
        s.commit()
    return token


def user(token):
    """Пользователь по токену из cookie или None; живая сессия продлевается."""
    if not token:
        return None
    with session() as s:
        row = s.exec(select(UserSession).where(UserSession.token_hash == _hash(token))).first()
        now = utcnow()
        if row is None or row.expires_at <= now:
            return None
        if (now - row.last_seen_at).total_seconds() > SESSION_TOUCH_S:
            row.last_seen_at, row.expires_at = now, now + timedelta(days=SESSION_DAYS)
            s.add(row)
            s.commit()
        return s.get(User, row.user_id)


def end(token):
    if token:
        with session() as s:
            s.exec(delete(UserSession).where(UserSession.token_hash == _hash(token)))
            s.commit()


# ── ссылки из писем ───────────────────────────────────────────────────────────
def issue_link_token(user_id, kind):
    """Одноразовая ссылка: kind — verify или reset. Возвращает токен для ссылки."""
    token = secrets.token_urlsafe(32)
    with session() as s:
        s.add(AuthToken(user_id=user_id, kind=kind, token_hash=_hash(token), expires_at=utcnow() + TOKEN_TTL[kind]))
        s.commit()
    return token


def _use_link_token(s, token, kind):
    row = s.exec(select(AuthToken).where(AuthToken.token_hash == _hash(token), AuthToken.kind == kind)).first()
    if row is None or row.used_at is not None or row.expires_at <= utcnow():
        raise Invalid("ссылка устарела или уже использована — запросите новую")
    row.used_at = utcnow()
    s.add(row)
    return s.get(User, row.user_id)


def verify_email(token):
    with session() as s:
        u = _use_link_token(s, token, "verify")
        u.email_verified_at = u.email_verified_at or utcnow()
        s.add(u)
        s.commit()
        return u


def reset_password(token, password):
    """Новый пароль по ссылке из письма: прежние входы закрываются, почта считается подтверждённой."""
    check_password(password)
    with session() as s:
        u = _use_link_token(s, token, "reset")
        u.password_hash = hash_password(password)
        u.email_verified_at = u.email_verified_at or utcnow()
        s.add(u)
        s.exec(delete(UserSession).where(UserSession.user_id == u.id))
        s.commit()
        return u
