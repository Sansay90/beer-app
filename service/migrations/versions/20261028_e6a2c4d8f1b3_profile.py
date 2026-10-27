"""профиль: ник вместо имени из почты, аватар

Прежние имена — часть почты до «@», её видели все под рецептами. Они стираются: ник пользователь задаёт сам
(при регистрации или в настройках), а пока его нет, интерфейс пишет «Неизвестный пивовар».

Revision ID: e6a2c4d8f1b3
Revises: d4b8e1f3a7c9
Create Date: 2026-10-28 00:30:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e6a2c4d8f1b3'
down_revision: Union[str, None] = 'd4b8e1f3a7c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('name_key', sa.String(), nullable=True))
    op.add_column('users', sa.Column('avatar', sa.LargeBinary(), nullable=True))
    op.add_column('users', sa.Column('avatar_version', sa.Integer(), server_default='0', nullable=False))
    op.alter_column('users', 'name', existing_type=sa.String(), nullable=True)
    op.execute("update users set name = null")
    op.create_unique_constraint('users_name_key_key', 'users', ['name_key'])


def downgrade() -> None:
    op.drop_constraint('users_name_key_key', 'users', type_='unique')
    op.execute("update users set name = coalesce(split_part(email, '@', 1), 'Владелец')")
    op.alter_column('users', 'name', existing_type=sa.String(), nullable=False)
    op.drop_column('users', 'avatar_version')
    op.drop_column('users', 'avatar')
    op.drop_column('users', 'name_key')
