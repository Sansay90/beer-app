"""Стили BJCP 2021 → app/data/bjcp-2021.json: код, название, категория и рамки OG / FG / IBU / EBC / ABV.

    python scripts/bjcp.py

Источник — github.com/beerjson/bjcp-json (MIT). Цвет переводится из SRM в EBC (× 1.97).
У специальных стилей (фруктовые, пряные, дикие и т. п.) рамки берутся от базового стиля — там null.
Категорий 27 (исторические) и 33 (выдержка в дереве) в источнике нет.
"""
import json
import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/beerjson/bjcp-json/main/styles/bjcp_styleguide-2021.json"
OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "bjcp-2021.json"


def span(style, key, scale=1.0, digits=3):
    r = style.get(key)
    if not r:
        return None
    return [round(r["minimum"]["value"] * scale, digits), round(r["maximum"]["value"] * scale, digits)]


def main():
    with urllib.request.urlopen(URL, timeout=30) as resp:
        styles = json.load(resp)["beerjson"]["styles"]
    out = [{
        "code": s["style_id"],
        "name": s["name"],
        "category": s["category"],
        "og": span(s, "original_gravity"),
        "fg": span(s, "final_gravity"),
        "ibu": span(s, "international_bitterness_units", digits=0),
        "ebc": span(s, "color", 1.97, 0),
        "abv": span(s, "alcohol_by_volume", digits=1),
    } for s in styles]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{OUT.name}: {len(out)} стилей")


if __name__ == "__main__":
    main()
