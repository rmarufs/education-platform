"""Add organization membership integrity constraints.

Revision ID: 20260608_org_membership_b
Revises: 20260608_integrity_a
Create Date: 2026-06-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260608_org_membership_b"
down_revision: Union[str, None] = "20260608_integrity_a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM organization_teachers
        WHERE organization_id IS NULL
          AND teacher_id IS NULL
        """
    )

    op.alter_column(
        "organization_teachers",
        "organization_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.alter_column(
        "organization_teachers",
        "teacher_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.alter_column(
        "organization_teachers",
        "status",
        existing_type=sa.String(),
        nullable=False,
    )
    op.alter_column(
        "organization_teachers",
        "was_accepted_notification",
        existing_type=sa.Boolean(),
        nullable=False,
    )
    op.create_unique_constraint(
        "uq_organization_teacher",
        "organization_teachers",
        ["organization_id", "teacher_id"],
    )

    op.alter_column(
        "organization_students",
        "organization_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.alter_column(
        "organization_students",
        "student_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.alter_column(
        "organization_students",
        "status",
        existing_type=sa.String(length=20),
        nullable=False,
    )
    op.alter_column(
        "organization_students",
        "was_removed_notification",
        existing_type=sa.Boolean(),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_constraint("uq_organization_teacher", "organization_teachers", type_="unique")

    op.alter_column(
        "organization_students",
        "was_removed_notification",
        existing_type=sa.Boolean(),
        nullable=True,
    )
    op.alter_column(
        "organization_students",
        "status",
        existing_type=sa.String(length=20),
        nullable=True,
    )
    op.alter_column(
        "organization_students",
        "student_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.alter_column(
        "organization_students",
        "organization_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

    op.alter_column(
        "organization_teachers",
        "was_accepted_notification",
        existing_type=sa.Boolean(),
        nullable=True,
    )
    op.alter_column(
        "organization_teachers",
        "status",
        existing_type=sa.String(),
        nullable=True,
    )
    op.alter_column(
        "organization_teachers",
        "teacher_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.alter_column(
        "organization_teachers",
        "organization_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

    # Legacy organization_teachers rows with both foreign keys NULL are not restored.
