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
    assert brew["plan"]["fermentation"] == [
        {"name": "Основное", "temp": 18, "days": 7, "until": "days", "gravity": None},   # без условия — по дням
        {"name": "Дображивание", "temp": 20, "days": 3, "until": "days", "gravity": None}]
    assert brew["plan"]["dryHops"] == [{"day": 4, "gravity": None, "items": ["Citra 100 г", "Simcoe 50 г"]}]
    assert brew["fermentStart"] is None and brew["packagedAt"] is None   # варочный день идёт — брожение впереди
    brew = brewer.ok("POST", f"/brews/{brew['id']}/finish")
    assert brew["fermentStart"] == brew["endedAt"]                        # задачи дрожжей нет — с конца варочного дня

    pitch = brewer.ok("POST", f"/brews/{brew['id']}/entries", {"kind": "pitch", "at": brew["startedAt"] + 3600})
    package = brewer.ok("POST", f"/brews/{brew['id']}/entries", {"kind": "package"})
    [summary] = brewer.ok("GET", "/brews")
    assert summary["fermentStart"] == pitch["at"] and summary["packagedAt"] == package["at"]


def test_past_brew_ferments_from_its_day(brewer, ferment_recipe):
    """Записанная задним числом — варочный день позади, брожение с того дня."""
    rid = brewer.ok("POST", "/recipes", ferment_recipe)["id"]
    past = brewer.ok("POST", "/brews", {"recipeId": rid, "startedAt": time.time() - 3 * DAY})
    assert past["phase"] == "fermenting" and past["fermentStart"] == past["startedAt"]


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


def test_stuck_then_dumped(service, brewer, three_stages, pushes):
    """Плотность встала на тёплом этапе заметно выше плана — «застряло» вместо «закончилось», и «пора» по дням
    этого этапа не зовёт к холоду; вылитая партия — без напоминаний."""
    t0 = time.time() - 14 * DAY
    bid = pitched(brewer, {**three_stages, "batch": {"volume": 20, "efficiency": 75}}, t0)    # объём — будет FG плана
    high = round(brewer.ok("GET", f"/brews/{bid}")["plan"]["fg"] + 0.008, 4)
    for day, sg in ((2, 1.030), (4, high), (6, high)):
        brewer.ok("POST", f"/brews/{bid}/entries", {"kind": "gravity", "value": sg, "at": t0 + day * DAY})
    tick = service.state.reminders.tick
    assert tick(at(t0 + 6 * DAY + 600)) == 1
    stuck = brewer.ok("GET", "/notifications")[0]
    assert stuck["title"] == "Похоже, брожение застряло"
    assert stuck["text"].endswith("Поднимите температуру на 2–3 °C и взболтайте дрожжи")

    assert tick(at(t0 + 7 * DAY + 600)) == 0                                    # «Пора: Дображивание» — нет
    brewer.ok("POST", f"/brews/{bid}/entries", {"kind": "dumped"})
    assert tick(at(t0 + 10 * DAY + 600)) == 0                                   # вылито — и «Пора: Холодное» нет


@pytest.fixture
def lager(ferment_recipe):
    """Лагер по плотности: 12 °C до 1,024, 14 °C до 1,018, пауза до FG, холодное — выдержка 2 дня;
    сухое охмеление — при 1,020."""
    return {**ferment_recipe, "batch": {"volume": 20, "efficiency": 75},
            "hops": [*ferment_recipe["hops"][:-2],
                     {"name": "Citra", "amount": 50, "use": "dry_hop", "day": 5, "gravity": 1.020}],
            "fermentation": [{"name": "Основное", "temp": 12, "days": 5, "until": "gravity", "gravity": 1.024},
                             {"name": "Подъём", "temp": 14, "days": 3, "until": "gravity", "gravity": 1.018},
                             {"name": "Диацетиловая пауза", "temp": 16.5, "days": 4, "until": "fg"},
                             {"name": "Холодное осветление", "temp": 4, "days": 2}]}


def lager_brew(brewer, recipe, t0, og_shift=0.0):
    """Варка лагера с задачей дрожжей в t0 и замером OG (план + og_shift); вернуть (id, OG по плану)."""
    bid = pitched(brewer, recipe, t0)
    plan_og = brewer.ok("GET", f"/brews/{bid}")["plan"]["og"]
    brewer.ok("POST", f"/brews/{bid}/entries", {"kind": "og", "value": round(plan_og + og_shift, 4), "at": t0})
    return bid, plan_og


def measure(brewer, bid, t, sg, kind="gravity"):
    brewer.ok("POST", f"/brews/{bid}/entries", {"kind": kind, "value": sg, "at": t})


def test_stages_by_gravity(service, brewer, lager, pushes):
    """Этап кончается, когда плотность дошла до цели; «до FG» — когда плотность встала; дни — только прикидка."""
    t0 = time.time() - 14 * DAY
    bid, _ = lager_brew(brewer, lager, t0)
    tick = service.state.reminders.tick
    measure(brewer, bid, t0 + 3 * DAY, 1.032)
    assert tick(at(t0 + 3 * DAY + 600)) == 0
    measure(brewer, bid, t0 + 6 * DAY, 1.023)                                  # 5 дней прикидки прошли — по плотности
    assert tick(at(t0 + 6 * DAY + 600)) == 1
    [n] = brewer.ok("GET", "/notifications")
    assert n["title"] == "Пора: Подъём" and n["text"].startswith("Плотность 1,023") and "14 °C, до 1,018" in n["text"]

    brewer.ok("POST", f"/brews/{bid}/entries", {"kind": "stage", "value": 1, "at": t0 + 6 * DAY})
    measure(brewer, bid, t0 + 8 * DAY, 1.0175)                                 # и подъём, и сухое охмеление
    assert tick(at(t0 + 8 * DAY + 600)) == 2
    titles = [n["title"] for n in brewer.ok("GET", "/notifications")]
    assert "Пора: Диацетиловая пауза" in titles and "Сухое охмеление" in titles

    brewer.ok("POST", f"/brews/{bid}/entries", {"kind": "stage", "value": 2, "at": t0 + 8 * DAY})
    measure(brewer, bid, t0 + 9 * DAY, 1.012)
    measure(brewer, bid, t0 + 10 * DAY, 1.012)
    assert tick(at(t0 + 10 * DAY + 600)) == 0                                  # сутки — мало
    measure(brewer, bid, t0 + 11 * DAY, 1.0115)
    assert tick(at(t0 + 11 * DAY + 600)) == 1                                  # двое суток — конечная
    fg = brewer.ok("GET", "/notifications")[0]
    assert fg["title"] == "Пора: Холодное осветление" and "не меняется двое суток" in fg["text"]
    assert tick(at(t0 + 11 * DAY + 1200)) == 0                                 # и без «похоже, закончилось» вдогонку


def test_target_follows_actual_og(service, brewer, lager, pushes):
    """Сварили плотнее плана — цель выше: та же доля сбраживания."""
    t0 = time.time() - 14 * DAY
    bid, plan_og = lager_brew(brewer, lager, t0, og_shift=0.004)
    target = 1 + (1.024 - 1) * (plan_og + 0.004 - 1) / (plan_og - 1)
    assert target > 1.025
    measure(brewer, bid, t0 + 4 * DAY, round(target - 0.0003, 4))              # выше цели рецепта, ниже своей
    assert service.state.reminders.tick(at(t0 + 4 * DAY + 600)) == 1
    assert brewer.ok("GET", "/notifications")[0]["title"] == "Пора: Подъём"


def test_slowdown_and_measure_reminders(service, brewer, lager, pushes):
    """Цель не наступает, а брожение встало — пора всё равно; дни прошли без замеров — пора замерить."""
    t0 = time.time() - 14 * DAY
    bid, _ = lager_brew(brewer, lager, t0)
    tick = service.state.reminders.tick
    assert tick(at(t0 + 5 * DAY + 600)) == 1                                   # 5 дней прикидки, замеров нет
    assert brewer.ok("GET", "/notifications")[0]["title"] == "Пора замерить плотность"
    assert tick(at(t0 + 5 * DAY + 1200)) == 0                                  # раз в сутки
    measure(brewer, bid, t0 + 6 * DAY, 1.0300)
    measure(brewer, bid, t0 + 7 * DAY, 1.0290)                                 # −0,001 за сутки, цель 1,024 далеко
    assert tick(at(t0 + 7 * DAY + 600)) == 1
    slow = brewer.ok("GET", "/notifications")[0]
    assert slow["title"] == "Пора: Подъём" and slow["text"].startswith("Брожение замедлилось")


def test_no_late_stable_after_fg_stage(service, brewer, lager, pushes):
    """Пауза началась после «до FG» — «похоже, закончилось» по замерам прошлого этапа вдогонку не приходит."""
    t0 = time.time() - 14 * DAY
    bid, _ = lager_brew(brewer, lager, t0)
    for value, stage in ((1, 1), (2, 2)):
        brewer.ok("POST", f"/brews/{bid}/entries", {"kind": "stage", "value": value, "at": t0 + stage * DAY})
    for day, sg in ((3, 1.012), (4, 1.012), (5, 1.0115)):
        measure(brewer, bid, t0 + day * DAY, sg)
    tick = service.state.reminders.tick
    assert tick(at(t0 + 5 * DAY + 600)) == 1                                   # «до FG» — пора к холоду
    brewer.ok("POST", f"/brews/{bid}/entries", {"kind": "stage", "value": 3, "at": t0 + 5 * DAY + 900})
    assert tick(at(t0 + 5 * DAY + 1200)) == 0                                  # и без «можно разливать» в начале холода
    assert [n["title"] for n in brewer.ok("GET", "/notifications")] == ["Пора: Холодное осветление"]


def test_texts_use_batch_targets(service, brewer, lager, pushes):
    """В уведомлении — цель партии (от фактической OG), а не рецепта."""
    t0 = time.time() - 14 * DAY
    bid, plan_og = lager_brew(brewer, lager, t0, og_shift=0.004)
    measure(brewer, bid, t0 + 4 * DAY, 1.024)
    assert service.state.reminders.tick(at(t0 + 4 * DAY + 600)) == 1
    text = brewer.ok("GET", "/notifications")[0]["text"]
    next_target = 1 + (1.018 - 1) * (plan_og + 0.004 - 1) / (plan_og - 1)
    assert f"до {round(next_target, 3):.3f}".replace(".", ",") in text and "до 1,018" not in text


def test_slowdown_counts_from_stage_start(service, brewer, lager, pushes):
    """Второй этап «до плотности»: половина пути — от плотности на его начало, а не от OG."""
    t0 = time.time() - 14 * DAY
    bid, _ = lager_brew(brewer, lager, t0)
    measure(brewer, bid, t0 + 4 * DAY, 1.0235)
    brewer.ok("POST", f"/brews/{bid}/entries", {"kind": "stage", "value": 1, "at": t0 + 4 * DAY + 600})
    tick = service.state.reminders.tick
    tick(at(t0 + 4 * DAY + 1200))
    measure(brewer, bid, t0 + 5 * DAY + 900, 1.022)                            # −0,0015 за сутки, до цели 1,018 далеко
    assert tick(at(t0 + 5 * DAY + 1200)) == 0


def test_dry_hop_by_gravity_asks_to_measure(service, brewer, three_stages, pushes):
    """Сухое по плотности на плане из выдержек: в его примерный день без замеров — «пора замерить»."""
    recipe = {**three_stages, "hops": [*three_stages["hops"],
                                       {"name": "Citra", "amount": 50, "use": "dry_hop", "day": 3, "gravity": 1.020}]}
    t0 = time.time() - 14 * DAY
    bid = pitched(brewer, recipe, t0)
    assert service.state.reminders.tick(at(t0 + 2 * DAY + 600)) == 1
    [n] = brewer.ok("GET", "/notifications")
    assert n["title"] == "Пора замерить плотность" and "Сухое охмеление (Citra 50 г)" in n["text"]
    measure(brewer, bid, t0 + 3 * DAY, 1.019)
    assert service.state.reminders.tick(at(t0 + 3 * DAY + 600)) == 1
    assert brewer.ok("GET", "/notifications")[0]["title"] == "Сухое охмеление"


def test_fermentation_stage_is_checked(brewer, ferment_recipe):
    """«До плотности» без плотности и плотность вне разумного — 422; дни у этапа по плотности необязательны."""
    stage = {"name": "Основное", "temp": 12, "until": "gravity"}
    assert brewer.post("/recipes", {**ferment_recipe, "fermentation": [stage]})[0] == 422
    assert brewer.post("/recipes", {**ferment_recipe, "fermentation": [{**stage, "gravity": 1.5}]})[0] == 422
    rid = brewer.ok("POST", "/recipes", {**ferment_recipe, "fermentation": [{**stage, "gravity": 1.024}]})["id"]
    assert brewer.ok("GET", f"/recipes/{rid}")["fermentation"][0]["days"] == 0
