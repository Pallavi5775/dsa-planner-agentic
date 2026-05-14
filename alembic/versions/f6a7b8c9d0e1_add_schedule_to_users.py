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
    op.execute("ALTER TABLE dsa.users DROP COLUMN IF EXISTS schedule")
    op.execute("ALTER TABLE dsa.users ADD COLUMN IF NOT EXISTS practice_days VARCHAR NOT NULL DEFAULT ''")


def downgrade() -> None:
    op.drop_column('users', 'practice_days', schema='dsa')
