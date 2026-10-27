"""рецепт целиком: name + data (schemas.Recipe) вместо notes + steps

Паузы → mash, первое кипячение → boil, закладки кипячения → hops (хмель), fermentables (сахар) и miscs (остальное).
Откат теряет то, чего старый формат не умел: вирпул, закладки в начале и в конце кипячения, ингредиенты без времени.

Revision ID: 5c0d7e2a9b14
Revises: 98e49a463529
Create Date: 2026-10-27 10:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '5c0d7e2a9b14'
down_revision: Union[str, None] = '98e49a463529'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

recipes = sa.table('recipes', sa.column('id', sa.Uuid()), sa.column('name', sa.String()), sa.column('notes', sa.String()),
                   sa.column('steps', postgresql.JSONB()), sa.column('data', postgresql.JSONB()))


def to_document(name, notes, steps):
    mash = [{k: s[k] for k in ("name", "temp", "minutes", "watts") if s.get(k) is not None}
            for s in steps if not s.get("boil")]
    boil = next((s for s in steps if s.get("boil")), None)
    hops, miscs, fermentables = [], [], []
    for a in (boil or {}).get("additions") or []:
        item = {"name": a.get("name") or "", "amount": a.get("amount"), "use": "boil", "minutes": a["minutes"]}
        if a.get("kind", "hop") == "hop":
            hops.append({k: v for k, v in item.items() if v is not None})
        elif a["kind"] == "sugar":
            grams = a.get("amount") if a.get("unit", "g") == "g" else None
            kg = grams / 1000 if grams is not None else a.get("amount")
            fermentables.append({k: v for k, v in {**item, "kind": "sugar", "amount": kg}.items() if v is not None})
        else:
            miscs.append({k: v for k, v in {**item, "kind": a["kind"], "unit": a.get("unit") or "g"}.items()
                          if v is not None})
    doc = {"name": name, "notes": notes or "", "batch": {}, "targets": {}, "fermentables": fermentables, "hops": hops,
           "miscs": miscs, "yeasts": [], "mash": mash, "fermentation": []}
    if boil:
        doc["boil"] = {"minutes": boil["minutes"], "watts": boil["watts"]}
    return doc


def to_steps(doc):
    steps = [{**s, "boil": False, "additions": []} for s in doc.get("mash") or []]
    boil = doc.get("boil")
    if boil:
        # старый формат знал только таймеры пивоварни: строго внутри кипячения
        inside = lambda x: x.get("use") == "boil" and 0 < (x.get("minutes") or 0) < boil["minutes"]
        additions = [{"minutes": h["minutes"], "kind": "hop", "name": h.get("name"), "amount": h.get("amount"),
                      "unit": "g"} for h in doc.get("hops") or [] if inside(h)]
        additions += [{"minutes": m["minutes"], "kind": m.get("kind", "adjunct"), "name": m.get("name"),
                       "amount": m.get("amount"), "unit": m.get("unit", "g")}
                      for m in doc.get("miscs") or [] if inside(m)]
        additions += [{"minutes": f["minutes"], "kind": "sugar", "name": f.get("name"),
                       "amount": f.get("amount"), "unit": "kg"} for f in doc.get("fermentables") or [] if inside(f)]
        steps.append({"name": "Кипячение", "boil": True, "minutes": boil["minutes"], "watts": boil["watts"],
                      "additions": additions})
    return steps


def upgrade() -> None:
    op.add_column('recipes', sa.Column('data', postgresql.JSONB(), server_default='{}', nullable=False))
    db = op.get_bind()
    for rid, name, notes, steps in db.execute(sa.select(recipes.c.id, recipes.c.name, recipes.c.notes,
                                                        recipes.c.steps)).all():
        db.execute(recipes.update().where(recipes.c.id == rid).values(data=to_document(name, notes, steps or [])))
    op.alter_column('recipes', 'data', server_default=None)
    op.drop_column('recipes', 'steps')
    op.drop_column('recipes', 'notes')


def downgrade() -> None:
    op.add_column('recipes', sa.Column('notes', sa.String(), server_default='', nullable=False))
    op.add_column('recipes', sa.Column('steps', postgresql.JSONB(), server_default='[]', nullable=False))
    db = op.get_bind()
    for rid, doc in db.execute(sa.select(recipes.c.id, recipes.c.data)).all():
        db.execute(recipes.update().where(recipes.c.id == rid)
                   .values(notes=doc.get("notes") or "", steps=to_steps(doc)))
    op.drop_column('recipes', 'data')
