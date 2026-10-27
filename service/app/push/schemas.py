"""Схемы API уведомлений (Web Push)."""

from pydantic import BaseModel, Field


class PushKey(BaseModel):
    publicKey: str = Field(description="VAPID-ключ сервера, base64url — applicationServerKey для pushManager.subscribe")


class PushKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionIn(BaseModel):
    """PushSubscription.toJSON() браузера."""
    endpoint: str
    keys: PushKeys
    userAgent: str | None = None


class PushEndpoint(BaseModel):
    endpoint: str


class PushTest(BaseModel):
    devices: int = Field(description="сколько устройств подписано — на столько и отправлено")
