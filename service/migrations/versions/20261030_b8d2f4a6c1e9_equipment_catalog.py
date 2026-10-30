"""оборудование — каталог видов: параметры вида (props) и заметки; эффективность и испарение — только у варочных систем

Revision ID: b8d2f4a6c1e9
Revises: a7c4e2f9b1d3
Create Date: 2026-10-30 18:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'b8d2f4a6c1e9'
down_revision: Union[str, None] = 'a7c4e2f9b1d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # всё, что было, — варочные системы (кастрюля или котёл, Easy Brew): их цифры остаются как есть
    op.add_column('equipment', sa.Column('props', postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                                         server_default='{}'))
    op.add_column('equipment', sa.Column('notes', sa.Text(), nullable=True))
    op.alter_column('equipment', 'efficiency', existing_type=sa.Float(), nullable=True)
    op.alter_column('equipment', 'evaporation', existing_type=sa.Float(), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM equipment WHERE kind NOT IN ('manual', 'allinone', 'easybrew')")
    op.execute("UPDATE equipment SET kind = 'manual' WHERE kind = 'allinone'")
    op.alter_column('equipment', 'evaporation', existing_type=sa.Float(), nullable=False)
    op.alter_column('equipment', 'efficiency', existing_type=sa.Float(), nullable=False)
    op.drop_column('equipment', 'notes')
    op.drop_column('equipment', 'props')
