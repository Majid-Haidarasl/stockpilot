"""Sales orders and order lines.

Revision ID: 0006_orders
Revises: 0005_reservations
Create Date: 2026-11-11
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006_orders"
down_revision: str | None = "0005_reservations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE sales.customers
          ADD CONSTRAINT uq_sales_customers_tenant_id UNIQUE (tenant_id, id)
        """
    )
    op.execute(
        """
        CREATE TABLE sales.orders (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES access.tenants(id),
            customer_id UUID NOT NULL,
            status TEXT NOT NULL
              CHECK (status IN (
                'DRAFT', 'RESERVED', 'CONFIRMED', 'SHIPPED', 'CANCELLED', 'EXPIRED'
              )),
            version INTEGER NOT NULL DEFAULT 1,
            reserved_at TIMESTAMPTZ,
            expires_at TIMESTAMPTZ,
            confirmed_at TIMESTAMPTZ,
            shipped_at TIMESTAMPTZ,
            cancelled_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_sales_orders_tenant_id UNIQUE (tenant_id, id),
            CONSTRAINT fk_sales_orders_customer
              FOREIGN KEY (tenant_id, customer_id)
              REFERENCES sales.customers (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_sales_orders_tenant_created "
        "ON sales.orders (tenant_id, created_at DESC, id DESC)"
    )
    op.execute(
        "CREATE INDEX ix_sales_orders_tenant_status "
        "ON sales.orders (tenant_id, status)"
    )
    op.execute(
        """
        CREATE TABLE sales.order_lines (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL,
            order_id UUID NOT NULL,
            product_id UUID NOT NULL,
            quantity BIGINT NOT NULL CHECK (quantity >= 1 AND quantity <= 100000),
            product_sku TEXT NOT NULL,
            product_title TEXT NOT NULL,
            unit_price_rial BIGINT NOT NULL CHECK (unit_price_rial >= 0),
            currency CHAR(3) NOT NULL DEFAULT 'IRR',
            CONSTRAINT uq_order_lines_order_product UNIQUE (order_id, product_id),
            CONSTRAINT fk_order_lines_order
              FOREIGN KEY (tenant_id, order_id)
              REFERENCES sales.orders (tenant_id, id),
            CONSTRAINT fk_order_lines_product
              FOREIGN KEY (tenant_id, product_id)
              REFERENCES catalog.products (tenant_id, id)
        )
        """
    )

    op.execute(
        """
        GRANT SELECT, INSERT, UPDATE ON sales.orders TO stockpilot_app;
        GRANT SELECT, INSERT, UPDATE, DELETE ON sales.order_lines TO stockpilot_app;
        GRANT SELECT, INSERT, UPDATE, DELETE ON sales.orders TO stockpilot_migrator;
        GRANT SELECT, INSERT, UPDATE, DELETE ON sales.order_lines TO stockpilot_migrator;
        """
    )

    for table in ("sales.orders", "sales.order_lines"):
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
    op.execute("DROP TABLE IF EXISTS sales.order_lines CASCADE")
    op.execute("DROP TABLE IF EXISTS sales.orders CASCADE")
    op.execute(
        "ALTER TABLE sales.customers DROP CONSTRAINT IF EXISTS uq_sales_customers_tenant_id"
    )
