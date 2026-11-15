"""Persistence for catalog.product_images."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection


class ProductImageRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def get_product(self, tenant_id: UUID, product_id: UUID) -> dict[str, Any] | None:
        row = (
            self._conn.execute(
                text(
                    """
                    SELECT id, tenant_id, sku, title
                    FROM catalog.products
                    WHERE tenant_id = :tenant_id AND id = :id
                    """
                ),
                {"tenant_id": str(tenant_id), "id": str(product_id)},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def lock_product(self, tenant_id: UUID, product_id: UUID) -> dict[str, Any] | None:
        row = (
            self._conn.execute(
                text(
                    """
                    SELECT id, tenant_id, sku, title
                    FROM catalog.products
                    WHERE tenant_id = :tenant_id AND id = :id
                    FOR UPDATE
                    """
                ),
                {"tenant_id": str(tenant_id), "id": str(product_id)},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def count_for_product(self, tenant_id: UUID, product_id: UUID) -> int:
        value = self._conn.execute(
            text(
                """
                SELECT count(*) FROM catalog.product_images
                WHERE tenant_id = :tenant_id AND product_id = :product_id
                """
            ),
            {"tenant_id": str(tenant_id), "product_id": str(product_id)},
        ).scalar_one()
        return int(value)

    def find_by_sha(self, tenant_id: UUID, product_id: UUID, sha256: str) -> dict[str, Any] | None:
        row = (
            self._conn.execute(
                text(
                    """
                    SELECT id FROM catalog.product_images
                    WHERE tenant_id = :tenant_id
                      AND product_id = :product_id
                      AND sha256 = :sha256
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "product_id": str(product_id),
                    "sha256": sha256,
                },
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def next_sort_order(self, tenant_id: UUID, product_id: UUID) -> int:
        value = self._conn.execute(
            text(
                """
                SELECT COALESCE(MAX(sort_order) + 1, 0)
                FROM catalog.product_images
                WHERE tenant_id = :tenant_id AND product_id = :product_id
                """
            ),
            {"tenant_id": str(tenant_id), "product_id": str(product_id)},
        ).scalar_one()
        return int(value)

    def insert(
        self,
        *,
        tenant_id: UUID,
        product_id: UUID,
        storage_key: str,
        thumb_key: str,
        content_type: str,
        width: int,
        height: int,
        size_bytes: int,
        sha256: str,
        is_primary: bool,
        sort_order: int,
        created_by: UUID,
    ) -> dict[str, Any]:
        image_id = uuid4()
        row = (
            self._conn.execute(
                text(
                    """
                    INSERT INTO catalog.product_images (
                      id, tenant_id, product_id, storage_key, thumb_key, content_type,
                      width, height, size_bytes, sha256, is_primary, sort_order, created_by
                    ) VALUES (
                      :id, :tenant_id, :product_id, :storage_key, :thumb_key, :content_type,
                      :width, :height, :size_bytes, :sha256, :is_primary, :sort_order,
                      :created_by
                    )
                    RETURNING id, tenant_id, product_id, storage_key, thumb_key, content_type,
                              width, height, size_bytes, sha256, is_primary, sort_order,
                              created_at, created_by
                    """
                ),
                {
                    "id": str(image_id),
                    "tenant_id": str(tenant_id),
                    "product_id": str(product_id),
                    "storage_key": storage_key,
                    "thumb_key": thumb_key,
                    "content_type": content_type,
                    "width": width,
                    "height": height,
                    "size_bytes": size_bytes,
                    "sha256": sha256,
                    "is_primary": is_primary,
                    "sort_order": sort_order,
                    "created_by": str(created_by),
                },
            )
            .mappings()
            .one()
        )
        return dict(row)

    def list_for_product(self, tenant_id: UUID, product_id: UUID) -> list[dict[str, Any]]:
        rows = (
            self._conn.execute(
                text(
                    """
                    SELECT id, tenant_id, product_id, storage_key, thumb_key, content_type,
                           width, height, size_bytes, sha256, is_primary, sort_order,
                           created_at, created_by
                    FROM catalog.product_images
                    WHERE tenant_id = :tenant_id AND product_id = :product_id
                    ORDER BY sort_order, created_at, id
                    """
                ),
                {"tenant_id": str(tenant_id), "product_id": str(product_id)},
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    def get(self, tenant_id: UUID, image_id: UUID) -> dict[str, Any] | None:
        row = (
            self._conn.execute(
                text(
                    """
                    SELECT id, tenant_id, product_id, storage_key, thumb_key, content_type,
                           width, height, size_bytes, sha256, is_primary, sort_order,
                           created_at, created_by
                    FROM catalog.product_images
                    WHERE tenant_id = :tenant_id AND id = :id
                    """
                ),
                {"tenant_id": str(tenant_id), "id": str(image_id)},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def clear_primary(self, tenant_id: UUID, product_id: UUID) -> None:
        self._conn.execute(
            text(
                """
                UPDATE catalog.product_images
                SET is_primary = FALSE
                WHERE tenant_id = :tenant_id
                  AND product_id = :product_id
                  AND is_primary = TRUE
                """
            ),
            {"tenant_id": str(tenant_id), "product_id": str(product_id)},
        )

    def set_primary(self, tenant_id: UUID, image_id: UUID) -> dict[str, Any] | None:
        row = (
            self._conn.execute(
                text(
                    """
                    UPDATE catalog.product_images
                    SET is_primary = TRUE
                    WHERE tenant_id = :tenant_id AND id = :id
                    RETURNING id, tenant_id, product_id, storage_key, thumb_key, content_type,
                              width, height, size_bytes, sha256, is_primary, sort_order,
                              created_at, created_by
                    """
                ),
                {"tenant_id": str(tenant_id), "id": str(image_id)},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def update_sort_orders(
        self, tenant_id: UUID, product_id: UUID, ordered_ids: list[UUID]
    ) -> None:
        for index, image_id in enumerate(ordered_ids):
            self._conn.execute(
                text(
                    """
                    UPDATE catalog.product_images
                    SET sort_order = :sort_order
                    WHERE tenant_id = :tenant_id
                      AND product_id = :product_id
                      AND id = :id
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "product_id": str(product_id),
                    "id": str(image_id),
                    "sort_order": index,
                },
            )

    def delete(self, tenant_id: UUID, image_id: UUID) -> dict[str, Any] | None:
        row = (
            self._conn.execute(
                text(
                    """
                    DELETE FROM catalog.product_images
                    WHERE tenant_id = :tenant_id AND id = :id
                    RETURNING id, tenant_id, product_id, storage_key, thumb_key, content_type,
                              width, height, size_bytes, sha256, is_primary, sort_order,
                              created_at, created_by
                    """
                ),
                {"tenant_id": str(tenant_id), "id": str(image_id)},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def promote_next_primary(self, tenant_id: UUID, product_id: UUID) -> dict[str, Any] | None:
        row = (
            self._conn.execute(
                text(
                    """
                    SELECT id FROM catalog.product_images
                    WHERE tenant_id = :tenant_id AND product_id = :product_id
                    ORDER BY sort_order, created_at, id
                    LIMIT 1
                    """
                ),
                {"tenant_id": str(tenant_id), "product_id": str(product_id)},
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return self.set_primary(tenant_id, UUID(str(row["id"])))

    def key_referenced(self, tenant_id: UUID, key: str) -> bool:
        value = self._conn.execute(
            text(
                """
                SELECT 1 FROM catalog.product_images
                WHERE tenant_id = :tenant_id
                  AND (storage_key = :key OR thumb_key = :key)
                LIMIT 1
                """
            ),
            {"tenant_id": str(tenant_id), "key": key},
        ).first()
        return value is not None

    def lock_content_sha(self, tenant_id: UUID, sha256: str) -> None:
        """Transaction-scoped advisory lock for content-addressed media keys.

        Serializes put/commit against check/unlink for the same tenant+sha.
        Call after the product row lock on upload; cleanup uses only this lock.
        """
        self._conn.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:tenant), hashtext(:sha))"),
            {"tenant": f"product-image:{tenant_id}", "sha": sha256},
        )

    def primary_image_id(self, tenant_id: UUID, product_id: UUID) -> UUID | None:
        row = (
            self._conn.execute(
                text(
                    """
                    SELECT id FROM catalog.product_images
                    WHERE tenant_id = :tenant_id
                      AND product_id = :product_id
                      AND is_primary = TRUE
                    LIMIT 1
                    """
                ),
                {"tenant_id": str(tenant_id), "product_id": str(product_id)},
            )
            .mappings()
            .first()
        )
        return UUID(str(row["id"])) if row else None

    def write_audit(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        action_type: str,
        entity_id: UUID,
        payload: dict[str, Any],
    ) -> None:
        self._conn.execute(
            text(
                """
                INSERT INTO platform.audit_log
                  (id, tenant_id, actor_user_id, action_type, entity_type, entity_id, payload_json)
                VALUES
                  (:id, :tenant_id, :actor_user_id, :action_type, 'product', :entity_id,
                   CAST(:payload AS jsonb))
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "actor_user_id": str(actor_user_id),
                "action_type": action_type,
                "entity_id": str(entity_id),
                "payload": json.dumps(payload),
            },
        )
