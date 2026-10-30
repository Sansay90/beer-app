"""Пересчитать ожидания в общих примерах (calc-cases.json, program-cases.json, scale-cases.json, ferment-cases.json)
по реализации сервиса.

Запускать, только когда правило намеренно изменено в обеих реализациях: после пересчёта интерфейс должен
сойтись с новыми ожиданиями сам (web: npm run test), иначе реализации разошлись. Из папки brewapp/service:

    python ../shared/update.py
"""
import json
import os
import sys
from types import SimpleNamespace

SHARED = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(SHARED), "service"))

from app.brewery.reminders import Ferment  # noqa: E402
from app.models import from_unix  # noqa: E402
from app.recipes.calc import calc_recipe  # noqa: E402
from app.recipes.program import addition_slots, device_timers, program_steps  # noqa: E402
from app.recipes.scale import scale_recipe  # noqa: E402


def program(recipe):
    return {"steps": [{k: s[k] for k in ("temp", "minutes", "watts", "boil")} for s in program_steps(recipe)],
            "timers": device_timers(recipe),
            "slots": [{"minutes": s["minutes"], "items": s["items"]} for s in addition_slots(recipe)]}


def ferment(case):
    """Где брожение партии: идущий этап, даты и цели этапов, «пора» и «похоже, закончилось»."""
    entries = [SimpleNamespace(kind=e["kind"], at=from_unix(e["at"]), value=e["value"]) for e in case["entries"]]
    return Ferment(case["plan"], from_unix(case["start"]), entries, from_unix(case["now"])).view()


def update(name, expected):
    path = os.path.join(SHARED, name)
    with open(path, encoding="utf-8") as f:
        cases = json.load(f)
    for case in cases:
        if "recipe" not in case:
            case["expected"] = expected(case)
        else:
            case["expected"] = expected(case["recipe"], case["to"]) if "to" in case else expected(case["recipe"])
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"{name}: {len(cases)}")


if __name__ == "__main__":
    update("calc-cases.json", calc_recipe)
    update("program-cases.json", program)
    update("scale-cases.json", lambda r, to: scale_recipe(r, to["volume"], to["efficiency"]))
    update("ferment-cases.json", ferment)
