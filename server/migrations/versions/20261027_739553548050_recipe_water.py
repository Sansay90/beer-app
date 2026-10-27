"""вода рецепта: соли и кислоты из «Другого» (kind = water) — в отдельный раздел water

Соль узнаётся по названию (CaCl₂, гипс, сода…); не узналась — agent = other с прежним названием.

Revision ID: 739553548050
Revises: 5c0d7e2a9b14
Create Date: 2026-10-27 12:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '739553548050'
down_revision: Union[str, None] = '5c0d7e2a9b14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

recipes = sa.table('recipes', sa.column('id', sa.Uuid()), sa.column('data', postgresql.JSONB()))

AGENTS = [("cacl", "cacl2"), ("хлорид кальц", "cacl2"), ("caso4", "gypsum"), ("гипс", "gypsum"),
          ("nahco3", "nahco3"), ("сода", "nahco3"), ("caco3", "caco3"), ("мел", "caco3"),
          ("mgso4", "epsom"), ("английская", "epsom"), ("nacl", "nacl"), ("поварен", "nacl"),
          ("молочн", "lactic80"), ("lactic", "lactic80")]
LABELS = {"cacl2": "CaCl₂", "cacl2_anhydrous": "CaCl₂", "gypsum": "Гипс", "nacl": "NaCl", "nahco3": "NaHCO₃",
          "caco3": "CaCO₃", "epsom": "MgSO₄", "lactic80": "Молочная кислота", "lactic88": "Молочная кислота"}


def agent_of(name):
    low = (name or "").lower()
    return next((agent for key, agent in AGENTS if key in low), "other")


def upgrade() -> None:
    db = op.get_bind()
    for rid, doc in db.execute(sa.select(recipes.c.id, recipes.c.data)).all():
        salts = [m for m in doc.get("miscs") or [] if m.get("kind") == "water"]
        if not salts and "water" in doc:
            continue
        water = doc.get("water") or {"source": {}, "additions": []}
        for m in salts:
            agent = agent_of(m.get("name"))
            addition = {"agent": agent, "amount": m.get("amount"), "target": "mash"}
            if agent == "other":
                addition["name"] = m.get("name") or ""
            water.setdefault("additions", []).append({k: v for k, v in addition.items() if v is not None})
        doc = {**doc, "water": water, "miscs": [m for m in doc.get("miscs") or [] if m.get("kind") != "water"]}
        db.execute(recipes.update().where(recipes.c.id == rid).values(data=doc))


def downgrade() -> None:
    db = op.get_bind()
    for rid, doc in db.execute(sa.select(recipes.c.id, recipes.c.data)).all():
        water = doc.pop("water", None) or {}
        miscs = list(doc.get("miscs") or [])
        for a in water.get("additions") or []:
            unit = "ml" if a["agent"].startswith("lactic") else "g"
            miscs.append({k: v for k, v in {"name": a.get("name") or LABELS.get(a["agent"], ""), "kind": "water",
                                             "amount": a.get("amount"), "unit": unit, "use": "mash"}.items()
                          if v is not None})
        db.execute(recipes.update().where(recipes.c.id == rid).values(data={**doc, "miscs": miscs}))
