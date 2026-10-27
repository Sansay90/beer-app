"""превью фото пива (recipe_photos.thumb)

Revision ID: b81d4e6f2c90
Revises: a3f1c9e07b52
Create Date: 2026-10-27 22:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b81d4e6f2c90'
down_revision: Union[str, None] = 'a3f1c9e07b52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('recipe_photos', sa.Column('thumb', sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column('recipe_photos', 'thumb')
