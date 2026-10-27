"""Рецепты через API: показатели считает сервис."""


def test_targets_computed_on_save(brewer, recipe):
    pils = {**recipe, "batch": {"volume": 30, "efficiency": 75},
            "fermentables": [{"name": "Pilsner", "kind": "grain", "amount": 6, "ebc": 3.5, "use": "mash"}],
            "yeasts": [{"name": "W-34/70", "attenuation": 80}],
            "targets": {"og": 1.2, "fg": 1.1, "ibu": 999, "ebc": 999}}         # присланное не сохраняется
    rid = brewer.ok("POST", "/recipes", pils)["id"]
    saved = brewer.ok("GET", f"/recipes/{rid}")["targets"]
    assert 1.045 < saved["og"] < 1.050 and saved["fg"] < saved["og"] and saved["ibu"] < 10 and saved["ebc"] < 10
    assert 4.5 < saved["abv"] < 5.5
    listed = next(r for r in brewer.ok("GET", "/recipes") if r["id"] == rid)
    assert listed["targets"] == saved


def test_without_volume_no_targets(brewer, recipe):
    rid = brewer.ok("POST", "/recipes", {**recipe, "targets": {"og": 1.05}})["id"]
    assert brewer.ok("GET", f"/recipes/{rid}")["targets"] == {"og": None, "fg": None, "ibu": None, "ebc": None,
                                                              "abv": None}
