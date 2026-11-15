"""Product images table with tenant composite FK and RLS.

Revision ID: 0009_product_images
Revises: 0008_audit_log_seq
Create Date: 2026-11-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0009_product_images"
down_revision: str | None = "0008_audit_log_seq"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Composite FK target uq_catalog_products_tenant_id already exists (0004+).
    op.execute(
        """
        CREATE TABLE catalog.product_images (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES access.tenants(id),
            product_id UUID NOT NULL,
            storage_key TEXT NOT NULL,
            thumb_key TEXT NOT NULL,
            content_type TEXT NOT NULL CHECK (content_type = 'image/webp'),
            width INTEGER NOT NULL CHECK (width > 0),
            height INTEGER NOT NULL CHECK (height > 0),
            size_bytes INTEGER NOT NULL CHECK (size_bytes > 0),
            sha256 TEXT NOT NULL,
            is_primary BOOLEAN NOT NULL DEFAULT FALSE,
            sort_order INTEGER NOT NULL CHECK (sort_order >= 0),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by UUID NOT NULL REFERENCES access.users(id),
            CONSTRAINT fk_product_images_product_tenant
              FOREIGN KEY (tenant_id, product_id)
              REFERENCES catalog.products (tenant_id, id)
              ON DELETE RESTRICT,
            CONSTRAINT uq_product_images_product_sha
              UNIQUE (tenant_id, product_id, sha256)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_product_images_tenant_product_sort
          ON catalog.product_images (tenant_id, product_id, sort_order)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_product_images_one_primary
          ON catalog.product_images (tenant_id, product_id)
          WHERE is_primary
        """
    )
    op.execute(
        """
        GRANT SELECT, INSERT, UPDATE, DELETE ON catalog.product_images
          TO stockpilot_app
        """
    )
    op.execute(
        """
        GRANT SELECT, INSERT, UPDATE, DELETE ON catalog.product_images
          TO stockpilot_migrator
        """
    )
    op.execute("ALTER TABLE catalog.product_images ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE catalog.product_images FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON catalog.product_images
          FOR ALL TO stockpilot_app
          USING (tenant_id::text = NULLIF(current_setting('app.tenant_id', true), ''))
          WITH CHECK (tenant_id::text = NULLIF(current_setting('app.tenant_id', true), ''))
        """
    )
    op.execute(
        """
        CREATE POLICY migrator_all ON catalog.product_images
          FOR ALL TO stockpilot_migrator
          USING (true) WITH CHECK (true)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS catalog.product_images CASCADE")
