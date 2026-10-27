import json

from agent.state import Memory


def test_survives_restart(tmp_path):
    path = tmp_path / "data" / "state.json"
    Memory(str(path)).update(model="14", brew={"id": "b1", "energyWh": 12.5})
    again = Memory(str(path))
    assert again.get("model") == "14"
    assert again.get("brew") == {"id": "b1", "energyWh": 12.5}


def test_ignores_unknown_and_broken(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"model": "14", "secret": "x"}), encoding="utf-8")
    assert Memory(str(path)).get("secret") is None
    path.write_text("{не json", encoding="utf-8")
    assert Memory(str(path)).get("model") is None
