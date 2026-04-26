"""add github fields to users

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-04-26 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'a0b1c2d3e4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('github_username',     sa.String(), nullable=True), schema='dsa')
    op.add_column('users', sa.Column('github_access_token', sa.String(), nullable=True), schema='dsa')


def downgrade() -> None:
    op.drop_column('users', 'github_access_token', schema='dsa')
    op.drop_column('users', 'github_username',     schema='dsa')
