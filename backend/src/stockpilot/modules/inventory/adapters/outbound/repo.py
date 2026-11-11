"""Inventory persistence adapters."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from stockpilot.modules.inventory.domain.models import DEFAULT_WAREHOUSE, StockPosition


class InventoryRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def product_exists(self, tenant_id: UUID, product_id: UUID) -> bool:
        row = self._conn.execute(
            text(
                """
                SELECT 1 FROM catalog.products
                WHERE tenant_id = :tenant_id AND id = :id
                LIMIT 1
                """
            ),
            {"tenant_id": str(tenant_id), "id": str(product_id)},
        ).first()
        return row is not None

    def list_positions(self, tenant_id: UUID) -> list[dict[str, Any]]:
        rows = (
            self._conn.execute(
                text(
                    """
                SELECT sp.id, sp.tenant_id, sp.warehouse_code, sp.product_id,
                       sp.on_hand, sp.reserved, sp.version,
                       p.sku, p.title, p.stock_warning_threshold
                FROM inventory.stock_positions sp
                JOIN catalog.products p
                  ON p.tenant_id = sp.tenant_id AND p.id = sp.product_id
                WHERE sp.tenant_id = :tenant_id
                ORDER BY p.sku
                """
                ),
                {"tenant_id": str(tenant_id)},
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    def list_movements(
        self,
        tenant_id: UUID,
        *,
        product_id: UUID | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 100))
        params: dict[str, Any] = {"tenant_id": str(tenant_id), "limit": limit}
        product_filter = ""
        if product_id is not None:
            product_filter = "AND m.product_id = :product_id"
            params["product_id"] = str(product_id)
        rows = (
            self._conn.execute(
                text(
                    f"""
                SELECT m.id, m.tenant_id, m.warehouse_code, m.product_id,
                       m.physical_delta, m.reserved_delta, m.reason, m.reference,
                       m.actor_user_id, m.created_at, p.sku, p.title
                FROM inventory.movements m
                JOIN catalog.products p
                  ON p.tenant_id = m.tenant_id AND p.id = m.product_id
                WHERE m.tenant_id = :tenant_id
                {product_filter}
                ORDER BY m.created_at DESC, m.id DESC
                LIMIT :limit
                """
                ),
                params,
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    def get_position_for_update(
        self,
        tenant_id: UUID,
        product_id: UUID,
        warehouse_code: str = DEFAULT_WAREHOUSE,
    ) -> StockPosition | None:
        row = (
            self._conn.execute(
                text(
                    """
                SELECT id, tenant_id, warehouse_code, product_id, on_hand, reserved, version
                FROM inventory.stock_positions
                WHERE tenant_id = :tenant_id
                  AND product_id = :product_id
                  AND warehouse_code = :warehouse_code
                FOR UPDATE
                """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "product_id": str(product_id),
                    "warehouse_code": warehouse_code,
                },
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return StockPosition(
            id=UUID(str(row["id"])),
            tenant_id=UUID(str(row["tenant_id"])),
            warehouse_code=str(row["warehouse_code"]),
            product_id=UUID(str(row["product_id"])),
            on_hand=int(row["on_hand"]),
            reserved=int(row["reserved"]),
            version=int(row["version"]),
        )

    def create_position(
        self,
        *,
        tenant_id: UUID,
        product_id: UUID,
        warehouse_code: str = DEFAULT_WAREHOUSE,
        on_hand: int = 0,
        reserved: int = 0,
    ) -> StockPosition:
        position_id = uuid4()
        self._conn.execute(
            text(
                """
                INSERT INTO inventory.stock_positions (
                  id, tenant_id, warehouse_code, product_id, on_hand, reserved
                ) VALUES (
                  :id, :tenant_id, :warehouse_code, :product_id, :on_hand, :reserved
                )
                ON CONFLICT (tenant_id, warehouse_code, product_id) DO NOTHING
                """
            ),
            {
                "id": str(position_id),
                "tenant_id": str(tenant_id),
                "warehouse_code": warehouse_code,
                "product_id": str(product_id),
                "on_hand": on_hand,
                "reserved": reserved,
            },
        )
        locked = self.get_position_for_update(tenant_id, product_id, warehouse_code)
        if locked is None:
            raise RuntimeError("Failed to create or lock stock position")
        return locked

    def ensure_position_for_update(
        self,
        *,
        tenant_id: UUID,
        product_id: UUID,
        warehouse_code: str = DEFAULT_WAREHOUSE,
    ) -> StockPosition:
        existing = self.get_position_for_update(tenant_id, product_id, warehouse_code)
        if existing is not None:
            return existing
        return self.create_position(
            tenant_id=tenant_id,
            product_id=product_id,
            warehouse_code=warehouse_code,
        )

    def save_position(self, position: StockPosition) -> None:
        self._conn.execute(
            text(
                """
                UPDATE inventory.stock_positions
                SET on_hand = :on_hand,
                    reserved = :reserved,
                    version = :version,
                    updated_at = now()
                WHERE id = :id AND tenant_id = :tenant_id AND version = :expected_version
                """
            ),
            {
                "id": str(position.id),
                "tenant_id": str(position.tenant_id),
                "on_hand": position.on_hand,
                "reserved": position.reserved,
                "version": position.version,
                "expected_version": position.version - 1,
            },
        )

    def movement_exists(self, tenant_id: UUID, reference: str) -> bool:
        row = self._conn.execute(
            text(
                """
                SELECT 1 FROM inventory.movements
                WHERE tenant_id = :tenant_id AND reference = :reference
                LIMIT 1
                """
            ),
            {"tenant_id": str(tenant_id), "reference": reference},
        ).first()
        return row is not None

    def insert_movement(
        self,
        *,
        tenant_id: UUID,
        product_id: UUID,
        physical_delta: int,
        reserved_delta: int,
        reason: str,
        reference: str | None,
        actor_user_id: UUID | None,
        warehouse_code: str = DEFAULT_WAREHOUSE,
    ) -> dict[str, Any]:
        movement_id = uuid4()
        row = (
            self._conn.execute(
                text(
                    """
                INSERT INTO inventory.movements (
                  id, tenant_id, warehouse_code, product_id,
                  physical_delta, reserved_delta, reason, reference, actor_user_id
                ) VALUES (
                  :id, :tenant_id, :warehouse_code, :product_id,
                  :physical_delta, :reserved_delta, :reason, :reference, :actor_user_id
                )
                RETURNING id, tenant_id, warehouse_code, product_id,
                          physical_delta, reserved_delta, reason, reference,
                          actor_user_id, created_at
                """
                ),
                {
                    "id": str(movement_id),
                    "tenant_id": str(tenant_id),
                    "warehouse_code": warehouse_code,
                    "product_id": str(product_id),
                    "physical_delta": physical_delta,
                    "reserved_delta": reserved_delta,
                    "reason": reason,
                    "reference": reference,
                    "actor_user_id": str(actor_user_id) if actor_user_id else None,
                },
            )
            .mappings()
            .one()
        )
        return dict(row)

    def balance_report(self, tenant_id: UUID | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        tenant_filter = ""
        if tenant_id is not None:
            tenant_filter = "WHERE sp.tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)
        rows = (
            self._conn.execute(
                text(
                    f"""
                SELECT sp.tenant_id, sp.product_id, sp.warehouse_code,
                       sp.on_hand, sp.reserved,
                       COALESCE(SUM(m.physical_delta), 0) AS physical_sum,
                       COALESCE(SUM(m.reserved_delta), 0) AS reserved_sum
                FROM inventory.stock_positions sp
                LEFT JOIN inventory.movements m
                  ON m.tenant_id = sp.tenant_id
                 AND m.product_id = sp.product_id
                 AND m.warehouse_code = sp.warehouse_code
                {tenant_filter}
                GROUP BY sp.tenant_id, sp.product_id, sp.warehouse_code, sp.on_hand, sp.reserved
                ORDER BY sp.tenant_id, sp.product_id
                """
                ),
                params,
            )
            .mappings()
            .all()
        )
        report: list[dict[str, Any]] = []
        for row in rows:
            physical_sum = int(row["physical_sum"])
            reserved_sum = int(row["reserved_sum"])
            on_hand = int(row["on_hand"])
            reserved = int(row["reserved"])
            report.append(
                {
                    "tenant_id": str(row["tenant_id"]),
                    "product_id": str(row["product_id"]),
                    "warehouse_code": str(row["warehouse_code"]),
                    "on_hand": on_hand,
                    "reserved": reserved,
                    "physical_sum": physical_sum,
                    "reserved_sum": reserved_sum,
                    "physical_ok": physical_sum == on_hand,
                    "reserved_ok": reserved_sum == reserved,
                }
            )
        return report

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
                  (:id, :tenant_id, :actor_user_id, :action_type, 'stock_position', :entity_id,
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
