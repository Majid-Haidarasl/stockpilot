"""Order cycle use cases sharing one UnitOfWork with inventory (ADR-002).

Lock order for every command:
  idempotency → order → products by id (reserve) → positions by id → reservation
Never lock the reservation before positions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.engine import Connection

from stockpilot.modules.inventory.adapters.outbound.commands import SqlInventoryCommands
from stockpilot.modules.inventory.adapters.outbound.repo import InventoryRepository
from stockpilot.modules.inventory.public import (
    AllocateStock,
    ConsumeStock,
    InactiveProduct,
    ReleaseStock,
    RequestedStock,
    ReserveStock,
)
from stockpilot.modules.sales.adapters.outbound.order_repo import OrderRepository
from stockpilot.modules.sales.domain.order import (
    InvalidOrderState,
    Order,
    OrderLine,
    OrderStatus,
)
from stockpilot.platform.outbox.writer import enqueue
from stockpilot.platform.time.clock import Clock, SystemClock


@dataclass(slots=True)
class CycleResult:
    order: Order
    http_status: int = 200
    problem_code: str | None = None
    problem_title: str | None = None
    problem_errors: list[dict[str, Any]] | None = None


class VersionConflict(Exception):
    pass


class OrderNotFound(Exception):
    pass


class OrderCycleService:
    def __init__(self, conn: Connection, clock: Clock | None = None) -> None:
        self._conn = conn
        self._orders = OrderRepository(conn)
        self._inventory_repo = InventoryRepository(conn)
        self._inventory = SqlInventoryCommands(conn)
        self._clock = clock or SystemClock()

    def reserve(
        self,
        *,
        tenant_id: UUID,
        order_id: UUID,
        actor_user_id: UUID,
        expected_version: int,
    ) -> CycleResult:
        order = self._require_order(tenant_id, order_id)
        if order.version != expected_version:
            raise VersionConflict()
        if order.status != OrderStatus.DRAFT:
            raise InvalidOrderState(f"Cannot reserve from status {order.status}")

        product_ids = [line.product_id for line in order.lines]
        products = self._orders.lock_products_for_update(tenant_id, product_ids)
        by_id = {UUID(str(p["id"])): p for p in products}
        frozen: list[OrderLine] = []
        requested: list[RequestedStock] = []
        for line in sorted(order.lines, key=lambda ln: ln.product_id):
            product = by_id[line.product_id]
            if not bool(product["is_active"]):
                raise InactiveProduct(f"Product {product['sku']} is inactive")
            frozen.append(
                OrderLine(
                    id=line.id,
                    product_id=line.product_id,
                    quantity=line.quantity,
                    product_sku=str(product["sku"]),
                    product_title=str(product["title"]),
                    unit_price_rial=int(product["unit_price_rial"]),
                    currency=str(product.get("currency") or "IRR"),
                )
            )
            requested.append(
                RequestedStock(
                    product_id=line.product_id,
                    quantity=line.quantity,
                    sku=str(product["sku"]),
                    is_active=True,
                )
            )
        order.lines = frozen
        now = self._clock.now()
        self._inventory.reserve_all(
            ReserveStock(
                tenant_id=tenant_id,
                order_id=order.id,
                items=tuple(requested),
                actor_user_id=actor_user_id,
            )
        )
        expected = order.version
        order.reserve(now)
        if not self._orders.save_order(order, expected_version=expected):
            raise VersionConflict()
        self._orders.write_audit(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action_type="order.reserved",
            entity_id=order.id,
            payload={"expires_at": order.expires_at.isoformat() if order.expires_at else None},
        )
        enqueue(
            self._conn,
            tenant_id=tenant_id,
            event_type="OrderReserved",
            event_version="v1",
            aggregate_type="order",
            aggregate_id=order.id,
            payload={"order_id": str(order.id), "status": order.status.value},
        )
        return CycleResult(order=order)

    def confirm(
        self,
        *,
        tenant_id: UUID,
        order_id: UUID,
        actor_user_id: UUID,
        expected_version: int,
    ) -> CycleResult:
        order = self._require_order(tenant_id, order_id)
        if order.version != expected_version:
            raise VersionConflict()
        now = self._clock.now()
        if order.status == OrderStatus.EXPIRED:
            return CycleResult(
                order=order,
                http_status=409,
                problem_code="RESERVATION_EXPIRED",
                problem_title="Reservation has expired",
            )
        if order.status == OrderStatus.RESERVED and order.expires_at is not None:
            from datetime import UTC

            expires = order.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
            if now >= expires:
                return self._expire_locked(
                    order=order,
                    actor_user_id=actor_user_id,
                    now=now,
                    as_confirm_conflict=True,
                )

        if order.status != OrderStatus.RESERVED:
            raise InvalidOrderState(f"Cannot confirm from status {order.status}")

        reservation_id = self._inventory_repo.get_reservation_id_by_order(tenant_id, order.id)
        if reservation_id is None:
            raise OrderNotFound()
        self._inventory.allocate(
            AllocateStock(
                tenant_id=tenant_id,
                reservation_id=reservation_id,
                actor_user_id=actor_user_id,
            )
        )
        expected = order.version
        order.confirm(now)
        if not self._orders.save_order(order, expected_version=expected):
            raise VersionConflict()
        self._orders.write_audit(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action_type="order.confirmed",
            entity_id=order.id,
            payload={},
        )
        enqueue(
            self._conn,
            tenant_id=tenant_id,
            event_type="OrderConfirmed",
            event_version="v1",
            aggregate_type="order",
            aggregate_id=order.id,
            payload={"order_id": str(order.id)},
        )
        return CycleResult(order=order)

    def cancel(
        self,
        *,
        tenant_id: UUID,
        order_id: UUID,
        actor_user_id: UUID,
        expected_version: int,
    ) -> CycleResult:
        order = self._require_order(tenant_id, order_id)
        if order.version != expected_version:
            raise VersionConflict()
        # Second cancel: already terminal cancelled — no stock change.
        if order.status == OrderStatus.CANCELLED:
            return CycleResult(order=order)

        now = self._clock.now()
        reservation_id = self._inventory_repo.get_reservation_id_by_order(tenant_id, order.id)
        releasable = order.status in {OrderStatus.RESERVED, OrderStatus.CONFIRMED}
        if releasable and reservation_id is not None:
            self._inventory.release(
                ReleaseStock(
                    tenant_id=tenant_id,
                    reservation_id=reservation_id,
                    actor_user_id=actor_user_id,
                    as_expired=False,
                )
            )
        expected = order.version
        order.cancel(now)
        if not self._orders.save_order(order, expected_version=expected):
            raise VersionConflict()
        self._orders.write_audit(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action_type="order.cancelled",
            entity_id=order.id,
            payload={},
        )
        enqueue(
            self._conn,
            tenant_id=tenant_id,
            event_type="OrderCancelled",
            event_version="v1",
            aggregate_type="order",
            aggregate_id=order.id,
            payload={"order_id": str(order.id)},
        )
        return CycleResult(order=order)

    def expire(
        self,
        *,
        tenant_id: UUID,
        order_id: UUID,
        actor_user_id: UUID | None = None,
    ) -> CycleResult:
        order = self._require_order(tenant_id, order_id)
        if order.status != OrderStatus.RESERVED:
            return CycleResult(order=order)
        return self._expire_locked(
            order=order,
            actor_user_id=actor_user_id,
            now=self._clock.now(),
            as_confirm_conflict=False,
        )

    def ship(
        self,
        *,
        tenant_id: UUID,
        order_id: UUID,
        actor_user_id: UUID,
        expected_version: int,
    ) -> CycleResult:
        order = self._require_order(tenant_id, order_id)
        if order.version != expected_version:
            raise VersionConflict()
        reservation_id = self._inventory_repo.get_reservation_id_by_order(tenant_id, order.id)
        if reservation_id is None:
            raise OrderNotFound()
        self._inventory.consume(
            ConsumeStock(
                tenant_id=tenant_id,
                reservation_id=reservation_id,
                actor_user_id=actor_user_id,
            )
        )
        now = self._clock.now()
        expected = order.version
        order.ship(now)
        if not self._orders.save_order(order, expected_version=expected):
            raise VersionConflict()
        self._orders.write_audit(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action_type="order.shipped",
            entity_id=order.id,
            payload={},
        )
        enqueue(
            self._conn,
            tenant_id=tenant_id,
            event_type="OrderShipped",
            event_version="v1",
            aggregate_type="order",
            aggregate_id=order.id,
            payload={"order_id": str(order.id)},
        )
        return CycleResult(order=order)

    def _expire_locked(
        self,
        *,
        order: Order,
        actor_user_id: UUID | None,
        now: datetime,
        as_confirm_conflict: bool,
    ) -> CycleResult:
        reservation_id = self._inventory_repo.get_reservation_id_by_order(order.tenant_id, order.id)
        if reservation_id is not None:
            self._inventory.release(
                ReleaseStock(
                    tenant_id=order.tenant_id,
                    reservation_id=reservation_id,
                    actor_user_id=actor_user_id,
                    as_expired=True,
                )
            )
        expected = order.version
        order.expire(now)
        if not self._orders.save_order(order, expected_version=expected):
            raise VersionConflict()
        self._orders.write_audit(
            tenant_id=order.tenant_id,
            actor_user_id=actor_user_id,
            action_type="order.expired",
            entity_id=order.id,
            payload={},
        )
        enqueue(
            self._conn,
            tenant_id=order.tenant_id,
            event_type="OrderExpired",
            event_version="v1",
            aggregate_type="order",
            aggregate_id=order.id,
            payload={"order_id": str(order.id)},
        )
        if as_confirm_conflict:
            return CycleResult(
                order=order,
                http_status=409,
                problem_code="RESERVATION_EXPIRED",
                problem_title="Reservation has expired",
            )
        return CycleResult(order=order)

    def _require_order(self, tenant_id: UUID, order_id: UUID) -> Order:
        order = self._orders.get_order_for_update(tenant_id, order_id)
        if order is None:
            raise OrderNotFound()
        return order
