"""брожение: напоминания по плану варки — уведомления о варке, что уже напомнили, push о брожении — настройка

Revision ID: c7a1e9d3b5f2
Revises: b4e8c2f6a1d9
Create Date: 2026-10-28 18:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c7a1e9d3b5f2'
down_revision: Union[str, None] = 'b4e8c2f6a1d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('push_brews', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('brews', sa.Column('reminded', postgresql.JSONB(astext_type=sa.Text()), server_default='[]',
                                     nullable=False))

    # уведомление о варке — без автора, рецепта и комментария
    for column in ('actor_id', 'recipe_id', 'comment_id'):
        op.alter_column('notifications', column, existing_type=sa.Uuid(), nullable=True)
    op.add_column('notifications', sa.Column('brew_id', sa.Uuid(), nullable=True))
    op.add_column('notifications', sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_foreign_key('notifications_brew_id_fkey', 'notifications', 'brews', ['brew_id'], ['id'],
                          ondelete='CASCADE')
    op.create_index(op.f('ix_notifications_brew_id'), 'notifications', ['brew_id'], unique=False)


def downgrade() -> None:
    op.execute("delete from notifications where kind = 'brew'")
    op.drop_index(op.f('ix_notifications_brew_id'), table_name='notifications')
    op.drop_constraint('notifications_brew_id_fkey', 'notifications', type_='foreignkey')
    op.drop_column('notifications', 'data')
    op.drop_column('notifications', 'brew_id')
    for column in ('actor_id', 'recipe_id', 'comment_id'):
        op.alter_column('notifications', column, existing_type=sa.Uuid(), nullable=False)
    op.drop_column('brews', 'reminded')
    op.drop_column('users', 'push_brews')
