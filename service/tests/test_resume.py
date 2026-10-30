"""Обрывы: перезапуск агента посреди варки, перезапуск и зависание сервиса, конец варки без связи.
Записи агента не теряются (seq/ack), а варку, о которой агент ещё знает, сервис не закрывает как прерванную."""
from agent.fake import FakeBrewery

from .conftest import new_agent_token
from .support import Proxy, eventually
from .test_brewery import IDLE


def start_brew(brewer, agent, recipe):
    rid = brewer.ok("POST", "/recipes", recipe)["id"]
    bid = brewer.ok("POST", "/brews", {"recipeId": rid})["id"]
    brewer.ok("POST", f"/brews/{bid}/upload")
    brewer.ok("POST", "/recipe/start")
    agent.brewery.push({"104": 2, "144": 1, "6": 2, "10": 250})
    brews = eventually(lambda: brewer.get("/brews")[1])
    assert len(brews) == 1 and brews[0]["status"] == "running"
    return brews[0]["id"]


def readings(brewer, brew_id):
    return [t for _, t, _ in brewer.get(f"/brews/{brew_id}/readings")[1]]


def online_agent(brewer, agents, **kw):
    agent = agents(new_agent_token(brewer), **kw)
    agent.brewery.set_online(True)
    agent.brewery.push(IDLE)
    assert eventually(lambda: brewer.get("/state")[1]["online"])
    return agent


def test_agent_restart_mid_brew(service, brewer, agents, recipe):
    agent = online_agent(brewer, agents)
    token = agent.token
    brew_id = start_brew(brewer, agent, recipe)

    hub = service.state.hub
    old_link = next(iter(hub.links.values()))
    agent.stop()                                            # та же память, пивоварня ещё не ответила
    again = agents(token, brewery=FakeBrewery())
    # ждать новое соединение агента, а не «в сети»: новая пивоварня ещё молчит, и «в сети» было бы только
    # у старого снимка — до первого состояния нового агента (на медленной машине его не поймать)
    assert eventually(lambda: any(link is not old_link for link in hub.links.values()))
    assert brewer.get(f"/brews/{brew_id}")[1]["status"] == "running"
    again.brewery.set_online(True)
    again.brewery.push({**IDLE, "1": True, "104": 2, "101": 1, "144": 2, "6": 2, "10": 400})
    assert again.controller.brew_id == brew_id              # варка подхвачена из памяти
    assert eventually(lambda: 40.0 in readings(brewer, brew_id))


def test_service_restart_keeps_records(service, brewer, agents, recipe):
    agent = online_agent(brewer, agents)
    brew_id = start_brew(brewer, agent, recipe)

    service.stop()
    for temp in (410, 420, 430):
        agent.brewery.push({"10": temp})
    agent.brewery.push({"143": 2})                          # «конец затирания», пока сервиса нет
    service.start()

    assert eventually(lambda: {41.0, 42.0, 43.0} <= set(readings(brewer, brew_id)))
    events = brewer.get(f"/brews/{brew_id}")[1]["events"]
    assert any(e["kind"] == "alert" and e.get("alert") == "mashEnd" for e in events)
    assert brewer.get("/state")[1]["online"] is True


def test_hung_service_loses_nothing(service, brewer, agents, recipe):
    proxy = Proxy(service.port)
    agent = online_agent(brewer, agents, url=f"ws://127.0.0.1:{proxy.port}/api/agent")
    brew_id = start_brew(brewer, agent, recipe)

    proxy.frozen = True                                     # сервис «завис»: принимает и молчит
    for temp in (440, 450):
        agent.brewery.push({"10": temp})
    proxy.drop()
    proxy.frozen = False
    assert eventually(lambda: {44.0, 45.0} <= set(readings(brewer, brew_id)))


def test_brew_finished_while_service_down(service, brewer, agents, recipe):
    agent = online_agent(brewer, agents)
    brew_id = start_brew(brewer, agent, recipe)

    service.stop()
    agent.brewery.push({"144": 4, "6": 1, "10": 1000})
    agent.brewery.push({"6": 0})
    agent.brewery.push({"1": False, "104": 0, "144": 0})
    assert agent.controller.brew_id is None                 # у агента варка закрыта
    service.start()

    brew = eventually(lambda: (b := brewer.get(f"/brews/{brew_id}")[1])["status"] != "running" and b)
    assert brew["status"] == "finished"                     # завершена, а не прервана
    assert any(e["kind"] == "end" for e in brew["events"]) and 100.0 in readings(brewer, brew_id)
    assert len(brewer.get("/brews")[1]) == 1
