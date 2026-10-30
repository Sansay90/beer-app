"""Фоновые напоминания по партиям: поток раз в interval секунд — или раньше, к ближайшему сроку, если наследник его
знает (next_at): конец паузы приходит вовремя, а не на следующем проходе; уведомления на сайте и push
(users.push_brews).
Что и когда напоминать, решает наследник (due): брожение — reminders.py, таймеры варочного дня — brewday.py.
Напоминание уходит, когда время пришло, но не позже LATE: варку записали задним числом или сервис стоял — старое
молча пропускается. О чём уже напомнили — brews.reminded. Проход идёт под замком: роутер может позвать tick сразу
после записи, не дожидаясь потока, — дублей не будет. Открытым вкладкам — «новое уведомление» (streams.py).
"""
import logging
import threading
from datetime import timedelta

from sqlmodel import select

from ..db import session
from ..models import Notification, User, utcnow
from ..notifications.feed import BREW

log = logging.getLogger("brewapp.ticker")


class Ticker:
    """Наследник задаёт NAME (поток и журнал), TAG (метка push), INTERVAL_S, LATE и due(); pusher — push/pusher.py,
    streams — brewery/streams.py."""

    NAME = "ticker"
    TAG = "brew"
    INTERVAL_S = 300
    LATE = timedelta(hours=12)

    def __init__(self, pusher=None, streams=None, interval=None):
        self.pusher = pusher
        self.streams = streams
        self.interval = interval or self.INTERVAL_S
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name=self.NAME, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=5)

    def _run(self):
        while not self._stop.wait(self._pause()):
            try:
                self.tick()
            except Exception:
                log.exception("%s: ошибка напоминаний", self.NAME)

    def _pause(self):
        """Сколько ждать до прохода: interval, а подходит срок раньше — до него (с запасом на округление)."""
        now = utcnow()
        try:
            nxt = self.next_at(now)
        except Exception:
            log.exception("%s: ошибка расписания", self.NAME)
            nxt = None
        if nxt is None:
            return self.interval
        return min(self.interval, max(0.5, (nxt - now).total_seconds() + 0.1))

    def next_at(self, now):
        """Ближайший срок ещё не отправленного напоминания позже now; None — проверять раз в interval."""
        return None

    def due(self, s, now, brew_id=None):
        """[(варка, [(ключ, когда, заголовок, текст, молча)])] — чему пора (когда ≤ now); brew_id — только эта.
        «Молча» — отметить напомненным без уведомления (этап начат по факту)."""
        raise NotImplementedError

    def tick(self, now=None, brew_id=None):
        """Напомнить обо всём, чему пришло время; вернуть, сколько уведомлений создано."""
        now = now or utcnow()
        sent = []
        with self._lock, session() as s:
            for b, items in self.due(s, now, brew_id):
                done = set(b.reminded or [])
                fresh = [r for r in items if r[0] not in done]
                if not fresh:
                    continue
                for _, at, title, text, silent in fresh:
                    if not silent and now - at <= self.LATE:
                        s.add(Notification(user_id=b.user_id, kind=BREW, brew_id=b.id,
                                           data={"title": title, "text": text}))
                        sent.append((b.user_id, b.id, b.name, title, text))
                b.reminded = [*done, *(r[0] for r in fresh)]       # новый список — ORM заметит правку JSONB
                s.add(b)
            s.commit()
        if self.streams is not None:
            for uid in {uid for uid, *_ in sent}:
                self.streams.notice(uid)
        self._push(sent)
        return len(sent)

    def _push(self, sent):
        if not sent or self.pusher is None:
            return
        with session() as s:
            wanting = set(s.exec(select(User.id).where(User.id.in_({uid for uid, *_ in sent}), User.push_brews)).all())
        for uid, bid, name, title, text in sent:
            if uid in wanting:
                self.pusher.notify(uid, {"title": f"{title} — «{name}»", "body": text, "tag": f"{self.TAG}-{bid}",
                                         "url": f"/brews/{bid}"})
