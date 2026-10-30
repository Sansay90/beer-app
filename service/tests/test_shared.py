"""Общие примеры сервиса и интерфейса (shared/): обе реализации расчёта, программы пивоварни, пересчёта под
оборудование и расписания брожения дают одно и то же. Интерфейс проверяет себя по тем же файлам
(web/test/shared.test.ts)."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.brewery.reminders import Ferment
from app.models import from_unix
from app.recipes.calc import calc_recipe, targets
from app.recipes.program import addition_slots, device_timers, program_steps
from app.recipes.scale import scale_recipe

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


def same(got, expected, path=""):
    """Глубокое сравнение: числа — приблизительно, остальное — точно."""
    if isinstance(expected, dict):
        assert isinstance(got, dict) and got.keys() == expected.keys(), path
        for k, v in expected.items():
            same(got[k], v, f"{path}.{k}")
    elif isinstance(expected, list):
        assert isinstance(got, list) and len(got) == len(expected), path
        for i, v in enumerate(expected):
            same(got[i], v, f"{path}[{i}]")
    elif isinstance(expected, float):
        assert got == pytest.approx(expected, rel=1e-9), path
    else:
        assert got == expected, path


@pytest.mark.parametrize("case", cases("scale-cases.json"))
def test_scale(case):
    same(scale_recipe(case["recipe"], case["to"]["volume"], case["to"]["efficiency"]), case["expected"])


def test_targets_are_the_saved_subset():
    case = json.loads((SHARED / "calc-cases.json").read_text(encoding="utf-8"))[0]
    assert targets(case["recipe"]) == {k: case["expected"][k] for k in ("og", "fg", "ibu", "ebc", "abv")}


@pytest.mark.parametrize("case", cases("ferment-cases.json"))
def test_ferment(case):
    entries = [SimpleNamespace(kind=e["kind"], at=from_unix(e["at"]), value=e["value"]) for e in case["entries"]]
    got = Ferment(case["plan"], from_unix(case["start"]), entries, from_unix(case["now"])).view()
    assert _close(got, case["expected"]), (got, case["expected"])


def _close(got, expected):
    """Глубокое сравнение: числа — приблизительно."""
    if isinstance(expected, dict):
        return got.keys() == expected.keys() and all(_close(got[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return len(got) == len(expected) and all(_close(g, e) for g, e in zip(got, expected, strict=True))
    if isinstance(expected, float):
        return got == pytest.approx(expected)
    return got == expected
