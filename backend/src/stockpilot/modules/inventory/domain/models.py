"""Inventory domain types, stock position invariants, and reservations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID

MAX_ON_HAND = 1_000_000_000
MAX_LINE_QUANTITY = 100_000
MAX_RESERVATION_LINES = 20
RESERVATION_TTL = timedelta(minutes=30)
DEFAULT_WAREHOUSE = "main"


class InventoryError(Exception):
    """Base inventory domain error."""


class InvalidQuantity(InventoryError):
    pass


class StockInvariantViolation(InventoryError):
    pass


class InactiveProduct(InventoryError):
    pass


class DuplicateProductLine(InventoryError):
    pass


class TooManyLines(InventoryError):
    pass


class ReservationConflict(InventoryError):
    pass


@dataclass(frozen=True, slots=True)
class StockShortfall:
    sku: str
    requested: int
    available: int


class InsufficientStock(InventoryError):
    def __init__(self, shortfalls: list[StockShortfall]) -> None:
        self.shortfalls = shortfalls
        detail = ", ".join(f"{s.sku}: need {s.requested} have {s.available}" for s in shortfalls)
        super().__init__(f"Insufficient stock: {detail}")


@dataclass(frozen=True, slots=True)
class Quantity:
    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise InvalidQuantity("Quantity cannot be negative")


class ReservationStatus(StrEnum):
    HELD = "HELD"
    ALLOCATED = "ALLOCATED"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"
    CONSUMED = "CONSUMED"


@dataclass(slots=True)
class ReservationLine:
    id: UUID
    product_id: UUID
    quantity: int
    sku: str = ""


@dataclass(slots=True)
class Reservation:
    id: UUID
    tenant_id: UUID
    order_id: UUID
    status: ReservationStatus
    expires_at: datetime | None
    version: int
    lines: list[ReservationLine] = field(default_factory=list)

    def allocate(self) -> None:
        if self.status != ReservationStatus.HELD:
            raise ReservationConflict(f"Cannot allocate from status {self.status}")
        self.status = ReservationStatus.ALLOCATED
        self.expires_at = None
        self.version += 1

    def release(self) -> None:
        if self.status not in (ReservationStatus.HELD, ReservationStatus.ALLOCATED):
            raise ReservationConflict(f"Cannot release from status {self.status}")
        self.status = ReservationStatus.RELEASED
        self.version += 1

    def expire(self) -> None:
        if self.status != ReservationStatus.HELD:
            raise ReservationConflict(f"Cannot expire from status {self.status}")
        self.status = ReservationStatus.EXPIRED
        self.version += 1

    def consume(self) -> None:
        if self.status != ReservationStatus.ALLOCATED:
            raise ReservationConflict(f"Cannot consume from status {self.status}")
        self.status = ReservationStatus.CONSUMED
        self.version += 1


def reservation_expires_at(now: datetime | None = None) -> datetime:
    base = now or datetime.now(UTC)
    if base.tzinfo is None:
        base = base.replace(tzinfo=UTC)
    return base + RESERVATION_TTL


@dataclass(slots=True)
class StockPosition:
    id: UUID
    tenant_id: UUID
    warehouse_code: str
    product_id: UUID
    on_hand: int
    reserved: int
    version: int

    def __post_init__(self) -> None:
        self._assert_invariants()

    @property
    def available(self) -> int:
        return self.on_hand - self.reserved

    def _assert_invariants(self) -> None:
        if self.on_hand < 0 or self.reserved < 0:
            raise StockInvariantViolation("on_hand and reserved must be non-negative")
        if self.reserved > self.on_hand:
            raise StockInvariantViolation("reserved cannot exceed on_hand")
        if self.on_hand > MAX_ON_HAND:
            raise StockInvariantViolation(f"on_hand cannot exceed {MAX_ON_HAND}")

    def apply_receipt(self, quantity: int) -> int:
        if quantity <= 0:
            raise InvalidQuantity("Receipt quantity must be positive")
        new_on_hand = self.on_hand + quantity
        if new_on_hand > MAX_ON_HAND:
            raise StockInvariantViolation(f"on_hand cannot exceed {MAX_ON_HAND}")
        self.on_hand = new_on_hand
        self.version += 1
        self._assert_invariants()
        return quantity

    def apply_adjustment(self, delta: int) -> int:
        if delta == 0:
            raise InvalidQuantity("Adjustment quantity cannot be zero")
        new_on_hand = self.on_hand + delta
        if new_on_hand < 0:
            raise StockInvariantViolation("on_hand cannot go negative")
        if new_on_hand < self.reserved:
            raise StockInvariantViolation(
                "Decreasing adjustment cannot take on_hand below reserved"
            )
        if new_on_hand > MAX_ON_HAND:
            raise StockInvariantViolation(f"on_hand cannot exceed {MAX_ON_HAND}")
        self.on_hand = new_on_hand
        self.version += 1
        self._assert_invariants()
        return delta

    def apply_reserve(self, quantity: int) -> int:
        if quantity <= 0:
            raise InvalidQuantity("Reserve quantity must be positive")
        if quantity > MAX_LINE_QUANTITY:
            raise InvalidQuantity(f"Quantity cannot exceed {MAX_LINE_QUANTITY}")
        if quantity > self.available:
            raise StockInvariantViolation("Cannot reserve more than available")
        self.reserved += quantity
        self.version += 1
        self._assert_invariants()
        return quantity

    def apply_release(self, quantity: int) -> int:
        if quantity <= 0:
            raise InvalidQuantity("Release quantity must be positive")
        if quantity > self.reserved:
            raise StockInvariantViolation("Cannot release more than reserved")
        self.reserved -= quantity
        self.version += 1
        self._assert_invariants()
        return quantity

    def apply_consume(self, quantity: int) -> int:
        if quantity <= 0:
            raise InvalidQuantity("Consume quantity must be positive")
        if quantity > self.reserved:
            raise StockInvariantViolation("Cannot consume more than reserved")
        if quantity > self.on_hand:
            raise StockInvariantViolation("Cannot consume more than on_hand")
        self.on_hand -= quantity
        self.reserved -= quantity
        self.version += 1
        self._assert_invariants()
        return quantity
