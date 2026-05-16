"""Add teacher accept notification flag

Revision ID: c4d8e2f1a901
Revises: a67200bcb9b3
Create Date: 2026-05-16 12:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d8e2f1a901'
down_revision: Union[str, None] = 'a67200bcb9b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'organization_teachers',
        sa.Column('was_accepted_notification', sa.Boolean(), nullable=True, server_default='false'),
    )
    op.execute(
        "UPDATE organization_teachers "
        "SET was_accepted_notification = false "
        "WHERE was_accepted_notification IS NULL"
    )
    op.alter_column(
        'organization_teachers',
        'was_accepted_notification',
        existing_type=sa.Boolean(),
        nullable=False,
        server_default='false',
    )


def downgrade() -> None:
    op.drop_column('organization_teachers', 'was_accepted_notification')
