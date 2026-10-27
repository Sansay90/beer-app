"""Программа сервиса → шаги Easy Brew → блок DP 128 и обратно (PROTOCOL.md)."""
import base64

import pytest

from agent.recipe import BLOCK_SIZE, BOIL_TEMP, MAX_STEPS, Step, decode, encode, same_program, to_steps

PROGRAM = {
    "recipeId": "r1", "name": "Пилс",
    "steps": [{"name": "Белковая", "temp": 52, "minutes": 10, "watts": 1500, "boil": False},
              {"name": "Осахаривание", "temp": 65, "minutes": 60, "watts": 1500, "boil": False},
              {"name": "Кипячение", "temp": 100, "minutes": 90, "watts": 2500, "boil": True}],
    "timers": [60, 15, 5],
    "slots": [],
}


def test_to_steps_boil_gets_marker_and_timers():
    steps = to_steps(PROGRAM)
    assert [s.temp for s in steps] == [52.0, 65.0, BOIL_TEMP]
    assert [s.additions for s in steps] == [[], [], [60, 15, 5]]
    assert steps[2].is_boil and not steps[0].is_boil


def test_encode_layout():
    raw = base64.b64decode(encode(to_steps(PROGRAM), 2500))
    assert len(raw) == BLOCK_SIZE
    first = raw[1:26]
    assert int.from_bytes(first[0:2], "big") == 520            # десятые °C
    assert int.from_bytes(first[2:4], "big") == 10
    assert first[4] == 1500 // 100 + 2                          # байт мощности
    boil = raw[1 + 25 * 2:1 + 25 * 3]
    assert int.from_bytes(boil[0:2], "big") == 1001             # метка кипячения
    assert [int.from_bytes(boil[i:i + 2], "big") for i in (6, 8, 10)] == [60, 15, 5]


def test_roundtrip():
    steps = to_steps(PROGRAM)
    assert decode(encode(steps, 2500)) == steps


def test_same_program():
    raw = encode(to_steps(PROGRAM), 2500)
    assert same_program(PROGRAM, raw)
    assert not same_program({**PROGRAM, "timers": [60, 15]}, raw)
    assert not same_program(PROGRAM, None)
    assert not same_program({"steps": []}, raw)


@pytest.mark.parametrize(("steps", "error"), [
    ([], "шагов должно быть"),
    ([Step(65, 60, 1500)] * (MAX_STEPS + 1), "шагов должно быть"),
    ([Step(10, 60, 1500)], "температура"),
    ([Step(65, 0, 1500)], "длительность"),
    ([Step(65, 60, 1550)], "мощность"),
    ([Step(65, 60, 2600)], "мощность"),
    ([Step(65, 60, 1500, [10])], "только на кипячении"),
    ([Step(BOIL_TEMP, 60, 2500, [10, 10])], "повторяется"),
    ([Step(BOIL_TEMP, 60, 2500, [60])], "закладка 60 мин"),
    ([Step(BOIL_TEMP, 60, 2500, list(range(1, 11)))], "больше 9"),
])
def test_encode_rejects(steps, error):
    with pytest.raises(ValueError, match=error):
        encode(steps, 2500)


def test_to_steps_rejects():
    with pytest.raises(ValueError, match="нет программы"):
        to_steps({"steps": []})
    with pytest.raises(ValueError, match="шаг 1: неполные данные"):
        to_steps({"steps": [{"temp": 65, "minutes": 60}]})
