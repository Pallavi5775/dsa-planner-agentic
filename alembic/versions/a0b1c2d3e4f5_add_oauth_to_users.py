"""add oauth fields to users

Revision ID: a0b1c2d3e4f5
Revises: f6a7b8c9d0e1
Create Date: 2026-04-26 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a0b1c2d3e4f5'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make hashed_password nullable for OAuth users
    op.alter_column('users', 'hashed_password', nullable=True, schema='dsa')

    op.add_column('users', sa.Column('oauth_provider', sa.String(), nullable=True), schema='dsa')
    op.add_column('users', sa.Column('oauth_id',       sa.String(), nullable=True), schema='dsa')
    op.add_column('users', sa.Column('avatar_url',     sa.String(), nullable=True), schema='dsa')


def downgrade() -> None:
    op.drop_column('users', 'avatar_url',     schema='dsa')
    op.drop_column('users', 'oauth_id',       schema='dsa')
    op.drop_column('users', 'oauth_provider', schema='dsa')
    op.alter_column('users', 'hashed_password', nullable=False, schema='dsa')
