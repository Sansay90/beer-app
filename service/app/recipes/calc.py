"""Показатели рецепта по ингредиентам. Интерфейс считает их на лету (web/app/utils/calc.ts), сервис — при сохранении,
и сохраняет свои: правила одни, менять вместе; общие примеры обеих реализаций — shared/calc-cases.json.

OG — экстракт засыпи с учётом эффективности на объём после кипячения, FG — по сбраживанию дрожжей, ABV — по всему
сбраживаемому и FG, IBU — Tinseth, цвет — Morey. Сахар сбраживается целиком, где бы его ни добавили; добавленное
на брожении в OG не входит, а в крепость — входит. Упрощения: выход экстракта — средний по типу и цвету сырья
(справочника пока нет); IBU — по OG, вирпул и сухое охмеление горечи не дают (как у Tinseth).
"""
import math

# выход экстракта, % массы — средние значения по типу сырья; у солода зависит от цвета (yield_of)
YIELD = {"grain": 80, "adjunct": 75, "sugar": 100, "extract": 95}
DEFAULT_EFFICIENCY = 75
DEFAULT_ATTENUATION = 75
LB_PER_KG = 2.20462
L_PER_GAL = 3.78541


def _or(value, default):
    """Как ?? в TS: подставить default только вместо None — ноль остаётся нулём."""
    return default if value is None else value


# ── пивные величины (web/app/utils/beer.ts) ──────────────────────────────────
def plato_from_sg(sg):
    return -616.868 + 1111.14 * sg - 630.272 * sg ** 2 + 135.997 * sg ** 3


def sg_from_plato(p):
    return 1 + p / (258.6 - (p / 258.2) * 227.1)


def abv_of(og, fg):
    """Крепость, % об., по начальной и конечной плотности."""
    if not og or not fg or fg >= og:
        return None
    return ((76.08 * (og - fg)) / (1.775 - og)) * (fg / 0.794)


# ── экстракт и плотность ─────────────────────────────────────────────────────
def yield_of(f):
    """Солод: светлый ~80 %, карамельный и специальный ~75 %, жжёный ~60 % (PPG 1.037 / 1.034 / 1.028)."""
    kind = _or(f.get("kind"), "grain")
    if kind != "grain":
        return YIELD[kind]
    ebc = _or(f.get("ebc"), 0)
    return 60 if ebc >= 400 else 75 if ebc >= 50 else 80


def in_wort(f):
    """Сырьё, которое попадает в сусло до брожения."""
    return f.get("use") != "fermentation"


def fully_fermentable(f):
    """Сахар сбраживается целиком; остальное — на степень сбраживания дрожжей."""
    return f.get("kind") == "sugar"


def mashed(f):
    """Затирается — тогда работает эффективность; сахар и экстракт растворяются целиком."""
    return _or(f.get("use"), "mash") == "mash" and _or(f.get("kind"), "grain") != "sugar" and f.get("kind") != "extract"


def extract_of(f, efficiency):
    """Экстракт, кг, который строка засыпи отдаст суслу."""
    share = (yield_of(f) / 100) * (efficiency / 100 if mashed(f) else 1)
    return _or(f.get("amount"), 0) * share


def sg_from_extract(kg, litres):
    """Плотность (SG) сусла объёмом litres, в котором kg экстракта."""
    p = (kg / litres) * 100
    for _ in range(8):
        p = (kg * 100) / (litres * sg_from_plato(p))
    return sg_from_plato(p)


# ── горечь и цвет ────────────────────────────────────────────────────────────
def boil_time(h, boil_minutes):
    """Минуты кипячения, которые дают горечь: закладка на кипячении или в первое сусло."""
    if h.get("use") == "first_wort":
        return _or(boil_minutes, 0)
    if _or(h.get("use"), "boil") == "boil":
        return _or(h.get("minutes"), 0)
    return 0


def hop_ibu(h, og, litres, boil_minutes):
    t = boil_time(h, boil_minutes)
    if not t or not h.get("alpha") or not h.get("amount"):
        return 0
    utilisation = 1.65 * 0.000125 ** (og - 1) * ((1 - math.exp(-0.04 * t)) / 4.15)
    return utilisation * (h["alpha"] / 100) * h["amount"] * 1000 / litres


def lovibond(ebc):
    """Цвет солода EBC → °L для Morey: EBC → SRM (÷ 1.97), SRM → °L = (SRM + 0.76) / 1.3546."""
    return (ebc / 1.97 + 0.76) / 1.3546


def mcu_of(f, litres):
    """MCU Morey: °L × фунты / галлоны."""
    if not f.get("ebc") or not f.get("amount"):
        return 0
    return (f["amount"] * LB_PER_KG * lovibond(f["ebc"])) / (litres / L_PER_GAL)


def ebc_from_mcu(mcu):
    return 1.4922 * mcu ** 0.6859 * 1.97


# ── расчёт ───────────────────────────────────────────────────────────────────
def extract_where(r, keep):
    """Экстракт, кг, строк засыпи, которые отбирает keep."""
    efficiency = _or((r.get("batch") or {}).get("efficiency"), DEFAULT_EFFICIENCY)
    return sum(extract_of(f, efficiency) for f in r.get("fermentables") or [] if keep(f))


def attenuable_sg(r, litres):
    """Плотность от того, что сбраживается на степень дрожжей: всё, кроме сахара. От неё считается FG."""
    return sg_from_extract(extract_where(r, lambda f: not fully_fermentable(f)), litres)


def calc_recipe(r):
    """r — рецепт в форме Recipe (recipes/schemas.py). Показатели, которых не посчитать, — None."""
    litres = (r.get("batch") or {}).get("volume")
    yeast = next((y for y in r.get("yeasts") or [] if y.get("attenuation") is not None), None)
    attenuation = yeast["attenuation"] if yeast else DEFAULT_ATTENUATION
    out = {"og": None, "fg": None, "abv": None, "ibu": None, "ebc": None, "attenuation": attenuation,
           "defaultAttenuation": yeast is None}
    if not litres:
        return out

    fermentables = r.get("fermentables") or []
    wort = extract_where(r, in_wort)
    if wort > 0:
        out["og"] = sg_from_extract(wort, litres)
        out["fg"] = 1 + (attenuable_sg(r, litres) - 1) * (1 - attenuation / 100)
        # крепость — со всем сбраживаемым, и с сахаром, добавленным на брожении
        out["abv"] = abv_of(sg_from_extract(extract_where(r, lambda f: True), litres), out["fg"])
    hops = r.get("hops") or []
    if hops:
        boil_minutes = (r.get("boil") or {}).get("minutes")
        out["ibu"] = sum(hop_ibu(h, _or(out["og"], 1.05), litres, boil_minutes) for h in hops)
    mcu = sum(mcu_of(f, litres) for f in fermentables)
    if mcu > 0:
        out["ebc"] = ebc_from_mcu(mcu)
    return out


def targets(r):
    """Показатели для сохранения в рецепте (Targets): OG, FG, IBU, цвет, крепость."""
    c = calc_recipe(r)
    return {k: c[k] for k in ("og", "fg", "ibu", "ebc", "abv")}
