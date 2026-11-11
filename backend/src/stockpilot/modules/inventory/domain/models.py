"""Inventory domain types and stock position invariants."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

MAX_ON_HAND = 1_000_000_000
DEFAULT_WAREHOUSE = "main"


class InventoryError(Exception):
    """Base inventory domain error."""


class InvalidQuantity(InventoryError):
    pass


class StockInvariantViolation(InventoryError):
    pass


@dataclass(frozen=True, slots=True)
class Quantity:
    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise InvalidQuantity("Quantity cannot be negative")


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
