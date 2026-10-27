"""Сквозь сервис и агента: пивоварня-имитация, настоящие Controller и Link, настоящий сервис с базой."""
import asyncio
import json

import websockets

from .conftest import new_agent_token
from .support import eventually

IDLE = {"1": False, "104": 0, "101": 0, "10": 200, "109": "14", "144": 0}


def online(service, brewer, agents):
    """Агент на связи с пивоварней в простое."""
    agent = agents(new_agent_token(brewer))
    agent.brewery.set_online(True)
    agent.brewery.push(IDLE)
    assert eventually(lambda: brewer.get("/state")[1]["online"])
    return agent


def test_without_agent(service, brewer, recipe):
    guest = service.client()
    assert guest.get("/state")[0] == 401
    assert guest.get("/limits")[1]["maxSteps"] == 9                     # ограничения по умолчанию — и гостю
    assert brewer.get("/state")[1]["online"] is False
    assert brewer.post("/recipes", recipe)[0] == 200                   # рецепт сохраняется и без пивоварни
    status, err = brewer.post("/pump", {"on": False})
    assert status == 503 and err["detail"] == "пивоварня не в сети"


def test_bad_token_rejected(service):
    async def connect():
        try:
            async with websockets.connect(f"ws://127.0.0.1:{service.port}/api/agent",
                                          additional_headers={"Authorization": "Bearer nope"}):
                return None
        except websockets.exceptions.InvalidStatus as e:
            return e.response.status_code
    assert asyncio.run(connect()) == 403


def test_limits_from_agent(service, brewer, agents, recipe):
    online(service, brewer, agents)
    limits = brewer.get("/limits")[1]
    assert limits["maxWatts"] == 2500 and limits["wattsStep"] == 100
    too_strong = {**recipe, "boil": {**recipe["boil"], "watts": 2600}}
    status, err = brewer.post("/recipes", too_strong)
    assert status == 400 and "мощность 2600" in err["detail"]          # пивоварня такую программу не примет


def test_command_errors(service, brewer, agents):
    online(service, brewer, agents)
    assert brewer.post("/manual", {"setpoint": 10, "minutes": 5, "watts": 1000})[0] == 400
    assert brewer.post("/alert/confirm")[0] == 400
    status, err = brewer.post("/additions/7/ack")
    assert status == 404 and err["detail"] == "такой закладки не ждём"


def test_brew(service, brewer, agents, recipe):
    agent = online(service, brewer, agents)
    fake = agent.brewery
    rid = brewer.ok("POST", "/recipes", recipe)["id"]

    brewer.ok("POST", f"/recipes/{rid}/upload")
    assert any("128" in w for w in fake.writes)
    device_recipe = eventually(lambda: brewer.get("/state")[1]["deviceRecipe"])
    assert device_recipe["id"] == rid and device_recipe["steps"][0]["name"] == "Пауза 1"

    brewer.ok("PUT", f"/recipes/{rid}", {**recipe, "name": "Переименован"})       # программа та же — имя новое
    assert eventually(lambda: brewer.get("/state")[1]["deviceRecipe"]["name"] == "Переименован")

    brewer.ok("POST", "/recipe/start")
    assert fake.writes[-3:] == [{"1": True}, {"101": 1}, {"2": True}]       # включить → режим «рецепт» → старт
    fake.push({"104": 2, "144": 1, "6": 2, "10": 250})
    for temp in (260, 280, 300):
        fake.push({"10": temp})
    fake.push({"143": 1})                                                   # подсказка: засыпь солода
    brewer.ok("POST", "/alert/confirm")
    assert fake.dps["143"] == 0
    fake.push({"144": 4, "6": 3, "10": 1000})                               # кипячение, отсчёт пошёл
    fake.push({"6": 2})                                                     # закладка «за 2 мин»
    pending = eventually(lambda: brewer.get("/state")[1]["additionsPending"])
    assert [a["minutes"] for a in pending] == [2] and pending[0]["label"] == "Тест-хмель А 10 г"
    brewer.ok("POST", "/additions/2/ack")
    fake.push({"6": 0})
    fake.push({"1": False, "104": 0, "144": 0})                             # конец программы

    brews = eventually(lambda: [b for b in brewer.get("/brews")[1] if b["status"] == "finished"])
    assert len(brews) == 1 and brews[0]["recipeId"] == rid
    detail = brewer.get(f"/brews/{brews[0]['id']}")[1]
    kinds = [e["kind"] for e in detail["events"]]
    assert {"alert", "alertCleared", "step", "addition", "added", "end"} <= set(kinds)
    assert [t for _, t, _ in detail["readings"]][:4] == [25.0, 26.0, 28.0, 30.0]
    assert len(brewer.get("/events")[1]) >= 6
    assert brewer.get(f"/brews?recipe={rid}")[1][0]["id"] == brews[0]["id"]
    assert brewer.get("/brews?recipe=not-an-id")[1] == []

    brewer.ok("DELETE", f"/recipes/{rid}")                                  # пивоварня забывает удалённый рецепт
    assert eventually(lambda: (brewer.get("/state")[1]["deviceRecipe"] or {}).get("id") is None)

    agent.stop()
    assert eventually(lambda: brewer.get("/state")[1]["online"] is False)
    assert brewer.post("/pump", {"on": False})[0] == 503


def test_other_users_brewery_is_invisible(service, brewer, agents):
    online(service, brewer, agents)
    other = service.client()
    other.signup("other@test.local")
    assert other.get("/state")[1]["online"] is False
    assert other.post("/pump", {"on": True})[0] == 503
    assert other.get("/brews")[1] == []


def test_equipment(service, brewer, agents):
    assert brewer.get("/equipment")[1] == {"efficiency": 75, "evaporation": 3.0}
    assert brewer.put("/equipment", {"efficiency": 83, "evaporation": 3.5})[0] == 409    # пивоварни ещё нет
    online(service, brewer, agents)
    brewer.ok("PUT", "/equipment", {"efficiency": 83, "evaporation": 3.5})
    assert brewer.get("/equipment")[1] == {"efficiency": 83, "evaporation": 3.5}


def test_foreign_brewery_rejected(service, brewer, agents, caplog):
    online(service, brewer, agents)                          # пивоварня fake-easybrew заведена у brewer
    other = service.client()
    other.me = other.signup("other@test.local")[1]
    token = new_agent_token(other)

    async def hello():
        async with websockets.connect(f"ws://127.0.0.1:{service.port}/api/agent",
                                      additional_headers={"Authorization": f"Bearer {token}"}) as ws:
            await ws.send(json.dumps({"type": "hello", "session": "s", "device": {"tuyaId": "fake-easybrew"}}))
            try:
                await ws.recv()
            except websockets.exceptions.ConnectionClosed as e:
                return e.rcvd.code if e.rcvd else None
    assert asyncio.run(hello()) == 1008                       # чужую пивоварню не привязать
    assert brewer.get("/state")[1]["online"] is True
    assert not [r for r in caplog.records if r.levelname == "ERROR"]


def test_brews_of_published_recipe_counted_for_all(service, brewer, agents, recipe):
    """Чужой опубликованный рецепт сварили — варка к нему привязана, «сколько раз варили» видят все."""
    author = service.client()
    author.signup("author@test.local")
    author.ok("POST", "/auth/verify", {"token": service.outbox.link("verify")})
    rid = author.ok("POST", "/recipes", recipe)["id"]
    author.ok("PUT", f"/recipes/{rid}/visibility", {"visibility": "public"})

    agent = online(service, brewer, agents)
    brewer.ok("POST", f"/recipes/{rid}/upload")
    brewer.ok("POST", "/recipe/start")
    agent.brewery.push({"104": 2, "144": 1, "6": 2, "10": 250})
    brews = eventually(lambda: brewer.get("/brews")[1])
    assert brews[0]["recipeId"] == rid
    assert service.client().get("/recipes")[1][0]["brewsTotal"] == 1
    assert author.get(f"/recipes/{rid}")[1]["meta"]["brewsTotal"] == 1
