"""SQLAlchemy staging adapter for InventoryCommands (no commit)."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.engine import Connection

from stockpilot.modules.inventory.adapters.outbound.repo import InventoryRepository
from stockpilot.modules.inventory.domain.models import (
    MAX_LINE_QUANTITY,
    MAX_RESERVATION_LINES,
    DuplicateProductLine,
    InactiveProduct,
    InsufficientStock,
    InvalidQuantity,
    Reservation,
    ReservationConflict,
    ReservationLine,
    ReservationStatus,
    StockPosition,
    StockShortfall,
    TooManyLines,
    reservation_expires_at,
)
from stockpilot.modules.inventory.public import (
    AllocateStock,
    ConsumeStock,
    ReleaseStock,
    RequestedStock,
    ReserveStock,
)


class SqlInventoryCommands:
    """Stages reservation/counter/movement changes on the shared connection."""

    def __init__(self, conn: Connection) -> None:
        self._repo = InventoryRepository(conn)

    def reserve_all(self, command: ReserveStock) -> UUID:
        items = self._validated_items(command.items)
        # Lock positions in stable product_id order; missing position = zero available.
        locked: list[tuple[RequestedStock, StockPosition | None]] = []
        shortfalls: list[StockShortfall] = []
        for item in items:
            position = self._repo.get_position_for_update(command.tenant_id, item.product_id)
            available = 0 if position is None else position.available
            if item.quantity > available:
                shortfalls.append(
                    StockShortfall(
                        sku=item.sku,
                        requested=item.quantity,
                        available=available,
                    )
                )
            locked.append((item, position))

        if shortfalls:
            raise InsufficientStock(shortfalls)

        reservation_id = uuid4()
        reservation = Reservation(
            id=reservation_id,
            tenant_id=command.tenant_id,
            order_id=command.order_id,
            status=ReservationStatus.HELD,
            expires_at=reservation_expires_at(),
            version=1,
            lines=[],
        )
        for item, position in locked:
            assert position is not None  # shortfalls would have raised
            position.apply_reserve(item.quantity)
            self._repo.save_position(position)
            line = ReservationLine(
                id=uuid4(),
                product_id=item.product_id,
                quantity=item.quantity,
                sku=item.sku,
            )
            reservation.lines.append(line)
            self._repo.insert_movement(
                tenant_id=command.tenant_id,
                product_id=item.product_id,
                physical_delta=0,
                reserved_delta=item.quantity,
                reason="reserve",
                reference=f"reserve:{command.order_id}:{item.product_id}",
                actor_user_id=command.actor_user_id,
            )

        self._repo.insert_reservation(reservation)
        self._repo.write_audit(
            tenant_id=command.tenant_id,
            actor_user_id=command.actor_user_id,
            action_type="inventory.reserve",
            entity_id=reservation_id,
            payload={
                "order_id": str(command.order_id),
                "lines": [
                    {"product_id": str(line.product_id), "quantity": line.quantity}
                    for line in reservation.lines
                ],
            },
        )
        return reservation_id

    def allocate(self, command: AllocateStock) -> None:
        reservation = self._repo.get_reservation_for_update(
            command.tenant_id, command.reservation_id
        )
        if reservation is None:
            raise ReservationConflict("Reservation not found")
        reservation.allocate()
        self._repo.save_reservation(reservation)
        self._repo.write_audit(
            tenant_id=command.tenant_id,
            actor_user_id=command.actor_user_id,
            action_type="inventory.allocate",
            entity_id=reservation.id,
            payload={"order_id": str(reservation.order_id)},
        )

    def release(self, command: ReleaseStock) -> None:
        reservation = self._repo.get_reservation_for_update(
            command.tenant_id, command.reservation_id
        )
        if reservation is None:
            raise ReservationConflict("Reservation not found")
        if command.as_expired:
            reservation.expire()
            reason = "expire"
        else:
            reservation.release()
            reason = "release"
        for line in sorted(reservation.lines, key=lambda ln: ln.product_id):
            position = self._repo.get_position_for_update(command.tenant_id, line.product_id)
            if position is None:
                raise ReservationConflict("Missing stock position for reservation line")
            position.apply_release(line.quantity)
            self._repo.save_position(position)
            self._repo.insert_movement(
                tenant_id=command.tenant_id,
                product_id=line.product_id,
                physical_delta=0,
                reserved_delta=-line.quantity,
                reason=reason,
                reference=f"{reason}:{reservation.order_id}:{line.product_id}",
                actor_user_id=command.actor_user_id,
            )
        self._repo.save_reservation(reservation)
        self._repo.write_audit(
            tenant_id=command.tenant_id,
            actor_user_id=command.actor_user_id,
            action_type=f"inventory.{reason}",
            entity_id=reservation.id,
            payload={"order_id": str(reservation.order_id)},
        )

    def consume(self, command: ConsumeStock) -> None:
        reservation = self._repo.get_reservation_for_update(
            command.tenant_id, command.reservation_id
        )
        if reservation is None:
            raise ReservationConflict("Reservation not found")
        reservation.consume()
        for line in sorted(reservation.lines, key=lambda ln: ln.product_id):
            position = self._repo.get_position_for_update(command.tenant_id, line.product_id)
            if position is None:
                raise ReservationConflict("Missing stock position for reservation line")
            position.apply_consume(line.quantity)
            self._repo.save_position(position)
            self._repo.insert_movement(
                tenant_id=command.tenant_id,
                product_id=line.product_id,
                physical_delta=-line.quantity,
                reserved_delta=-line.quantity,
                reason="consume",
                reference=f"consume:{reservation.order_id}:{line.product_id}",
                actor_user_id=command.actor_user_id,
            )
        self._repo.save_reservation(reservation)
        self._repo.write_audit(
            tenant_id=command.tenant_id,
            actor_user_id=command.actor_user_id,
            action_type="inventory.consume",
            entity_id=reservation.id,
            payload={"order_id": str(reservation.order_id)},
        )

    def _validated_items(self, items: tuple[RequestedStock, ...]) -> list[RequestedStock]:
        if not items:
            raise InvalidQuantity("Reservation requires at least one line")
        if len(items) > MAX_RESERVATION_LINES:
            raise TooManyLines(f"At most {MAX_RESERVATION_LINES} lines allowed")
        seen: set[UUID] = set()
        for item in items:
            if item.product_id in seen:
                raise DuplicateProductLine(f"Duplicate product {item.product_id}")
            seen.add(item.product_id)
            if item.quantity <= 0:
                raise InvalidQuantity("Line quantity must be positive")
            if item.quantity > MAX_LINE_QUANTITY:
                raise InvalidQuantity(f"Quantity cannot exceed {MAX_LINE_QUANTITY}")
            if not item.is_active:
                raise InactiveProduct(f"Product {item.sku} is inactive")
        return sorted(items, key=lambda item: item.product_id)
