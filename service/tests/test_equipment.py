"""Оборудование пивовара: без подключения и пивоварня, основное — одно, правка, удаление, чужое не видно;
заранее добавленная «Easy Brew» получает пивоварню, которую завёл агент; варка — на основном или выбранном."""
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
    assert brewer.post("/equipment", {**POT, "efficiency": 0})[0] == 422
    assert brewer.post("/equipment", {**POT, "volume": 0.1})[0] == 422

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

    for i in range(9):
        brewer.ok("POST", "/equipment", {**POT, "name": f"Ещё {i}"})
    assert brewer.post("/equipment", POT)[0] == 409                         # не больше 10


def test_easybrew_added_before_the_agent(service, brewer, agents):
    planned = brewer.ok("POST", "/equipment", {"name": "Моя Easy Brew", "kind": "easybrew", "volume": 30})
    assert not planned["connected"]
    agent = agents(new_agent_token(brewer))
    agent.brewery.set_online(True)
    agent.brewery.push(IDLE)
    assert eventually(lambda: brewer.get("/state")[1]["online"])
    [e] = brewer.ok("GET", "/equipment")                                    # то же оборудование, а не второе
    assert e["id"] == planned["id"] and e["connected"] and e["name"] == "Моя Easy Brew"


def test_brew_on_equipment(service, brewer, recipe):
    rid = brewer.ok("POST", "/recipes", recipe)["id"]
    pot = brewer.ok("POST", "/equipment", POT)
    kettle = brewer.ok("POST", "/equipment", {"name": "Котёл 50 л"})
    assert brewer.ok("POST", "/brews", {"recipeId": rid})["equipment"] == {"id": pot["id"], "name": POT["name"]}
    on_kettle = brewer.ok("POST", "/brews", {"recipeId": rid, "equipmentId": kettle["id"]})
    assert on_kettle["equipment"]["name"] == "Котёл 50 л"
    moved = brewer.ok("PATCH", f"/brews/{on_kettle['id']}", {"equipmentId": pot["id"]})
    assert moved["equipment"]["id"] == pot["id"] and moved["startedAt"] == on_kettle["startedAt"]

    other = service.client()
    other.signup("other@test.local")
    foreign = other.ok("POST", "/equipment", POT)
    assert brewer.post("/brews", {"recipeId": rid, "equipmentId": foreign["id"]})[0] == 404
