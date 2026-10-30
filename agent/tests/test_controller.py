"""Контроллер на имитации пивоварни: команды, варка, таймер и закладки, перезапуск агента."""
import pytest

from agent.controller import Controller
from agent.state import Memory

from .conftest import eventually

PROGRAM = {
    "recipeId": "r1", "name": "Тест",
    "steps": [{"name": "Пауза", "temp": 65, "minutes": 2, "watts": 1500, "boil": False},
              {"name": "Кипячение", "temp": 100, "minutes": 3, "watts": 2500, "boil": True}],
    "timers": [2],
    "slots": [{"minutes": 2, "items": [{"minutes": 2, "kind": "hop", "name": "Хмель", "amount": 10, "unit": "g"}],
               "label": "Хмель 10 г"},
              {"minutes": 0, "items": [], "label": "Вирпул"}],
}
IDLE = {"1": False, "104": 0, "101": 0, "10": 200, "109": "14", "144": 0, "6": 0}


@pytest.fixture
def idle(brewery, ctl):
    brewery.push(IDLE)
    return ctl


def upload(ctl, program=PROGRAM):
    assert ctl.cmd_upload(program).result(timeout=2)["ok"]
    assert eventually(lambda: ctl.active is not None)


def start_program(ctl, brewery):
    upload(ctl)
    assert ctl.cmd_start_recipe().result(timeout=2)["ok"]
    brewery.push({"104": 2, "144": 1, "6": 2, "10": 640})


def test_device_and_limits(idle, recorder):
    assert recorder.of("device")[-1] == {"type": "device", "model": "14", "limits": idle.limits()}
    assert idle.limits()["maxWatts"] == 2500
    snap = idle.snapshot()
    assert snap["online"] is True and snap["temp"] == 20.0 and snap["status"] == "idle"
    assert snap["settings"]["model"] == "14"


def test_max_watts_override(brewery, memory):
    assert Controller(brewery, memory, max_watts=3000).limits()["maxWatts"] == 3000


def test_upload_remembers_program(idle, brewery, memory):
    upload(idle)
    assert "128" in brewery.writes[-1]
    assert memory.get("active")["program"]["recipeId"] == "r1"
    view = idle.snapshot()["deviceRecipe"]
    assert view["id"] == "r1" and [s["name"] for s in view["steps"]] == ["Пауза", "Кипячение"]
    assert view["steps"][1]["additions"] == [2]


def test_upload_refused_while_running(idle, brewery):
    brewery.push({"104": 2})
    with pytest.raises(ValueError, match="программа идёт"):
        idle.cmd_upload(PROGRAM)


def test_start_recipe_sequence(idle, brewery):
    with pytest.raises(ValueError, match="нет известного рецепта"):
        idle.cmd_start_recipe()
    upload(idle)
    assert idle.cmd_start_recipe().result(timeout=2)["ok"]
    assert brewery.writes[-3:] == [{"1": True}, {"101": 1}, {"2": True}]


def test_program_names_the_brew(idle, brewery, recorder):
    """Программа от «Сварить» несёт brewId — первый запуск идёт в эту партию, повторный — новой варкой."""
    upload(idle, {**PROGRAM, "brewId": "batch-1"})
    assert idle.snapshot()["deviceRecipe"]["brewId"] == "batch-1"
    assert idle.cmd_start_recipe().result(timeout=2)["ok"]
    brewery.push({"104": 2, "144": 1, "6": 2, "10": 640})
    assert recorder.of("brewStarted")[-1]["id"] == "batch-1" and idle.snapshot()["brewId"] == "batch-1"

    brewery.push({"1": False, "104": 0, "144": 0})                       # конец программы
    assert idle.cmd_start_recipe().result(timeout=2)["ok"]              # та же программа ещё раз — новая варка
    brewery.push({"104": 2, "144": 1, "6": 2, "10": 640})
    assert recorder.of("brewStarted")[-1]["id"] != "batch-1"


def test_manual_validation(idle, brewery):
    with pytest.raises(ValueError, match="уставка"):
        idle.cmd_manual(10, 5, 1000)
    with pytest.raises(ValueError, match="мощность"):
        idle.cmd_manual(65, 5, 1550)
    assert idle.cmd_manual(65, 5, 1000).result(timeout=2)["ok"]
    assert brewery.writes[-1] == {"101": 0, "138": 650, "102": 5, "103": 12}


def test_brew_with_addition_and_end(idle, brewery, recorder, memory):
    start_program(idle, brewery)
    started = recorder.of("brewStarted")
    assert len(started) == 1 and started[0]["recipeId"] == "r1" and started[0]["name"] == "Тест"
    brew_id = started[0]["id"]
    assert memory.get("brew")["id"] == brew_id

    brewery.push({"144": 2, "6": 3, "10": 1000})        # кипячение, температура достигнута — отсчёт пошёл
    brewery.push({"6": 2})                               # минута прошла — закладка «за 2 мин»
    assert [a["minutes"] for a in idle.snapshot()["additionsPending"]] == [2]
    with pytest.raises(KeyError):
        idle.ack_addition(7)
    idle.ack_addition(2)
    assert idle.snapshot()["additionsPending"] == []

    brewery.push({"6": 0})
    brewery.push({"1": False, "104": 0, "144": 0})       # конец программы: пивоварня сама выключается
    finished = recorder.of("brewFinished")
    assert finished[-1]["id"] == brew_id and finished[-1]["status"] == "finished"
    assert memory.get("brew") is None and idle.brew_id is None
    events = recorder.events()
    for kind in ("step", "addition", "added", "end"):
        assert kind in events
    assert events.count("addition") == 2                 # «за 2 мин» и «в конце кипячения»
    readings = recorder.of("reading")
    assert readings[0]["brewId"] is None                 # до запуска программы — температура без варки
    assert {r["brewId"] for r in readings[1:]} == {brew_id}
    assert any(r["temp"] == 100.0 and r["target"] == 100.0 for r in readings)


def test_power_off_stops_brew(idle, brewery, recorder):
    start_program(idle, brewery)
    brewery.push({"1": False})
    assert recorder.of("brewFinished")[-1]["status"] == "stopped"
    assert "powerOff" in recorder.events()


def test_alert_confirm(idle, brewery, recorder):
    with pytest.raises(ValueError, match="подсказки нет"):
        idle.cmd_confirm_alert()
    brewery.push({"143": 1})
    assert idle.snapshot()["alert"] == "malt"
    assert idle.cmd_confirm_alert().result(timeout=2)["ok"]
    assert brewery.writes[-1] == {"142": 1}
    assert recorder.events()[-2:] == ["alert", "alertCleared"]


def test_offline_event(idle, brewery, recorder):
    brewery.set_online(False)
    assert recorder.events()[-1] == "offline"
    assert idle.snapshot()["online"] is False


def test_restart_mid_brew(brewery, tmp_path, recorder):
    memory = Memory(str(tmp_path / "state.json"))
    memory.update(brew={"id": "b1", "energyWh": 5.0})
    ctl = Controller(brewery, memory, reading_interval=0)
    ctl.subscribe(recorder)
    assert ctl.hello()["brewId"] == "b1"                 # пивоварня ещё не ответила — варка не закрыта
    brewery.push({**IDLE, "1": True, "104": 2, "101": 1, "144": 1})
    assert ctl.brew_id == "b1"
    assert recorder.of("brewFinished") == []


def test_restart_after_brew_ended(brewery, tmp_path, recorder):
    memory = Memory(str(tmp_path / "state.json"))
    memory.update(brew={"id": "b1", "energyWh": 5.0})
    ctl = Controller(brewery, memory, reading_interval=0)
    ctl.subscribe(recorder)
    brewery.push(IDLE)                                   # программа не идёт — варка кончилась без агента
    assert recorder.of("brewFinished")[-1] == {"type": "brewFinished", "id": "b1", "status": "stopped",
                                               "at": recorder.of("brewFinished")[-1]["at"], "energyWh": 5.0}
    assert memory.get("brew") is None

