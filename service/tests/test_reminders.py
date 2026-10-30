"""Брожение по плану варки: этапы и сухое охмеление в плане, начало — от задачи дрожжей, розлив; напоминания —
вовремя, без повторов, старое молча пропускается, после розлива — тишина, push — по настройке."""
import time
from datetime import UTC, datetime

import pytest

DAY = 86400


def at(t):
    return datetime.fromtimestamp(t, UTC)


@pytest.fixture
def ferment_recipe(recipe):
    return {**recipe, "fermentables": [{"name": "Пилснер", "amount": 5, "ebc": 3.5}],
            "yeasts": [{"name": "US-05", "attenuation": 80}],
            "hops": [*recipe["hops"], {"name": "Citra", "amount": 100, "use": "dry_hop", "day": 4},
                     {"name": "Simcoe", "amount": 50, "use": "dry_hop", "day": 4}],
            "fermentation": [{"name": "Основное", "temp": 18, "days": 7},
                             {"name": "Дображивание", "temp": 20, "days": 3}]}


def test_plan_start_and_package(brewer, ferment_recipe):
    rid = brewer.ok("POST", "/recipes", ferment_recipe)["id"]
    brew = brewer.ok("POST", "/brews", {"recipeId": rid})
    assert brew["plan"]["fermentation"] == [{"name": "Основное", "temp": 18, "days": 7},
                                            {"name": "Дображивание", "temp": 20, "days": 3}]
    assert brew["plan"]["dryHops"] == [{"day": 4, "items": ["Citra 100 г", "Simcoe 50 г"]}]
    assert brew["fermentStart"] is None and brew["packagedAt"] is None   # варочный день идёт — брожение впереди
    brew = brewer.ok("POST", f"/brews/{brew['id']}/finish")
    assert brew["fermentStart"] == brew["endedAt"]                        # задачи дрожжей нет — с конца варочного дня

    pitch = brewer.ok("POST", f"/brews/{brew['id']}/entries", {"kind": "pitch", "at": brew["startedAt"] + 3600})
    package = brewer.ok("POST", f"/brews/{brew['id']}/entries", {"kind": "package"})
    [summary] = brewer.ok("GET", "/brews")
    assert summary["fermentStart"] == pitch["at"] and summary["packagedAt"] == package["at"]


def test_moving_the_day_moves_fermentation(brewer, ferment_recipe):
    """Записанная задним числом — брожение с того дня; день варки поправили — брожение сдвигается с ним."""
    rid = brewer.ok("POST", "/recipes", ferment_recipe)["id"]
    past = brewer.ok("POST", "/brews", {"recipeId": rid, "startedAt": time.time() - 3 * DAY})
    assert past["phase"] == "fermenting" and past["fermentStart"] == past["startedAt"]
    moved = brewer.ok("PATCH", f"/brews/{past['id']}", {"startedAt": past["startedAt"] - DAY})
    assert moved["fermentStart"] == moved["startedAt"] == past["startedAt"] - DAY


def test_reminders_follow_the_plan(service, brewer, ferment_recipe, pushes):
    rid = brewer.ok("POST", "/recipes", ferment_recipe)["id"]
    bid = brewer.ok("POST", "/brews", {"recipeId": rid})["id"]
    t0 = time.time() - 60
    brewer.ok("POST", f"/brews/{bid}/entries", {"kind": "pitch", "at": t0})
    tick = service.state.reminders.tick

    assert tick(at(t0 + DAY)) == 0
    assert tick(at(t0 + 3 * DAY + 3600)) == 1                                   # сухое охмеление на 4-й день
    assert tick(at(t0 + 3 * DAY + 7200)) == 0                                   # без повторов
    assert tick(at(t0 + 7 * DAY + 3600)) == 1                                   # следующий этап

    stage, dry = brewer.ok("GET", "/notifications")
    assert stage["kind"] == "brew" and stage["brew"] == {"id": bid, "name": ferment_recipe["name"]}
    assert stage["title"] == "Пора: Дображивание" and stage["text"] == "20 °C, 3 дн." and stage["actor"] is None
    assert dry["title"] == "Сухое охмеление" and dry["text"] == "Citra 100 г, Simcoe 50 г"
    name = ferment_recipe["name"]
    assert [n["title"] for _, n in pushes] == [f"Сухое охмеление — «{name}»", f"Пора: Дображивание — «{name}»"]
    assert pushes[0][1]["url"] == f"/brews/{bid}"

    brewer.ok("POST", f"/brews/{bid}/entries", {"kind": "package"})
    assert tick(at(t0 + 10 * DAY + 3600)) == 0                                  # разлили — конец не напоминаем


def test_old_plan_is_skipped_and_push_follows_setting(service, brewer, ferment_recipe, pushes):
    rid = brewer.ok("POST", "/recipes", ferment_recipe)["id"]
    long_ago = time.time() - 9 * DAY                                           # записали задним числом
    brewer.ok("POST", "/brews", {"recipeId": rid, "startedAt": long_ago})
    tick = service.state.reminders.tick

    assert tick() == 0                                                         # прошедшее — молча
    brewer.ok("PUT", "/notifications/settings", {"pushBrews": False})
    assert tick(at(long_ago + 10 * DAY + 600)) == 1                            # конец брожения по плану
    assert pushes == [] and brewer.ok("GET", "/notifications/unread")["count"] == 1   # на сайте — всё равно

    other = service.client()
    other.signup("other@test.local")
    assert other.ok("GET", "/notifications") == []


@pytest.fixture
def three_stages(ferment_recipe):
    return {**ferment_recipe, "hops": ferment_recipe["hops"][:-2],                   # без сухого охмеления
            "fermentation": [{"name": "Основное", "temp": 18, "days": 7},
                             {"name": "Дображивание", "temp": 20, "days": 3},
                             {"name": "Холодное осветление", "temp": 4, "days": 3}]}


def pitched(brewer, recipe, t0):
    """Варка в день t0 с задачей дрожжей тогда же; t0 — в прошлом: записи в будущее не принимаются."""
    rid = brewer.ok("POST", "/recipes", recipe)["id"]
    bid = brewer.ok("POST", "/brews", {"recipeId": rid, "startedAt": t0})["id"]
    brewer.ok("POST", f"/brews/{bid}/entries", {"kind": "pitch", "at": t0})
    return bid


def test_stage_by_fact_shifts_the_rest(service, brewer, three_stages, pushes):
    t0 = time.time() - 14 * DAY
    bid = pitched(brewer, three_stages, t0)
    entry = lambda body: brewer.request("POST", f"/brews/{bid}/entries", body)  # noqa: E731
    assert entry({"kind": "stage", "value": 3})[0] == 400                       # в плане три этапа: 1 и 2
    assert entry({"kind": "stage"})[0] == 400

    moved = brewer.ok("POST", f"/brews/{bid}/entries", {"kind": "stage", "value": 1, "at": t0 + 5 * DAY})
    assert moved["text"] == "Дображивание"                                      # название — из плана
    tick = service.state.reminders.tick
    assert tick(at(t0 + 5 * DAY + 600)) == 0                                    # начатый по факту — не напоминаем
    assert tick(at(t0 + 8 * DAY + 600)) == 1                                    # холодное — через 3 дня от факта
    assert brewer.ok("GET", "/notifications")[0]["title"] == "Пора: Холодное осветление"


def test_cold_crash_starts_the_cold_stage(service, brewer, three_stages, pushes):
    t0 = time.time() - 14 * DAY
    bid = pitched(brewer, three_stages, t0)
    brewer.ok("POST", f"/brews/{bid}/entries", {"kind": "cold_crash", "at": t0 + 9 * DAY})   # на день раньше
    tick = service.state.reminders.tick
    assert tick(at(t0 + 7 * DAY + 600)) == 1                                    # дображивание — по плану
    assert tick(at(t0 + 10 * DAY + 600)) == 0                                   # холодное уже начато
    assert tick(at(t0 + 12 * DAY + 600)) == 1                                   # конец — от факта, 9 + 3
    assert brewer.ok("GET", "/notifications")[0]["title"] == "Брожение по плану закончено"


def test_stable_gravity(service, brewer, three_stages, pushes):
    t0 = time.time() - 14 * DAY
    bid = pitched(brewer, three_stages, t0)
    for day, sg in ((2, 1.030), (4, 1.012), (5, 1.012)):
        brewer.ok("POST", f"/brews/{bid}/entries", {"kind": "gravity", "value": sg, "at": t0 + day * DAY})
    tick = service.state.reminders.tick
    assert tick(at(t0 + 5 * DAY + 600)) == 0                                    # сутки без изменений — мало
    brewer.ok("POST", f"/brews/{bid}/entries", {"kind": "gravity", "value": 1.0115, "at": t0 + 6 * DAY})
    assert tick(at(t0 + 6 * DAY + 600)) == 1                                    # двое суток в пределах 0,001
    stable = brewer.ok("GET", "/notifications")[0]
    assert stable["title"] == "Похоже, брожение закончилось"
    assert stable["text"].endswith("можно переходить к этапу «Дображивание»")
    assert tick(at(t0 + 6 * DAY + 1200)) == 0                                   # один раз
