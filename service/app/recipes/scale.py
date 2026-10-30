"""Рецепт под другое оборудование: то же пиво — OG, горечь, цвет, крепость — на другом объёме и при другой
эффективности. Интерфейс считает то же для предпросмотра (web/app/utils/scale.ts): правила одни, менять вместе;
общие примеры обеих реализаций — shared/scale-cases.json.

Объём меняет всё, что кладут в сусло, пропорционально; эффективность — только то, что затирается (сахар
и экстракт растворяются целиком). Хмель — по объёму: при той же OG использование то же, значит та же горечь;
сухое охмеление и вирпул — те же граммы на литр. Соли в затор — по засыпи (заторная вода — гидромодуль × засыпь),
в промывку — по объёму. Дрожжи: пачки — по объёму с округлением вверх, граммы — пропорционально. Паузы, кипячение,
гидромодуль, профиль воды и брожение — без изменений. Показатели пересчитываются по новым количествам (calc.py).
Нет объёма у рецепта или у оборудования — по объёму не пересчитывается, только по эффективности.
"""
import copy
import math

from .calc import DEFAULT_EFFICIENCY, mashed, targets

WHOLE = ("pkg", "pcs")          # штучное: пачки дрожжей, таблетки — целое вверх


def rounded(x, digits):
    """Половина — вверх, как Math.round в интерфейсе (round в Python — к чётному)."""
    k = 10 ** digits
    return math.floor(x * k + 0.5) / k


def whole_up(x):
    """Целое вверх с допуском на плавающую точку: 2,0000000001 — это 2."""
    return math.ceil(x - 1e-9)


def factors(r, volume, efficiency):
    """(по объёму, по засыпи, объём, эффективность): множители для того, что кладут в сусло, и для того,
    что затирается; объём и эффективность партии."""
    b = r.get("batch") or {}
    v1, e1 = b.get("volume"), b.get("efficiency")
    v2, e2 = volume or v1, efficiency or e1          # ни у рецепта, ни у оборудования — остаётся пустой
    kv = v2 / v1 if v1 and v2 else 1.0
    return kv, kv * (e1 or DEFAULT_EFFICIENCY) / (e2 or DEFAULT_EFFICIENCY), v2, e2


def scaled(amount, k, digits):
    return None if amount is None else rounded(amount * k, digits)


def whole(amount, k):
    return None if amount is None else (whole_up(amount * k) if amount > 0 else 0)


def scale_recipe(r, volume, efficiency):
    """Копия рецепта r (форма Recipe, recipes/schemas.py) под объём volume (л после кипячения) и эффективность
    efficiency, %. Те же объём и эффективность — копия без изменений."""
    kv, kg, v2, e2 = factors(r, volume, efficiency)
    out = copy.deepcopy(r)
    out["batch"] = {**(r.get("batch") or {}), "volume": v2, "efficiency": e2}
    if kv != 1 or kg != 1:
        for f in out.get("fermentables") or []:
            f["amount"] = scaled(f.get("amount"), kg if mashed(f) else kv, 3)
        for h in out.get("hops") or []:
            h["amount"] = scaled(h.get("amount"), kv, 1)
        for m in out.get("miscs") or []:
            unit = m.get("unit") or "g"
            m["amount"] = (whole(m.get("amount"), kv) if unit in WHOLE
                           else scaled(m.get("amount"), kv, 3 if unit == "kg" else 1))
        for y in out.get("yeasts") or []:
            y["amount"] = (whole(y.get("amount"), kv) if (y.get("unit") or "pkg") in WHOLE
                           else scaled(y.get("amount"), kv, 1))
        for a in (out.get("water") or {}).get("additions") or []:
            a["amount"] = scaled(a.get("amount"), kg if (a.get("target") or "mash") == "mash" else kv, 2)
    out["targets"] = targets(out)
    return out
