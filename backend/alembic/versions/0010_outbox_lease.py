"""Outbox lease columns, last_error, and stockpilot_relay grants.

Revision ID: 0010_outbox_lease
Revises: 0009_product_images
Create Date: 2026-11-15

Does NOT CREATE ROLE or set passwords. Role must exist via postgres init
or `ops ensure-db-roles` before this migration runs.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "0010_outbox_lease"
down_revision: str | None = "0009_product_images"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        text("SELECT 1 FROM pg_roles WHERE rolname = 'stockpilot_relay'")
    ).first()
    if exists is None:
        raise RuntimeError(
            "Database role stockpilot_relay does not exist. "
            "Run `docker compose ... run --rm ops ensure-db-roles` "
            "(or recreate Postgres from init) before migrate. "
            "Migrations never CREATE ROLE or store passwords."
        )

    op.execute("ALTER TABLE platform.outbox ADD COLUMN IF NOT EXISTS lease_owner TEXT")
    op.execute("ALTER TABLE platform.outbox ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ")
    op.execute("ALTER TABLE platform.outbox ADD COLUMN IF NOT EXISTS last_error TEXT")

    op.execute("DROP INDEX IF EXISTS platform.ix_outbox_unpublished")
    op.execute(
        """
        CREATE INDEX ix_outbox_claimable
        ON platform.outbox (created_at)
        WHERE published_at IS NULL
        """
    )

    op.execute("GRANT USAGE ON SCHEMA platform TO stockpilot_relay")
    op.execute("GRANT SELECT ON platform.outbox TO stockpilot_relay")
    op.execute(
        """
        GRANT UPDATE (
          published_at,
          lease_owner,
          lease_expires_at,
          attempt_count,
          last_error
        ) ON platform.outbox TO stockpilot_relay
        """
    )

    op.execute("DROP POLICY IF EXISTS relay_outbox_all ON platform.outbox")
    op.execute(
        """
        CREATE POLICY relay_outbox_all ON platform.outbox
          FOR ALL TO stockpilot_relay
          USING (true) WITH CHECK (true)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS relay_outbox_all ON platform.outbox")
    op.execute(
        """
        REVOKE UPDATE (
          published_at,
          lease_owner,
          lease_expires_at,
          attempt_count,
          last_error
        ) ON platform.outbox FROM stockpilot_relay
        """
    )
    op.execute("REVOKE SELECT ON platform.outbox FROM stockpilot_relay")
    op.execute("REVOKE USAGE ON SCHEMA platform FROM stockpilot_relay")
    op.execute("DROP INDEX IF EXISTS platform.ix_outbox_claimable")
    op.execute(
        """
        CREATE INDEX ix_outbox_unpublished
        ON platform.outbox (published_at, created_at)
        WHERE published_at IS NULL
        """
    )
    op.execute("ALTER TABLE platform.outbox DROP COLUMN IF EXISTS last_error")
    op.execute("ALTER TABLE platform.outbox DROP COLUMN IF EXISTS lease_expires_at")
    op.execute("ALTER TABLE platform.outbox DROP COLUMN IF EXISTS lease_owner")
