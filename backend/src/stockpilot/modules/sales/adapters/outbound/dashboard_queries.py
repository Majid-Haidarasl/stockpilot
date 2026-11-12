"""Flat SQL reads for the limited dashboard (tenant-scoped via RLS + filters)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection


class DashboardQueries:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def order_counts_by_status(self, tenant_id: UUID) -> dict[str, int]:
        rows = (
            self._conn.execute(
                text(
                    """
                SELECT status, COUNT(*)::int AS cnt
                FROM sales.orders
                WHERE tenant_id = :tenant_id
                GROUP BY status
                """
                ),
                {"tenant_id": str(tenant_id)},
            )
            .mappings()
            .all()
        )
        return {str(r["status"]): int(r["cnt"]) for r in rows}

    def shipped_total_rial(
        self,
        tenant_id: UUID,
        *,
        range_from: datetime,
        range_to: datetime,
    ) -> int:
        value = self._conn.execute(
            text(
                """
                SELECT COALESCE(SUM(ol.quantity::bigint * ol.unit_price_rial), 0)
                FROM sales.orders o
                JOIN sales.order_lines ol
                  ON ol.tenant_id = o.tenant_id AND ol.order_id = o.id
                WHERE o.tenant_id = :tenant_id
                  AND o.status = 'SHIPPED'
                  AND o.shipped_at IS NOT NULL
                  AND o.shipped_at >= :range_from
                  AND o.shipped_at <= :range_to
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "range_from": range_from,
                "range_to": range_to,
            },
        ).scalar()
        return int(value or 0)

    def products_below_threshold(self, tenant_id: UUID) -> list[dict[str, Any]]:
        rows = (
            self._conn.execute(
                text(
                    """
                SELECT p.id AS product_id,
                       p.sku,
                       p.title,
                       p.stock_warning_threshold,
                       (COALESCE(sp.on_hand, 0) - COALESCE(sp.reserved, 0))::int AS available
                FROM catalog.products p
                LEFT JOIN inventory.stock_positions sp
                  ON sp.tenant_id = p.tenant_id AND sp.product_id = p.id
                WHERE p.tenant_id = :tenant_id
                  AND (COALESCE(sp.on_hand, 0) - COALESCE(sp.reserved, 0))
                      <= p.stock_warning_threshold
                ORDER BY p.sku
                """
                ),
                {"tenant_id": str(tenant_id)},
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]
