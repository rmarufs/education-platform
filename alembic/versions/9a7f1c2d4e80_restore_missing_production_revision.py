"""restore missing production revision

Revision ID: 9a7f1c2d4e80
Revises: 3f2a1d8c9b7e
Create Date: 2026-05-20 16:10:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "9a7f1c2d4e80"
down_revision: Union[str, None] = "3f2a1d8c9b7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
