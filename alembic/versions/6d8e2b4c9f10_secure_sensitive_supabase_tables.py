"""secure sensitive supabase tables

Revision ID: 6d8e2b4c9f10
Revises: d4e5f6a7b8c9
Create Date: 2026-06-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "6d8e2b4c9f10"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SENSITIVE_TABLES = (
    "password_reset_tokens",
    "push_subscriptions",
)
SUPABASE_CLIENT_ROLES = (
    "anon",
    "authenticated",
)


def upgrade() -> None:
    for table_name in SENSITIVE_TABLES:
        op.execute(f"ALTER TABLE IF EXISTS public.{table_name} ENABLE ROW LEVEL SECURITY;")
        for role_name in SUPABASE_CLIENT_ROLES:
            op.execute(
                f"""
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role_name}') THEN
                        REVOKE ALL PRIVILEGES ON TABLE public.{table_name} FROM {role_name};
                    END IF;
                END
                $$;
                """
            )


def downgrade() -> None:
    for table_name in SENSITIVE_TABLES:
        op.execute(f"ALTER TABLE IF EXISTS public.{table_name} DISABLE ROW LEVEL SECURITY;")
    # Keep direct Supabase API grants revoked, matching the project's existing
    # security migrations that do not restore dangerous grants on downgrade.
