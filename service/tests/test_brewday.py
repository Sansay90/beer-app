"""Варочный день партии: шаги из рецепта партии, текущий шаг по записям «step» и по событиям пивоварни, таймеры
шагов, к которым перешёл пивовар, — конец паузы и закладки на кипячении уведомлением и push; конец дня — дрожжи,
«закончить» или полтора суток без них."""
import time
from datetime import timedelta

from app.brewery.brewday import DAY_SPAN, progress, steps_of
from app.models import from_unix


def test_steps_from_batch_recipe(brewer, recipe):
    rid = brewer.ok("POST", "/recipes", recipe)["id"]
    brew = brewer.ok("POST", "/brews", {"recipeId": rid})
    steps = brew["brewDay"]
    assert [s["kind"] for s in steps] == ["prepare", "heat", "mash_in", "rest", "rest", "rest", "sparge", "boil",
                                          "chill", "pitch"]
    assert [s["index"] for s in steps] == list(range(10))
    assert steps[1]["temp"] == 30 and steps[2]["measures"] == ["ph", "mash_temp"]
    assert steps[3]["name"] == "Пауза 1" and steps[3]["temp"] == 30 and steps[3]["minutes"] == 2
    assert steps[6]["measures"] == ["first_wort", "preboil_volume", "preboil_gravity"]
    boil = steps[7]
    assert boil["minutes"] == 3 and [a["minutes"] for a in boil["additions"]] == [2, 1]
    assert boil["additions"][0]["label"] == "Тест-хмель А 10 г"
    assert steps[8]["measures"] == ["og", "fermenter_volume"]
    assert brew["currentStep"] == 0 and brew["phase"] == "brewday"
    assert steps[0]["at"] == brew["startedAt"] and steps[1]["at"] is None     # подготовка — с начала варки


def test_progress_by_brewery_events():
    """Программа пивоварни — паузы и кипячение: её шаги и подсказки ложатся на шаги варочного дня; позже по времени —
    запись пивовара или событие пивоварни — то и текущий шаг."""
    steps = steps_of({"mash": [{"temp": 66, "minutes": 60}, {"temp": 78, "minutes": 10}], "boil": {"minutes": 60}})
    kinds = [s["kind"] for s in steps]
    events = [(1, "step", {"step": 1}), (2, "alert", {"alert": "malt"}), (3, "alertCleared", None),
              (4, "step", {"step": 2}), (5, "alert", {"alert": "mashEnd"}), (6, "alertCleared", None),
              (7, "step", {"step": 3}), (8, "end", None)]
    seen = [kinds[progress(steps, 0, [], events[:n])[0]] for n in range(1, len(events) + 1)]
    assert seen == ["heat", "mash_in", "rest", "rest", "sparge", "sparge", "boil", "chill"]
    _, starts, manual = progress(steps, 0, [], events)
    assert starts[kinds.index("boil")] == 7 and manual is False
    assert progress(steps, 0, [(9, "step", kinds.index("pitch"))], events)[::2] == (kinds.index("pitch"), True)
    assert progress(steps, 0, [(9, "pitch", None)], events)[0] == len(steps) - 1


def test_step_timers(service, brewer, recipe, pushes):
    rid = brewer.ok("POST", "/recipes", recipe)["id"]
    bid = brewer.ok("POST", "/brews", {"recipeId": rid})["id"]
    assert brewer.post(f"/brews/{bid}/entries", {"kind": "step", "value": 42})[0] == 400   # такого шага нет
    t0 = time.time() - 30
    step = brewer.ok("POST", f"/brews/{bid}/entries", {"kind": "step", "value": 3, "at": t0})   # первая пауза, 2 мин
    assert step["text"] == "Пауза 1"
    tick = service.state.brewday.tick

    assert tick(from_unix(t0 + 60)) == 0
    assert tick(from_unix(t0 + 121)) == 1                                       # пауза прошла — напомнили
    assert tick(from_unix(t0 + 200)) == 0                                       # без повторов
    [n] = brewer.ok("GET", "/notifications")
    assert n["kind"] == "brew" and n["title"] == "Пауза 1 — 2 мин прошло" and n["text"].startswith("Дальше — Пауза 2")
    assert pushes[0][1]["url"] == f"/brews/{bid}" and pushes[0][1]["title"].startswith("Пауза 1 — 2 мин прошло")

    brewer.ok("POST", f"/brews/{bid}/entries", {"kind": "step", "value": 7, "at": t0 + 300})   # кипячение 3 мин
    assert tick(from_unix(t0 + 300 + 61)) == 1                                  # закладка за 2 мин до конца
    assert tick(from_unix(t0 + 300 + 185)) == 2                                 # за 1 мин и конец кипячения
    titles = [n["title"] for n in brewer.ok("GET", "/notifications")]
    assert "Закладка: Тест-хмель А 10 г" in titles and "Кипячение закончено" in titles

    brewer.ok("POST", f"/brews/{bid}/entries", {"kind": "pitch"})               # дрожжи — варочный день позади
    done = brewer.ok("GET", f"/brews/{bid}")
    assert done["status"] == "finished" and done["phase"] == "fermenting" and done["currentStep"] == 9
    assert tick(from_unix(t0 + 3600)) == 0


def test_abandoned_day_goes_on(service, brewer, recipe):
    """Варочный день без дрожжей и «закончить» через полтора суток кончается сам — партия переходит к брожению."""
    rid = brewer.ok("POST", "/recipes", recipe)["id"]
    brew = brewer.ok("POST", "/brews", {"recipeId": rid})
    assert [b["id"] for b in brewer.ok("GET", "/brews?phase=brewday&limit=1")] == [brew["id"]]
    service.state.brewday.tick(from_unix(brew["startedAt"]) + DAY_SPAN - timedelta(minutes=1))
    assert brewer.ok("GET", f"/brews/{brew['id']}")["phase"] == "brewday"
    service.state.brewday.tick(from_unix(brew["startedAt"]) + DAY_SPAN + timedelta(minutes=1))
    assert brewer.ok("GET", f"/brews/{brew['id']}")["phase"] == "fermenting"
    assert brewer.ok("GET", "/brews?phase=brewday") == []
    assert [b["id"] for b in brewer.ok("GET", "/brews?phase=fermenting")] == [brew["id"]]
    assert brewer.ok("GET", "/brews?phase=packaged") == []
