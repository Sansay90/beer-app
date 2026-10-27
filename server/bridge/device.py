"""Единственное подключение к пивоварне.

Фоновый поток держит сокет, копит состояние DP и выполняет команды по очереди:
tinytuya не потокобезопасен, а модуль Tuya обслуживает не больше трёх подключений
(PROTOCOL.md), так что всё общение с пивоварней идёт только через этот поток.
"""
import logging
import queue
import threading
import time
from concurrent.futures import Future

import tinytuya

log = logging.getLogger("brewapp.device")

ECHO_TIMEOUT_S = 4
SOCKET_TIMEOUT_S = 1
# Выдернутая из розетки пивоварня соединение не закрывает — TCP заметит это через минуты.
# Поэтому живость проверяем сами: тишина дольше PING_S — спрашиваем статус, дольше DEAD_S — пропала.
PING_S = 3
DEAD_S = 7
HEARTBEAT_S = 10         # без heartbeat модуль через ~30 с шлёт служебный пакет, который tinytuya не разбирает
RECONNECT_S = 2
DISCOVER_S = 6           # окно поиска по широковещанию: модуль Tuya вещает раз в ~5 с
REDISCOVER_EVERY = 10    # при автопоиске: раз в N неудач по запомненному адресу искать заново (IP мог смениться)


class Brewery:
    def __init__(self, dev_id, local_key, address="Auto", version=None):
        self.dev_id = dev_id
        self.local_key = local_key
        # адрес не задан — ищем широковещанием и запоминаем, чтобы переподключаться напрямую
        self._auto = not address or address == "Auto" or not version
        self.address = None if self._auto else address
        self.version = None if self._auto else version
        self.dps = {}
        self.online = False
        self._cmds = queue.Queue()
        self._pending = []                 # [(ожидаемые {dp: value}, Future, срок)]
        self._listeners = []
        self._last_rx = 0.0                # когда пивоварня последний раз что-то прислала
        self._last_ping = 0.0
        self._last_hb = 0.0
        self._fails = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="brewery", daemon=True)

    # ── API для остальных модулей ─────────────────────────────────────────────
    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=5)

    def subscribe(self, fn):
        """fn(changed: dict[str, value]) — вызывается из потока пивоварни; changed={} при смене online."""
        self._listeners.append(fn)

    def write(self, dps, expect=None):
        """Записать {dp: value} по порядку. Future → {'ok': bool, 'missing': [dp…]} по эху от пивоварни.
        expect — какое эхо ждать вместо записанного (подтверждение подсказки: пишем 142, меняется 143)."""
        fut = Future()
        self._cmds.put(({str(k): v for k, v in dps.items()}, fut,
                        {str(k): v for k, v in (expect or dps).items()}))
        return fut

    # ── поток ─────────────────────────────────────────────────────────────────
    def _run(self):
        dev = None
        while not self._stop.is_set():
            if dev is None:
                dev = self._connect()
                if dev is None:
                    self._fail_pending("нет связи с пивоварней")
                    self._stop.wait(RECONNECT_S)
                    continue

            try:
                self._send_commands(dev)
                msg = dev.receive()
                if msg and msg.get("Err"):
                    # нераспознанный пакет — не обрыв; настоящую пропажу решает сторож (_check_alive)
                    log.debug("пивоварня прислала ошибку: %s", msg.get("Error"))
                    msg = None
                self._absorb(msg)
                self._check_alive(dev)
                self._check_pending()
            except Exception as e:                       # обрыв — переподключаемся
                log.warning("связь потеряна: %s", e)
                try:
                    dev.close()
                except Exception:
                    pass
                dev = None
                self._set_online(False)

    def _check_alive(self, dev):
        """Тишина — сами спрашиваем статус; нет ответа DEAD_S — пивоварня пропала (выключили из розетки)."""
        now = time.monotonic()
        if now - self._last_rx > DEAD_S:
            raise ConnectionError(f"нет ответа {DEAD_S} с")
        if now - self._last_hb > HEARTBEAT_S:
            self._last_hb = now
            dev.heartbeat()
        if now - self._last_rx > PING_S and now - self._last_ping > PING_S:
            self._last_ping = now
            r = dev.status()                             # ошибка не фатальна: решает DEAD_S
            if r and not r.get("Err"):
                self._absorb(r)

    def _connect(self):
        try:
            if self.address is None or (self._auto and self._fails and self._fails % REDISCOVER_EVERY == 0):
                self._discover()
            dev = tinytuya.Device(self.dev_id, address=self.address, local_key=self.local_key,
                                  version=float(self.version))
            dev.set_socketPersistent(True)
            dev.set_socketTimeout(SOCKET_TIMEOUT_S)
            dev.set_socketRetryLimit(1)
            dev.set_socketRetryDelay(1)
            st = dev.status()
            if not st or st.get("Err") or "dps" not in st:
                raise ConnectionError((st or {}).get("Error", "пустой ответ"))
        except Exception as e:
            self._fails += 1
            if self._fails == 1:                         # дальше молчим, пока пивоварня не появится
                log.info("пивоварня недоступна: %s", e)
            self._set_online(False)
            return None
        log.info("подключено: %s, протокол %s", dev.address, dev.version)
        self._fails = 0
        self._last_rx = self._last_ping = self._last_hb = time.monotonic()
        self._set_online(True)
        self._absorb(st)
        return dev

    def _discover(self):
        """Найти пивоварню по UDP-широковещанию модуля Tuya и запомнить адрес и версию протокола."""
        from tinytuya import scanner
        found = scanner.devices(verbose=False, scantime=DISCOVER_S, poll=False, forcescan=False,
                                byID=True, wantids=[self.dev_id]).get(self.dev_id)
        if not found:
            raise ConnectionError("не найдена в сети")
        self.address, self.version = found["ip"], found["version"]

    def _send_commands(self, dev):
        while True:
            try:
                dps, fut, want = self._cmds.get_nowait()
            except queue.Empty:
                return
            want = dict(want)
            # ждём эхо с момента отправки: оно может прийти прямо в ответе на set_value
            self._pending.append((want, fut, time.monotonic() + ECHO_TIMEOUT_S))
            for dp, value in dps.items():
                r = dev.set_value(int(dp), value)
                if r and r.get("Err"):
                    raise ConnectionError(r.get("Error"))
                self._absorb(r)
            self._check_pending()

    def _absorb(self, msg):
        if msg and not msg.get("Err"):
            self._last_rx = time.monotonic()             # любой ответ — признак жизни
        changed = {}
        for dp, value in ((msg or {}).get("dps") or {}).items():
            # эхо засчитываем даже без изменения значения
            for want, _, _ in self._pending:
                if dp in want and want[dp] == value:
                    del want[dp]
            if self.dps.get(dp) != value:
                self.dps[dp] = value
                changed[dp] = value
        if changed:
            self._notify(changed)

    def _check_pending(self):
        now = time.monotonic()
        keep = []
        for want, fut, deadline in self._pending:
            if not want:
                fut.set_result({"ok": True, "missing": []})
            elif now > deadline:
                fut.set_result({"ok": False, "missing": list(want)})
            else:
                keep.append((want, fut, deadline))
        self._pending = keep

    def _fail_pending(self, why):
        while True:
            try:
                dps, fut, _ = self._cmds.get_nowait()
            except queue.Empty:
                break
            fut.set_result({"ok": False, "missing": list(dps), "error": why})
        for want, fut, _ in self._pending:
            fut.set_result({"ok": False, "missing": list(want), "error": why})
        self._pending = []

    def _set_online(self, online):
        if self.online != online:
            self.online = online
            self._notify({})

    def _notify(self, changed):
        for fn in self._listeners:
            try:
                fn(changed)
            except Exception:
                log.exception("ошибка в подписчике")
