"""add_allow_retake_to_vocabulary_sets

Revision ID: a1b2c3d4e505
Revises: f3a8c1d9e405
Create Date: 2026-05-16

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e505'
down_revision = 'f3a8c1d9e405'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'vocabulary_sets',
        sa.Column('allow_retake', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade():
    op.drop_column('vocabulary_sets', 'allow_retake')
