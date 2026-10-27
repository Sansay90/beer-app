"""вода рецепта: литры заторной и промывочной воды → гидромодуль (water.ratio, л/кг)

Промывочная вода больше не хранится: она зависит от испарения, а испарение — у оборудования.
Гидромодуль = заторная вода / засыпь в затор; без засыпи или заторной воды не задаётся.

Revision ID: cf2840d35b42
Revises: eda7cac77d90
Create Date: 2026-10-27 18:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'cf2840d35b42'
down_revision: Union[str, None] = 'eda7cac77d90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

recipes = sa.table('recipes', sa.column('id', sa.Uuid()), sa.column('data', postgresql.JSONB()))


def mash_kg(doc):
    return sum(f.get("amount") or 0 for f in doc.get("fermentables") or [] if f.get("use", "mash") == "mash")


def upgrade() -> None:
    db = op.get_bind()
    for rid, doc in db.execute(sa.select(recipes.c.id, recipes.c.data)).all():
        water = dict(doc.get("water") or {})
        if "mash" not in water and "sparge" not in water:
            continue
        mash, kg = water.pop("mash", None), mash_kg(doc)
        water.pop("sparge", None)
        if mash and kg:
            water["ratio"] = round(mash / kg, 2)
        db.execute(recipes.update().where(recipes.c.id == rid).values(data={**doc, "water": water}))


def downgrade() -> None:
    db = op.get_bind()
    for rid, doc in db.execute(sa.select(recipes.c.id, recipes.c.data)).all():
        water = dict(doc.get("water") or {})
        if "ratio" not in water:
            continue
        ratio, kg = water.pop("ratio"), mash_kg(doc)
        if ratio and kg:
            water["mash"] = round(ratio * kg, 1)
        db.execute(recipes.update().where(recipes.c.id == rid).values(data={**doc, "water": water}))
