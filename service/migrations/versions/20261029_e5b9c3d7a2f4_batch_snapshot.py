"""у варки — рецепт партии: пересчитан под оборудование на момент варки; у оборудования — объём котла

Revision ID: e5b9c3d7a2f4
Revises: d2f6a8c4e1b7
Create Date: 2026-10-29 12:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e5b9c3d7a2f4'
down_revision: Union[str, None] = 'd2f6a8c4e1b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # у прежних варок снимка нет: каким был рецепт на момент варки, уже не узнать — план у них остаётся
    op.add_column('brews', sa.Column('snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('equipment', sa.Column('kettle', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('equipment', 'kettle')
    op.drop_column('brews', 'snapshot')
