"""Scheduler heartbeats, tenants_select_scheduler, outbox_lag().

Revision ID: 0013_scheduler_heartbeats
Revises: 0012_failed_jobs_replay
Create Date: 2026-11-17
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0013_scheduler_heartbeats"
down_revision: str | None = "0012_failed_jobs_replay"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE platform.heartbeats (
            service_name TEXT PRIMARY KEY,
            last_success_at TIMESTAMPTZ NOT NULL,
            details JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    # 0001 DEFAULT PRIVILEGES grant full DML to stockpilot_app; revoke then re-grant.
    op.execute("REVOKE ALL ON TABLE platform.heartbeats FROM stockpilot_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON platform.heartbeats TO stockpilot_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON platform.heartbeats TO stockpilot_relay")
    op.execute(
        """
        GRANT SELECT, INSERT, UPDATE, DELETE ON platform.heartbeats
          TO stockpilot_migrator
        """
    )

    op.execute("ALTER TABLE platform.heartbeats ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE platform.heartbeats FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY migrator_all ON platform.heartbeats
          FOR ALL TO stockpilot_migrator
          USING (true) WITH CHECK (true)
        """
    )

    # SELECT open for health/ops (Phase 6 exporter). Writes are row-scoped below.
    op.execute(
        """
        CREATE POLICY heartbeats_select_app ON platform.heartbeats
          FOR SELECT TO stockpilot_app
          USING (true)
        """
    )
    op.execute(
        """
        CREATE POLICY heartbeats_select_relay ON platform.heartbeats
          FOR SELECT TO stockpilot_relay
          USING (true)
        """
    )

    # App writers: only own service_name matching app.role in (scheduler, worker).
    # No USING true / WITH CHECK true for stockpilot_app writes.
    op.execute(
        """
        CREATE POLICY heartbeats_insert_service ON platform.heartbeats
          FOR INSERT TO stockpilot_app
          WITH CHECK (
            service_name = NULLIF(current_setting('app.role', true), '')
            AND NULLIF(current_setting('app.role', true), '') IN ('scheduler', 'worker')
          )
        """
    )
    op.execute(
        """
        CREATE POLICY heartbeats_update_service ON platform.heartbeats
          FOR UPDATE TO stockpilot_app
          USING (
            service_name = NULLIF(current_setting('app.role', true), '')
            AND NULLIF(current_setting('app.role', true), '') IN ('scheduler', 'worker')
          )
          WITH CHECK (
            service_name = NULLIF(current_setting('app.role', true), '')
            AND NULLIF(current_setting('app.role', true), '') IN ('scheduler', 'worker')
          )
        """
    )

    op.execute(
        """
        CREATE POLICY heartbeats_insert_relay ON platform.heartbeats
          FOR INSERT TO stockpilot_relay
          WITH CHECK (service_name = 'relay')
        """
    )
    op.execute(
        """
        CREATE POLICY heartbeats_update_relay ON platform.heartbeats
          FOR UPDATE TO stockpilot_relay
          USING (service_name = 'relay')
          WITH CHECK (service_name = 'relay')
        """
    )

    # Operational org list for scheduler (no BYPASSRLS / no membership required).
    op.execute("DROP POLICY IF EXISTS tenants_select_scheduler ON access.tenants")
    op.execute(
        """
        CREATE POLICY tenants_select_scheduler ON access.tenants
          FOR SELECT TO stockpilot_app
          USING (NULLIF(current_setting('app.role', true), '') = 'scheduler')
        """
    )

    # Lag without cross-tenant Outbox SELECT for the app role.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION platform.outbox_lag()
        RETURNS TABLE (
          unpublished_count bigint,
          oldest_unpublished_age_seconds double precision
        )
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = platform, pg_temp
        AS $fn$
          SELECT
            COUNT(*)::bigint AS unpublished_count,
            EXTRACT(EPOCH FROM (now() - MIN(created_at)))::double precision
              AS oldest_unpublished_age_seconds
          FROM platform.outbox
          WHERE published_at IS NULL;
        $fn$
        """
    )
    op.execute("ALTER FUNCTION platform.outbox_lag() OWNER TO stockpilot_migrator")
    op.execute("REVOKE ALL ON FUNCTION platform.outbox_lag() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION platform.outbox_lag() TO stockpilot_app")
    op.execute("GRANT EXECUTE ON FUNCTION platform.outbox_lag() TO stockpilot_relay")
    op.execute("GRANT EXECUTE ON FUNCTION platform.outbox_lag() TO stockpilot_migrator")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS platform.outbox_lag()")
    op.execute("DROP POLICY IF EXISTS tenants_select_scheduler ON access.tenants")
    op.execute("DROP POLICY IF EXISTS heartbeats_update_relay ON platform.heartbeats")
    op.execute("DROP POLICY IF EXISTS heartbeats_insert_relay ON platform.heartbeats")
    op.execute("DROP POLICY IF EXISTS heartbeats_update_service ON platform.heartbeats")
    op.execute("DROP POLICY IF EXISTS heartbeats_insert_service ON platform.heartbeats")
    op.execute("DROP POLICY IF EXISTS heartbeats_select_relay ON platform.heartbeats")
    op.execute("DROP POLICY IF EXISTS heartbeats_select_app ON platform.heartbeats")
    op.execute("DROP POLICY IF EXISTS migrator_all ON platform.heartbeats")
    op.execute("DROP TABLE IF EXISTS platform.heartbeats CASCADE")
