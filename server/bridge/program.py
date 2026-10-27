"""Рецепт → программа пивоварни: паузы затирания, кипячение и закладки по его таймеру.

Рецепт — словарь в форме schemas.Recipe. Закладки берутся из ингредиентов: хмель, добавки и сахар с use = boil
(minutes — за сколько до конца кипячения), вирпул — в конце кипячения (0 мин). Таймер пивоварни есть только
у закладок строго внутри кипячения (0 < мин < длительности); о закладках в начале и в конце напоминает приложение.
"""
from .recipe import BOIL_TEMP, Step, decode

KIND_LABELS = {"hop": "Хмель", "spice": "Специи", "fining": "Осветлитель", "water": "Соли", "adjunct": "Добавка",
               "sugar": "Сахар", "equipment": "Оборудование"}
UNIT_LABELS = {"g": "г", "kg": "кг", "ml": "мл", "pcs": "шт", "pkg": "пак."}


def program_steps(recipe):
    """Шаги программы для пивоварни и экрана: паузы затирания, затем кипячение."""
    steps = [{"name": s.get("name"), "temp": s["temp"], "minutes": s["minutes"], "watts": s["watts"], "boil": False}
             for s in recipe.get("mash") or []]
    boil = recipe.get("boil")
    if boil:
        steps.append({"name": "Кипячение", "temp": BOIL_TEMP, "minutes": boil["minutes"], "watts": boil["watts"],
                      "boil": True})
    return steps


def boil_items(recipe):
    """Что класть в кипячение и когда — список Addition-словарей, от ранних к поздним."""
    boil = recipe.get("boil")
    if not boil:
        return []
    items = []

    def add(src, kind, unit, at):
        items.append({"minutes": at, "kind": kind, "name": src.get("name") or "", "amount": src.get("amount"),
                      "unit": unit})

    for h in recipe.get("hops") or []:
        if h.get("use") == "boil" and h.get("minutes") is not None:
            add(h, "hop", "g", h["minutes"])
        elif h.get("use") == "whirlpool":
            add(h, "hop", "g", 0)
    for m in recipe.get("miscs") or []:
        if m.get("use") == "boil" and m.get("minutes") is not None:
            add(m, m.get("kind") or "adjunct", m.get("unit") or "g", m["minutes"])
        elif m.get("use") == "whirlpool":
            add(m, m.get("kind") or "adjunct", m.get("unit") or "g", 0)
    for f in recipe.get("fermentables") or []:
        if f.get("use") == "boil" and f.get("minutes") is not None:
            add(f, "sugar", "kg", f["minutes"])
    items = [i for i in items if 0 <= i["minutes"] <= boil["minutes"]]
    return sorted(items, key=lambda i: -i["minutes"])


def device_timers(recipe):
    """Минуты, на которых пищит пивоварня: закладки строго внутри кипячения, без повторов."""
    boil = recipe.get("boil")
    if not boil:
        return []
    return sorted({i["minutes"] for i in boil_items(recipe) if 0 < i["minutes"] < boil["minutes"]}, reverse=True)


def addition_slots(recipe):
    """Напоминания на кипячении: по одному на минуту, со всем, что на неё приходится."""
    items = boil_items(recipe)
    minutes = sorted({i["minutes"] for i in items}, reverse=True)
    return [{"minutes": m, "items": (at := [i for i in items if i["minutes"] == m]), "label": addition_label(at)}
            for m in minutes]


def to_steps(recipe):
    """Рецепт → список Step для кодирования в DP пивоварни. ValueError — программы нет или она неполная."""
    steps = []
    for i, s in enumerate(program_steps(recipe), 1):
        try:
            steps.append(Step(temp=float(s["temp"]), minutes=int(s["minutes"]), watts=int(s["watts"]),
                              additions=device_timers(recipe) if s["boil"] else []))
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"шаг {i}: неполные данные ({e})")
    if not steps:
        raise ValueError("в рецепте нет программы: ни пауз, ни кипячения")
    return steps


def same_program(recipe, raw):
    """Программа рецепта совпадает с той, что лежит в пивоварне (DP 128), — шаги, мощности и таймеры закладок."""
    try:
        return bool(raw) and to_steps(recipe) == decode(raw)
    except ValueError:
        return False


def check_boil_items(recipe):
    """ValueError, если закладка на кипячении не помещается в его длительность или кипячения нет."""
    boil = recipe.get("boil")
    sources = [*(recipe.get("hops") or []), *(recipe.get("miscs") or []), *(recipe.get("fermentables") or [])]
    for src in sources:
        if src.get("use") != "boil" or src.get("minutes") is None:
            continue
        name = src.get("name") or "закладка"
        if not boil:
            raise ValueError(f"«{name}» — на кипячении, а кипячения в программе нет")
        if not 0 <= src["minutes"] <= boil["minutes"]:
            raise ValueError(f"«{name}» за {src['minutes']} мин — кипячение длится {boil['minutes']} мин")


def addition_label(items):
    """«Hallertau 30 г, Ирландский мох 5 г, Чиллер» — для журнала и уведомлений."""
    parts = []
    for a in items:
        name = (a.get("name") or "").strip() or KIND_LABELS.get(a.get("kind"), "Закладка")
        amount = a.get("amount")
        parts.append(f"{name} {amount:g} {UNIT_LABELS.get(a.get('unit'), 'г')}" if amount else name)
    return ", ".join(parts) or "Закладка"
