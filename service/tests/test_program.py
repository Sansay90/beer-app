"""Рецепт → программа пивоварни и напоминания о закладках (recipes/program.py)."""
import pytest

from app.brewery.hub import DEFAULT_LIMITS
from app.errors import Invalid
from app.recipes.program import (
    addition_label,
    addition_slots,
    boil_items,
    build_program,
    check_boil_items,
    check_program,
    device_timers,
    program_steps,
)

RECIPE = {
    "name": "Пилс",
    "mash": [{"name": "Осахаривание", "temp": 65, "minutes": 60, "watts": 1500}],
    "boil": {"minutes": 60, "watts": 2500},
    "hops": [{"name": "Saaz", "amount": 30, "use": "boil", "minutes": 60},
             {"name": "Saaz", "amount": 20, "use": "boil", "minutes": 15},
             {"name": "Saaz", "amount": 40, "use": "whirlpool", "minutes": 20},
             {"name": "Citra", "amount": 50, "use": "dry_hop", "day": 5}],
    "miscs": [{"name": "Ирландский мох", "kind": "fining", "amount": 5, "unit": "g", "use": "boil", "minutes": 15},
              {"name": "Чиллер", "kind": "equipment", "use": "boil", "minutes": 10}],
    "fermentables": [{"name": "Сахар", "kind": "sugar", "amount": 0.5, "use": "boil", "minutes": 5}],
}


def test_steps():
    assert program_steps(RECIPE) == [
        {"name": "Осахаривание", "temp": 65, "minutes": 60, "watts": 1500, "boil": False},
        {"name": "Кипячение", "temp": 100.0, "minutes": 60, "watts": 2500, "boil": True},
    ]
    assert program_steps({"mash": [], "boil": None}) == []


def test_boil_items_and_timers():
    minutes = [(i["minutes"], i["kind"], i["name"]) for i in boil_items(RECIPE)]
    assert minutes == [(60, "hop", "Saaz"), (15, "hop", "Saaz"), (15, "fining", "Ирландский мох"),
                       (10, "equipment", "Чиллер"), (5, "sugar", "Сахар"), (0, "hop", "Saaz")]
    assert device_timers(RECIPE) == [15, 10, 5]           # строго внутри кипячения: 60 и 0 — начало и конец


def test_slots():
    slots = {s["minutes"]: s["label"] for s in addition_slots(RECIPE)}
    assert slots == {60: "Saaz 30 г", 15: "Saaz 20 г, Ирландский мох 5 г", 10: "Чиллер", 5: "Сахар 0.5 кг",
                     0: "Saaz 40 г (вирпул 20 мин)"}
    program = build_program("r1", RECIPE)
    assert program["recipeId"] == "r1" and program["name"] == "Пилс" and program["timers"] == [15, 10, 5]


def test_label_fallbacks():
    assert addition_label([{"kind": "spice"}, {"name": " ", "kind": "water", "amount": 2}]) == "Специи, Соли 2 г"
    assert addition_label([]) == "Закладка"


@pytest.mark.parametrize(("change", "error"), [
    ({"mash": [], "boil": None}, "нет программы"),
    ({"mash": [{"temp": 65, "minutes": 10, "watts": 1500}] * 9}, "шагов должно быть"),
    ({"mash": [{"temp": 10, "minutes": 10, "watts": 1500}]}, "температура 10"),
    ({"mash": [{"temp": 65, "minutes": 0, "watts": 1500}]}, "длительность 0"),
    ({"mash": [{"temp": 65, "minutes": 10, "watts": 1550}]}, "мощность 1550"),
    ({"mash": [{"temp": 65, "minutes": 10, "watts": 50}]}, "мощность 50"),
])
def test_check_program(change, error):
    with pytest.raises(Invalid, match=error):
        check_program(build_program("", {**RECIPE, **change}), DEFAULT_LIMITS)


def test_check_program_limits():
    check_program(build_program("", RECIPE), DEFAULT_LIMITS)
    with pytest.raises(Invalid, match="мощность 2500"):
        check_program(build_program("", RECIPE), {**DEFAULT_LIMITS, "maxWatts": 2000})
    with pytest.raises(Invalid, match="больше 2 времён"):
        check_program(build_program("", RECIPE), {**DEFAULT_LIMITS, "maxAdditions": 2})


def test_check_boil_items():
    check_boil_items(RECIPE)
    with pytest.raises(Invalid, match="кипячения в программе нет"):
        check_boil_items({**RECIPE, "boil": None})
    with pytest.raises(Invalid, match="за 70 мин"):
        check_boil_items({**RECIPE, "hops": [{"name": "Saaz", "use": "boil", "minutes": 70}]})
    with pytest.raises(Invalid, match="укажите, за сколько минут"):
        check_boil_items({**RECIPE, "hops": [{"name": "Saaz", "amount": 20}]})     # use по умолчанию — кипячение
    check_boil_items({**RECIPE, "hops": [{"name": "Citra", "use": "dry_hop", "day": 3}]})
