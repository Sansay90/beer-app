"""основная варочная система у пользователя одна — уникальный индекс, а не только проверка в коде

Revision ID: c4e6a8b2d9f7
Revises: b8d2f4a6c1e9
Create Date: 2026-10-30 20:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4e6a8b2d9f7'
down_revision: Union[str, None] = 'b8d2f4a6c1e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # если две основные уже успели появиться — основной остаётся самая ранняя
    op.execute("""
        UPDATE equipment e SET main = false
        WHERE e.main AND EXISTS (SELECT 1 FROM equipment o WHERE o.user_id = e.user_id AND o.main
                                 AND (o.created_at, o.id) < (e.created_at, e.id))
    """)
    op.create_index('ix_equipment_one_main', 'equipment', ['user_id'], unique=True,
                    postgresql_where=sa.text('main'))


def downgrade() -> None:
    op.drop_index('ix_equipment_one_main', table_name='equipment')
