"""Связь с сервисом на поддельном сервере: hello/welcome, записи до подтверждения и после обрыва, команды."""
import asyncio
import json
from concurrent.futures import Future

from websockets.asyncio.server import serve

from agent.link import Link


class StubController:
    def __init__(self):
        self._listeners = []
        self.calls = []

    def subscribe(self, fn):
        self._listeners.append(fn)

    def emit(self, msg):
        for fn in self._listeners:
            fn(msg)

    def hello(self):
        return {"model": "14", "limits": {"maxSteps": 9}, "brewId": None}

    def snapshot(self):
        return {"online": True}

    def tick(self):
        pass

    def cmd_power(self, on):
        self.calls.append(("power", on))
        fut = Future()
        fut.set_result({"ok": True, "missing": []})
        return fut


class FakeService:
    """Сервис глазами агента: принимает hello, отвечает welcome, подтверждает записи, если ack включён."""

    def __init__(self):
        self.welcome = {"type": "welcome", "deviceId": "d1"}
        self.hellos, self.received, self.connections = [], [], []
        self.ack = True

    async def handler(self, ws):
        self.connections.append(ws)
        self.hellos.append(json.loads(await ws.recv()))
        await ws.send(json.dumps(self.welcome))
        async for raw in ws:
            msg = json.loads(raw)
            self.received.append(msg)
            if "seq" in msg and self.ack:
                await ws.send(json.dumps({"type": "ack", "seq": msg["seq"]}))

    def records(self, seq):
        return [m for m in self.received if m.get("seq") == seq]


async def until(check):
    async with asyncio.timeout(5):
        while not check():
            await asyncio.sleep(0.01)


def run(scenario, service):
    async def main():
        async with serve(service.handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            ctl = StubController()
            link = Link(f"ws://127.0.0.1:{port}", "token", ctl, {"tuyaId": "t1", "name": "Пивоварня"}, "test",
                        backoff=(0.05,))
            task = asyncio.create_task(link.run())
            try:
                await scenario(ctl, link)
            finally:
                task.cancel()
    asyncio.run(main())


def test_hello_and_welcome():
    service = FakeService()

    async def scenario(ctl, link):
        await until(lambda: service.hellos)
        hello = service.hellos[0]
        assert hello["type"] == "hello" and hello["device"] == {"tuyaId": "t1", "name": "Пивоварня"}
        assert hello["model"] == "14" and hello["brews"] == [] and hello["session"]
        await until(lambda: any(m["type"] == "state" for m in service.received))   # свежее состояние — сразу
    run(scenario, service)


def test_unacked_records_survive_reconnect():
    service = FakeService()
    service.ack = False

    async def scenario(ctl, link):
        await until(lambda: service.hellos)
        ctl.emit({"type": "event", "brewId": "b1", "data": {"kind": "step", "text": "Шаг 1", "at": 1.0}})
        await until(lambda: service.records(1))
        await service.connections[-1].close()                 # обрыв: сервис запись не подтвердил
        await until(lambda: len(service.hellos) == 2)
        assert service.hellos[1]["brews"] == ["b1"]           # варку с недосланными записями не закрывать
        assert service.hellos[1]["session"] == service.hellos[0]["session"]
        await until(lambda: len(service.records(1)) == 2)     # та же запись — с тем же номером
        service.ack = True
        ctl.emit({"type": "reading", "brewId": "b1", "at": 2.0, "temp": 65.0})
        await until(lambda: service.records(2))
        await until(lambda: not link._buffer)                 # подтверждённое больше не хранится
    run(scenario, service)


def test_commands():
    service = FakeService()

    async def scenario(ctl, link):
        await until(lambda: service.connections)
        ws = service.connections[0]
        await ws.send(json.dumps({"type": "command", "id": 7, "name": "power", "args": {"on": True}}))
        await ws.send(json.dumps({"type": "command", "id": 8, "name": "selfDestruct", "args": {}}))
        await until(lambda: len([m for m in service.received if m["type"] == "result"]) == 2)
        results = {m["id"]: m for m in service.received if m["type"] == "result"}
        assert results[7] == {"type": "result", "id": 7, "ok": True}
        assert results[8]["ok"] is False and results[8]["status"] == 400
        assert ctl.calls == [("power", True)]
    run(scenario, service)
