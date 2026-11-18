"""Backup heartbeat SECURITY DEFINER for stockpilot_backup role.

Revision ID: 0015_backup_heartbeat
Revises: 0014_ops_metrics
Create Date: 2026-11-18
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "0015_backup_heartbeat"
down_revision: str | None = "0014_ops_metrics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        text("SELECT 1 FROM pg_roles WHERE rolname = 'stockpilot_backup'")
    ).first()
    if exists is None:
        raise RuntimeError(
            "Database role stockpilot_backup does not exist. "
            "Run `docker compose ... run --rm ops ensure-db-roles` "
            "(or recreate Postgres from init) before migrate. "
            "Migrations never CREATE ROLE or store passwords."
        )

    op.execute("GRANT USAGE ON SCHEMA platform TO stockpilot_backup")
    # Backup role must not DML heartbeats directly — only via DEFINER function.
    op.execute("REVOKE ALL ON TABLE platform.heartbeats FROM stockpilot_backup")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION platform.record_backup_heartbeat(
          details jsonb DEFAULT '{}'::jsonb
        )
        RETURNS void
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = platform, pg_temp
        AS $fn$
        BEGIN
          INSERT INTO platform.heartbeats (
            service_name, last_success_at, details, updated_at
          ) VALUES (
            'backup', now(), COALESCE(details, '{}'::jsonb), now()
          )
          ON CONFLICT (service_name) DO UPDATE SET
            last_success_at = EXCLUDED.last_success_at,
            details = EXCLUDED.details,
            updated_at = now()
          WHERE platform.heartbeats.service_name = 'backup';
        END;
        $fn$
        """
    )
    op.execute(
        "ALTER FUNCTION platform.record_backup_heartbeat(jsonb) "
        "OWNER TO stockpilot_migrator"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION platform.record_backup_heartbeat(jsonb) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION platform.record_backup_heartbeat(jsonb) "
        "TO stockpilot_backup"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION platform.record_backup_heartbeat(jsonb) "
        "TO stockpilot_migrator"
    )


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION IF EXISTS platform.record_backup_heartbeat(jsonb)"
    )
    exists = (
        op.get_bind()
        .execute(text("SELECT 1 FROM pg_roles WHERE rolname = 'stockpilot_backup'"))
        .first()
    )
    if exists is not None:
        op.execute("REVOKE USAGE ON SCHEMA platform FROM stockpilot_backup")
