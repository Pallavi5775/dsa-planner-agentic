"""add microsoft fields to users

Revision ID: m3n4o5p6q7r8
Revises: h8i9j0k1l2m3
Create Date: 2026-05-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = 'm3n4o5p6q7r8'
down_revision = 'h8i9j0k1l2m3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    existing = [c["name"] for c in inspector.get_columns("users", schema="dsa")]

    if "microsoft_access_token" not in existing:
        op.add_column("users", sa.Column("microsoft_access_token", sa.String(), nullable=True), schema="dsa")
    if "microsoft_refresh_token" not in existing:
        op.add_column("users", sa.Column("microsoft_refresh_token", sa.String(), nullable=True), schema="dsa")
    if "microsoft_user_id" not in existing:
        op.add_column("users", sa.Column("microsoft_user_id", sa.String(), nullable=True), schema="dsa")
    if "teams_webhook_url" not in existing:
        op.add_column("users", sa.Column("teams_webhook_url", sa.String(), nullable=True), schema="dsa")


def downgrade() -> None:
    op.drop_column("users", "teams_webhook_url", schema="dsa")
    op.drop_column("users", "microsoft_user_id", schema="dsa")
    op.drop_column("users", "microsoft_refresh_token", schema="dsa")
    op.drop_column("users", "microsoft_access_token", schema="dsa")
