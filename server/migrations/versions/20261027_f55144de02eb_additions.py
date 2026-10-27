"""закладки вместо хмеля: в кипячение кладут не только хмель

Рецепты: steps[].hops [{minutes, name, grams}] → steps[].additions [{minutes, kind, name, amount, unit}].
Рецепт в варке (вид пивоварни): steps[].hops [мин] → steps[].additions.
События: hop / hopAdded → addition / added, data.hop → data.addition {minutes, items, label}.

Revision ID: f55144de02eb
Revises: e3bc688ddd34
Create Date: 2026-10-27 00:20:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f55144de02eb'
down_revision: Union[str, None] = 'e3bc688ddd34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

recipes = sa.table('recipes', sa.column('id', sa.Uuid()), sa.column('steps', postgresql.JSONB()))
brews = sa.table('brews', sa.column('id', sa.Uuid()), sa.column('recipe', postgresql.JSONB()))
events = sa.table('events', sa.column('id', sa.BigInteger()), sa.column('kind', sa.String()),
                  sa.column('data', postgresql.JSONB()))


def _addition(h):
    return {"minutes": h["minutes"], "kind": "hop", "name": h.get("name"), "amount": h.get("grams"), "unit": "g"}


def _hop(a):
    return {"minutes": a["minutes"], "name": a.get("name"), "grams": a.get("amount")}


def _rename(step, old, new, convert=lambda x: x):
    step = dict(step)
    step[new] = [convert(x) for x in step.pop(old, None) or []]
    return step


def _slot(hop):
    item = _addition(hop)
    label = " ".join(filter(None, [hop.get("name") or "Хмель", f"{hop['grams']:g} г" if hop.get("grams") else None]))
    return {"minutes": hop["minutes"], "items": [item], "label": label}


def upgrade() -> None:
    db = op.get_bind()
    for rid, steps in db.execute(sa.select(recipes.c.id, recipes.c.steps)).all():
        db.execute(recipes.update().where(recipes.c.id == rid)
                   .values(steps=[_rename(s, "hops", "additions", _addition) for s in steps or []]))
    for bid, recipe in db.execute(sa.select(brews.c.id, brews.c.recipe).where(brews.c.recipe.isnot(None))).all():
        recipe = {**recipe, "steps": [_rename(s, "hops", "additions") for s in recipe.get("steps") or []]}
        db.execute(brews.update().where(brews.c.id == bid).values(recipe=recipe))
    for kind, new in (("hop", "addition"), ("hopAdded", "added")):
        for eid, data in db.execute(sa.select(events.c.id, events.c.data).where(events.c.kind == kind)).all():
            data = dict(data or {})
            if data.get("hop"):
                data["addition"] = _slot(data.pop("hop"))
            db.execute(events.update().where(events.c.id == eid).values(kind=new, data=data or None))


def downgrade() -> None:
    db = op.get_bind()
    for rid, steps in db.execute(sa.select(recipes.c.id, recipes.c.steps)).all():
        db.execute(recipes.update().where(recipes.c.id == rid)
                   .values(steps=[_rename(s, "additions", "hops", _hop) for s in steps or []]))
    for bid, recipe in db.execute(sa.select(brews.c.id, brews.c.recipe).where(brews.c.recipe.isnot(None))).all():
        recipe = {**recipe, "steps": [_rename(s, "additions", "hops") for s in recipe.get("steps") or []]}
        db.execute(brews.update().where(brews.c.id == bid).values(recipe=recipe))
    for kind, old in (("addition", "hop"), ("added", "hopAdded")):
        for eid, data in db.execute(sa.select(events.c.id, events.c.data).where(events.c.kind == kind)).all():
            data = dict(data or {})
            slot = data.pop("addition", None)
            if slot:
                first = (slot.get("items") or [{}])[0]
                data["hop"] = {"minutes": slot["minutes"], "name": first.get("name"), "grams": first.get("amount"),
                               "label": slot.get("label")}
            db.execute(events.update().where(events.c.id == eid).values(kind=old, data=data or None))
