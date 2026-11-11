"""Inventory reservations and reservation lines.

Revision ID: 0005_reservations
Revises: 0004_inventory
Create Date: 2026-11-11
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0005_reservations"
down_revision: str | None = "0004_inventory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE inventory.reservations (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES access.tenants(id),
            order_id UUID NOT NULL,
            status TEXT NOT NULL
              CHECK (status IN ('HELD', 'ALLOCATED', 'RELEASED', 'EXPIRED', 'CONSUMED')),
            expires_at TIMESTAMPTZ,
            version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_reservations_tenant_order UNIQUE (tenant_id, order_id),
            CONSTRAINT uq_reservations_tenant_id UNIQUE (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_reservations_tenant_expires "
        "ON inventory.reservations (tenant_id, expires_at)"
    )
    op.execute(
        """
        CREATE TABLE inventory.reservation_lines (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL,
            reservation_id UUID NOT NULL,
            product_id UUID NOT NULL,
            quantity BIGINT NOT NULL CHECK (quantity > 0 AND quantity <= 100000),
            CONSTRAINT uq_reservation_lines_reservation_product
              UNIQUE (reservation_id, product_id),
            CONSTRAINT fk_reservation_lines_reservation
              FOREIGN KEY (tenant_id, reservation_id)
              REFERENCES inventory.reservations (tenant_id, id),
            CONSTRAINT fk_reservation_lines_product
              FOREIGN KEY (tenant_id, product_id)
              REFERENCES catalog.products (tenant_id, id)
        )
        """
    )

    op.execute(
        """
        GRANT SELECT, INSERT, UPDATE ON inventory.reservations TO stockpilot_app;
        GRANT SELECT, INSERT ON inventory.reservation_lines TO stockpilot_app;
        REVOKE UPDATE, DELETE ON inventory.reservation_lines FROM stockpilot_app;
        GRANT SELECT, INSERT, UPDATE, DELETE ON inventory.reservations TO stockpilot_migrator;
        GRANT SELECT, INSERT, UPDATE, DELETE ON inventory.reservation_lines TO stockpilot_migrator;
        """
    )

    for table in ("inventory.reservations", "inventory.reservation_lines"):
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
    op.execute("DROP TABLE IF EXISTS inventory.reservation_lines CASCADE")
    op.execute("DROP TABLE IF EXISTS inventory.reservations CASCADE")
