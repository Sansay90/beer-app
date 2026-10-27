"""фото пива по рецепту (recipe_photos)

Revision ID: a3f1c9e07b52
Revises: cf2840d35b42
Create Date: 2026-10-27 21:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'a3f1c9e07b52'
down_revision: Union[str, None] = 'cf2840d35b42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('recipe_photos',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('recipe_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('content_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('data', sa.LargeBinary(), nullable=False),
    sa.Column('credit', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recipe_photos_recipe_id'), 'recipe_photos', ['recipe_id'], unique=False)
    op.create_index(op.f('ix_recipe_photos_user_id'), 'recipe_photos', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_recipe_photos_user_id'), table_name='recipe_photos')
    op.drop_index(op.f('ix_recipe_photos_recipe_id'), table_name='recipe_photos')
    op.drop_table('recipe_photos')
