"""Web Push: уведомления о событиях варки на устройства пользователя, даже когда вкладка закрыта.

Ключ сервера — VAPID_PRIVATE_KEY в .env (новый: python -m app vapid); без него уведомления выключены.
Подписки браузеров — таблица push_subscriptions. Отправка идёт в своём потоке: пивоварня и интерфейс
не ждут push-сервисов.
"""
import json
import logging
import queue
import threading
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid01, b64urlencode
from pywebpush import WebPushException, webpush
from sqlmodel import delete, select

from ..db import session
from ..errors import Invalid
from ..models import PushSubscription, utcnow

log = logging.getLogger("brewapp.push")

SEND_TIMEOUT_S = 10
QUEUE_MAX = 100
GONE = {404, 410}                    # подписку отозвали — удаляем
# сервер ходит по адресу из подписки, поэтому принимает только push-сервисы браузеров
PUSH_HOSTS = {"fcm.googleapis.com", "updates.push.services.mozilla.com"}
PUSH_HOST_SUFFIXES = (".notify.windows.com", ".push.apple.com")

ALERTS = {
    "malt": ("Засыпьте солод", "Подтвердите, когда солод будет в корзине"),
    "mashEnd": ("Затирание закончено", "Выньте солодовую корзину и подтвердите"),
}


def allowed_endpoint(url):
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and (host in PUSH_HOSTS or host.endswith(PUSH_HOST_SUFFIXES))


def new_private_key():
    """Новый VAPID-ключ: 32 байта закрытого ключа P-256 в base64url — строка для .env."""
    vapid = Vapid01()
    vapid.generate_keys()
    return b64urlencode(vapid.private_key.private_numbers().private_value.to_bytes(32, "big"))


def message(ev, brewing):
    """Событие варки → уведомление; None — не беспокоить.
    urgent — висит, пока не нажмут, и звучит заново; action — кнопка в уведомлении (POST на сервис)."""
    kind = ev["kind"]
    if kind == "alert":
        title, body = ALERTS.get(ev.get("alert"), ("Нужно подтверждение", ev["text"]))
        return {"title": title, "body": body, "tag": "alert", "urgent": True,
                "action": {"title": "Подтвердить", "path": "/api/alert/confirm"}}
    if kind == "addition":
        slot = ev["addition"]
        return {"title": f"Заложите: {slot['label']}" if slot["items"] else "Время закладки",
                "body": f"За {slot['minutes']} мин до конца кипячения" if slot["minutes"] else "В конце кипячения",
                "tag": f"addition-{slot['minutes']}",
                "urgent": True, "action": {"title": "Заложил", "path": f"/api/additions/{slot['minutes']}/ack"}}
    if kind == "end":
        return {"title": "Программа завершена", "body": "Сусло готово к охлаждению", "tag": "end"}
    if kind == "error":
        return {"title": "Ошибка пивоварни", "body": ev["text"], "tag": "problem", "urgent": True}
    if kind == "offline" and brewing:
        return {"title": "Пивоварня не в сети", "body": "Связь пропала во время варки", "tag": "problem",
                "urgent": True}
    if kind == "powerOff" and brewing:
        return {"title": "Пивоварня выключена", "body": "Программа прервана", "tag": "problem", "urgent": True}
    return None


class Pusher:
    """Уведомления пользователям: у каждого свои подписанные браузеры."""

    def __init__(self, private_key, subject):
        """private_key — VAPID_PRIVATE_KEY; пусто — уведомления выключены (enabled = False)."""
        self.subject = subject
        self.vapid = Vapid01.from_string(private_key) if private_key else None
        self.public_key = None
        if self.vapid:
            raw = self.vapid.public_key.public_bytes(serialization.Encoding.X962,
                                                     serialization.PublicFormat.UncompressedPoint)
            self.public_key = b64urlencode(raw)
        else:
            log.warning("уведомления выключены: нет VAPID_PRIVATE_KEY (новый ключ — python -m app vapid)")
        self._q = queue.Queue(QUEUE_MAX)
        self._thread = threading.Thread(target=self._run, name="push", daemon=True)

    @property
    def enabled(self):
        return self.vapid is not None

    def start(self):
        if self.enabled:
            self._thread.start()

    def stop(self):
        if self._thread.is_alive():
            self._q.put(None)
            self._thread.join(timeout=SEND_TIMEOUT_S + 1)

    def watch(self, hub):
        """Слушать события пивоварен (brewery/hub.py) — уведомлять владельца; проблемы со связью — только
        во время варки."""
        def on_message(device_id, msg):
            if msg["type"] != "event" or (user_id := hub.owner(device_id)) is None:
                return
            if note := message(msg["data"], msg.get("brewing", False)):
                self.notify(user_id, note)
        hub.subscribe(on_message)

    def notify(self, user_id, note):
        """Из любого потока, не блокирует."""
        if not self.enabled:
            return
        try:
            self._q.put_nowait((user_id, note))
        except queue.Full:
            log.warning("очередь уведомлений переполнена — «%s» не отправлено", note["title"])

    # ── подписки ──────────────────────────────────────────────────────────────
    def subscribe(self, user_id, endpoint, p256dh, auth, user_agent=None):
        """Invalid — адрес не похож на push-сервис браузера. Браузер уже подписан другим пользователем
        (вошли под другой почтой) — подписка переходит к этому."""
        if not allowed_endpoint(endpoint):
            raise Invalid("адрес подписки не принадлежит push-сервису браузера")
        with session() as s:
            row = s.exec(select(PushSubscription).where(PushSubscription.endpoint == endpoint)).first()
            row = row or PushSubscription(user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth)
            row.user_id, row.p256dh, row.auth, row.user_agent = user_id, p256dh, auth, user_agent
            row.last_seen_at = utcnow()
            s.add(row)
            s.commit()

    def unsubscribe(self, user_id, endpoint):
        with session() as s:
            s.exec(delete(PushSubscription).where(PushSubscription.user_id == user_id,
                                                  PushSubscription.endpoint == endpoint))
            s.commit()

    def count(self, user_id):
        with session() as s:
            return len(s.exec(select(PushSubscription.id).where(PushSubscription.user_id == user_id)).all())

    # ── отправка ──────────────────────────────────────────────────────────────
    def _run(self):
        while (item := self._q.get()) is not None:
            try:
                self._send(*item)
            except Exception:
                log.exception("ошибка отправки уведомления")

    def _send(self, user_id, note):
        with session() as s:
            subs = s.exec(select(PushSubscription).where(PushSubscription.user_id == user_id)).all()
        data = json.dumps(note, ensure_ascii=False)
        for sub in subs:
            if self._deliver(sub, data, note):
                with session() as s:
                    row = s.get(PushSubscription, sub.id)
                    if row:
                        row.last_seen_at = utcnow()
                        s.add(row)
                        s.commit()

    def _deliver(self, sub, data, note):
        host = urlsplit(sub.endpoint).hostname
        try:
            # claims — новый словарь на каждую отправку: webpush дописывает в него aud конкретного push-сервиса
            webpush({"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}}, data,
                    vapid_private_key=self.vapid, vapid_claims={"sub": self.subject},
                    ttl=600 if note.get("urgent") else 3600, timeout=SEND_TIMEOUT_S,
                    headers={"Urgency": "high" if note.get("urgent") else "normal"})
            return True
        except WebPushException as e:
            status = e.response.status_code if e.response is not None else None
            if status in GONE:
                log.info("подписка %s отозвана (%s) — удаляю", host, status)
                self.unsubscribe(sub.user_id, sub.endpoint)
            else:
                log.warning("уведомление на %s не доставлено: %s", host, status or e)
        except Exception as e:                     # сеть, таймаут
            log.warning("уведомление на %s не доставлено: %s", host, e)
        return False
