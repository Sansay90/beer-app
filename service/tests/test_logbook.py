"""Журнал варок: варка без пивоварни по своему или опубликованному рецепту, рецепт партии под оборудование и план
по нему, записи (замеры, вехи, заметки) и итог по ним, день варки, удаление; «сварили N раз» — от пивовара
не больше одной варки в день."""
import time

import pytest

DAY = 86400


@pytest.fixture
def people(service):
    """author — администратор с подтверждённой почтой (может публиковать); reader — пользователь."""
    author, reader = service.client(), service.client()
    author.signup("author@test.local")
    author.ok("POST", "/auth/verify", {"token": service.outbox.link("verify")})
    reader.signup("reader@test.local")
    return author, reader


@pytest.fixture
def full_recipe(recipe):
    """Рецепт с засыпью и дрожжами — у него есть показатели, значит и план варки."""
    return {**recipe, "batch": {"volume": 25, "efficiency": 75},
            "fermentables": [{"name": "Пилснер", "amount": 5, "ebc": 3.5}],
            "yeasts": [{"name": "US-05", "attenuation": 80}]}


@pytest.fixture
def published(people, full_recipe):
    author = people[0]
    rid = author.ok("POST", "/recipes", full_recipe)["id"]
    author.ok("PUT", f"/recipes/{rid}/visibility", {"visibility": "public"})
    return rid


def total(client, rid):
    return client.ok("GET", f"/recipes/{rid}")["meta"]["brewsTotal"]


def test_manual_brew(service, people, published):
    author, reader = people
    rid = published
    assert service.client().post("/brews", {"recipeId": rid})[0] == 401
    private = author.ok("POST", "/recipes", {"name": "Личный"})["id"]
    assert reader.post("/brews", {"recipeId": private})[0] == 404              # чужой личный не виден

    brew = reader.ok("POST", "/brews", {"recipeId": rid})
    targets = author.ok("GET", f"/recipes/{rid}")["targets"]
    assert brew["manual"] is True and brew["recipeId"] == rid and brew["recipe"] is None
    assert brew["plan"]["og"] == pytest.approx(targets["og"]) and brew["plan"]["volume"] == 25
    assert brew["snapshot"]["batch"] == {"volume": 25, "efficiency": 75, "evaporation": None}   # без оборудования
    assert brew["snapshot"]["fermentables"][0]["amount"] == 5
    assert brew["entries"] == [] and brew["events"] == [] and reader.ok("GET", f"/brews/{brew['id']}/readings") == []
    assert brew["fermentStart"] is None                      # ни плана брожения, ни задачи дрожжей — брожения не видно
    assert [b["id"] for b in reader.ok("GET", f"/brews?recipe={rid}")] == [brew["id"]]
    assert author.ok("GET", "/brews") == [] and author.get(f"/brews/{brew['id']}")[0] == 404   # видит только сам
    assert total(reader, rid) == 1


def test_batch_recipe_follows_the_equipment(people, published, full_recipe):
    """Рецепт партии — под объём и эффективность оборудования: то же пиво на другом объёме; правка оригинала
    партию не трогает."""
    author, reader = people
    reader.ok("POST", "/equipment", {"name": "Кастрюля", "volume": 12.5, "efficiency": 60})
    original = author.ok("GET", f"/recipes/{published}")["targets"]
    brew = reader.ok("POST", "/brews", {"recipeId": published})
    snapshot = brew["snapshot"]
    assert snapshot["batch"] == {"volume": 12.5, "efficiency": 60, "evaporation": 3.0}   # испарение — на воду
    assert snapshot["fermentables"][0]["amount"] == pytest.approx(5 * 0.5 * 75 / 60)   # по объёму и эффективности
    assert snapshot["targets"]["og"] == pytest.approx(original["og"], abs=1e-3)
    assert brew["plan"]["volume"] == 12.5 and brew["plan"]["efficiency"] == 60
    assert brew["plan"]["og"] == pytest.approx(snapshot["targets"]["og"])

    author.ok("PUT", f"/recipes/{published}", {**full_recipe, "name": "Переименован"})
    assert reader.ok("GET", f"/brews/{brew['id']}")["snapshot"]["name"] == full_recipe["name"]


def test_brew_day(people, published):
    """Сварить сегодня — варочный день идёт, пока не заданы дрожжи или не закончили; задним числом — уже сварено;
    идущую партию без пивоварни можно удалить."""
    reader = people[1]
    today = reader.ok("POST", "/brews", {"recipeId": published})
    assert today["status"] == "running" and today["phase"] == "brewday"
    past = reader.ok("POST", "/brews", {"recipeId": published, "startedAt": time.time() - 3 * DAY})
    assert past["status"] == "finished" and past["phase"] == "fermenting"
    reader.ok("POST", f"/brews/{today['id']}/entries", {"kind": "pitch"})
    assert reader.ok("GET", f"/brews/{today['id']}")["phase"] == "fermenting"
    other = reader.ok("POST", "/brews", {"recipeId": published})
    done = reader.ok("POST", f"/brews/{other['id']}/finish")
    assert done["status"] == "finished" and done["phase"] == "fermenting"
    third = reader.ok("POST", "/brews", {"recipeId": published})
    reader.ok("DELETE", f"/brews/{third['id']}")
    assert reader.get(f"/brews/{third['id']}")[0] == 404


def test_entries_make_the_summary(people, published):
    author, reader = people
    bid = reader.ok("POST", "/brews", {"recipeId": published})["id"]
    add = lambda body: reader.request("POST", f"/brews/{bid}/entries", body)  # noqa: E731

    assert add({"kind": "og"})[0] == 400                                       # замер — со значением
    assert add({"kind": "og", "value": 12})[0] == 400                          # 12 — это °P, а нужен SG
    assert add({"kind": "note", "text": "  "})[0] == 400                       # заметка — с текстом
    assert add({"kind": "brix", "value": 1})[0] == 422                         # такого вида нет
    assert author.post(f"/brews/{bid}/entries", {"kind": "note", "text": "чужая"})[0] == 404

    now = time.time()
    reader.ok("POST", f"/brews/{bid}/entries", {"kind": "og", "value": 1.052, "at": now - 3 * DAY})
    reader.ok("POST", f"/brews/{bid}/entries", {"kind": "pitch", "text": "US-05, регидратация", "at": now - 3 * DAY})
    reader.ok("POST", f"/brews/{bid}/entries", {"kind": "fermenter_volume", "value": 23.5, "at": now - 3 * DAY})
    fg = reader.ok("POST", f"/brews/{bid}/entries", {"kind": "fg", "value": 1.014})
    reader.ok("POST", f"/brews/{bid}/entries", {"kind": "note", "text": "Чистое, сухое"})

    detail = reader.ok("GET", f"/brews/{bid}")
    assert [e["kind"] for e in detail["entries"]] == ["og", "pitch", "fermenter_volume", "fg", "note"]   # по времени
    assert detail["og"] == 1.052 and detail["fg"] == 1.014 and detail["volume"] == 23.5
    assert detail["abv"] == pytest.approx(5.1, abs=0.1)
    [summary] = reader.ok("GET", "/brews")
    assert summary["entries"] == 5 and summary["abv"] == detail["abv"]

    edited = reader.ok("PATCH", f"/brews/{bid}/entries/{fg['id']}", {"value": 1.010, "text": "через неделю"})
    assert edited["kind"] == "fg" and edited["value"] == 1.010 and edited["at"] == fg["at"]   # время — прежнее
    reader.ok("DELETE", f"/brews/{bid}/entries/{fg['id']}")
    assert reader.ok("GET", f"/brews/{bid}")["fg"] is None


def test_brews_counted_once_a_day(people, published):
    author, reader = people
    rid = published
    reader.ok("POST", "/brews", {"recipeId": rid})
    reader.ok("POST", "/brews", {"recipeId": rid})                             # второй раз за день — не в счёт
    assert total(reader, rid) == 1
    reader.ok("POST", "/brews", {"recipeId": rid, "startedAt": time.time() - 3 * DAY})
    author.ok("POST", "/brews", {"recipeId": rid})                             # свой рецепт автор тоже варит
    assert total(author, rid) == 3
    assert reader.post("/brews", {"recipeId": rid, "startedAt": time.time() + 3 * DAY})[0] == 400


def test_date_and_delete(people, published):
    _, reader = people
    rid = published
    bid = reader.ok("POST", "/brews", {"recipeId": rid})["id"]
    week_ago = time.time() - 7 * DAY
    assert reader.ok("PATCH", f"/brews/{bid}", {"startedAt": week_ago})["startedAt"] == pytest.approx(week_ago)
    reader.ok("POST", f"/brews/{bid}/entries", {"kind": "note", "text": "Запомнить"})
    reader.ok("DELETE", f"/brews/{bid}")
    assert reader.get(f"/brews/{bid}")[0] == 404 and total(reader, rid) == 0
