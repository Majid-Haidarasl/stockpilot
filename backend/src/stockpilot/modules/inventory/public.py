"""Public contract for the inventory module.

Lock order when called from an order use case (relative order must be obeyed):
1. idempotency record (outer)
2. order row (outer)
3. products by id (outer / T11; active+sku supplied on RequestedStock here)
4. stock positions by product id (inventory)
5. reservation row (inventory)

Inventory command adapters stage work on the caller's UnitOfWork and must not commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from stockpilot.modules.inventory.domain.models import (
    DEFAULT_WAREHOUSE,
    MAX_ON_HAND,
    MAX_RESERVATION_LINES,
    RESERVATION_TTL,
    DuplicateProductLine,
    InactiveProduct,
    InsufficientStock,
    InvalidQuantity,
    InventoryError,
    Quantity,
    Reservation,
    ReservationConflict,
    ReservationStatus,
    StockInvariantViolation,
    StockPosition,
    StockShortfall,
    TooManyLines,
)

__all__ = [
    "DEFAULT_WAREHOUSE",
    "MAX_ON_HAND",
    "MAX_RESERVATION_LINES",
    "RESERVATION_TTL",
    "AllocateStock",
    "ConsumeStock",
    "DuplicateProductLine",
    "InactiveProduct",
    "InsufficientStock",
    "InvalidQuantity",
    "InventoryCommands",
    "InventoryError",
    "Quantity",
    "ReleaseStock",
    "RequestedStock",
    "Reservation",
    "ReservationConflict",
    "ReservationStatus",
    "ReserveStock",
    "StockInvariantViolation",
    "StockPosition",
    "StockShortfall",
    "TooManyLines",
]


@dataclass(frozen=True, slots=True)
class RequestedStock:
    product_id: UUID
    quantity: int
    sku: str
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class ReserveStock:
    tenant_id: UUID
    order_id: UUID
    items: tuple[RequestedStock, ...]
    actor_user_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class AllocateStock:
    tenant_id: UUID
    reservation_id: UUID
    actor_user_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ReleaseStock:
    tenant_id: UUID
    reservation_id: UUID
    actor_user_id: UUID | None = None
    as_expired: bool = False


@dataclass(frozen=True, slots=True)
class ConsumeStock:
    tenant_id: UUID
    reservation_id: UUID
    actor_user_id: UUID | None = None


class InventoryCommands(Protocol):
    def reserve_all(self, command: ReserveStock) -> UUID:
        """Stage a complete reservation in the caller's unit of work. Does not commit."""
        ...

    def allocate(self, command: AllocateStock) -> None:
        """Mark reservation ALLOCATED (confirm). Does not commit."""
        ...

    def release(self, command: ReleaseStock) -> None:
        """Release held/allocated stock. Does not commit."""
        ...

    def consume(self, command: ConsumeStock) -> None:
        """Consume allocated stock on ship. Does not commit."""
        ...
