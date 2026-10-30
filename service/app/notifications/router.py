"""Уведомления на сайте: список, сколько непрочитанных, отметить прочитанными, push о комментариях."""
from typing import Annotated

from fastapi import APIRouter, Depends

from ..auth.dependencies import CurrentUser
from ..schemas import Ok
from .feed import Feed
from .schemas import NoticeSettings, NoticeSettingsEdit, NotificationOut, ReadIn, Unread

router = APIRouter(prefix="/notifications", tags=["уведомления"])


def user_feed(user: CurrentUser) -> Feed:
    return Feed(user)


UserFeed = Annotated[Feed, Depends(user_feed)]


@router.get("", response_model=list[NotificationOut], summary="Уведомления",
            description="Новые первыми, последние 50: комментарии к вашим рецептам, ответы на ваши комментарии "
                        "и напоминания о брожении.")
def list_notifications(feed: UserFeed):
    return feed.list()


@router.get("/unread", response_model=Unread, summary="Сколько непрочитанных")
def unread(feed: UserFeed):
    return {"count": feed.unread()}


@router.post("/read", response_model=Ok, summary="Отметить прочитанными")
def read(body: ReadIn, feed: UserFeed):
    feed.read(body.ids)
    return Ok()


@router.get("/settings", response_model=NoticeSettings, summary="Настройки уведомлений")
def get_settings(feed: UserFeed):
    return feed.settings()


@router.put("/settings", response_model=NoticeSettings, summary="Изменить настройки уведомлений",
            description="Не указанное — как было.")
def put_settings(body: NoticeSettingsEdit, feed: UserFeed):
    return feed.set_settings(body.pushComments, body.pushBrews)
