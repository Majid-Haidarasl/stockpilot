"""Idempotency records, outbox, and order expiry index.

Revision ID: 0007_idempotency_outbox
Revises: 0006_orders
Create Date: 2026-11-11
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0007_idempotency_outbox"
down_revision: str | None = "0006_orders"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE platform.idempotency_records (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES access.tenants(id),
            user_id UUID NOT NULL,
            operation TEXT NOT NULL,
            key TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('started', 'completed')),
            response_status INTEGER,
            response_body JSONB,
            response_headers JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            completed_at TIMESTAMPTZ,
            CONSTRAINT uq_idempotency_tenant_user_op_key
              UNIQUE (tenant_id, user_id, operation, key)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_idempotency_created ON platform.idempotency_records (created_at)"
    )
    op.execute(
        """
        CREATE TABLE platform.outbox (
            event_id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES access.tenants(id),
            event_type TEXT NOT NULL,
            event_version TEXT NOT NULL,
            aggregate_type TEXT NOT NULL,
            aggregate_id UUID NOT NULL,
            payload_json JSONB NOT NULL,
            trace_id TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            published_at TIMESTAMPTZ,
            attempt_count INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_outbox_unpublished "
        "ON platform.outbox (published_at, created_at) "
        "WHERE published_at IS NULL"
    )
    op.execute(
        "CREATE INDEX ix_sales_orders_tenant_status_expires "
        "ON sales.orders (tenant_id, status, expires_at)"
    )

    op.execute(
        """
        GRANT SELECT, INSERT, UPDATE ON platform.idempotency_records TO stockpilot_app;
        GRANT SELECT, INSERT, UPDATE ON platform.outbox TO stockpilot_app;
        GRANT SELECT, INSERT, UPDATE, DELETE ON platform.idempotency_records TO stockpilot_migrator;
        GRANT SELECT, INSERT, UPDATE, DELETE ON platform.outbox TO stockpilot_migrator;
        """
    )

    for table in ("platform.idempotency_records", "platform.outbox"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
              FOR ALL TO stockpilot_app
              USING (tenant_id::text = NULLIF(current_setting('app.tenant_id', true), ''))
              WITH CHECK (tenant_id::text = NULLIF(current_setting('app.tenant_id', true), ''))
            """
        )
        op.execute(
            f"""
            CREATE POLICY migrator_all ON {table}
              FOR ALL TO stockpilot_migrator
              USING (true) WITH CHECK (true)
            """
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS sales.ix_sales_orders_tenant_status_expires")
    op.execute("DROP TABLE IF EXISTS platform.outbox CASCADE")
    op.execute("DROP TABLE IF EXISTS platform.idempotency_records CASCADE")
