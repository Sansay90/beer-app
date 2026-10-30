"""Оборудование пивовара: каталог видов, варочные системы (основная — одна) и всё прочее со своими параметрами,
правка, удаление, чужое не видно; заранее добавленная «Easy Brew» получает пивоварню, которую завёл агент;
варка — на основной или выбранной варочной системе."""
import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app import db
from app.models import Equipment

from .conftest import new_agent_token
from .support import eventually
from .test_brewery import IDLE

POT = {"name": "Кастрюля 20 л", "volume": 15, "efficiency": 70, "evaporation": 2.5, "kettle": 20}


def test_equipment(service, brewer):
    pot = brewer.ok("POST", "/equipment", POT)
    assert pot["kind"] == "manual" and pot["main"] and not pot["connected"]   # первое — основное
    assert pot["kettle"] == 20
    kettle = brewer.ok("POST", "/equipment", {"name": "Котёл 50 л", "volume": 40})
    assert not kettle["main"] and kettle["efficiency"] == 75 and kettle["evaporation"] == 3.0
    assert kettle["kettle"] is None

    assert brewer.post("/equipment", {**POT, "name": "  "})[0] == 400
    for bad in ({"efficiency": 0}, {"volume": 0.1}, {"efficiency": 83.5}, {"props": {"pressure": 1}}):
        assert brewer.post("/equipment", {**POT, **bad})[0] == 400          # пределы и точность — по каталогу

    brewer.ok("PUT", f"/equipment/{kettle['id']}/main")
    assert [(e["name"], e["main"]) for e in brewer.ok("GET", "/equipment")] == [("Котёл 50 л", True),
                                                                              ("Кастрюля 20 л", False)]
    edited = brewer.ok("PUT", f"/equipment/{pot['id']}", {**POT, "name": "Кастрюля 25 л", "volume": 18})
    assert edited["name"] == "Кастрюля 25 л" and edited["volume"] == 18 and edited["kind"] == "manual"

    other = service.client()
    other.signup("other@test.local")
    assert other.ok("GET", "/equipment") == [] and other.put(f"/equipment/{pot['id']}/main")[0] == 404

    brewer.ok("DELETE", f"/equipment/{kettle['id']}")                       # основное ушло — основным другое
    [left] = brewer.ok("GET", "/equipment")
    assert left["id"] == pot["id"] and left["main"]


def test_catalog_and_props(service, brewer):
    """Всё прочее — по каталогу: свои параметры, без цифр варочной системы, основным не бывает."""
    kinds = {k["id"]: k for c in brewer.ok("GET", "/equipment/kinds") for k in c["kinds"]}
    assert {"manual", "easybrew", "fermenter", "keg", "mill", "refractometer"} <= set(kinds)
    assert kinds["manual"]["system"] and not kinds["fermenter"]["system"]
    assert [f["key"] for f in kinds["fermenter"]["fields"]] == ["volume", "pressure", "cooling"]

    pot = brewer.ok("POST", "/equipment", POT)
    tank = {"name": "ЦКТ 32 л", "kind": "fermenter", "notes": "  с поплавком  ",
            "props": {"volume": 32, "pressure": 1, "cooling": "jacket", "x": None}}
    assert brewer.post("/equipment", {**tank, "volume": 30})[0] == 400      # у ферментера объём — в props
    tank = brewer.ok("POST", "/equipment", tank)
    assert tank["category"] == "ferment" and not tank["system"] and not tank["main"]
    assert tank["props"] == {"volume": 32, "pressure": 1, "cooling": "jacket"} and tank["notes"] == "с поплавком"
    assert tank["volume"] is None and tank["efficiency"] is None and tank["evaporation"] is None   # не система
    assert pot["props"] == {} and pot["system"] and pot["category"] == "brew"

    bad = [{"pressure": 9}, {"cooling": "ice"}, {"wheels": 4}, {"pressure": "high"}, {"pressure": 1.25}]
    for props in bad:
        assert brewer.post("/equipment", {"name": "Бак", "kind": "fermenter", "props": props})[0] == 400
    assert brewer.post("/equipment", {"name": "Кегератор", "kind": "kegerator", "props": {"taps": 2.5}})[0] == 400
    mill = brewer.ok("POST", "/equipment", {"name": "Мельница", "kind": "mill",
                                            "props": {"gap_min": 0.5, "gap_max": 1.8}})
    assert mill["props"] == {"gap_min": 0.5, "gap_max": 1.8}
    assert brewer.post("/equipment", {"name": "Мельница", "kind": "mill",
                                      "props": {"gap_min": 1.8, "gap_max": 0.5}})[0] == 400   # «от» больше «до»
    assert brewer.post("/equipment", {"name": "Бак", "kind": "spaceship"})[0] == 422
    refr = brewer.ok("POST", "/equipment", {"name": "Рефрактометр", "kind": "refractometer", "props": {"atc": True}})
    assert refr["props"] == {"atc": True}
    assert brewer.put(f"/equipment/{tank['id']}/main")[0] == 400               # основной — только система
    edited = brewer.ok("PUT", f"/equipment/{tank['id']}", {"name": "ЦКТ", "props": {"volume": 30}, "notes": ""})
    assert edited["props"] == {"volume": 30} and edited["notes"] is None and edited["kind"] == "fermenter"

    # основную удалили — основной становится система, а не первое попавшееся
    kettle = brewer.ok("POST", "/equipment", {"name": "Котёл", "volume": 40})
    brewer.ok("DELETE", f"/equipment/{pot['id']}")
    assert [e["id"] for e in brewer.ok("GET", "/equipment") if e["main"]] == [kettle["id"]]

    for i in range(96):                                                  # с четырьмя оставшимися — 100
        brewer.ok("POST", "/equipment", {"name": f"Кег {i}", "kind": "keg"})
    assert brewer.post("/equipment", POT)[0] == 409                         # не больше 100


def test_easybrew_added_before_the_agent(service, brewer, agents):
    planned = brewer.ok("POST", "/equipment", {"name": "Моя Easy Brew", "kind": "easybrew", "volume": 30})
    assert not planned["connected"]
    agent = agents(new_agent_token(brewer))
    agent.brewery.set_online(True)
    agent.brewery.push(IDLE)
    assert eventually(lambda: brewer.get("/state")[1]["online"])
    [e] = brewer.ok("GET", "/equipment")                                    # то же оборудование, а не второе
    assert e["id"] == planned["id"] and e["connected"] and e["name"] == "Моя Easy Brew"
    assert e["controlled"] and not planned["controlled"]                    # ею и управляет сайт


def test_kind_gone_from_catalog(brewer):
    """Вида уже нет в каталоге — список не падает: видно как «Другое», а не правится до миграции данных."""
    tank = brewer.ok("POST", "/equipment", {"name": "Бак", "kind": "fermenter", "props": {"volume": 30}})
    with db.session() as s:
        s.get(Equipment, uuid.UUID(tank["id"])).kind = "spaceship"
        s.commit()
    [e] = brewer.ok("GET", "/equipment")
    assert e["kind"] == "spaceship" and e["category"] == "other" and e["props"] == {"volume": 30}
    assert brewer.put(f"/equipment/{tank['id']}", {"name": "Бак 2"})[0] == 400


def test_one_main_in_the_database(brewer):
    """Основная система одна — это держит и база: вторая основная не запишется даже мимо кода."""
    brewer.ok("POST", "/equipment", POT)
    second = brewer.ok("POST", "/equipment", {"name": "Котёл"})
    with db.session() as s:
        s.exec(select(Equipment).where(Equipment.id == uuid.UUID(second["id"]))).one().main = True
        with pytest.raises(IntegrityError):
            s.commit()


def test_brew_on_equipment(service, brewer, recipe):
    rid = brewer.ok("POST", "/recipes", recipe)["id"]
    pot = brewer.ok("POST", "/equipment", POT)
    kettle = brewer.ok("POST", "/equipment", {"name": "Котёл 50 л"})
    assert brewer.ok("POST", "/brews", {"recipeId": rid})["equipment"] == {"id": pot["id"], "name": POT["name"]}
    on_kettle = brewer.ok("POST", "/brews", {"recipeId": rid, "equipmentId": kettle["id"]})
    assert on_kettle["equipment"]["name"] == "Котёл 50 л"
    assert brewer.request("PATCH", f"/brews/{on_kettle['id']}", {"equipmentId": pot["id"]})[0] == 405  # раз и навсегда

    other = service.client()
    other.signup("other@test.local")
    foreign = other.ok("POST", "/equipment", POT)
    assert brewer.post("/brews", {"recipeId": rid, "equipmentId": foreign["id"]})[0] == 404
    keg = brewer.ok("POST", "/equipment", {"name": "Кег", "kind": "keg"})
    assert brewer.post("/brews", {"recipeId": rid, "equipmentId": keg["id"]})[0] == 400   # варят на системе
