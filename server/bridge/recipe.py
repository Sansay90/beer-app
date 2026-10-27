"""Рецепт Easy Brew: кодирование в бинарный блок DP book1 и обратно.

Формат — PROTOCOL.md: байт заголовка, затем шаги по 25 байт
(температура, длительность, мощность, закладки).
В протоколе закладки хмелевые, но контроллеру всё равно, что закладывают: это таймеры с писком
за N минут до конца кипячения. Что именно класть по каждому — знает только рецепт приложения.
"""
import base64
from dataclasses import dataclass, field

BOIL_TEMP = 100.1           # 1001 в десятых °C — так приложение помечает кипячение
MIN_TEMP = 20.0
MAX_STEPS = 9              # в блоке места на 10, но контроллер отбрасывает 10-й шаг
MAX_ADDITIONS = 9          # таймеров закладок на шаг
STEP_SIZE = 25
BLOCK_SIZE = 255
MIN_WATTS = 100
# потолок мощности зависит от модели (DP 109 power_model); подтверждена только «B14» — 40 л, 2500 W
MODEL_MAX_WATTS = {"14": 2500}
RECIPE_DP = 128     # book1; book2…book9 (DP 129–136) есть в схеме Tuya, но прошивка их не принимает


@dataclass
class Step:
    temp: float                                    # °C; BOIL_TEMP — кипячение
    minutes: int
    watts: int
    additions: list = field(default_factory=list)  # таймеры закладок, мин до конца шага, без повторов

    @property
    def is_boil(self):
        return round(self.temp * 10) == round(BOIL_TEMP * 10)


def _check(steps, max_watts):
    if not 1 <= len(steps) <= MAX_STEPS:
        raise ValueError(f"шагов должно быть 1…{MAX_STEPS}, а не {len(steps)}")
    for k, s in enumerate(steps, 1):
        if not MIN_TEMP <= s.temp <= BOIL_TEMP:
            raise ValueError(f"шаг {k}: температура {s.temp} вне {MIN_TEMP}…{BOIL_TEMP}")
        if not 1 <= s.minutes <= 0xFFFF:
            raise ValueError(f"шаг {k}: длительность {s.minutes} мин")
        if not (MIN_WATTS <= s.watts <= max_watts and s.watts % 100 == 0):
            raise ValueError(f"шаг {k}: мощность {s.watts} W — нужно {MIN_WATTS}…{max_watts} кратно 100")
        if s.additions and not s.is_boil:
            raise ValueError(f"шаг {k}: закладки только на кипячении — контроллер вырезает их с пауз")
        if len(s.additions) > MAX_ADDITIONS:
            raise ValueError(f"шаг {k}: больше {MAX_ADDITIONS} времён закладок")
        if len(set(s.additions)) != len(s.additions):
            raise ValueError(f"шаг {k}: повторяется время закладки")
        for m in s.additions:
            # штатное приложение не даёт закладку, равную длительности шага
            if not 1 <= m < s.minutes:
                raise ValueError(f"шаг {k}: закладка {m} мин должна быть 1…{s.minutes - 1}")


def encode(steps, max_watts):
    """Список Step → base64-строка для записи в DP рецепта. max_watts — потолок модели."""
    _check(steps, max_watts)
    buf = bytearray(BLOCK_SIZE)
    for k, s in enumerate(steps):
        o = 1 + STEP_SIZE * k
        buf[o:o + 2] = round(s.temp * 10).to_bytes(2, "big")
        buf[o + 2:o + 4] = s.minutes.to_bytes(2, "big")
        buf[o + 4] = s.watts // 100 + 2
        for i, m in enumerate(sorted(s.additions, reverse=True)):
            buf[o + 6 + 2 * i:o + 8 + 2 * i] = m.to_bytes(2, "big")
    return base64.b64encode(bytes(buf)).decode()


def decode(value):
    """base64-строка из DP рецепта → список Step (пустые шаги пропускаются)."""
    buf = base64.b64decode(value).ljust(BLOCK_SIZE, b"\0")
    steps = []
    for k in range(MAX_STEPS):
        raw = buf[1 + STEP_SIZE * k:1 + STEP_SIZE * (k + 1)]
        if not any(raw):
            continue
        additions = [int.from_bytes(raw[i:i + 2], "big") for i in range(6, 6 + 2 * MAX_ADDITIONS, 2)]
        steps.append(Step(temp=int.from_bytes(raw[0:2], "big") / 10,
                          minutes=int.from_bytes(raw[2:4], "big"),
                          watts=(raw[4] - 2) * 100,
                          additions=[m for m in additions if m]))
    return steps
