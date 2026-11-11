"""Catalog persistence."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection


class CatalogRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def list_products(self, tenant_id: UUID) -> list[dict[str, Any]]:
        rows = (
            self._conn.execute(
                text(
                    """
                SELECT id, tenant_id, sku, title, unit_price_rial, currency, is_active,
                       stock_warning_threshold, version, created_at, updated_at
                FROM catalog.products
                WHERE tenant_id = :tenant_id
                ORDER BY sku
                """
                ),
                {"tenant_id": str(tenant_id)},
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    def get_product(self, tenant_id: UUID, product_id: UUID) -> dict[str, Any] | None:
        row = (
            self._conn.execute(
                text(
                    """
                SELECT id, tenant_id, sku, title, unit_price_rial, currency, is_active,
                       stock_warning_threshold, version, created_at, updated_at
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

    def get_product_by_sku(self, tenant_id: UUID, sku: str) -> dict[str, Any] | None:
        row = (
            self._conn.execute(
                text(
                    """
                SELECT id, tenant_id, sku, title, unit_price_rial, currency, is_active,
                       stock_warning_threshold, version, created_at, updated_at
                FROM catalog.products
                WHERE tenant_id = :tenant_id AND sku = :sku
                """
                ),
                {"tenant_id": str(tenant_id), "sku": sku},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def create_product(
        self,
        *,
        tenant_id: UUID,
        sku: str,
        title: str,
        unit_price_rial: int,
        is_active: bool = True,
        stock_warning_threshold: int = 0,
    ) -> dict[str, Any]:
        product_id = uuid4()
        row = (
            self._conn.execute(
                text(
                    """
                INSERT INTO catalog.products (
                  id, tenant_id, sku, title, unit_price_rial, is_active, stock_warning_threshold
                ) VALUES (
                  :id, :tenant_id, :sku, :title, :unit_price_rial, :is_active, :threshold
                )
                RETURNING id, tenant_id, sku, title, unit_price_rial, currency, is_active,
                          stock_warning_threshold, version, created_at, updated_at
                """
                ),
                {
                    "id": str(product_id),
                    "tenant_id": str(tenant_id),
                    "sku": sku,
                    "title": title,
                    "unit_price_rial": unit_price_rial,
                    "is_active": is_active,
                    "threshold": stock_warning_threshold,
                },
            )
            .mappings()
            .one()
        )
        return dict(row)

    def update_product(
        self,
        *,
        tenant_id: UUID,
        product_id: UUID,
        expected_version: int,
        title: str | None,
        unit_price_rial: int | None,
        is_active: bool | None,
        stock_warning_threshold: int | None,
    ) -> dict[str, Any] | None:
        current = self.get_product(tenant_id, product_id)
        if current is None:
            return None
        if int(current["version"]) != expected_version:
            return {"__conflict__": True, "current": current}

        row = (
            self._conn.execute(
                text(
                    """
                UPDATE catalog.products
                SET title = COALESCE(:title, title),
                    unit_price_rial = COALESCE(:unit_price_rial, unit_price_rial),
                    is_active = COALESCE(:is_active, is_active),
                    stock_warning_threshold = COALESCE(:threshold, stock_warning_threshold),
                    version = version + 1,
                    updated_at = now()
                WHERE tenant_id = :tenant_id AND id = :id AND version = :expected_version
                RETURNING id, tenant_id, sku, title, unit_price_rial, currency, is_active,
                          stock_warning_threshold, version, created_at, updated_at
                """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "id": str(product_id),
                    "expected_version": expected_version,
                    "title": title,
                    "unit_price_rial": unit_price_rial,
                    "is_active": is_active,
                    "threshold": stock_warning_threshold,
                },
            )
            .mappings()
            .first()
        )
        return dict(row) if row else {"__conflict__": True, "current": current}

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
