"""Уведомления: подписка браузеров на Web Push."""
from typing import Annotated

from fastapi import APIRouter, Depends

from ..auth.dependencies import CurrentUser
from ..deps import PusherDep
from ..errors import AppError
from ..schemas import Ok
from .pusher import Pusher
from .schemas import PushEndpoint, PushKey, PushSubscriptionIn, PushTest

router = APIRouter(prefix="/push", tags=["уведомления"])


def enabled_pusher(pusher: PusherDep) -> Pusher:
    """503, если на сервере не задан VAPID-ключ."""
    if not pusher.enabled:
        raise AppError("уведомления не настроены на сервере: нет VAPID_PRIVATE_KEY", 503)
    return pusher


EnabledPusher = Annotated[Pusher, Depends(enabled_pusher)]


@router.get("/key", response_model=PushKey, summary="Ключ сервера для подписки браузера")
def push_key(user: CurrentUser, pusher: EnabledPusher):
    return {"publicKey": pusher.public_key}


@router.post("/subscriptions", response_model=Ok, summary="Подписать браузер")
def push_subscribe(body: PushSubscriptionIn, user: CurrentUser, pusher: EnabledPusher):
    pusher.subscribe(user.id, body.endpoint, body.keys.p256dh, body.keys.auth, body.userAgent)
    return Ok()


@router.delete("/subscriptions", response_model=Ok, summary="Отписать браузер")
def push_unsubscribe(body: PushEndpoint, user: CurrentUser, pusher: EnabledPusher):
    pusher.unsubscribe(user.id, body.endpoint)
    return Ok()


@router.post("/test", response_model=PushTest, summary="Проверочное уведомление")
def push_test(user: CurrentUser, pusher: EnabledPusher):
    pusher.notify(user.id, {"title": "Уведомления работают", "body": "Так придут подсказки, закладки и конец программы",
                            "tag": "test"})
    return {"devices": pusher.count(user.id)}
