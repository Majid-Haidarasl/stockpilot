"""Create module schemas and grant runtime usage.

Revision ID: 0001_schemas
Revises:
Create Date: 2026-11-11
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001_schemas"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMAS = (
    "access",
    "catalog",
    "sales",
    "inventory",
    "notifications",
    "platform",
)


def upgrade() -> None:
    for schema in SCHEMAS:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    # Runtime role is prepared for later RLS; table grants grow in later migrations.
    op.execute(
        "GRANT USAGE ON SCHEMA access, catalog, sales, inventory, notifications, platform "
        "TO stockpilot_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE stockpilot_migrator "
        "IN SCHEMA access, catalog, sales, inventory, notifications, platform "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO stockpilot_app"
    )
    # Readiness checks read Alembic's version table as the runtime role.
    op.execute("GRANT SELECT ON TABLE alembic_version TO stockpilot_app")


def downgrade() -> None:
    for schema in reversed(SCHEMAS):
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
