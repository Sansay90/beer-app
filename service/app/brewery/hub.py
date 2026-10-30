"""Агенты на связи: приём их сообщений, последнее состояние пивоварни, команды.

Соединение открывает агент (WebSocket /api/agent, токен в заголовке Authorization) — сервис пивоварню не видит.
Формат сообщений — agent/README.md, «Протокол». Состояние уходит интерфейсу; события — интерфейсу, в журнал
и в уведомления; температура и варки — в журнал. Записи агент нумерует: сервис подтверждает каждую (ack),
а повтор после переподключения отбрасывает по номеру. Команда уходит только на живое соединение: агента нет —
сразу ошибка, команды не копятся (ARCHITECTURE.md, «Управление через интернет»).
"""
import asyncio
import itertools
import logging

from starlette.websockets import WebSocket, WebSocketDisconnect

from ..errors import AppError, Forbidden
from . import agents

log = logging.getLogger("brewapp.hub")

HELLO_TIMEOUT_S = 10
BREW_STATUSES = ("finished", "stopped")
# пока пивоварня ни разу не подключалась — ограничения Easy Brew, пока единственной (agent/recipe.py)
DEFAULT_LIMITS = {"maxSteps": 9, "maxAdditions": 9, "minTemp": 20.0, "maxTemp": 100.0, "boilTemp": 100.1,
                  "minWatts": 100, "maxWatts": None, "wattsStep": 100}
# пивоварня ещё не подключалась — все поля явно, как в снимке агента (поток SSE идёт мимо схемы ответа)
OFFLINE = {"online": False, "power": False, "running": False, "status": None, "mode": None, "temp": None,
           "setpoint": None, "manualMinutes": None, "manualWatts": None, "pump": False, "flow": None, "step": 0,
           "stepTarget": None, "timer": {"minutes": None, "remaining": None, "counting": False, "at": 0},
           "alert": None, "error": 0,
           "settings": {"calibration": None, "boilCompensation": None, "unit": None, "model": None, "maxWatts": None},
           "deviceRecipe": None, "additions": [], "additionsPending": [], "energy": {"wh": 0, "watts": 0}}


class AgentOffline(AppError):
    """Агента пивоварни нет на связи — команду некому отдать."""
    status = 503

    def __init__(self, detail="пивоварня не в сети"):
        super().__init__(detail)


class AgentLost(AgentOffline):
    """Связь с агентом оборвалась, пока команда ждала ответа: пивоварня могла её уже выполнить."""

    def __init__(self):
        super().__init__("связь с пивоварней прервалась — команда могла выполниться, проверьте её состояние")


class Link:
    """Одно соединение агента."""

    def __init__(self, ws, agent, device_id):
        self.ws = ws
        self.agent = agent
        self.device_id = device_id
        self._pending = {}             # id команды → Future ответа
        self._ids = itertools.count(1)

    async def command(self, name, args):
        cid = next(self._ids)
        fut = asyncio.get_running_loop().create_future()
        self._pending[cid] = fut
        try:
            try:
                await self.ws.send_json({"type": "command", "id": cid, "name": name, "args": args})
            except (WebSocketDisconnect, RuntimeError):       # соединение уже закрывается
                raise AgentOffline() from None
            return await fut
        finally:
            self._pending.pop(cid, None)

    def resolve(self, msg):
        fut = self._pending.get(msg.get("id"))
        if fut is not None and not fut.done():
            fut.set_result(msg)

    def drop(self):
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(AgentLost())


class Hub:
    def __init__(self, devices, journal):
        self.devices = devices
        self.journal = journal
        self.links = {}                # id пивоварни → Link
        self._snapshots = {}           # id пивоварни → последнее состояние от агента
        self._seen = {}                # id пивоварни → [запуск агента, номер последней принятой записи]
        self._owners = {}              # id пивоварни → id пользователя (по агенту)
        self._brews = {}               # id пивоварни → id её варок (из brewStarted и проверенные по базе)
        self._foreign = {}             # id пивоварни → id варок из её сообщений, принадлежащих другой пивоварне
        self._listeners = []

    def subscribe(self, fn):
        """fn(device_id, message) — {'type': 'state' | 'event', 'data': ...}; у event ещё brewing — идёт ли варка."""
        self._listeners.append(fn)

    def _emit(self, device_id, msg):
        for fn in self._listeners:
            try:
                fn(device_id, msg)
            except Exception:
                log.exception("ошибка в подписчике")

    # ── для API ───────────────────────────────────────────────────────────────
    def owner(self, device_id):
        """Чья пивоварня — id пользователя; None, если её агент не подключался с запуска сервиса."""
        return self._owners.get(device_id)

    def snapshot(self, device_id):
        snap = self._snapshots.get(device_id)
        if snap is None:
            return dict(OFFLINE)
        return snap if device_id in self.links else {**snap, "online": False}

    def limits(self, device_id):
        return (self.devices.limits(device_id) if device_id else None) or DEFAULT_LIMITS

    async def command(self, device_id, name, **args):
        """Ответ агента: {ok, status?, error?}. AgentOffline — агента нет на связи; сколько ждать ответа,
        решает вызывающий (asyncio.timeout)."""
        link = self.links.get(device_id)
        if link is None:
            raise AgentOffline()
        return await link.command(name, args)

    async def notify(self, device_id, msg):
        """Сообщение агенту без ответа (program, forget). Агента нет — не страшно: подключаясь, он спросит сам."""
        link = self.links.get(device_id)
        if link is not None:
            try:
                await link.ws.send_json(msg)
            except Exception:
                pass

    # ── соединение агента ─────────────────────────────────────────────────────
    async def serve(self, ws: WebSocket):
        token = (ws.headers.get("authorization") or "").removeprefix("Bearer ").strip()
        agent = await asyncio.to_thread(agents.by_token, token)
        if agent is None:
            await ws.close(code=1008)                        # до accept — агент получит 403
            return
        await ws.accept()
        try:
            hello = await asyncio.wait_for(ws.receive_json(), HELLO_TIMEOUT_S)
            if hello.get("type") != "hello":
                raise ValueError(f"ждали hello, пришло {hello.get('type')!r}")
            dev = hello["device"]
            device_id = await asyncio.to_thread(self.devices.attach, agent, dev["tuyaId"],
                                                dev.get("name") or "Пивоварня", hello.get("model"), hello.get("limits"))
        except (TimeoutError, WebSocketDisconnect, Forbidden, KeyError, TypeError, ValueError) as e:
            log.warning("агент «%s» не представился: %s", agent.name, e)
            try:
                await ws.close(code=1008)
            except RuntimeError:                             # агент уже отключился
                pass
            return

        link = Link(ws, agent, device_id)
        self._owners[device_id] = agent.user_id
        # варки, которые агент ещё ведёт или о которых не дослал записи, не закрывать: их конец, может быть, в пути
        keep = {b for b in (hello.get("brewId"), *(hello.get("brews") or ())) if isinstance(b, str)}
        self.journal.close_brews(device_id, keep=keep)
        seen = self._seen.get(device_id)
        if seen is None or seen[0] != hello.get("session"):            # агент перезапущен — номера с начала
            seen = self._seen[device_id] = [hello.get("session"), 0]
        old, self.links[device_id] = self.links.get(device_id), link
        if old is not None:                                  # тот же агент переподключился — старое соединение лишнее
            try:
                await old.ws.close()
            except Exception:
                pass
        await ws.send_json({"type": "welcome", "deviceId": str(device_id)})
        await asyncio.to_thread(agents.touch, agent.id)
        log.info("агент «%s» на связи", agent.name)
        try:
            while True:
                msg = await ws.receive_json()
                seq = msg.get("seq")
                if seq is not None:
                    if seq <= seen[1]:                               # уже принято — повтор после переподключения
                        await ws.send_json({"type": "ack", "seq": seq})
                        continue
                    seen[1] = seq                                # до обработки: повтор по новому соединению не пройдёт
                try:
                    await self._handle(link, msg)
                except Exception:
                    log.exception("агент «%s»: сообщение %s не обработано", agent.name, msg.get("type"))
                if seq is not None:                                  # и сломанное подтверждаем — иначе вечный повтор
                    await ws.send_json({"type": "ack", "seq": seq})
        except (WebSocketDisconnect, RuntimeError):                  # RuntimeError — отправка в закрытое соединение
            pass
        finally:
            link.drop()
            if self.links.get(device_id) is link:
                del self.links[device_id]
                self._emit(device_id, {"type": "state", "data": self.snapshot(device_id)})
            await asyncio.to_thread(agents.touch, agent.id)
            log.info("агент «%s» отключился", agent.name)

    async def _handle(self, link, msg):
        kind, d = msg.get("type"), link.device_id
        if kind == "state":
            self._snapshots[d] = msg["data"]
            self._emit(d, {"type": "state", "data": msg["data"]})
        elif kind == "event":
            brew = await self._brew(d, msg.get("brewId"))
            self.journal.event(d, brew, msg["data"])
            self._emit(d, {"type": "event", "data": msg["data"], "brewing": brew is not None})
        elif kind == "reading":
            self.journal.reading(d, await self._brew(d, msg.get("brewId")), msg["at"], msg["temp"], msg.get("target"),
                                 msg.get("step"), msg.get("status"))
        elif kind == "brewStarted":
            bid = msg["id"]
            if bid not in self._foreign.setdefault(d, set()) and \
                    await asyncio.to_thread(self.journal.brew_device, bid) in (None, d):
                self._brews.setdefault(d, set()).add(bid)
                self.journal.start_brew(d, link.agent.user_id, bid, msg.get("name") or "Варка",
                                        msg.get("recipeId"), msg.get("recipe"), msg["at"])
        elif kind == "brewUpdated":
            if brew := await self._brew(d, msg.get("id")):
                self.journal.update_brew(brew, energy_wh=msg["energyWh"])
        elif kind == "brewFinished":
            if brew := await self._brew(d, msg.get("id")):
                status = msg.get("status") if msg.get("status") in BREW_STATUSES else "stopped"
                self.journal.finish_brew(brew, status, msg.get("energyWh") or 0.0, msg.get("at"))
        elif kind == "device":
            await asyncio.to_thread(self.devices.update, d, model=msg.get("model"), limits=msg.get("limits"))
        elif kind == "result":
            link.resolve(msg)
        else:
            log.warning("агент «%s»: неизвестное сообщение %r", link.agent.name, kind)

    async def _brew(self, device_id, brew_id):
        """id варки из сообщения агента, если варка этой пивоварни, иначе None. Варки, начатые при этом запуске
        сервиса, известны и до записи в базу (журнал пишет очередью); после его перезапуска — проверяются по базе."""
        if not isinstance(brew_id, str) or brew_id in self._foreign.setdefault(device_id, set()):
            return None
        known = self._brews.setdefault(device_id, set())
        if brew_id not in known:
            owner = await asyncio.to_thread(self.journal.brew_device, brew_id)
            if owner is None:
                return None
            (known if owner == device_id else self._foreign[device_id]).add(brew_id)
        return brew_id if brew_id in known else None
