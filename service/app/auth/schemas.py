"""Схемы API входа и администрирования пользователей."""
from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["user", "admin"]


class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class RegisterIn(Credentials):
    name: str | None = Field(None, max_length=40,
                             description="ник, необязателен: 3–24 знака, буквы (русские или латинские), цифры, _ и -")


class NameIn(BaseModel):
    name: str = Field(max_length=40, description="новый ник")


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
    name: str | None = Field(None, description="ник — его видят все; нет — «Неизвестный пивовар»")
    avatar: str | None = Field(None, description="адрес аватара; нет — интерфейс рисует бокал")
    emailVerified: bool
    role: Role


class Author(BaseModel):
    """Пивовар, как его видят все: без почты."""
    id: str = Field(description="по нему интерфейс рисует бокал, если аватара нет")
    name: str | None = Field(None, description="ник; нет — «Неизвестный пивовар», страницы у такого нет")
    avatar: str | None = None


class Brewer(Author):
    name: str
    joinedAt: float = Field(description="когда зарегистрировался")
    recipes: int = Field(description="опубликованных рецептов")


class AdminUser(BaseModel):
    id: str
    email: str
    name: str | None = None
    role: Role
    emailVerified: bool
    createdAt: float
    recipes: int = Field(description="рецептов всего, личных и опубликованных")


class RoleIn(BaseModel):
    role: Role
