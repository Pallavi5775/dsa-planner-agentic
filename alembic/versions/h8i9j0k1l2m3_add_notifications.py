"""add notification preferences and notifications table

Revision ID: h8i9j0k1l2m3
Revises: f6a7b8c9d0e1
Create Date: 2026-05-08 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'h8i9j0k1l2m3'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Notification preference columns on users
    op.add_column('users', sa.Column('email_notif_enabled', sa.Boolean(), nullable=False, server_default='false'), schema='dsa')
    op.add_column('users', sa.Column('telegram_notif_enabled', sa.Boolean(), nullable=False, server_default='false'), schema='dsa')
    op.add_column('users', sa.Column('telegram_chat_id', sa.String(), nullable=True), schema='dsa')
    op.add_column('users', sa.Column('notify_hour', sa.Integer(), nullable=False, server_default='8'), schema='dsa')
    op.add_column('users', sa.Column('last_notif_date', sa.String(), nullable=True), schema='dsa')

    # In-app notification inbox
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('dsa.users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('message', sa.String(), nullable=False),
        sa.Column('notif_type', sa.String(), nullable=False, server_default='info'),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.String(), nullable=False),
        schema='dsa',
    )
    op.create_index('ix_dsa_notifications_user_id', 'notifications', ['user_id'], schema='dsa')


def downgrade() -> None:
    op.drop_index('ix_dsa_notifications_user_id', table_name='notifications', schema='dsa')
    op.drop_table('notifications', schema='dsa')
    op.drop_column('users', 'last_notif_date', schema='dsa')
    op.drop_column('users', 'notify_hour', schema='dsa')
    op.drop_column('users', 'telegram_chat_id', schema='dsa')
    op.drop_column('users', 'telegram_notif_enabled', schema='dsa')
    op.drop_column('users', 'email_notif_enabled', schema='dsa')
