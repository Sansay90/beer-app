"""Вход по почте и паролю: регистрация, сессии, подтверждение почты и сброс пароля по ссылке из письма.

Пароль — scrypt (стандартная библиотека), в базе только хэш. Сессия — случайный токен в httpOnly-cookie, в базе —
его SHA-256; живёт SESSION_DAYS дней с последнего захода. Ссылки из писем — одноразовые токены (auth_tokens)
со сроком годности.

Кто администратор. Сервис в интернете: ADMIN_EMAILS — почты администраторов, остальные регистрируются
пользователями. Установка у себя (ADMIN_EMAILS пусто): администратор — первый зарегистрировавшийся.
Данные, заведённые до входа, принадлежат пользователю без почты: его забирает регистрация администратора
(без ADMIN_EMAILS — первая), если других пользователей нет, — так владелец не теряет рецепты и пивоварню.
"""
import base64
import hashlib
import hmac
import re
import secrets
import threading
import time
from collections import deque
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlmodel import delete, select

from .access import ADMIN, ROLES, USER
from .db import env, session
from .models import AuthToken, Recipe, User, UserSession, utcnow
from .store import as_uuid, unix

SESSION_DAYS = 30
SESSION_TOUCH_S = 3600                   # продлевать сессию не чаще раза в час
TOKEN_TTL = {"verify": timedelta(days=2), "reset": timedelta(hours=1)}
PASSWORD_MIN, PASSWORD_MAX = 8, 128
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1}  # ~16 МБ и десятки миллисекунд на проверку


def _b64(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _hash(token):
    return hashlib.sha256((token or "").encode()).hexdigest()


def normalize_email(email):
    """Почта строчными буквами; ValueError — на адрес не похоже."""
    e = (email or "").strip().lower()
    if len(e) > 254 or not EMAIL_RE.fullmatch(e):
        raise ValueError("похоже, в адресе почты ошибка")
    return e


def check_password(password):
    if not PASSWORD_MIN <= len(password or "") <= PASSWORD_MAX:
        raise ValueError(f"пароль — от {PASSWORD_MIN} до {PASSWORD_MAX} символов")


def hash_password(password):
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **SCRYPT)
    return f"scrypt${SCRYPT['n']}${SCRYPT['r']}${SCRYPT['p']}${_b64(salt)}${_b64(dk)}"


def verify_password(password, stored):
    try:
        algo, n, r, p, salt, dk = stored.split("$")
        expected = _unb64(dk)
        got = hashlib.scrypt(password.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except (ValueError, AttributeError):
        return False
    return algo == "scrypt" and hmac.compare_digest(got, expected)


_dummy = []


def _dummy_hash():
    """Хэш-пустышка: проверка пароля для несуществующей почты занимает столько же времени."""
    if not _dummy:
        _dummy.append(hash_password(secrets.token_hex(8)))
    return _dummy[0]


# ── пользователи ──────────────────────────────────────────────────────────────
def admin_emails():
    """Почты администраторов из ADMIN_EMAILS (через запятую); пусто — установка у себя."""
    return {e.strip().lower() for e in (env("ADMIN_EMAILS") or "").split(",") if e.strip()}


def register(email, password):
    """Новый пользователь (или владелец данных до входа, если он единственный). ValueError — неверные данные
    или почта уже занята."""
    email = normalize_email(email)
    check_password(password)
    taken = ValueError("эта почта уже зарегистрирована — войдите или восстановите пароль")
    admins = admin_emails()
    with session() as s:
        if s.exec(select(User.id).where(User.email == email)).first():
            raise taken
        users = s.exec(select(User).limit(2)).all()
        legacy = users[0] if len(users) == 1 and users[0].email is None else None
        if admins and email not in admins:
            legacy = None                              # данные до входа забирает только администратор
        user = legacy or User(name="")
        user.name, user.email, user.password_hash = email.split("@")[0], email, hash_password(password)
        if admins:
            user.role = ADMIN if email in admins else USER
        elif legacy is not None or not users:            # установка у себя: владелец — администратор
            user.role = ADMIN
        s.add(user)
        try:
            s.commit()
        except IntegrityError:
            raise taken
        return user


def authenticate(email, password):
    """Пользователь по почте и паролю или None. По времени ответа не понять, есть ли такая почта."""
    try:
        email = normalize_email(email)
    except ValueError:
        email = None
    with session() as s:
        user = s.exec(select(User).where(User.email == email)).first() if email else None
    stored = user.password_hash if user is not None and user.password_hash else _dummy_hash()
    ok = verify_password(password or "", stored)
    return user if user is not None and user.password_hash and ok else None


def user_by_email(email):
    try:
        email = normalize_email(email)
    except ValueError:
        return None
    with session() as s:
        return s.exec(select(User).where(User.email == email)).first()


def me(user):
    return {"id": str(user.id), "email": user.email, "name": user.name,
            "emailVerified": user.email_verified_at is not None, "role": user.role}


def list_users():
    """Зарегистрированные пользователи для администратора, старые первыми."""
    with session() as s:
        counts = dict(s.exec(select(Recipe.user_id, func.count()).group_by(Recipe.user_id)).all())
        users = s.exec(select(User).where(User.email.is_not(None)).order_by(User.created_at)).all()
    return [{"id": str(u.id), "email": u.email, "name": u.name, "role": u.role,
             "emailVerified": u.email_verified_at is not None, "createdAt": unix(u.created_at),
             "recipes": counts.get(u.id, 0)} for u in users]


def set_role(user_id, role):
    """KeyError — нет такого пользователя; ValueError — неизвестная роль или это последний администратор."""
    if role not in ROLES:
        raise ValueError(f"роль — {' или '.join(ROLES)}")
    with session() as s:
        user = s.get(User, as_uuid(user_id))
        if user is None or user.email is None:
            raise KeyError(user_id)
        admins = s.exec(select(func.count()).select_from(User).where(User.role == ADMIN)).one()
        if user.role == ADMIN and role != ADMIN and admins <= 1:
            raise ValueError("это последний администратор — сначала назначьте другого")
        user.role = role
        s.add(user)
        s.commit()
        return user


# ── сессии ────────────────────────────────────────────────────────────────────
def start_session(user_id, user_agent=None):
    """Новый вход → токен для cookie (в базе — только его хэш)."""
    token = secrets.token_urlsafe(32)
    with session() as s:
        s.add(UserSession(user_id=user_id, token_hash=_hash(token), user_agent=(user_agent or "")[:300] or None,
                          expires_at=utcnow() + timedelta(days=SESSION_DAYS)))
        s.commit()
    return token


def session_user(token):
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


def end_session(token):
    if token:
        with session() as s:
            s.exec(delete(UserSession).where(UserSession.token_hash == _hash(token)))
            s.commit()


# ── ссылки из писем ───────────────────────────────────────────────────────────
def issue_token(user_id, kind):
    """Одноразовая ссылка: kind — verify или reset. Возвращает токен для ссылки."""
    token = secrets.token_urlsafe(32)
    with session() as s:
        s.add(AuthToken(user_id=user_id, kind=kind, token_hash=_hash(token), expires_at=utcnow() + TOKEN_TTL[kind]))
        s.commit()
    return token


def _use_token(s, token, kind):
    row = s.exec(select(AuthToken).where(AuthToken.token_hash == _hash(token), AuthToken.kind == kind)).first()
    if row is None or row.used_at is not None or row.expires_at <= utcnow():
        raise ValueError("ссылка устарела или уже использована — запросите новую")
    row.used_at = utcnow()
    s.add(row)
    return s.get(User, row.user_id)


def verify_email(token):
    with session() as s:
        user = _use_token(s, token, "verify")
        user.email_verified_at = user.email_verified_at or utcnow()
        s.add(user)
        s.commit()
        return user


def reset_password(token, password):
    """Новый пароль по ссылке из письма: прежние входы закрываются, почта считается подтверждённой."""
    check_password(password)
    with session() as s:
        user = _use_token(s, token, "reset")
        user.password_hash = hash_password(password)
        user.email_verified_at = user.email_verified_at or utcnow()
        s.add(user)
        s.exec(delete(UserSession).where(UserSession.user_id == user.id))
        s.commit()
        return user


class Throttle:
    """Не больше limit попыток за window секунд на ключ (адрес или почта): от подбора пароля и спама письмами."""

    def __init__(self, limit, window):
        self.limit, self.window = limit, window
        self._hits = {}
        self._lock = threading.Lock()

    def _wait(self, key, now):
        q = self._hits.get(key)
        while q and now - q[0] > self.window:
            q.popleft()
        if q is not None and not q:
            del self._hits[key]
            return 0.0
        return self.window - (now - q[0]) if q is not None and len(q) >= self.limit else 0.0

    def wait(self, key):
        """Сколько секунд ждать, если лимит исчерпан, иначе 0. Попытку не засчитывает."""
        with self._lock:
            return self._wait(key, time.monotonic())

    def add(self, key):
        with self._lock:
            self._hits.setdefault(key, deque()).append(time.monotonic())

    def hit(self, key):
        """Проверить и засчитать: лимит исчерпан — сколько ждать (попытка не засчитана), иначе 0."""
        now = time.monotonic()
        with self._lock:
            wait = self._wait(key, now)
            if not wait:
                self._hits.setdefault(key, deque()).append(now)
            return wait
