"""Order persistence adapters."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from stockpilot.modules.sales.domain.order import Order, OrderLine, OrderStatus


class OrderRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def customer_exists(self, tenant_id: UUID, customer_id: UUID) -> bool:
        row = self._conn.execute(
            text(
                """
                SELECT 1 FROM sales.customers
                WHERE tenant_id = :tenant_id AND id = :id
                LIMIT 1
                """
            ),
            {"tenant_id": str(tenant_id), "id": str(customer_id)},
        ).first()
        return row is not None

    def get_product_snapshot(self, tenant_id: UUID, product_id: UUID) -> dict[str, Any] | None:
        """Read catalog product fields needed to snapshot a draft line estimate."""
        row = (
            self._conn.execute(
                text(
                    """
                SELECT id, sku, title, unit_price_rial, currency, is_active
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

    def lock_products_for_update(
        self, tenant_id: UUID, product_ids: list[UUID]
    ) -> list[dict[str, Any]]:
        """Lock catalog products in stable id order (reserve path)."""
        locked: list[dict[str, Any]] = []
        for product_id in sorted(product_ids, key=str):
            row = (
                self._conn.execute(
                    text(
                        """
                    SELECT id, sku, title, unit_price_rial, currency, is_active
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
            if row is None:
                raise LookupError(f"Product {product_id} not found")
            locked.append(dict(row))
        return locked

    def get_order_for_update(self, tenant_id: UUID, order_id: UUID) -> Order | None:
        row = (
            self._conn.execute(
                text(
                    """
                SELECT id, tenant_id, customer_id, status, version,
                       reserved_at, expires_at, confirmed_at, shipped_at, cancelled_at,
                       created_at, updated_at
                FROM sales.orders
                WHERE tenant_id = :tenant_id AND id = :id
                FOR UPDATE
                """
                ),
                {"tenant_id": str(tenant_id), "id": str(order_id)},
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return self._hydrate(row)

    def list_expired_reserved(
        self, tenant_id: UUID, *, now: datetime, limit: int = 50
    ) -> list[UUID]:
        limit = max(1, min(limit, 100))
        rows = self._conn.execute(
            text(
                """
                SELECT id FROM sales.orders
                WHERE tenant_id = :tenant_id
                  AND status = 'RESERVED'
                  AND expires_at IS NOT NULL
                  AND expires_at <= :now
                ORDER BY expires_at, id
                LIMIT :limit
                """
            ),
            {"tenant_id": str(tenant_id), "now": now, "limit": limit},
        ).fetchall()
        return [UUID(str(r[0])) for r in rows]

    def get_order(self, tenant_id: UUID, order_id: UUID) -> Order | None:
        row = (
            self._conn.execute(
                text(
                    """
                SELECT id, tenant_id, customer_id, status, version,
                       reserved_at, expires_at, confirmed_at, shipped_at, cancelled_at,
                       created_at, updated_at
                FROM sales.orders
                WHERE tenant_id = :tenant_id AND id = :id
                """
                ),
                {"tenant_id": str(tenant_id), "id": str(order_id)},
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return self._hydrate(row)

    def _hydrate(self, row: Any) -> Order:
        lines = (
            self._conn.execute(
                text(
                    """
                SELECT id, product_id, quantity, product_sku, product_title,
                       unit_price_rial, currency
                FROM sales.order_lines
                WHERE tenant_id = :tenant_id AND order_id = :order_id
                ORDER BY product_sku
                """
                ),
                {"tenant_id": str(row["tenant_id"]), "order_id": str(row["id"])},
            )
            .mappings()
            .all()
        )
        return Order(
            id=UUID(str(row["id"])),
            tenant_id=UUID(str(row["tenant_id"])),
            customer_id=UUID(str(row["customer_id"])),
            status=OrderStatus(str(row["status"])),
            version=int(row["version"]),
            reserved_at=row["reserved_at"],
            expires_at=row["expires_at"],
            confirmed_at=row["confirmed_at"],
            shipped_at=row["shipped_at"],
            cancelled_at=row["cancelled_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            lines=[
                OrderLine(
                    id=UUID(str(line["id"])),
                    product_id=UUID(str(line["product_id"])),
                    quantity=int(line["quantity"]),
                    product_sku=str(line["product_sku"]),
                    product_title=str(line["product_title"]),
                    unit_price_rial=int(line["unit_price_rial"]),
                    currency=str(line["currency"]),
                )
                for line in lines
            ],
        )

    def insert_order(self, order: Order) -> None:
        self._conn.execute(
            text(
                """
                INSERT INTO sales.orders (
                  id, tenant_id, customer_id, status, version,
                  reserved_at, expires_at, confirmed_at, shipped_at, cancelled_at
                ) VALUES (
                  :id, :tenant_id, :customer_id, :status, :version,
                  :reserved_at, :expires_at, :confirmed_at, :shipped_at, :cancelled_at
                )
                """
            ),
            self._order_params(order),
        )
        self._replace_lines(order)

    def save_order(self, order: Order, *, expected_version: int) -> bool:
        result = self._conn.execute(
            text(
                """
                UPDATE sales.orders
                SET customer_id = :customer_id,
                    status = :status,
                    version = :version,
                    reserved_at = :reserved_at,
                    expires_at = :expires_at,
                    confirmed_at = :confirmed_at,
                    shipped_at = :shipped_at,
                    cancelled_at = :cancelled_at,
                    updated_at = now()
                WHERE id = :id AND tenant_id = :tenant_id AND version = :expected_version
                """
            ),
            {**self._order_params(order), "expected_version": expected_version},
        )
        if result.rowcount != 1:
            return False
        self._conn.execute(
            text(
                """
                DELETE FROM sales.order_lines
                WHERE tenant_id = :tenant_id AND order_id = :order_id
                """
            ),
            {"tenant_id": str(order.tenant_id), "order_id": str(order.id)},
        )
        self._replace_lines(order)
        return True

    def list_orders(
        self,
        tenant_id: UUID,
        *,
        status: str | None = None,
        limit: int = 50,
        cursor_created_at: datetime | None = None,
        cursor_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 100))
        params: dict[str, Any] = {"tenant_id": str(tenant_id), "limit": limit}
        filters = ["tenant_id = :tenant_id"]
        if status is not None:
            filters.append("status = :status")
            params["status"] = status
        if cursor_created_at is not None and cursor_id is not None:
            filters.append("(created_at, id) < (:cursor_created_at, :cursor_id)")
            params["cursor_created_at"] = cursor_created_at
            params["cursor_id"] = str(cursor_id)
        where = " AND ".join(filters)
        rows = (
            self._conn.execute(
                text(
                    f"""
                SELECT id, tenant_id, customer_id, status, version,
                       reserved_at, expires_at, created_at, updated_at
                FROM sales.orders
                WHERE {where}
                ORDER BY created_at DESC, id DESC
                LIMIT :limit
                """
                ),
                params,
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    def list_order_timeline(self, tenant_id: UUID, order_id: UUID) -> list[dict[str, Any]]:
        """Safe change events for one order (tenant-scoped via RLS + explicit filter)."""
        rows = (
            self._conn.execute(
                text(
                    """
                SELECT a.id,
                       a.action_type,
                       a.created_at,
                       a.payload_json,
                       u.display_name AS actor_display_name
                FROM platform.audit_log a
                LEFT JOIN access.users u ON u.id = a.actor_user_id
                WHERE a.tenant_id = :tenant_id
                  AND a.entity_type = 'order'
                  AND a.entity_id = :order_id
                ORDER BY a.created_at ASC, a.id ASC
                """
                ),
                {"tenant_id": str(tenant_id), "order_id": str(order_id)},
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    def write_audit(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID | None,
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
                  (:id, :tenant_id, :actor_user_id, :action_type, 'order', :entity_id,
                   CAST(:payload AS jsonb))
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "actor_user_id": str(actor_user_id) if actor_user_id else None,
                "action_type": action_type,
                "entity_id": str(entity_id),
                "payload": json.dumps(payload),
            },
        )

    def _replace_lines(self, order: Order) -> None:
        for line in order.lines:
            self._conn.execute(
                text(
                    """
                    INSERT INTO sales.order_lines (
                      id, tenant_id, order_id, product_id, quantity,
                      product_sku, product_title, unit_price_rial, currency
                    ) VALUES (
                      :id, :tenant_id, :order_id, :product_id, :quantity,
                      :product_sku, :product_title, :unit_price_rial, :currency
                    )
                    """
                ),
                {
                    "id": str(line.id),
                    "tenant_id": str(order.tenant_id),
                    "order_id": str(order.id),
                    "product_id": str(line.product_id),
                    "quantity": line.quantity,
                    "product_sku": line.product_sku,
                    "product_title": line.product_title,
                    "unit_price_rial": line.unit_price_rial,
                    "currency": line.currency,
                },
            )

    def _order_params(self, order: Order) -> dict[str, Any]:
        return {
            "id": str(order.id),
            "tenant_id": str(order.tenant_id),
            "customer_id": str(order.customer_id),
            "status": order.status.value,
            "version": order.version,
            "reserved_at": order.reserved_at,
            "expires_at": order.expires_at,
            "confirmed_at": order.confirmed_at,
            "shipped_at": order.shipped_at,
            "cancelled_at": order.cancelled_at,
        }
