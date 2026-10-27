"""обсуждение рецептов: комментарии, голоса за рецепты и комментарии

Revision ID: f3c1a7e9d2b4
Revises: e6a2c4d8f1b3
Create Date: 2026-10-28 02:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'f3c1a7e9d2b4'
down_revision: Union[str, None] = 'e6a2c4d8f1b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('recipe_votes',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('recipe_id', sa.Uuid(), nullable=False),
    sa.Column('value', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'recipe_id')
    )
    op.create_index(op.f('ix_recipe_votes_recipe_id'), 'recipe_votes', ['recipe_id'], unique=False)

    op.create_table('comments',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('recipe_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('parent_id', sa.Uuid(), nullable=True),
    sa.Column('text', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['parent_id'], ['comments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_comments_parent_id'), 'comments', ['parent_id'], unique=False)
    op.create_index(op.f('ix_comments_recipe_id'), 'comments', ['recipe_id'], unique=False)
    op.create_index(op.f('ix_comments_user_id'), 'comments', ['user_id'], unique=False)

    op.create_table('comment_votes',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('comment_id', sa.Uuid(), nullable=False),
    sa.Column('value', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['comment_id'], ['comments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'comment_id')
    )
    op.create_index(op.f('ix_comment_votes_comment_id'), 'comment_votes', ['comment_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_comment_votes_comment_id'), table_name='comment_votes')
    op.drop_table('comment_votes')
    op.drop_index(op.f('ix_comments_user_id'), table_name='comments')
    op.drop_index(op.f('ix_comments_recipe_id'), table_name='comments')
    op.drop_index(op.f('ix_comments_parent_id'), table_name='comments')
    op.drop_table('comments')
    op.drop_index(op.f('ix_recipe_votes_recipe_id'), table_name='recipe_votes')
    op.drop_table('recipe_votes')
