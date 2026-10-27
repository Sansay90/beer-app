"""Лимиты попыток: от подбора пароля и спама письмами. Счёт — в памяти процесса."""
import threading
import time
from collections import deque


class Throttle:
    """Не больше limit попыток за window секунд на ключ (адрес или почта)."""

    def __init__(self, limit, window):
        self.limit, self.window = limit, window
        self._hits = {}
        self._lock = threading.Lock()

    def _wait(self, key, now):
        q = self._hits.get(key)
        while q and now - q[0] > self.window:
            q.popleft()
        if q is not None and not q:
            del self._hits[key]
            return 0.0
        return self.window - (now - q[0]) if q is not None and len(q) >= self.limit else 0.0

    def wait(self, key):
        """Сколько секунд ждать, если лимит исчерпан, иначе 0. Попытку не засчитывает."""
        with self._lock:
            return self._wait(key, time.monotonic())

    def add(self, key):
        with self._lock:
            self._hits.setdefault(key, deque()).append(time.monotonic())


class AuthLimits:
    """Лимиты входа. По адресу — мягче: за NAT провайдера или шлюзом Docker с одного адреса приходят многие люди."""

    def __init__(self):
        self.failed_by_email = Throttle(10, 15 * 60)         # неудачные входы в одну почту
        self.failed_by_ip = Throttle(50, 15 * 60)            # и с одного адреса
        self.letters_by_email = Throttle(5, 60 * 60)         # писем со ссылками на одну почту в час
        self.letters_by_ip = Throttle(30, 60 * 60)
        self.signups_by_ip = Throttle(30, 60 * 60)
