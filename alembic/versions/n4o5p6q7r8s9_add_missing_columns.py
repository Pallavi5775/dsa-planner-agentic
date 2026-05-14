"""add missing columns — hint_used, hint, description

Reconciliation migration: adds columns that exist in the SQLAlchemy
models but were never added to the DB due to a gap in the migration chain.
All statements use IF NOT EXISTS so this is safe to run on any DB state.

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-05-14

"""
from typing import Sequence, Union
from alembic import op

revision: str = 'n4o5p6q7r8s9'
down_revision: Union[str, Sequence[str], None] = 'm3n4o5p6q7r8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # practice_logs
    op.execute("ALTER TABLE dsa.practice_logs ADD COLUMN IF NOT EXISTS hint_used BOOLEAN NOT NULL DEFAULT false")

    # questions
    op.execute("ALTER TABLE dsa.questions ADD COLUMN IF NOT EXISTS hint VARCHAR")
    op.execute("ALTER TABLE dsa.questions ADD COLUMN IF NOT EXISTS description VARCHAR")
    op.execute("ALTER TABLE dsa.questions ADD COLUMN IF NOT EXISTS difficulty VARCHAR DEFAULT 'Medium'")

    # user_question_progress — these should exist from e5f6a7b8c9d0 but add IF NOT EXISTS for safety
    op.execute("ALTER TABLE dsa.user_question_progress ADD COLUMN IF NOT EXISTS accuracy FLOAT")
    op.execute("ALTER TABLE dsa.user_question_progress ADD COLUMN IF NOT EXISTS suggestions VARCHAR")
    op.execute("ALTER TABLE dsa.user_question_progress ADD COLUMN IF NOT EXISTS notes VARCHAR")
    op.execute("ALTER TABLE dsa.user_question_progress ADD COLUMN IF NOT EXISTS my_gap_analysis VARCHAR")

    # users — pattern_notes table (if not created by the pattern notes migration)
    op.execute("""
        CREATE TABLE IF NOT EXISTS dsa.user_pattern_notes (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES dsa.users(id) ON DELETE CASCADE,
            pattern VARCHAR NOT NULL,
            notes VARCHAR DEFAULT '',
            memory_techniques VARCHAR DEFAULT '',
            CONSTRAINT uq_pattern_note_user UNIQUE (user_id, pattern)
        )
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE dsa.practice_logs DROP COLUMN IF EXISTS hint_used")
    op.execute("ALTER TABLE dsa.questions DROP COLUMN IF EXISTS hint")
    op.execute("ALTER TABLE dsa.questions DROP COLUMN IF EXISTS description")
