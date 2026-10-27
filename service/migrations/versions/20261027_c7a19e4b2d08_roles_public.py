"""роли и публичные рецепты: users.role, recipes.visibility, recipes.published_at

Самый ранний пользователь — владелец установки — становится администратором.

Revision ID: c7a19e4b2d08
Revises: 8d3e6a1f5c27
Create Date: 2026-10-28 01:30:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'c7a19e4b2d08'
down_revision: Union[str, None] = '8d3e6a1f5c27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('role', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='user'))
    op.add_column('recipes', sa.Column('visibility', sqlmodel.sql.sqltypes.AutoString(), nullable=False,
                                       server_default='private'))
    op.add_column('recipes', sa.Column('published_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_recipes_visibility'), 'recipes', ['visibility'], unique=False)
    op.execute("UPDATE users SET role = 'admin' WHERE id = (SELECT id FROM users ORDER BY created_at LIMIT 1)")


def downgrade() -> None:
    op.drop_index(op.f('ix_recipes_visibility'), table_name='recipes')
    op.drop_column('recipes', 'published_at')
    op.drop_column('recipes', 'visibility')
    op.drop_column('users', 'role')
