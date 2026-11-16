"""Inbox, failed_jobs, and notifications tables with least-privilege RLS.

Revision ID: 0011_inbox_notifications
Revises: 0010_outbox_lease
Create Date: 2026-11-16
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0011_inbox_notifications"
down_revision: str | None = "0010_outbox_lease"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE platform.inbox (
            consumer_name TEXT NOT NULL,
            event_id UUID NOT NULL,
            tenant_id UUID NOT NULL,
            processed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (consumer_name, event_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_inbox_tenant_processed "
        "ON platform.inbox (tenant_id, processed_at)"
    )

    op.execute(
        """
        CREATE TABLE platform.failed_jobs (
            id UUID PRIMARY KEY,
            tenant_id UUID,
            event_id UUID,
            task_name TEXT NOT NULL,
            error_message TEXT NOT NULL,
            attempts INTEGER NOT NULL CHECK (attempts >= 1),
            first_failed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_failed_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_failed_jobs_last_failed "
        "ON platform.failed_jobs (last_failed_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE notifications.notifications (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL,
            recipient_user_id UUID NOT NULL,
            type TEXT NOT NULL,
            data JSONB NOT NULL DEFAULT '{}'::jsonb,
            inbox_consumer_name TEXT NOT NULL,
            inbox_event_id UUID NOT NULL,
            read_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT fk_notifications_inbox
              FOREIGN KEY (inbox_consumer_name, inbox_event_id)
              REFERENCES platform.inbox (consumer_name, event_id)
              ON DELETE RESTRICT
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_notifications_recipient_created
          ON notifications.notifications (
            tenant_id, recipient_user_id, created_at DESC, id DESC
          )
        """
    )

    # --- grants (least privilege) ---
    # 0001 DEFAULT PRIVILEGES grant full DML to stockpilot_app; revoke then re-grant.
    op.execute("REVOKE ALL ON TABLE platform.inbox FROM stockpilot_app")
    op.execute("GRANT SELECT, INSERT ON platform.inbox TO stockpilot_app")

    op.execute("REVOKE ALL ON TABLE platform.failed_jobs FROM stockpilot_app")
    op.execute("GRANT INSERT ON platform.failed_jobs TO stockpilot_app")

    op.execute("REVOKE ALL ON TABLE notifications.notifications FROM stockpilot_app")
    op.execute(
        "GRANT SELECT, INSERT ON notifications.notifications TO stockpilot_app"
    )
    op.execute(
        "GRANT UPDATE (read_at) ON notifications.notifications TO stockpilot_app"
    )

    op.execute(
        """
        GRANT SELECT, INSERT, UPDATE, DELETE ON platform.inbox,
          platform.failed_jobs, notifications.notifications
          TO stockpilot_migrator
        """
    )

    # --- RLS ---
    for table in (
        "platform.inbox",
        "platform.failed_jobs",
        "notifications.notifications",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY migrator_all ON {table}
              FOR ALL TO stockpilot_migrator
              USING (true) WITH CHECK (true)
            """
        )

    op.execute(
        """
        CREATE POLICY tenant_isolation ON platform.inbox
          FOR ALL TO stockpilot_app
          USING (tenant_id::text = NULLIF(current_setting('app.tenant_id', true), ''))
          WITH CHECK (tenant_id::text = NULLIF(current_setting('app.tenant_id', true), ''))
        """
    )

    # failed_jobs: INSERT-only policies (no FOR ALL / USING for null tenant).
    op.execute(
        """
        CREATE POLICY tenant_isolation ON platform.failed_jobs
          FOR INSERT TO stockpilot_app
          WITH CHECK (
            tenant_id::text = NULLIF(current_setting('app.tenant_id', true), '')
          )
        """
    )
    op.execute(
        """
        CREATE POLICY failed_jobs_unscoped ON platform.failed_jobs
          FOR INSERT TO stockpilot_app
          WITH CHECK (
            tenant_id IS NULL
            AND NULLIF(current_setting('app.tenant_id', true), '') IS NULL
          )
        """
    )

    op.execute(
        """
        CREATE POLICY tenant_isolation ON notifications.notifications
          FOR ALL TO stockpilot_app
          USING (tenant_id::text = NULLIF(current_setting('app.tenant_id', true), ''))
          WITH CHECK (tenant_id::text = NULLIF(current_setting('app.tenant_id', true), ''))
        """
    )

    # Worker session role: SELECT-only memberships for recipient resolution.
    # Not a human Role; HTTP ActorContext never sets app.role to 'worker'.
    op.execute("DROP POLICY IF EXISTS memberships_select_worker ON access.memberships")
    op.execute(
        """
        CREATE POLICY memberships_select_worker ON access.memberships
          FOR SELECT TO stockpilot_app
          USING (
            tenant_id::text = NULLIF(current_setting('app.tenant_id', true), '')
            AND NULLIF(current_setting('app.role', true), '') = 'worker'
          )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS memberships_select_worker ON access.memberships")
    op.execute("DROP TABLE IF EXISTS notifications.notifications CASCADE")
    op.execute("DROP TABLE IF EXISTS platform.failed_jobs CASCADE")
    op.execute("DROP TABLE IF EXISTS platform.inbox CASCADE")
