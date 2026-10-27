"""Общие примеры сервиса и интерфейса (shared/): обе реализации расчёта и программы пивоварни дают одно и то же.
Интерфейс проверяет себя по тем же файлам (web/test/shared.test.ts)."""
import json
from pathlib import Path

import pytest

from app.recipes.calc import calc_recipe, targets
from app.recipes.program import addition_slots, device_timers, program_steps

SHARED = Path(__file__).resolve().parents[2] / "shared"


def cases(name):
    data = json.loads((SHARED / name).read_text(encoding="utf-8"))
    return [pytest.param(c, id=c["name"]) for c in data]


@pytest.mark.parametrize("case", cases("calc-cases.json"))
def test_calc(case):
    got, expected = calc_recipe(case["recipe"]), case["expected"]
    assert got.keys() == expected.keys()
    for key, value in expected.items():
        assert got[key] == (pytest.approx(value, rel=1e-9) if isinstance(value, float) else value), key


@pytest.mark.parametrize("case", cases("program-cases.json"))
def test_program(case):
    r, expected = case["recipe"], case["expected"]
    assert [{k: s[k] for k in ("temp", "minutes", "watts", "boil")} for s in program_steps(r)] == expected["steps"]
    assert device_timers(r) == expected["timers"]
    assert [{"minutes": s["minutes"], "items": s["items"]} for s in addition_slots(r)] == expected["slots"]


def test_targets_are_the_saved_subset():
    case = json.loads((SHARED / "calc-cases.json").read_text(encoding="utf-8"))[0]
    assert targets(case["recipe"]) == {k: case["expected"][k] for k in ("og", "fg", "ibu", "ebc", "abv")}
