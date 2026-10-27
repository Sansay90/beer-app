"""Связь агента с сервисом: WebSocket, переподключение с нарастающей паузой, буфер на время обрыва.

Соединение открывает агент: сервис пивоварню не видит, а пивовару не нужны ни белый IP, ни проброс портов.
Формат сообщений — README.md, раздел «Протокол».

Записи (всё, кроме состояния и ответов на команды) нумеруются и лежат у агента, пока сервис не подтвердит их
номер (ack): отправленное в оборвавшееся соединение не теряется, после переподключения уходит снова, а повторы
сервис отбрасывает по номеру. Из состояний (state) нужно только последнее. Команды не копятся: сервис шлёт их
только на живое соединение.
"""
import asyncio
import json
import logging
import uuid
from collections import deque

import websockets
from websockets.exceptions import ConnectionClosed, InvalidStatus

log = logging.getLogger("brewapp.link")

BACKOFF_S = (1, 2, 5, 10, 30)
HELLO_TIMEOUT_S = 10
COMMAND_TIMEOUT_S = 30           # «включить → режим → старт» — до трёх пачек команд, каждая ждёт эха
BUFFER_MAX = 20_000              # ~11 ч температуры раз в 2 с; дольше без связи — старое теряется

COMMANDS = {
    "power": lambda c, a: c.cmd_power(a["on"]),
    "manual": lambda c, a: c.cmd_manual(a["setpoint"], a["minutes"], a["watts"]),
    "run": lambda c, a: c.cmd_run(a["run"]),
    "startRecipe": lambda c, a: c.cmd_start_recipe(),
    "pump": lambda c, a: c.cmd_pump(a["on"]),
    "flow": lambda c, a: c.cmd_flow(a["level"]),
    "settings": lambda c, a: c.cmd_settings(a.get("calibration"), a.get("boilCompensation")),
    "confirmAlert": lambda c, a: c.cmd_confirm_alert(),
    "ackAddition": lambda c, a: c.ack_addition(a["minutes"]),
    "upload": lambda c, a: c.cmd_upload(a["program"]),
}


class Link:
    def __init__(self, url, token, controller, device, version, backoff=BACKOFF_S):
        """device — {tuyaId, name}: какую пивоварню обслуживает агент; backoff — паузы, с, между попытками
        переподключения. Создавать внутри работающего event loop."""
        self.url = url
        self.backoff = backoff
        self.token = token
        self.ctl = controller
        self.device = device
        self.version = version
        self.loop = asyncio.get_running_loop()
        self._run_id = uuid.uuid4().hex            # номера записей — в пределах этого запуска агента
        self._seq = 0
        self._buffer = deque()                     # записи, которые сервис ещё не подтвердил
        self._sent = 0                             # сколько из них уже отправлено в текущее соединение
        self._state = None
        self._wake = asyncio.Event()
        self._dropped = 0
        self._tasks = set()
        controller.subscribe(self._from_controller)

    # ── сообщения контроллера (из потока пивоварни) ───────────────────────────
    def _from_controller(self, msg):
        self.loop.call_soon_threadsafe(self._enqueue, msg)

    def _enqueue(self, msg):
        if msg["type"] == "state":
            self._state = msg
        else:
            if len(self._buffer) >= BUFFER_MAX:
                self._buffer.popleft()
                self._sent = max(0, self._sent - 1)
                if not self._dropped:
                    log.warning("связи с сервисом нет слишком долго — старые записи теряются")
                self._dropped += 1
            self._seq += 1
            self._buffer.append({**msg, "seq": self._seq})
        self._wake.set()

    def _ack(self, seq):
        while self._buffer and self._buffer[0]["seq"] <= seq:
            self._buffer.popleft()
            self._sent = max(0, self._sent - 1)

    def _pending_brews(self):
        """Варки, о которых сервису ещё не дослано: закрывать их как прерванные нельзя — конец, может быть, в пути."""
        ids = {m.get("brewId") or (m.get("id") if m["type"].startswith("brew") else None) for m in self._buffer}
        return sorted(i for i in ids if i)

    # ── соединение ────────────────────────────────────────────────────────────
    async def run(self):
        ticker = asyncio.create_task(self._tick())
        attempt = 0
        try:
            while True:
                try:
                    async with websockets.connect(self.url, open_timeout=10, max_size=4 * 1024 * 1024,
                                                  additional_headers={"Authorization": f"Bearer {self.token}"}) as ws:
                        attempt = 0
                        await self._session(ws)
                except InvalidStatus as e:
                    if e.response.status_code in (401, 403):
                        log.error("сервис не принял агента — проверьте AGENT_TOKEN")
                    elif not attempt:
                        log.warning("сервис ответил %s", e.response.status_code)
                except Exception as e:                       # любая ошибка связи — переподключиться, а не упасть
                    if not attempt:
                        log.warning("нет связи с сервисом: %r", e)
                await asyncio.sleep(self.backoff[min(attempt, len(self.backoff) - 1)])
                attempt += 1
        finally:
            ticker.cancel()

    async def _session(self, ws):
        await ws.send(json.dumps({"type": "hello", "agent": self.version, "session": self._run_id,
                                  "device": self.device, "brews": self._pending_brews(), **self.ctl.hello()},
                                 ensure_ascii=False))
        welcome = json.loads(await asyncio.wait_for(ws.recv(), HELLO_TIMEOUT_S))
        if welcome.get("type") != "welcome":
            raise ConnectionError(f"сервис ответил {welcome.get('type')!r} вместо welcome")
        log.info("на связи с сервисом")
        if self._dropped:
            log.warning("пока не было связи, потеряно записей: %d", self._dropped)
            self._dropped = 0
        self._apply(welcome)
        self._sent = 0                                                      # неподтверждённое — заново
        self._state = {"type": "state", "data": self.ctl.snapshot()}        # свежее состояние — сразу
        self._wake.set()
        sender = asyncio.create_task(self._send(ws))
        try:
            async for raw in ws:
                msg = json.loads(raw)
                if msg.get("type") == "ack":
                    self._ack(msg["seq"])
                elif msg.get("type") == "command":
                    task = asyncio.create_task(self._command(ws, msg))
                    self._tasks.add(task)
                    task.add_done_callback(self._tasks.discard)
                else:
                    self._apply(msg)
        finally:
            sender.cancel()

    def _apply(self, msg):
        """Сервис о рецепте, загруженном в пивоварню: его поправили (program) или удалили (forget)."""
        if msg.get("program"):
            self.ctl.apply_program(msg["program"])
        if msg.get("forget"):
            self.ctl.forget(msg["forget"])

    async def _send(self, ws):
        try:
            while True:
                while self._sent < len(self._buffer):
                    msg = self._buffer[self._sent]
                    self._sent += 1
                    await ws.send(json.dumps(msg, ensure_ascii=False))
                if self._state is not None:
                    state, self._state = self._state, None
                    await ws.send(json.dumps(state, ensure_ascii=False))
                self._wake.clear()
                if self._sent >= len(self._buffer) and self._state is None:
                    await self._wake.wait()
        except ConnectionClosed:
            pass
        except Exception:
            log.exception("отправка сервису сломалась — переподключаюсь")
            await ws.close()

    async def _tick(self):
        while True:
            await asyncio.sleep(1)
            try:
                self.ctl.tick()
            except Exception:
                log.exception("ошибка в такте контроллера")

    # ── команды ───────────────────────────────────────────────────────────────
    async def _command(self, ws, msg):
        res = await self._execute(msg.get("name"), msg.get("args") or {})
        try:
            await ws.send(json.dumps({"type": "result", "id": msg.get("id"), **res}, ensure_ascii=False))
        except ConnectionClosed:
            pass

    async def _execute(self, name, args):
        """{ok: true} или {ok: false, status, error}; status — как у HTTP: 400 неверные данные, 404 нет такого,
        502 пивоварня не подтвердила, 504 не ответила."""
        fn = COMMANDS.get(name)
        if fn is None:
            return {"ok": False, "status": 400, "error": f"неизвестная команда {name}"}
        try:
            fut = await asyncio.to_thread(fn, self.ctl, args)
        except ValueError as e:
            return {"ok": False, "status": 400, "error": str(e)}
        except KeyError as e:
            return {"ok": False, "status": 404, "error": f"не найдено: {e}"}
        except Exception:
            log.exception("команда %s сломалась", name)
            return {"ok": False, "status": 500, "error": "ошибка агента"}
        if fut is None:                                  # без записи в пивоварню (закладка заложена)
            return {"ok": True}
        try:
            res = await asyncio.wait_for(asyncio.wrap_future(fut), COMMAND_TIMEOUT_S)
        except TimeoutError:
            return {"ok": False, "status": 504, "error": "пивоварня не ответила"}
        if not res.get("ok"):
            return {"ok": False, "status": 502, "error": res.get("error") or "пивоварня не подтвердила команду (DP "
                    + ", ".join(res.get("missing", [])) + ")"}
        return {"ok": True}
