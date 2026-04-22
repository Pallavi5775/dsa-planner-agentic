"""add practice_days to users

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-22 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop schedule if it was added manually, ignore error if it doesn't exist
    try:
        op.drop_column('users', 'schedule', schema='dsa')
    except Exception:
        pass
    op.add_column(
        'users',
        sa.Column('practice_days', sa.String(), nullable=False, server_default=''),
        schema='dsa',
    )


def downgrade() -> None:
    op.drop_column('users', 'practice_days', schema='dsa')
