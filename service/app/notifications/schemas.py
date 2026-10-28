"""Схемы API уведомлений на сайте."""
from typing import Literal

from pydantic import BaseModel, Field

from ..auth.schemas import Author


class NoticeRecipe(BaseModel):
    id: str
    name: str


class NotificationOut(BaseModel):
    id: str
    kind: Literal["comment", "reply"] = Field(description="comment — к вашему рецепту, reply — ответ вам")
    createdAt: float
    read: bool
    actor: Author = Field(description="кто написал")
    recipe: NoticeRecipe
    commentId: str = Field(description="комментарий на странице рецепта — якорь #c-{commentId}")
    text: str = Field(description="начало комментария")


class Unread(BaseModel):
    count: int


class ReadIn(BaseModel):
    ids: list[str] | None = Field(None, description="какие отметить прочитанными; не указаны — все")


class NoticeSettings(BaseModel):
    pushComments: bool = Field(description="push на устройства о комментариях и ответах")
