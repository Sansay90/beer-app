"""Поток SSE (/api/stream) — открытым вкладкам пользователя: состояние и события его пивоварни (state, event),
«варка изменилась» (brew — уже в базе: пивоварня начала или закончила варку, сменила шаг; варочный день закрылся
сам) и «новое уведомление» (notice). Публиковать можно из любого потока: из чужого сообщение передаётся в цикл
событий сервиса — журнал и напоминания пишут в базу в своих потоках."""
import asyncio
from contextlib import contextmanager


class Streams:
    def __init__(self, loop=None):
        self._queues = {}            # id пользователя → очереди его вкладок
        self._loop = loop            # цикл событий сервиса; None — публикуют только из него

    def publish(self, user_id, msg):
        """{'type': 'state' | 'event' | 'brew' | 'notice', 'data': ...}."""
        loop = self._loop
        if loop is None or self._inside(loop):
            self._put(user_id, msg)
            return
        try:
            loop.call_soon_threadsafe(self._put, user_id, msg)
        except RuntimeError:         # цикл закрыт — сервис останавливается, вкладкам уже не до этого
            pass

    def brew(self, user_id, brew_id):
        self.publish(user_id, {"type": "brew", "data": {"id": str(brew_id)}})

    def notice(self, user_id):
        self.publish(user_id, {"type": "notice", "data": {}})

    def _put(self, user_id, msg):
        for q in list(self._queues.get(user_id, ())):
            q.put_nowait(msg)

    @staticmethod
    def _inside(loop):
        try:
            return asyncio.get_running_loop() is loop
        except RuntimeError:
            return False

    @contextmanager
    def subscribe(self, user_id):
        q = asyncio.Queue()
        subscribers = self._queues.setdefault(user_id, set())
        subscribers.add(q)
        try:
            yield q
        finally:
            subscribers.discard(q)
            if not subscribers:
                self._queues.pop(user_id, None)
