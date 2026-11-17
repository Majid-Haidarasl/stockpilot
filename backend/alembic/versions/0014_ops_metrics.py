"""Ops metrics SECURITY DEFINER aggregates and stockpilot_metrics grants.

Revision ID: 0014_ops_metrics
Revises: 0013_scheduler_heartbeats
Create Date: 2026-11-18
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "0014_ops_metrics"
down_revision: str | None = "0013_scheduler_heartbeats"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        text("SELECT 1 FROM pg_roles WHERE rolname = 'stockpilot_metrics'")
    ).first()
    if exists is None:
        raise RuntimeError(
            "Database role stockpilot_metrics does not exist. "
            "Run `docker compose ... run --rm ops ensure-db-roles` "
            "(or recreate Postgres from init) before migrate. "
            "Migrations never CREATE ROLE or store passwords."
        )

    op.execute("GRANT USAGE ON SCHEMA platform TO stockpilot_metrics")
    op.execute("REVOKE ALL ON TABLE platform.heartbeats FROM stockpilot_metrics")
    op.execute("GRANT SELECT ON TABLE platform.heartbeats TO stockpilot_metrics")
    op.execute("DROP POLICY IF EXISTS heartbeats_select_metrics ON platform.heartbeats")
    op.execute(
        """
        CREATE POLICY heartbeats_select_metrics ON platform.heartbeats
          FOR SELECT TO stockpilot_metrics
          USING (true)
        """
    )

    # No direct table access for metrics role on commercial / queue tables.
    for table in (
        "platform.outbox",
        "platform.failed_jobs",
        "sales.orders",
    ):
        op.execute(f"REVOKE ALL ON TABLE {table} FROM stockpilot_metrics")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION platform.failed_jobs_metrics()
        RETURNS TABLE (unreplayed_count bigint)
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = platform, pg_temp
        AS $fn$
          SELECT COUNT(*)::bigint AS unreplayed_count
          FROM platform.failed_jobs
          WHERE replayed_at IS NULL;
        $fn$
        """
    )
    op.execute(
        "ALTER FUNCTION platform.failed_jobs_metrics() OWNER TO stockpilot_migrator"
    )
    op.execute("REVOKE ALL ON FUNCTION platform.failed_jobs_metrics() FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION platform.failed_jobs_metrics() TO stockpilot_metrics"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION platform.failed_jobs_metrics() TO stockpilot_migrator"
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION platform.stale_reserved_orders_metrics()
        RETURNS TABLE (stale_count bigint)
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = sales, pg_temp
        AS $fn$
          SELECT COUNT(*)::bigint AS stale_count
          FROM sales.orders
          WHERE status = 'RESERVED'
            AND expires_at IS NOT NULL
            AND expires_at < (now() - interval '2 minutes');
        $fn$
        """
    )
    op.execute(
        "ALTER FUNCTION platform.stale_reserved_orders_metrics() "
        "OWNER TO stockpilot_migrator"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION platform.stale_reserved_orders_metrics() FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION platform.stale_reserved_orders_metrics() "
        "TO stockpilot_metrics"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION platform.stale_reserved_orders_metrics() "
        "TO stockpilot_migrator"
    )

    op.execute("GRANT EXECUTE ON FUNCTION platform.outbox_lag() TO stockpilot_metrics")


def downgrade() -> None:
    op.execute("REVOKE EXECUTE ON FUNCTION platform.outbox_lag() FROM stockpilot_metrics")
    op.execute("DROP FUNCTION IF EXISTS platform.stale_reserved_orders_metrics()")
    op.execute("DROP FUNCTION IF EXISTS platform.failed_jobs_metrics()")
    op.execute("DROP POLICY IF EXISTS heartbeats_select_metrics ON platform.heartbeats")
    op.execute("REVOKE ALL ON TABLE platform.heartbeats FROM stockpilot_metrics")
    # USAGE may remain if other grants exist later; revoke is safe.
    exists = (
        op.get_bind()
        .execute(text("SELECT 1 FROM pg_roles WHERE rolname = 'stockpilot_metrics'"))
        .first()
    )
    if exists is not None:
        op.execute("REVOKE USAGE ON SCHEMA platform FROM stockpilot_metrics")
