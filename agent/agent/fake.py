"""Имитация пивоварни для тестов: тот же интерфейс, что у device.Brewery, без сети и Tuya.

Как настоящая, сообщает об изменениях DP из своего потока; push и set_online — то, что «прислала пивоварня»,
write — команда, которую она сразу исполняет и подтверждает. Все записи — в writes.
"""
import queue
import threading
from concurrent.futures import Future

DP_CONFIRM, DP_ALERT = "142", "143"


class FakeBrewery:
    def __init__(self):
        self.dps = {}
        self.online = False
        self.writes = []
        self._listeners = []
        self._q = queue.Queue()
        threading.Thread(target=self._run, name="fake-brewery", daemon=True).start()

    def subscribe(self, fn):
        self._listeners.append(fn)

    def start(self):
        pass

    def stop(self):
        pass

    # ── со стороны пивоварни ──────────────────────────────────────────────────
    def push(self, changed):
        """Пивоварня прислала DP; возвращается, когда подписчики их обработали."""
        self._call(lambda: self._apply({str(k): v for k, v in changed.items()}))

    def set_online(self, online):
        def go():
            self.online = online
            self._notify({})
        self._call(go)

    # ── команды ───────────────────────────────────────────────────────────────
    def write(self, dps, expect=None):
        """Как Brewery.write: Future → {"ok": True, "missing": []} после «эха» пивоварни."""
        fut = Future()
        dps = {str(k): v for k, v in dps.items()}
        self.writes.append(dps)

        def go():
            # подтверждение подсказки: сам DP 142 остаётся 0, пивоварня сбрасывает DP 143 (PROTOCOL.md)
            self._apply({DP_CONFIRM: 0, DP_ALERT: 0} if DP_CONFIRM in dps else dps)
            fut.set_result({"ok": True, "missing": []})
        self._q.put(go)
        return fut

    # ── внутреннее ────────────────────────────────────────────────────────────
    def _run(self):
        while True:
            self._q.get()()

    def _call(self, fn, timeout=5):
        done = threading.Event()

        def wrapped():
            try:
                fn()
            finally:
                done.set()
        self._q.put(wrapped)
        if not done.wait(timeout):
            raise TimeoutError("имитация пивоварни не ответила")

    def _apply(self, changed):
        real = {k: v for k, v in changed.items() if self.dps.get(k) != v}
        self.dps.update(changed)
        if real:
            self._notify(real)

    def _notify(self, changed):
        for fn in self._listeners:
            fn(changed)
