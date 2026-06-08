"""revoke unsafe supabase table grants

Revision ID: 9f4d2c8a1b7e
Revises: 3c9e2a1b4d6f
Create Date: 2026-05-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "9f4d2c8a1b7e"
down_revision: Union[str, None] = "3c9e2a1b4d6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SUPABASE_CLIENT_ROLES = ("anon", "authenticated")
DEFAULT_PRIVILEGE_OWNER_ROLES = ("postgres",)
UNSAFE_TABLE_PRIVILEGES = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "TRUNCATE",
    "REFERENCES",
    "TRIGGER",
)


def upgrade() -> None:
    privileges = ", ".join(UNSAFE_TABLE_PRIVILEGES)
    for role_name in SUPABASE_CLIENT_ROLES:
        op.execute(
            f"REVOKE {privileges} ON ALL TABLES IN SCHEMA public FROM {role_name}"
        )
    for owner_role in DEFAULT_PRIVILEGE_OWNER_ROLES:
        for grantee_role in SUPABASE_CLIENT_ROLES:
            op.execute(
                f"ALTER DEFAULT PRIVILEGES FOR ROLE {owner_role} IN SCHEMA public "
                f"REVOKE {privileges} ON TABLES FROM {grantee_role}"
            )


def downgrade() -> None:
    # Do not automatically restore unsafe Data API write privileges.
    pass
