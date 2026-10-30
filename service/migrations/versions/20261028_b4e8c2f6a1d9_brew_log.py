"""журнал варки: варка без пивоварни (source, device_id необязателен), план по рецепту, записи пивовара

Revision ID: b4e8c2f6a1d9
Revises: a9d3f5b7c1e2
Create Date: 2026-10-28 16:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql


revision: str = 'b4e8c2f6a1d9'
down_revision: Union[str, None] = 'a9d3f5b7c1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # убрали пивоварню — варки остаются, без ссылки на неё
    op.alter_column('brews', 'device_id', existing_type=sa.Uuid(), nullable=True)
    op.drop_constraint('brews_device_id_fkey', 'brews', type_='foreignkey')
    op.create_foreign_key('brews_device_id_fkey', 'brews', 'devices', ['device_id'], ['id'], ondelete='SET NULL')
    op.add_column('brews', sa.Column('source', sqlmodel.sql.sqltypes.AutoString(), server_default='device',
                                     nullable=False))
    op.add_column('brews', sa.Column('plan', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    op.create_table('brew_entries',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('brew_id', sa.Uuid(), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('kind', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('value', sa.Float(), nullable=True),
    sa.Column('text', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['brew_id'], ['brews.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_brew_entries_brew_id'), 'brew_entries', ['brew_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_brew_entries_brew_id'), table_name='brew_entries')
    op.drop_table('brew_entries')
    op.drop_column('brews', 'plan')
    op.drop_column('brews', 'source')
    op.execute("delete from brews where device_id is null")
    op.drop_constraint('brews_device_id_fkey', 'brews', type_='foreignkey')
    op.create_foreign_key('brews_device_id_fkey', 'brews', 'devices', ['device_id'], ['id'], ondelete='CASCADE')
    op.alter_column('brews', 'device_id', existing_type=sa.Uuid(), nullable=False)
