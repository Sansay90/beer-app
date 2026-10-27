"""Смысл поверх DP пивоварни: состояние для интерфейса, оценка таймера шага, расписание закладок,
события и варки. Всё это уходит сервису сообщениями (link.py) — хранит сервис; сам агент помнит только то,
что должно пережить перезапуск (state.py).

Приложение не вносит поправок под конкретный экземпляр или привычки пивовара:
в пивоварню уходит ровно то, что задано в рецепте (PROTOCOL.md).
"""
import logging
import threading
import time
import uuid
from concurrent.futures import Future

from .energy import EnergyMeter
from .recipe import (
    BOIL_TEMP,
    MAX_ADDITIONS,
    MAX_STEPS,
    MIN_TEMP,
    MIN_WATTS,
    MODEL_MAX_WATTS,
    RECIPE_DP,
    WATTS_STEP,
    decode,
    encode,
    same_program,
    to_steps,
)

log = logging.getLogger("brewapp.brew")

# DP — PROTOCOL.md
DP_SWITCH, DP_START, DP_TIMER, DP_TEMP = "1", "2", "6", "10"
DP_MODE, DP_MANUAL_MIN, DP_MANUAL_POWER, DP_STATUS, DP_ERROR = "101", "102", "103", "104", "105"
DP_PUMP, DP_MODEL, DP_FLOW, DP_SETPOINT = "108", "109", "110", "138"
DP_CALIBRATION, DP_BOIL_COMP, DP_CONFIRM, DP_ALERT, DP_STEP = "139", "140", "142", "143", "144"
RECIPE_DP_S = str(RECIPE_DP)

STATUS = {0: "idle", 1: "paused", 2: "running"}
MODE = {0: "manual", 1: "recipe"}
ALERT = {1: "malt", 2: "mashEnd"}
READING_STEP_S = 2                   # не чаще одной точки температуры за 2 с
ENERGY_SAVE_S = 30                   # как часто сообщать и запоминать расход текущей варки
ENERGY_EMIT_S = 5                    # снимок интерфейсу, пока ТЭН работает, а DP молчат (кипячение)
# после включения пивоварня сама сбрасывает режим на ручной: команды, отправленные сразу, теряются
POWER_ON_SETTLE_S = 2
STEP_TIMEOUT_S = 10                  # ожидание эха одной пачки команд в последовательности
REACHED_MARGIN = 0.2                 # °C: шаг считается достигнутым чуть раньше уставки


def watts_from_byte(b):
    return (b - 2) * 100


class Controller:
    def __init__(self, brewery, memory, max_watts=None, reading_interval=READING_STEP_S):
        """brewery — device.Brewery (или fake.FakeBrewery); memory — state.Memory; max_watts — потолок мощности
        для модели, которой нет в MODEL_MAX_WATTS; reading_interval — как часто, с, записывать температуру."""
        self.dev = brewery
        self.memory = memory
        self.max_watts_override = max_watts
        self.reading_interval = reading_interval
        self.model = memory.get("model")                    # DP 109 приходит, только пока пивоварня в сети
        self.device_recipe_raw = memory.get("recipe_raw")   # DP 128 не входит в status — помним последний
        # программа, загруженная из приложения: знаем названия шагов и закладок. Пивоварню могли перепрограммировать
        # в Smart Life, пока агент был выключен, — тогда напоминания по ней разошлись бы с таймерами пивоварни
        active = memory.get("active")
        self.active = active if active and active.get("encoded") == self.device_recipe_raw else None
        if active and not self.active:
            memory.update(active=None)
        self.energy = EnergyMeter(memory.get("heat_capacity"),
                                  on_capacity=lambda c: memory.update(heat_capacity=round(c)))
        self.brew_id = None
        self._brew_checked = False                          # незакрытую варку проверяем при первом статусе
        self._energy_saved_at = 0.0
        self._emitted_at = 0.0
        self._last_reading = 0.0
        self._lock = threading.RLock()
        self._listeners = []
        self._timer = {"anchor_t": None, "anchor_rem": None, "counting": False}
        self._additions_fired = set()
        self._additions_pending = []     # закладки, о которых напомнили, а человек ещё не нажал «Заложил»
        self._prev = {}
        brewery.subscribe(self._on_change)

    # ── сообщения сервису ─────────────────────────────────────────────────────
    def subscribe(self, fn):
        """fn(message) — сообщение сервису: state, event, reading, brewStarted, brewUpdated, brewFinished, device
        (README.md, «Протокол»). Вызывается из потока пивоварни."""
        self._listeners.append(fn)

    def _emit(self, msg):
        for fn in self._listeners:
            try:
                fn(msg)
            except Exception:
                log.exception("ошибка в подписчике")

    def _event(self, kind, text, **extra):
        ev = {"kind": kind, "text": text, "at": time.time(), **extra}
        self._emit({"type": "event", "brewId": self.brew_id, "data": ev})

    def _emit_state(self):
        self._emitted_at = time.monotonic()
        self._emit({"type": "state", "data": self.snapshot()})

    def hello(self):
        """Что сервису знать сразу после подключения."""
        with self._lock:
            # незакрытая варка из памяти, пока пивоварня не сказала, идёт ли программа, — ещё не закрыта
            brew = self.brew_id if self._brew_checked else (self.memory.get("brew") or {}).get("id")
            return {"model": self._model(), "limits": self.limits(), "brewId": brew,
                    "activeRecipeId": self.active["program"].get("recipeId") if self.active else None}

    # ── реакция на DP ─────────────────────────────────────────────────────────
    def _on_change(self, changed):
        with self._lock:
            dps = self.dev.dps
            now = time.monotonic()
            prev = self._prev

            if RECIPE_DP_S in changed:
                self._recipe_seen(changed[RECIPE_DP_S])
            if DP_MODEL in changed:
                self.model = str(changed[DP_MODEL])
                self.memory.update(model=self.model)
                self._emit({"type": "device", "model": self.model, "limits": self.limits()})

            # запуск программы — смена состояния «простой → работа». По DP start судить нельзя: пивоварня
            # не снимает его ни в конце программы, ни при выключении, и новый старт его не меняет.
            # prev пуст при первом снимке после подключения — это не «запуск», а уже идущее состояние
            started_from_idle = bool(prev) and changed.get(DP_STATUS) == 2 and not prev.get(DP_STATUS)
            if DP_STEP in changed or started_from_idle:      # новый шаг или новый запуск; после паузы — нет
                self._timer = {"anchor_t": None, "anchor_rem": None, "counting": False}
            # в конце программы шаг → 0: сработавшие закладки помним — «в конце кипячения» проверяется по событию end
            if (changed.get(DP_STEP)) or started_from_idle:
                self._additions_fired = set()
            if started_from_idle:
                self.energy.reset()
                self._additions_pending = []
            self._track_brew(started_from_idle)
            self._track_timer(changed, now)
            self._track_energy(now, with_temp=DP_TEMP in changed)
            self._track_events(changed, prev)

            if DP_TEMP in changed and self.dev.online and now - self._last_reading >= self.reading_interval:
                self._last_reading = now
                # цель — только пока программа идёт: в ожидании уставка просто лежит в пивоварне
                target = self._current_target() if dps.get(DP_STATUS) in (1, 2) else None
                self._emit({"type": "reading", "brewId": self.brew_id, "at": time.time(), "temp": dps[DP_TEMP] / 10,
                            "target": target, "step": dps.get(DP_STEP) or None,
                            "status": STATUS.get(dps.get(DP_STATUS))})
            self._check_additions()
            self._prev = dict(dps)
            self._emit_state()

    def _track_brew(self, started_from_idle):
        dps = self.dev.dps
        if not self._brew_checked and DP_STATUS in dps:
            self._brew_checked = True
            open_brew = self.memory.get("brew")
            in_program = dps.get(DP_MODE) == 1 and dps.get(DP_STATUS) in (1, 2)
            if open_brew and in_program:
                self.brew_id = open_brew["id"]               # агент перезапустили посреди варки
                self.energy.reset(open_brew.get("energyWh") or 0.0)
            elif open_brew:
                self._emit({"type": "brewFinished", "id": open_brew["id"], "status": "stopped", "at": time.time(),
                            "energyWh": open_brew.get("energyWh") or 0.0})
                self.memory.update(brew=None)
            elif in_program:
                self._start_brew()                           # программа шла без записи — пишем хотя бы с этого момента
        if started_from_idle and dps.get(DP_MODE) == 1 and self.brew_id is None:
            self._start_brew()

    def _start_brew(self):
        program = self.active["program"] if self.active else None
        self.brew_id = str(uuid.uuid4())
        self.memory.update(brew={"id": self.brew_id, "energyWh": 0.0})
        self._emit({"type": "brewStarted", "id": self.brew_id, "at": time.time(),
                    "name": program["name"] if program else "Рецепт из Smart Life",
                    "recipeId": program.get("recipeId") if program else None, "recipe": self._recipe_view()})

    def _finish_brew(self, status):
        if self.brew_id:
            self._emit({"type": "brewFinished", "id": self.brew_id, "status": status, "at": time.time(),
                        "energyWh": round(self.energy.wh, 1)})
            self.memory.update(brew=None)
            self.brew_id = None

    # ── расход электричества (оценка, energy.py) ──────────────────────────────
    def _energy_phase(self):
        d = self.dev.dps
        if not self.dev.online or d.get(DP_STATUS) != 2:
            return "off"
        target = self._current_target()
        counting = self._timer["counting"]
        if not counting and not d.get(DP_ALERT) and target is not None \
                and d.get(DP_TEMP, 0) / 10 < target - REACHED_MARGIN:
            return "heating"
        if d.get(DP_MODE) == 1:
            step = self._current_step()
            boil = bool(step and step.is_boil)
        else:
            boil = (d.get(DP_SETPOINT) or 0) >= round(BOIL_TEMP * 10)
        return "boil" if boil and counting else "hold"

    def _heater_watts(self):
        d = self.dev.dps
        if d.get(DP_MODE) == 0:
            return watts_from_byte(d[DP_MANUAL_POWER]) if d.get(DP_MANUAL_POWER) else 0
        step = self._current_step()
        return step.watts if step else 0

    def _track_energy(self, now, with_temp):
        temp = self.dev.dps.get(DP_TEMP)
        self.energy.update(now, self._energy_phase(), self._heater_watts(),
                           temp / 10 if with_temp and temp is not None and self.dev.online else None,
                           self._current_target())
        if self.brew_id and now - self._energy_saved_at >= ENERGY_SAVE_S:
            self._energy_saved_at = now
            wh = round(self.energy.wh, 1)
            self.memory.update(brew={"id": self.brew_id, "energyWh": wh})
            self._emit({"type": "brewUpdated", "id": self.brew_id, "energyWh": wh})

    def _track_timer(self, changed, now):
        """Оценка остатка шага в секундах. DP 6 — минуты с округлением вверх, отсчёт идёт
        с момента достижения температуры шага (PROTOCOL.md)."""
        dps, t = self.dev.dps, self._timer
        value = dps.get(DP_TIMER)
        running = dps.get(DP_STATUS) == 2
        if value is None:
            return
        if DP_TIMER in changed and self._prev.get(DP_TIMER) == value + 1:
            t.update(anchor_t=now, anchor_rem=value * 60, counting=running)      # точная синхронизация
            return
        if not running and t["counting"]:                                        # пауза — замораживаем
            t.update(anchor_rem=self._remaining(now), anchor_t=now, counting=False)
            return
        if running and not t["counting"]:
            target = self._current_target()
            # пока висит подсказка (засыпь солода), контроллер отсчёт не начинает
            reached = (target is not None and not dps.get(DP_ALERT)
                       and dps.get(DP_TEMP, 0) / 10 >= target - REACHED_MARGIN)
            if t["anchor_rem"] is not None or reached:                           # продолжение или старт отсчёта
                t.update(anchor_t=now, anchor_rem=t["anchor_rem"] if t["anchor_rem"] is not None else value * 60,
                         counting=True)

    def _remaining(self, now=None):
        t, value = self._timer, self.dev.dps.get(DP_TIMER)
        if value is None:
            return None
        if t["anchor_rem"] is None:
            return value * 60
        rem = t["anchor_rem"] - ((now or time.monotonic()) - t["anchor_t"] if t["counting"] else 0)
        return max((value - 1) * 60, min(value * 60, rem)) if value else 0

    def _current_target(self):
        dps = self.dev.dps
        if dps.get(DP_MODE) == 0:
            sp = dps.get(DP_SETPOINT)
            return sp / 10 if sp else None
        step = self._current_step()
        if not step:
            return None
        return 100.0 if step.is_boil else step.temp

    def _current_step(self):
        steps = self.device_steps()
        n = self.dev.dps.get(DP_STEP) or 0
        return steps[n - 1] if 0 < n <= len(steps) else None

    def _track_events(self, changed, prev):
        if DP_ALERT in changed:
            a = changed[DP_ALERT]
            if a:
                text = {1: "Засыпь солода", 2: "Конец затирания"}.get(a, f"Подсказка {a}")
                self._event("alert", text, alert=ALERT.get(a, str(a)))
            elif prev.get(DP_ALERT):
                self._event("alertCleared", "Подсказка подтверждена")
        if changed.get(DP_STEP):
            step = self._current_step()
            name = (self._active_step_name(changed[DP_STEP]) or
                    ("Кипячение" if step and step.is_boil else f"{step.temp:g} °C" if step else ""))
            self._event("step", f"Шаг {changed[DP_STEP]}: {name}".strip(), step=changed[DP_STEP])
        if DP_SWITCH in changed and not changed[DP_SWITCH] and prev.get(DP_SWITCH):
            # по окончании программы контроллер сам выключается при таймере 0 (PROTOCOL.md)
            if prev.get(DP_STEP) and prev.get(DP_TIMER) == 0:
                self._fire_flameout(prev[DP_STEP])
                self._event("end", "Программа завершена")
                self._finish_brew("finished")
            else:
                self._event("powerOff", "Пивоварня выключена")
                self._finish_brew("stopped")
        if changed.get(DP_ERROR):
            self._event("error", f"Код ошибки {changed[DP_ERROR]}")
        if not changed and not self.dev.online:
            self._event("offline", "Связь с пивоварней потеряна")
        elif not changed and self.dev.online:
            self._event("online", "Пивоварня на связи")

    def _check_additions(self):
        step = self._current_step()
        rem = self._remaining()
        if not step or not step.is_boil or rem is None or not self._timer["counting"]:
            return
        n = self.dev.dps.get(DP_STEP)
        for slot in self.addition_schedule():
            if (n, slot["minutes"]) not in self._additions_fired and rem <= slot["minutes"] * 60:
                self._fire_addition(n, slot)

    def _fire_flameout(self, n):
        """Таймер 0 и выключение пивоварня может прислать одним пакетом — закладки «в конце кипячения» не теряем."""
        for slot in self.addition_schedule():
            if slot["minutes"] == 0 and (n, 0) not in self._additions_fired:
                self._fire_addition(n, slot)

    def _fire_addition(self, n, slot):
        self._additions_fired.add((n, slot["minutes"]))
        self._additions_pending.append(slot)
        when = f"за {slot['minutes']} мин" if slot["minutes"] else "в конце кипячения"
        self._event("addition", f"Закладка {when}: {slot['label']}", addition=slot)

    def ack_addition(self, minutes):
        """Человек всё заложил — снять напоминание. KeyError, если такой закладки не ждём."""
        with self._lock:
            slot = next((a for a in self._additions_pending if a["minutes"] == minutes), None)
            if slot is None:
                raise KeyError(minutes)
            self._additions_pending.remove(slot)
            self._event("added", f"Заложено: {slot['label']}", addition=slot)
            self._emit_state()

    def tick(self):
        """Вызывать раз в секунду: закладки и расход электричества идут и без новых DP."""
        with self._lock:
            now = time.monotonic()
            before = len(self._additions_fired)
            self._check_additions()
            self._track_energy(now, with_temp=False)
            if len(self._additions_fired) != before or (self.energy.watts and now - self._emitted_at >= ENERGY_EMIT_S):
                self._emit_state()

    # ── программа в пивоварне ─────────────────────────────────────────────────
    def _recipe_seen(self, raw):
        self.device_recipe_raw = raw
        self.memory.update(recipe_raw=raw)
        if self.active and self.active["encoded"] != raw:
            self.active = None                     # рецепт сменили в Smart Life — названий больше не знаем
            self.memory.update(active=None)

    def device_steps(self):
        return decode(self.device_recipe_raw) if self.device_recipe_raw else []

    def _active_step_name(self, n):
        steps = self.active["program"]["steps"] if self.active else []
        return steps[n - 1].get("name") if 0 < n <= len(steps) else None

    def _recipe_view(self):
        """Программа пивоварни для интерфейса и истории: шаги из DP 128 + названия, если она загружена из приложения."""
        steps = self.device_steps()
        if not steps:
            return None
        program = self.active["program"] if self.active else None
        names = [s.get("name") for s in program["steps"]] if program else []
        return {
            "name": program["name"] if program else None,
            "id": program.get("recipeId") if program else None,
            "steps": [{"temp": s.temp, "minutes": s.minutes, "watts": s.watts, "additions": s.additions,
                       "boil": s.is_boil, "name": names[i] if i < len(names) else None}
                      for i, s in enumerate(steps)],
        }

    def addition_schedule(self):
        """Таймеры закладок текущего (или первого) кипячения и что по каждому класть — из программы приложения."""
        steps = self.device_steps()
        n = self.dev.dps.get(DP_STEP) or 0
        idx = n - 1 if 0 < n <= len(steps) and steps[n - 1].is_boil else \
            next((i for i, s in enumerate(steps) if s.is_boil), None)
        if idx is None:
            return []
        # программа наша (совпадает с DP 128 байт в байт) — кипячение в ней одно, после пауз затирания
        if self.active:
            program_boil = next((i for i, s in enumerate(self.active["program"]["steps"]) if s.get("boil")), None)
            if idx == program_boil:
                return list(self.active["program"].get("slots") or [])
        return [{"minutes": m, "items": [], "label": "Закладка"} for m in steps[idx].additions]

    def apply_program(self, program):
        """Загруженный рецепт поправили, не меняя программы пивоварни (названия, ингредиенты), — обновить экран.
        Если программа уже другая, в пивоварне по-прежнему старая: её названия не трогаем."""
        with self._lock:
            if (self.active and program.get("recipeId") == self.active["program"].get("recipeId")
                    and same_program(program, self.active["encoded"])):
                self.active = {"program": program, "encoded": self.active["encoded"]}
                self.memory.update(active=self.active)
                self._emit_state()

    def forget(self, recipe_id):
        """Загруженный рецепт удалили — его названия больше не показываем."""
        with self._lock:
            if self.active and self.active["program"].get("recipeId") == recipe_id:
                self.active = None
                self.memory.update(active=None)
                self._emit_state()

    # ── состояние для интерфейса ──────────────────────────────────────────────
    def _model(self):
        return str(self.dev.dps.get(DP_MODEL) or self.model or "") or None

    def max_watts(self):
        return self.max_watts_override or MODEL_MAX_WATTS.get(self._model())

    def snapshot(self):
        with self._lock:
            d = self.dev.dps

            def scaled(dp):
                return d[dp] / 10 if d.get(dp) is not None else None

            return {
                "online": self.dev.online,
                "power": bool(d.get(DP_SWITCH)),
                "running": bool(d.get(DP_START)),
                "status": STATUS.get(d.get(DP_STATUS), d.get(DP_STATUS)),
                "mode": MODE.get(d.get(DP_MODE), d.get(DP_MODE)),
                "temp": scaled(DP_TEMP),
                "setpoint": scaled(DP_SETPOINT),
                "manualMinutes": d.get(DP_MANUAL_MIN),
                "manualWatts": watts_from_byte(d[DP_MANUAL_POWER]) if d.get(DP_MANUAL_POWER) else None,
                "pump": bool(d.get(DP_PUMP)),
                "flow": d.get(DP_FLOW),
                "step": d.get(DP_STEP) or 0,
                "stepTarget": self._current_target() if d.get(DP_STATUS) in (1, 2) else None,
                "timer": {"minutes": d.get(DP_TIMER), "remaining": self._remaining(),
                          "counting": self._timer["counting"], "at": time.time()},
                "alert": ALERT.get(d.get(DP_ALERT)) if d.get(DP_ALERT) else None,
                "error": d.get(DP_ERROR) or 0,
                "settings": {"calibration": scaled(DP_CALIBRATION), "boilCompensation": scaled(DP_BOIL_COMP),
                             "unit": d.get("11"), "model": self._model(), "maxWatts": self.max_watts()},
                "deviceRecipe": self._recipe_view(),
                "additions": self.addition_schedule(),
                "additionsPending": list(self._additions_pending),
                "energy": {"wh": round(self.energy.wh, 1), "watts": self.energy.watts},
            }

    def limits(self):
        return {"maxSteps": MAX_STEPS, "maxAdditions": MAX_ADDITIONS, "minTemp": MIN_TEMP, "maxTemp": 100.0,
                "boilTemp": BOIL_TEMP, "minWatts": MIN_WATTS, "maxWatts": self.max_watts(), "wattsStep": WATTS_STEP}

    # ── команды ───────────────────────────────────────────────────────────────
    def _sequence(self, *batches):
        """Пачки команд строго по очереди: следующая — только после эха предыдущей, после включения — пауза.
        Future → итог как у Brewery.write; не подтвердилась пачка — дальше не идём."""
        fut = Future()

        def run():
            for i, batch in enumerate(batches):
                try:
                    res = self.dev.write(batch).result(timeout=STEP_TIMEOUT_S)
                except Exception as e:
                    res = {"ok": False, "missing": list(map(str, batch)), "error": str(e)}
                if not res.get("ok"):
                    fut.set_result(res)
                    return
                if DP_SWITCH in batch and i < len(batches) - 1:
                    time.sleep(POWER_ON_SETTLE_S)
            fut.set_result({"ok": True, "missing": []})

        threading.Thread(target=run, name="commands", daemon=True).start()
        return fut

    def _power_on_first(self):
        return [] if self.dev.dps.get(DP_SWITCH) else [{DP_SWITCH: True}]

    def _need_watts(self, watts):
        mw = self.max_watts()
        if mw is None:
            raise ValueError("потолок мощности для этой модели неизвестен — задайте агенту MAX_WATTS")
        if not (MIN_WATTS <= watts <= mw and watts % WATTS_STEP == 0):
            raise ValueError(f"мощность {watts} W — нужно {MIN_WATTS}…{mw} кратно {WATTS_STEP}")
        return mw

    def cmd_power(self, on):
        return self.dev.write({DP_SWITCH: bool(on)})

    def cmd_manual(self, setpoint, minutes, watts):
        if not MIN_TEMP <= setpoint <= BOIL_TEMP:
            raise ValueError(f"уставка {setpoint} вне {MIN_TEMP}…{BOIL_TEMP} °C")
        if not 1 <= minutes <= 0xFFFF:
            raise ValueError(f"время {minutes} мин")
        self._need_watts(watts)
        return self._sequence(*self._power_on_first(),
                              {DP_MODE: 0, DP_SETPOINT: round(setpoint * 10), DP_MANUAL_MIN: int(minutes),
                               DP_MANUAL_POWER: watts // 100 + 2})

    def cmd_run(self, run):
        return self.dev.write({DP_START: bool(run)})

    def cmd_start_recipe(self):
        if not self.device_steps():
            raise ValueError("в пивоварне нет известного рецепта — сначала загрузите рецепт")
        # старт — только после подтверждённого режима «рецепт», иначе пивоварня запустит ручной режим
        return self._sequence(*self._power_on_first(), {DP_MODE: 1}, {DP_START: True})

    def cmd_pump(self, on):
        return self.dev.write({DP_PUMP: bool(on)})

    def cmd_flow(self, level):
        if not 0 <= level <= 10:
            raise ValueError("поток 0…10")
        return self.dev.write({DP_FLOW: int(level)})

    def cmd_settings(self, calibration=None, boil_compensation=None):
        cmds = {}
        if calibration is not None:
            if not -10 <= calibration <= 10:
                raise ValueError("калибровка −10…10 °C")
            cmds[DP_CALIBRATION] = round(calibration * 10)
        if boil_compensation is not None:
            if not 0 <= boil_compensation <= 10:
                raise ValueError("компенсация кипения 0…10 °C")
            cmds[DP_BOIL_COMP] = round(boil_compensation * 10)
        return self.dev.write(cmds)

    def cmd_confirm_alert(self):
        """Подтвердить подсказку (засыпь солода, конец затирания): запись 1 в DP 142 — пивоварня сбрасывает
        DP 143 в 0, сам 142 остаётся 0 (PROTOCOL.md). Запись 0 прямо в 143 пивоварня игнорирует."""
        if not self.dev.dps.get(DP_ALERT):
            raise ValueError("подсказки нет — подтверждать нечего")
        return self.dev.write({DP_CONFIRM: 1}, expect={DP_ALERT: 0})

    def cmd_upload(self, program):
        """Записать программу рецепта в пивоварню (программа — от сервиса, README.md, «Протокол»)."""
        if self.dev.dps.get(DP_STATUS) in (1, 2):
            raise ValueError("программа идёт — рецепт можно заменить после её окончания или выключения пивоварни")
        steps = to_steps(program)
        encoded = encode(steps, self._need_watts(max(s.watts for s in steps)))
        fut = self.dev.write({RECIPE_DP_S: encoded})

        def done(f):
            if f.result().get("ok"):
                with self._lock:
                    self.active = {"program": program, "encoded": encoded}
                    self.device_recipe_raw = encoded
                    self.memory.update(active=self.active, recipe_raw=encoded)
                    self._emit_state()
        fut.add_done_callback(done)
        return fut
