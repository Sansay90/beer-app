"""Звуки интерфейса → public/sounds/*.mp3: маримба с мягкой реверберацией, мажорные интервалы.

    pip install numpy lameenc
    python scripts/sounds.py

Каждый сигнал звучит один раз; повтор до подтверждения делает плагин уведомлений.
"""
from pathlib import Path

import lameenc
import numpy as np

SR = 44100
OUT = Path(__file__).resolve().parent.parent / "public" / "sounds"

# частоты нот, Гц
C5, E5, G5, A4, F4, GS5, B5, C6 = 523.25, 659.25, 783.99, 440.0, 349.23, 830.61, 987.77, 1046.5


def marimba(freq, dur):
    """Деревянная пластина: основной тон + обертон ~3.93× (быстро гаснет) + призвук удара."""
    t = np.arange(int(SR * dur)) / SR
    x = np.sin(2 * np.pi * freq * t) * np.exp(-t * 3.0)
    x += 0.32 * np.sin(2 * np.pi * freq * 3.93 * t) * np.exp(-t * 13)
    x += 0.07 * np.sin(2 * np.pi * freq * 9.2 * t) * np.exp(-t * 45)
    return x * np.minimum(1.0, t / 0.004)                 # атака 4 мс — без щелчка


def comb(x, delay, gain):
    y = x.copy()
    for i in range(delay, len(y)):
        y[i] += gain * y[i - delay]
    return y


def allpass(x, delay, gain):
    y = np.zeros_like(x)
    for i in range(len(x)):
        d = x[i - delay] if i >= delay else 0.0
        yd = y[i - delay] if i >= delay else 0.0
        y[i] = -gain * x[i] + d + gain * yd
    return y


def reverb(x, mix=0.2):
    """Небольшая комната (Шрёдер): 4 гребенчатых фильтра параллельно + 2 всепропускающих."""
    wet = sum(comb(x, int(SR * d), g) for d, g in ((0.0297, 0.77), (0.0371, 0.75), (0.0411, 0.73), (0.0437, 0.71))) / 4
    for d, g in ((0.005, 0.7), (0.0017, 0.7)):
        wet = allpass(wet, int(SR * d), g)
    return (1 - mix) * x + mix * wet


def render(notes, length, level):
    """notes: [(частота, начало с, громкость)]."""
    out = np.zeros(int(SR * length))
    for freq, start, vel in notes:
        s = int(SR * start)
        tone = marimba(freq, length - start) * vel
        out[s:s + len(tone)] += tone[: len(out) - s]
    out = reverb(out)
    fade = int(SR * 0.08)
    out[-fade:] *= np.linspace(1, 0, fade)
    return out / np.max(np.abs(out)) * level


SOUNDS = {
    # подсказка пивоварни — восходящее ми-мажорное трезвучие
    "alert": render([(E5, 0, 1), (GS5, 0.16, 0.9), (B5, 0.32, 0.85)], 1.7, 0.7),
    # закладка — «динь-дон»
    "addition": render([(G5, 0, 1), (E5, 0.3, 0.9)], 1.5, 0.7),
    # конец программы — нисходящее до-мажорное трезвучие и аккорд
    "end": render([(C6, 0, 1), (G5, 0.2, 0.9), (E5, 0.4, 0.85), (C5, 0.6, 0.85),
                   (C5, 1.0, 0.45), (E5, 1.0, 0.4), (G5, 1.0, 0.4)], 2.8, 0.7),
    # ошибка, потеря связи — две низкие ноты, тише остальных
    "problem": render([(A4, 0, 1), (F4, 0.28, 0.9)], 1.4, 0.5),
}


def to_mp3(x):
    enc = lameenc.Encoder()
    enc.set_bit_rate(96)
    enc.set_in_sample_rate(SR)
    enc.set_channels(1)
    enc.set_quality(2)
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()
    return enc.encode(pcm) + enc.flush()


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, wave in SOUNDS.items():
        path = OUT / f"{name}.mp3"
        path.write_bytes(to_mp3(wave))
        print(f"{path.name}: {len(wave) / SR:.1f} с, {path.stat().st_size // 1024} КБ")
