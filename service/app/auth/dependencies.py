"""Кто спрашивает: гость, пользователь или администратор — зависимости для роутеров (права — access.py)."""
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from ..access import is_admin
from ..models import User
from . import sessions

SESSION_COOKIE = "brewapp_session"


def optional_user(request: Request) -> User | None:
    """Вошедший пользователь или None — гость."""
    return sessions.user(request.cookies.get(SESSION_COOKIE))


def current_user(user: Annotated[User | None, Depends(optional_user)]) -> User:
    if user is None:
        raise HTTPException(401, "войдите")
    return user


def admin_user(user: Annotated[User, Depends(current_user)]) -> User:
    if not is_admin(user):
        raise HTTPException(403, "нужны права администратора")
    return user


Viewer = Annotated[User | None, Depends(optional_user)]
CurrentUser = Annotated[User, Depends(current_user)]
Admin = Annotated[User, Depends(admin_user)]
