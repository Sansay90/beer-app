"""Схемы API входа и администрирования пользователей."""
from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["user", "admin"]


class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class EmailIn(BaseModel):
    email: str = Field(max_length=254)


class TokenIn(BaseModel):
    token: str = Field(max_length=200, description="токен из ссылки в письме")


class ResetIn(BaseModel):
    token: str = Field(max_length=200)
    password: str = Field(max_length=128)


class Me(BaseModel):
    id: str
    email: str
    name: str
    emailVerified: bool
    role: Role


class AdminUser(BaseModel):
    id: str
    email: str
    name: str
    role: Role
    emailVerified: bool
    createdAt: float
    recipes: int = Field(description="рецептов всего, личных и опубликованных")


class RoleIn(BaseModel):
    role: Role
