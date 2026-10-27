"""Оценка расхода электричества ТЭНом (точность ±20–30 %): пивоварня потребление не сообщает.

- нагрев до цели и кипячение — ТЭН работает непрерывно: мощность шага × время;
- выдержка на паузе — ТЭН включается, только чтобы компенсировать остывание:
  теплоёмкость бака с содержимым × сумма подъёмов температуры (потери во время самих
  включений не видны — оценка на выдержке занижена на долю времени работы ТЭНа).
  Подъёмы выше цели не считаются: там ТЭН выключен, это инерция после нагрева;
- пауза программы, ожидание, нет связи — 0.

Теплоёмкость определяется по скорости нагрева на этой же варке: C = мощность / (dT/dt).
Потери на нагреве её замедляют, поэтому C выходит завышенной — это отчасти компенсирует недосчёт
на выдержке. Насос и электроника (десятки ватт) не считаются.
"""

LAG_S = 90                 # инерция ТЭНа и датчика: первые 90 с нагрева и после него — не показательны
ABOVE_TARGET_K = 0.3       # выше цели на столько — ТЭН точно выключен
MIN_RAMP_S = 180           # нагрев короче — скорость не измеряем
MIN_RAMP_K = 3.0
DEFAULT_CAPACITY = 130_000  # Дж/К ≈ 30 л воды с баком — пока своей оценки нет


class EnergyMeter:
    def __init__(self, heat_capacity=None, on_capacity=None):
        self.wh = 0.0
        self.watts = 0                       # оценка мощности ТЭНа сейчас
        self.capacity = heat_capacity        # Дж/К; None — ещё не измерена
        self._on_capacity = on_capacity      # колбэк: новая теплоёмкость — сохранить
        self._last_t = None
        self._last_temp = None
        self._ramp = None
        self._heated_until = None            # конец последнего нагрева — для отсева инерционного перелёта

    def reset(self, wh=0.0):
        self.wh = wh

    def update(self, now, phase, watts, temp, target=None):
        """now — монотонные секунды; phase: 'off' | 'heating' | 'boil' | 'hold'; watts — мощность шага; temp — °C;
        target — цель шага, °C. Вызывать на каждом тике и при каждой новой температуре."""
        dt = 0.0 if self._last_t is None else max(0.0, now - self._last_t)
        self._last_t = now

        if phase in ("heating", "boil") and watts:
            self.wh += watts * dt / 3600
            self.watts = watts
            self._heated_until = now
        else:
            self.watts = 0

        rose = temp is not None and self._last_temp is not None and temp > self._last_temp
        after_heating = self._heated_until is not None and now - self._heated_until < LAG_S
        above_target = target is not None and temp is not None and temp > target + ABOVE_TARGET_K
        if phase == "hold" and rose and not after_heating and not above_target:
            self.wh += (self.capacity or DEFAULT_CAPACITY) * (temp - self._last_temp) / 3600

        self._track_ramp(now, phase, watts, temp)
        if temp is not None:
            self._last_temp = temp

    def _track_ramp(self, now, phase, watts, temp):
        if phase == "heating" and watts and temp is not None:
            r = self._ramp
            if r is None or r["watts"] != watts:
                self._ramp = {"start": now, "watts": watts, "t0": None, "T0": None, "t1": None, "T1": None}
                return
            if r["t0"] is None:
                if now - r["start"] >= LAG_S:
                    r["t0"], r["T0"] = now, temp
                return
            r["t1"], r["T1"] = now, temp
            return
        r, self._ramp = self._ramp, None
        if r and r["t1"] and r["t1"] - r["t0"] >= MIN_RAMP_S and r["T1"] - r["T0"] >= MIN_RAMP_K:
            self.capacity = r["watts"] / ((r["T1"] - r["T0"]) / (r["t1"] - r["t0"]))
            if self._on_capacity:
                self._on_capacity(self.capacity)
