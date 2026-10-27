"""Поток SSE (/api/stream): состояние и события пивоварни — открытым вкладкам её владельца."""
import asyncio
from contextlib import contextmanager


class Streams:
    def __init__(self):
        self._queues = {}            # id пользователя → очереди его вкладок

    def publish(self, user_id, msg):
        """Из цикла событий сервиса: {'type': 'state' | 'event', 'data': ...}."""
        for q in list(self._queues.get(user_id, ())):
            q.put_nowait(msg)

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
