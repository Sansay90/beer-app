"""агенты: связь с пивоварней уходит из сервиса в агент (agents, devices.agent_id, devices.limits)

Ключ пивоварни, её адрес и память о программе теперь у агента (agent/) — из devices они удаляются.

Revision ID: 4f7c2b9e1a6d
Revises: b81d4e6f2c90
Create Date: 2026-10-27 23:30:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql


revision: str = '4f7c2b9e1a6d'
down_revision: Union[str, None] = 'b81d4e6f2c90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('agents',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('token_hash', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_agents_user_id'), 'agents', ['user_id'], unique=False)
    op.add_column('devices', sa.Column('agent_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_devices_agent_id'), 'devices', ['agent_id'], unique=False)
    op.create_foreign_key('devices_agent_id_fkey', 'devices', 'agents', ['agent_id'], ['id'], ondelete='SET NULL')
    op.add_column('devices', sa.Column('limits', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    for column in ('local_key', 'address', 'protocol', 'max_watts', 'recipe_raw', 'heat_capacity', 'active_recipe_id'):
        op.drop_column('devices', column)


def downgrade() -> None:
    # ключ пивоварни не восстановить — local_key возвращается пустым, сервис старой версии возьмёт его из devices.json
    op.add_column('devices', sa.Column('local_key', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''))
    op.alter_column('devices', 'local_key', server_default=None)
    op.add_column('devices', sa.Column('address', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('devices', sa.Column('protocol', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('devices', sa.Column('max_watts', sa.Integer(), nullable=True))
    op.add_column('devices', sa.Column('recipe_raw', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('devices', sa.Column('heat_capacity', sa.Float(), nullable=True))
    op.add_column('devices', sa.Column('active_recipe_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('devices_active_recipe_id_fkey', 'devices', 'recipes', ['active_recipe_id'], ['id'],
                          ondelete='SET NULL')
    op.drop_column('devices', 'limits')
    op.drop_constraint('devices_agent_id_fkey', 'devices', type_='foreignkey')
    op.drop_index(op.f('ix_devices_agent_id'), table_name='devices')
    op.drop_column('devices', 'agent_id')
    op.drop_index(op.f('ix_agents_user_id'), table_name='agents')
    op.drop_table('agents')
