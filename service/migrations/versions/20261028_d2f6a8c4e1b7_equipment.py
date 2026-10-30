"""оборудование пивовара: без подключения или пивоварня, одно основное; профиль пивоварни переезжает сюда;
варка запоминает, на чём варили

Revision ID: d2f6a8c4e1b7
Revises: c7a1e9d3b5f2
Create Date: 2026-10-28 20:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql


revision: str = 'd2f6a8c4e1b7'
down_revision: Union[str, None] = 'c7a1e9d3b5f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('equipment',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('kind', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('device_id', sa.Uuid(), nullable=True),
    sa.Column('volume', sa.Float(), nullable=True),
    sa.Column('efficiency', sa.Float(), nullable=False),
    sa.Column('evaporation', sa.Float(), nullable=False),
    sa.Column('main', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_equipment_device_id'), 'equipment', ['device_id'], unique=False)
    op.create_index(op.f('ix_equipment_user_id'), 'equipment', ['user_id'], unique=False)

    # профиль каждой заведённой пивоварни — её оборудованием; основное — последняя заведённая у пользователя
    op.execute("""
        insert into equipment (id, user_id, name, kind, device_id, efficiency, evaporation, main, created_at)
        select gen_random_uuid(), d.user_id, d.name, 'easybrew', d.id,
               coalesce((d.equipment->>'efficiency')::float, 75), coalesce((d.equipment->>'evaporation')::float, 3),
               d.id = (select d2.id from devices d2 where d2.user_id = d.user_id order by d2.created_at desc limit 1),
               d.created_at
        from devices d
    """)
    op.drop_column('devices', 'equipment')

    op.add_column('brews', sa.Column('equipment_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('brews_equipment_id_fkey', 'brews', 'equipment', ['equipment_id'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_brews_equipment_id'), 'brews', ['equipment_id'], unique=False)
    # варки с пивоварни — на её оборудовании, записанные вручную — на основном
    op.execute("update brews b set equipment_id = e.id from equipment e where e.device_id = b.device_id")
    op.execute("""
        update brews b set equipment_id = e.id from equipment e
        where b.device_id is null and b.equipment_id is null and e.user_id = b.user_id and e.main
    """)


def downgrade() -> None:
    op.drop_index(op.f('ix_brews_equipment_id'), table_name='brews')
    op.drop_constraint('brews_equipment_id_fkey', 'brews', type_='foreignkey')
    op.drop_column('brews', 'equipment_id')
    op.add_column('devices', sa.Column('equipment', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.execute("""
        update devices d set equipment = jsonb_build_object('efficiency', e.efficiency, 'evaporation', e.evaporation)
        from equipment e where e.device_id = d.id
    """)
    op.drop_index(op.f('ix_equipment_user_id'), table_name='equipment')
    op.drop_index(op.f('ix_equipment_device_id'), table_name='equipment')
    op.drop_table('equipment')
