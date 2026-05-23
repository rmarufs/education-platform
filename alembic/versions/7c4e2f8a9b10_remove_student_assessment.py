"""remove student assessment

Revision ID: 7c4e2f8a9b10
Revises: 5f2d9a7c1b34
Create Date: 2026-05-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "7c4e2f8a9b10"
down_revision: Union[str, None] = "5f2d9a7c1b34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS assessment_responses")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS assessment_answers")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS assessment_completed")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS level")


def downgrade() -> None:
    pass
