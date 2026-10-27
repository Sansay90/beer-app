"""избранное (favorites)

Revision ID: d4b8e1f3a7c9
Revises: c7a19e4b2d08
Create Date: 2026-10-27 23:40:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4b8e1f3a7c9'
down_revision: Union[str, None] = 'c7a19e4b2d08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('favorites',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('recipe_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'recipe_id')
    )
    op.create_index(op.f('ix_favorites_recipe_id'), 'favorites', ['recipe_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_favorites_recipe_id'), table_name='favorites')
    op.drop_table('favorites')
