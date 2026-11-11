"""Order aggregate and named status transitions (no inventory side effects)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID, uuid4

from stockpilot.modules.sales.domain.money import Money

MAX_ORDER_LINES = 20
MAX_LINE_QUANTITY = 100_000
RESERVATION_TTL = timedelta(minutes=30)


class OrderError(Exception):
    """Base sales order domain error."""


class InvalidOrderState(OrderError):
    pass


class OrderNotEditable(OrderError):
    pass


class DuplicateProductLine(OrderError):
    pass


class TooManyOrderLines(OrderError):
    pass


class InvalidLineQuantity(OrderError):
    pass


class ReservationExpired(OrderError):
    """Confirm attempted at or after expires_at."""


class OrderStatus(StrEnum):
    DRAFT = "DRAFT"
    RESERVED = "RESERVED"
    CONFIRMED = "CONFIRMED"
    SHIPPED = "SHIPPED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


_TERMINAL = frozenset({OrderStatus.SHIPPED, OrderStatus.CANCELLED, OrderStatus.EXPIRED})


@dataclass(slots=True)
class OrderLine:
    id: UUID
    product_id: UUID
    quantity: int
    product_sku: str
    product_title: str
    unit_price_rial: int
    currency: str = "IRR"

    def __post_init__(self) -> None:
        if self.quantity < 1 or self.quantity > MAX_LINE_QUANTITY:
            raise InvalidLineQuantity(
                f"Line quantity must be 1..{MAX_LINE_QUANTITY}, got {self.quantity}"
            )
        if self.unit_price_rial < 0:
            raise InvalidLineQuantity("unit_price_rial cannot be negative")
        if not self.product_sku:
            raise InvalidLineQuantity("product_sku is required")
        if not self.product_title:
            raise InvalidLineQuantity("product_title is required")


@dataclass(slots=True)
class Order:
    id: UUID
    tenant_id: UUID
    customer_id: UUID
    status: OrderStatus
    version: int
    lines: list[OrderLine] = field(default_factory=list)
    reserved_at: datetime | None = None
    expires_at: datetime | None = None
    confirmed_at: datetime | None = None
    shipped_at: datetime | None = None
    cancelled_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def new_draft(
        cls,
        *,
        tenant_id: UUID,
        customer_id: UUID,
        lines: list[OrderLine],
        order_id: UUID | None = None,
    ) -> Order:
        order = cls(
            id=order_id or uuid4(),
            tenant_id=tenant_id,
            customer_id=customer_id,
            status=OrderStatus.DRAFT,
            version=1,
            lines=[],
        )
        order._set_lines(lines)
        return order

    def _ensure_draft_editable(self) -> None:
        if self.status != OrderStatus.DRAFT:
            raise OrderNotEditable(
                f"Order in status {self.status} cannot be edited; cancel and create a new order"
            )

    def _set_lines(self, lines: list[OrderLine]) -> None:
        if len(lines) > MAX_ORDER_LINES:
            raise TooManyOrderLines(f"At most {MAX_ORDER_LINES} lines allowed")
        seen: set[UUID] = set()
        for line in lines:
            if line.product_id in seen:
                raise DuplicateProductLine(f"Duplicate product {line.product_id}")
            seen.add(line.product_id)
        self.lines = list(lines)

    def set_customer(self, customer_id: UUID) -> None:
        self._ensure_draft_editable()
        self.customer_id = customer_id
        self.version += 1

    def replace_lines(self, lines: list[OrderLine]) -> None:
        self._ensure_draft_editable()
        self._set_lines(lines)
        self.version += 1

    def total(self) -> Money:
        total = Money(0, "IRR")
        for line in self.lines:
            line_total = Money(line.unit_price_rial * line.quantity, line.currency)
            total = total.add(line_total)
        return total

    def reserve(self, now: datetime) -> None:
        now = _as_utc(now)
        if self.status != OrderStatus.DRAFT:
            raise InvalidOrderState(f"Cannot reserve from status {self.status}")
        if not self.lines:
            raise InvalidOrderState("Cannot reserve an order with no lines")
        self.status = OrderStatus.RESERVED
        self.reserved_at = now
        self.expires_at = now + RESERVATION_TTL
        self.version += 1

    def confirm(self, now: datetime) -> None:
        now = _as_utc(now)
        if self.status != OrderStatus.RESERVED:
            raise InvalidOrderState(f"Cannot confirm from status {self.status}")
        if self.expires_at is None:
            raise InvalidOrderState("Reserved order missing expires_at")
        # Valid while now < expires_at; at/after deadline is expired.
        if now >= _as_utc(self.expires_at):
            raise ReservationExpired("Reservation has expired; confirm is not allowed")
        self.status = OrderStatus.CONFIRMED
        self.confirmed_at = now
        self.expires_at = None
        self.version += 1

    def cancel(self, now: datetime) -> None:
        now = _as_utc(now)
        if self.status in _TERMINAL:
            raise InvalidOrderState(f"Cannot cancel terminal status {self.status}")
        if self.status == OrderStatus.SHIPPED:
            raise InvalidOrderState("Cannot cancel a shipped order")
        if self.status not in {
            OrderStatus.DRAFT,
            OrderStatus.RESERVED,
            OrderStatus.CONFIRMED,
        }:
            raise InvalidOrderState(f"Cannot cancel from status {self.status}")
        self.status = OrderStatus.CANCELLED
        self.cancelled_at = now
        self.version += 1

    def expire(self, now: datetime) -> None:
        now = _as_utc(now)
        if self.status != OrderStatus.RESERVED:
            raise InvalidOrderState(f"Cannot expire from status {self.status}")
        self.status = OrderStatus.EXPIRED
        self.cancelled_at = None
        self.version += 1
        _ = now  # server clock authorizes; stored for use-case audit in T11

    def ship(self, now: datetime) -> None:
        now = _as_utc(now)
        if self.status != OrderStatus.CONFIRMED:
            raise InvalidOrderState(f"Cannot ship from status {self.status}")
        self.status = OrderStatus.SHIPPED
        self.shipped_at = now
        self.version += 1


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
