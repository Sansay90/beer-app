"""Администрирование: пользователи и их роли."""
from fastapi import APIRouter

from . import users
from .dependencies import Admin
from .schemas import AdminUser, RoleIn

router = APIRouter(prefix="/admin", tags=["администрирование"])


@router.get("/users", response_model=list[AdminUser], summary="Пользователи")
def admin_users(admin: Admin):
    return users.list_users()


@router.put("/users/{uid}/role", response_model=AdminUser, summary="Сменить роль")
def admin_set_role(uid: str, body: RoleIn, admin: Admin):
    return users.set_role(uid, body.role)
