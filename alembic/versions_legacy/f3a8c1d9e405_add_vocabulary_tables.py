"""add_vocabulary_tables

Revision ID: f3a8c1d9e405
Revises: e25a3ebae447
Create Date: 2026-05-15

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f3a8c1d9e405'
down_revision = '9c2f7a4d5e10'
branch_labels = None
depends_on = None


def upgrade():
    # vocabulary_sets
    op.create_table(
        'vocabulary_sets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('lesson_id', sa.Integer(), sa.ForeignKey('group_lessons.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_vocabulary_sets_id', 'vocabulary_sets', ['id'])
    op.create_index('ix_vocabulary_sets_lesson_id', 'vocabulary_sets', ['lesson_id'])

    # vocabulary_items
    op.create_table(
        'vocabulary_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('vocab_set_id', sa.Integer(), sa.ForeignKey('vocabulary_sets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('prompt_word', sa.String(length=512), nullable=False),
        sa.Column('accepted_answers', sa.Text(), nullable=True),
        sa.Column('accepted_answers_ru', sa.Text(), nullable=True),
        sa.Column('accepted_answers_tj', sa.Text(), nullable=True),
    )
    op.create_index('ix_vocabulary_items_id', 'vocabulary_items', ['id'])
    op.create_index('ix_vocabulary_items_vocab_set_id', 'vocabulary_items', ['vocab_set_id'])

    # vocabulary_attempts
    op.create_table(
        'vocabulary_attempts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('vocab_set_id', sa.Integer(), sa.ForeignKey('vocabulary_sets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('lang_used', sa.String(length=10), nullable=False, server_default='ru'),
        sa.Column('completed_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_vocabulary_attempts_id', 'vocabulary_attempts', ['id'])
    op.create_index('ix_vocabulary_attempts_vocab_set_id', 'vocabulary_attempts', ['vocab_set_id'])
    op.create_index('ix_vocabulary_attempts_student_id', 'vocabulary_attempts', ['student_id'])

    # vocabulary_attempt_answers
    op.create_table(
        'vocabulary_attempt_answers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('attempt_id', sa.Integer(), sa.ForeignKey('vocabulary_attempts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('item_id', sa.Integer(), sa.ForeignKey('vocabulary_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_answer', sa.Text(), nullable=True),
        sa.Column('is_correct', sa.Boolean(), nullable=False, server_default='false'),
    )
    op.create_index('ix_vocabulary_attempt_answers_id', 'vocabulary_attempt_answers', ['id'])
    op.create_index('ix_vocabulary_attempt_answers_attempt_id', 'vocabulary_attempt_answers', ['attempt_id'])


def downgrade():
    op.drop_table('vocabulary_attempt_answers')
    op.drop_table('vocabulary_attempts')
    op.drop_table('vocabulary_items')
    op.drop_table('vocabulary_sets')
