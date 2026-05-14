"""shared questions – per-user progress table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-21 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # 1. Drop per-user columns from questions — use IF EXISTS so this is
    #    safe on both existing databases and fresh ones where some columns
    #    may never have existed.
    for col in ('user_id', 'coverage_status', 'revision_status', 'ease_factor',
                'interval_days', 'next_revision', 'accuracy', 'suggestions',
                'notes', 'my_gap_analysis'):
        op.execute(f"ALTER TABLE dsa.questions DROP COLUMN IF EXISTS {col}")

    # 2. Add unique constraint on questions.title
    op.create_unique_constraint('uq_questions_title', 'questions', ['title'], schema='dsa')

    # 3. Add user_id to practice_logs
    op.add_column(
        'practice_logs',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('dsa.users.id'), nullable=True),
        schema='dsa',
    )

    # 4. Create user_question_progress table
    op.create_table(
        'user_question_progress',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('question_id', sa.Integer(), sa.ForeignKey('dsa.questions.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('dsa.users.id'), nullable=False),
        sa.Column('coverage_status', sa.String(), server_default='Not Covered'),
        sa.Column('revision_status', sa.String(), server_default='Pending'),
        sa.Column('ease_factor', sa.Float(), server_default='2.5'),
        sa.Column('interval_days', sa.Integer(), server_default='0'),
        sa.Column('next_revision', sa.String(), nullable=True),
        sa.Column('accuracy', sa.Float(), nullable=True),
        sa.Column('suggestions', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('my_gap_analysis', sa.String(), nullable=True),
        sa.UniqueConstraint('question_id', 'user_id', name='uq_progress_question_user'),
        schema='dsa',
    )


def downgrade():
    op.drop_table('user_question_progress', schema='dsa')
    op.drop_column('practice_logs', 'user_id', schema='dsa')
    op.drop_constraint('uq_questions_title', 'questions', schema='dsa', type_='unique')
    op.add_column('questions', sa.Column('user_id', sa.Integer(), nullable=True), schema='dsa')
    op.add_column('questions', sa.Column('coverage_status', sa.String(), server_default='Not Covered'), schema='dsa')
    op.add_column('questions', sa.Column('revision_status', sa.String(), server_default='Pending'), schema='dsa')
    op.add_column('questions', sa.Column('ease_factor', sa.Float(), server_default='2.5'), schema='dsa')
    op.add_column('questions', sa.Column('interval_days', sa.Integer(), server_default='0'), schema='dsa')
    op.add_column('questions', sa.Column('next_revision', sa.String(), nullable=True), schema='dsa')
    op.add_column('questions', sa.Column('accuracy', sa.Float(), nullable=True), schema='dsa')
    op.add_column('questions', sa.Column('suggestions', sa.String(), nullable=True), schema='dsa')
    op.add_column('questions', sa.Column('notes', sa.String(), nullable=True), schema='dsa')
    op.add_column('questions', sa.Column('my_gap_analysis', sa.String(), nullable=True), schema='dsa')
