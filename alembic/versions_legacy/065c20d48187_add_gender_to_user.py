"""add_gender_to_user

Revision ID: 065c20d48187
Revises: de486074425b
Create Date: 2026-05-31 02:25:11.817677

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '065c20d48187'
down_revision: Union[str, None] = 'de486074425b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('gender', sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'gender')
