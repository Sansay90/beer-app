"""Помощники тестов сервиса: сервис в потоке, HTTP-клиент с cookie входа, агент с имитацией пивоварни, прокси."""
import asyncio
import http.cookiejar
import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request

import uvicorn

from app.main import create_app

AGENT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "agent")
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

from agent.controller import Controller  # noqa: E402
from agent.fake import FakeBrewery  # noqa: E402
from agent.link import Link  # noqa: E402
from agent.state import Memory  # noqa: E402


def eventually(check, timeout=10.0, interval=0.05):
    """Ждать, пока check() не станет истинным; вернуть последнее значение (ложное — не дождались)."""
    deadline = time.monotonic() + timeout
    while True:
        value = check()
        if value or time.monotonic() > deadline:
            return value
        time.sleep(interval)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Outbox:
    """Почта для тестов: письма не уходят, а копятся здесь (вместо mail.Mailer)."""

    def __init__(self):
        self.letters = []

    def send(self, to, subject, text):
        self.letters.append((to, subject, text))

    def link(self, kind):
        """Токен из последней ссылки вида /verify?token=… или /reset?token=…"""
        for _, _, text in reversed(self.letters):
            if f"/{kind}?token=" in text:
                return text.split(f"/{kind}?token=")[1].split()[0]
        return None


class Service:
    """Сервис в потоке этого процесса — как настоящий: uvicorn, lifespan, WebSocket. Перезапуск — новое приложение
    с чистой памятью на том же порту (база остаётся)."""

    def __init__(self, settings, port=None):
        self.settings = settings
        self.port = port or free_port()
        self.outbox = Outbox()
        self.app = self.server = self.thread = None

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    def start(self):
        self.app = create_app(self.settings)
        self.app.state.mailer = self.outbox
        config = uvicorn.Config(self.app, host="127.0.0.1", port=self.port, log_level="warning",
                                timeout_graceful_shutdown=1)
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, name="service", daemon=True)
        self.thread.start()
        if not eventually(lambda: self.server.started or not self.thread.is_alive(), timeout=30):
            raise RuntimeError("сервис не поднялся")
        if not self.server.started:
            raise RuntimeError("сервис упал при запуске")
        return self

    def stop(self):
        self.server.should_exit = True
        self.thread.join(15)
        if self.thread.is_alive():
            self.server.force_exit = True
            self.thread.join(5)

    def restart(self):
        self.stop()
        return self.start()

    @property
    def state(self):
        return self.app.state

    def client(self):
        return Client(self.url)


class Client:
    """HTTP-клиент одного браузера: своя cookie входа. Ответ — (статус, JSON)."""

    def __init__(self, base):
        self.base = base
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self, method, path, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"{self.base}/api{path}", data=data, method=method,
                                     headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with self.opener.open(req, timeout=60) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"null")

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self.request("POST", path, body, **kw)

    def put(self, path, body=None, **kw):
        return self.request("PUT", path, body, **kw)

    def delete(self, path, **kw):
        return self.request("DELETE", path, **kw)

    def ok(self, method, path, body=None):
        """Запрос, который должен пройти: вернуть тело ответа."""
        status, data = self.request(method, path, body)
        assert status == 200, (method, path, status, data)
        return data

    def signup(self, email, password="password123"):
        return self.post("/auth/register", {"email": email, "password": password})


class Agent:
    """Агент пивоварни в своём потоке: настоящие Controller и Link, пивоварня — имитация."""

    def __init__(self, url, token, memory_path, brewery=None):
        self.url, self.token, self.memory_path = url, token, memory_path
        self.brewery = brewery or FakeBrewery()
        self.controller = self._loop = self._task = None

    def start(self):
        self.controller = Controller(self.brewery, Memory(self.memory_path), reading_interval=0)
        started = threading.Event()

        async def run():
            link = Link(self.url, self.token, self.controller, {"tuyaId": "fake-easybrew", "name": "Имитация"},
                        "test", backoff=(0.2, 0.5))
            self._loop, self._task = asyncio.get_running_loop(), asyncio.current_task()
            started.set()
            try:
                await link.run()
            except asyncio.CancelledError:
                pass

        threading.Thread(target=lambda: asyncio.run(run()), name="agent", daemon=True).start()
        started.wait(5)
        return self

    def stop(self):
        try:
            self._loop.call_soon_threadsafe(self._task.cancel)
        except RuntimeError:                   # цикл агента уже закрыт
            pass


class Proxy:
    """TCP-прокси между агентом и сервисом. freeze — данные агента принимаются и пропадают, как у зависшего
    сервиса; drop — оборвать все соединения."""

    def __init__(self, target_port):
        self.target_port = target_port
        self.port = free_port()
        self.frozen = False
        self._writers = set()
        self._loop = None
        ready = threading.Event()
        threading.Thread(target=lambda: asyncio.run(self._main(ready)), name="proxy", daemon=True).start()
        ready.wait(5)

    async def _main(self, ready):
        self._loop = asyncio.get_running_loop()
        server = await asyncio.start_server(self._client, "127.0.0.1", self.port)
        ready.set()
        async with server:
            await server.serve_forever()

    async def _client(self, reader, writer):
        try:
            up_reader, up_writer = await asyncio.open_connection("127.0.0.1", self.target_port)
        except OSError:
            writer.close()
            return
        self._writers |= {writer, up_writer}
        await asyncio.gather(self._pipe(reader, up_writer, upstream=True), self._pipe(up_reader, writer),
                             return_exceptions=True)

    async def _pipe(self, reader, writer, upstream=False):
        try:
            while data := await reader.read(65536):
                if upstream and self.frozen:
                    continue                    # зависший сервис: принял и молчит
                writer.write(data)
                await writer.drain()
        finally:
            writer.close()
            self._writers.discard(writer)

    def drop(self):
        def close_all():
            for w in list(self._writers):
                w.transport.abort()
        self._loop.call_soon_threadsafe(close_all)
