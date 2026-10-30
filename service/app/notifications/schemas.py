"""Схемы API уведомлений на сайте."""
from typing import Literal

from pydantic import BaseModel, Field

from ..auth.schemas import Author


class NoticeRecipe(BaseModel):
    id: str
    name: str


class NoticeBrew(BaseModel):
    id: str
    name: str


class NotificationOut(BaseModel):
    id: str
    kind: Literal["comment", "reply", "brew"] = Field(
        description="comment — к вашему рецепту, reply — ответ вам, brew — напоминание о брожении")
    createdAt: float
    read: bool
    actor: Author | None = Field(None, description="кто написал (комментарий, ответ)")
    recipe: NoticeRecipe | None = None
    commentId: str | None = Field(None, description="комментарий на странице рецепта — якорь #c-{commentId}")
    brew: NoticeBrew | None = Field(None, description="варка (напоминание)")
    title: str | None = Field(None, description="напоминание: что пора сделать")
    text: str = Field(description="начало комментария или подробности напоминания")


class Unread(BaseModel):
    count: int


class ReadIn(BaseModel):
    ids: list[str] | None = Field(None, description="какие отметить прочитанными; не указаны — все")


class NoticeSettings(BaseModel):
    pushComments: bool = Field(description="push на устройства о комментариях и ответах")
    pushBrews: bool = Field(description="push на устройства — напоминания о брожении")


class NoticeSettingsEdit(BaseModel):
    pushComments: bool | None = None
    pushBrews: bool | None = None
