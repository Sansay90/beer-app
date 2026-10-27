import threading
import time

import pytest

from agent import controller as controller_module
from agent.controller import Controller
from agent.fake import FakeBrewery
from agent.state import Memory


def eventually(check, timeout=5.0, interval=0.02):
    """Ждать, пока check() не станет истинным (сообщения идут из потоков); вернуть его значение."""
    deadline = time.monotonic() + timeout
    while True:
        value = check()
        if value or time.monotonic() > deadline:
            return value
        time.sleep(interval)


class Recorder:
    """Сообщения контроллера сервису (subscribe)."""

    def __init__(self):
        self.messages = []
        self._lock = threading.Lock()

    def __call__(self, msg):
        with self._lock:
            self.messages.append(msg)

    def of(self, kind):
        with self._lock:
            return [m for m in self.messages if m["type"] == kind]

    def events(self):
        return [m["data"]["kind"] for m in self.of("event")]


@pytest.fixture(autouse=True)
def no_settle(monkeypatch):
    """После включения настоящая пивоварня 2 с сбрасывает режим; имитации пауза не нужна."""
    monkeypatch.setattr(controller_module, "POWER_ON_SETTLE_S", 0)


@pytest.fixture
def brewery():
    fake = FakeBrewery()
    fake.set_online(True)
    return fake


@pytest.fixture
def memory(tmp_path):
    return Memory(str(tmp_path / "state.json"))


@pytest.fixture
def recorder():
    return Recorder()


@pytest.fixture
def ctl(brewery, memory, recorder):
    c = Controller(brewery, memory, reading_interval=0)
    c.subscribe(recorder)
    return c
