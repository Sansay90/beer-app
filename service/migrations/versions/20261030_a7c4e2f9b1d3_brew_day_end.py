"""у варки — конец варочного дня отдельно от исхода программы пивоварни; у рецепта партии — испарение оборудования

Revision ID: a7c4e2f9b1d3
Revises: e5b9c3d7a2f4
Create Date: 2026-10-30 12:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7c4e2f9b1d3'
down_revision: Union[str, None] = 'e5b9c3d7a2f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('brews', sa.Column('day_ended_at', sa.DateTime(timezone=True), nullable=True))
    # день кончился с задачей дрожжей; без неё — с концом варки (программы или «закончить»), а записанная задним
    # числом — в свой день. Идущие остаются идущими: брошенные закроет таймер варочного дня
    op.execute("""
        UPDATE brews b SET day_ended_at = coalesce(
            (SELECT min(e.at) FROM brew_entries e WHERE e.brew_id = b.id AND e.kind = 'pitch'),
            CASE WHEN b.status <> 'running' THEN coalesce(b.ended_at, b.started_at) END)
    """)
    # вода на варку считается по испарению оборудования на день варки — теперь оно в рецепте партии
    op.execute("""
        UPDATE brews b SET snapshot = jsonb_set(b.snapshot, '{batch,evaporation}', to_jsonb(q.evaporation))
        FROM equipment q
        WHERE q.id = b.equipment_id AND jsonb_typeof(b.snapshot -> 'batch') = 'object'
    """)


def downgrade() -> None:
    op.execute("UPDATE brews SET snapshot = snapshot #- '{batch,evaporation}' WHERE snapshot IS NOT NULL")
    op.drop_column('brews', 'day_ended_at')
