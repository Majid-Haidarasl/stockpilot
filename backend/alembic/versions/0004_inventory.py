"""Inventory stock positions and movements.

Revision ID: 0004_inventory
Revises: 0003_catalog_customers_rls
Create Date: 2026-11-11
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004_inventory"
down_revision: str | None = "0003_catalog_customers_rls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Composite FKs that include tenant_id require a matching unique key on products.
    op.execute(
        """
        ALTER TABLE catalog.products
          ADD CONSTRAINT uq_catalog_products_tenant_id UNIQUE (tenant_id, id)
        """
    )
    op.execute(
        """
        CREATE TABLE inventory.stock_positions (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES access.tenants(id),
            warehouse_code TEXT NOT NULL DEFAULT 'main',
            product_id UUID NOT NULL,
            on_hand BIGINT NOT NULL DEFAULT 0
              CHECK (on_hand >= 0 AND on_hand <= 1000000000),
            reserved BIGINT NOT NULL DEFAULT 0
              CHECK (reserved >= 0),
            version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_stock_reserved_le_on_hand CHECK (reserved <= on_hand),
            CONSTRAINT uq_stock_positions_tenant_wh_product
              UNIQUE (tenant_id, warehouse_code, product_id),
            CONSTRAINT fk_stock_positions_product
              FOREIGN KEY (tenant_id, product_id)
              REFERENCES catalog.products (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE inventory.movements (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES access.tenants(id),
            warehouse_code TEXT NOT NULL DEFAULT 'main',
            product_id UUID NOT NULL,
            physical_delta BIGINT NOT NULL,
            reserved_delta BIGINT NOT NULL DEFAULT 0,
            reason TEXT NOT NULL,
            reference TEXT,
            actor_user_id UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT fk_movements_product
              FOREIGN KEY (tenant_id, product_id)
              REFERENCES catalog.products (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_movements_tenant_product_created "
        "ON inventory.movements (tenant_id, product_id, created_at DESC)"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_movements_tenant_reference "
        "ON inventory.movements (tenant_id, reference) "
        "WHERE reference IS NOT NULL"
    )

    op.execute(
        """
        GRANT SELECT, INSERT, UPDATE ON inventory.stock_positions TO stockpilot_app;
        GRANT SELECT, INSERT ON inventory.movements TO stockpilot_app;
        REVOKE UPDATE, DELETE ON inventory.movements FROM stockpilot_app;
        GRANT SELECT, INSERT, UPDATE, DELETE ON inventory.stock_positions TO stockpilot_migrator;
        GRANT SELECT, INSERT ON inventory.movements TO stockpilot_migrator;
        """
    )

    for table in ("inventory.stock_positions", "inventory.movements"):
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
    op.execute("DROP TABLE IF EXISTS inventory.movements CASCADE")
    op.execute("DROP TABLE IF EXISTS inventory.stock_positions CASCADE")
    op.execute(
        "ALTER TABLE catalog.products DROP CONSTRAINT IF EXISTS uq_catalog_products_tenant_id"
    )
