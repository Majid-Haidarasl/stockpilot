"""Catalog products, customers, audit log, and RLS.

Revision ID: 0003_catalog_customers_rls
Revises: 0002_access_identity
Create Date: 2026-11-11
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003_catalog_customers_rls"
down_revision: str | None = "0002_access_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE platform.audit_log (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL,
            actor_user_id UUID,
            action_type TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id UUID,
            payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_audit_log_tenant_created ON platform.audit_log (tenant_id, created_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE catalog.products (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES access.tenants(id),
            sku TEXT NOT NULL,
            title TEXT NOT NULL,
            unit_price_rial BIGINT NOT NULL CHECK (unit_price_rial >= 0 AND unit_price_rial <= 1000000000000),
            currency TEXT NOT NULL DEFAULT 'IRR' CHECK (currency = 'IRR'),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            stock_warning_threshold INTEGER NOT NULL DEFAULT 0 CHECK (stock_warning_threshold >= 0),
            version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_catalog_products_tenant_sku UNIQUE (tenant_id, sku)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE sales.customers (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES access.tenants(id),
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            notes TEXT,
            version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_sales_customers_tenant_name ON sales.customers (tenant_id, name)"
    )

    op.execute(
        """
        GRANT SELECT, INSERT, UPDATE, DELETE ON
          catalog.products, sales.customers, platform.audit_log
        TO stockpilot_app
        """
    )
    # Runtime role must not delete/update audit rows ad hoc beyond insert/select.
    op.execute("REVOKE UPDATE, DELETE ON platform.audit_log FROM stockpilot_app")
    op.execute("GRANT SELECT, INSERT ON platform.audit_log TO stockpilot_app")

    for table in ("catalog.products", "sales.customers", "platform.audit_log"):
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
    op.execute(
        "GRANT SELECT, INSERT ON platform.audit_log TO stockpilot_migrator"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON catalog.products, sales.customers TO stockpilot_migrator"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sales.customers CASCADE")
    op.execute("DROP TABLE IF EXISTS catalog.products CASCADE")
    op.execute("DROP TABLE IF EXISTS platform.audit_log CASCADE")
