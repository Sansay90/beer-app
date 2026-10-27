"""Пользователи: регистрация, вход по паролю, роли.

Кто администратор. Сервис в интернете: ADMIN_EMAILS — почты администраторов, остальные регистрируются
пользователями. Установка у себя (ADMIN_EMAILS пусто): администратор — первый зарегистрировавшийся.
Данные, заведённые до входа, принадлежат пользователю без почты: его забирает регистрация администратора
(без ADMIN_EMAILS — первая), если других пользователей нет, — так владелец не теряет рецепты и пивоварню.
"""
import re

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from ..access import ADMIN, ROLES, USER
from ..db import session
from ..errors import Conflict, Invalid, NotFound
from ..models import Recipe, User, parse_id, unix
from .passwords import check_password, dummy_hash, hash_password, verify_password

EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def normalize_email(email):
    """Почта строчными буквами; Invalid — на адрес не похоже."""
    e = (email or "").strip().lower()
    if len(e) > 254 or not EMAIL_RE.fullmatch(e):
        raise Invalid("похоже, в адресе почты ошибка")
    return e


def register(email, password, admins=frozenset()):
    """Новый пользователь (или владелец данных до входа, если он единственный). admins — почты администраторов
    (ADMIN_EMAILS). Invalid — неверные данные или почта уже занята."""
    email = normalize_email(email)
    check_password(password)
    taken = Invalid("эта почта уже зарегистрирована — войдите или восстановите пароль")
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
            raise taken from None
        return user


def authenticate(email, password):
    """Пользователь по почте и паролю или None. По времени ответа не понять, есть ли такая почта."""
    user = by_email(email)
    stored = user.password_hash if user is not None and user.password_hash else dummy_hash()
    ok = verify_password(password or "", stored)
    return user if user is not None and user.password_hash and ok else None


def by_email(email):
    try:
        email = normalize_email(email)
    except Invalid:
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
    return [_admin_view(u, counts.get(u.id, 0)) for u in users]


def set_role(user_id, role):
    """Сменить роль → пользователь для администратора. NotFound — нет такого; Conflict — это последний администратор."""
    if role not in ROLES:
        raise Invalid(f"роль — {' или '.join(ROLES)}")
    with session() as s:
        user = s.get(User, uid) if (uid := parse_id(user_id)) else None
        if user is None or user.email is None:
            raise NotFound("пользователь не найден")
        admins = s.exec(select(func.count()).select_from(User).where(User.role == ADMIN)).one()
        if user.role == ADMIN and role != ADMIN and admins <= 1:
            raise Conflict("это последний администратор — сначала назначьте другого")
        user.role = role
        s.add(user)
        s.commit()
        recipes = s.exec(select(func.count()).select_from(Recipe).where(Recipe.user_id == user.id)).one()
        return _admin_view(user, recipes)


def _admin_view(u, recipes):
    return {"id": str(u.id), "email": u.email, "name": u.name, "role": u.role,
            "emailVerified": u.email_verified_at is not None, "createdAt": unix(u.created_at), "recipes": recipes}
