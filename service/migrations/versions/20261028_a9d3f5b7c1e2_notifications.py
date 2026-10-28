"""уведомления на сайте: комментарий к моему рецепту, ответ на мой комментарий; push о комментариях — настройка

Revision ID: a9d3f5b7c1e2
Revises: f3c1a7e9d2b4
Create Date: 2026-10-28 14:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'a9d3f5b7c1e2'
down_revision: Union[str, None] = 'f3c1a7e9d2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('push_comments', sa.Boolean(), server_default='true', nullable=False))

    op.create_table('notifications',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('actor_id', sa.Uuid(), nullable=False),
    sa.Column('recipe_id', sa.Uuid(), nullable=False),
    sa.Column('comment_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['comment_id'], ['comments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_notifications_user_created', 'notifications', ['user_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_notifications_actor_id'), 'notifications', ['actor_id'], unique=False)
    op.create_index(op.f('ix_notifications_comment_id'), 'notifications', ['comment_id'], unique=False)
    op.create_index(op.f('ix_notifications_recipe_id'), 'notifications', ['recipe_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_notifications_recipe_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_comment_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_actor_id'), table_name='notifications')
    op.drop_index('ix_notifications_user_created', table_name='notifications')
    op.drop_table('notifications')
    op.drop_column('users', 'push_comments')
