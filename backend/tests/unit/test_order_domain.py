"""Domain tests for Order status machine, edits, totals, and expiry confirm."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from stockpilot.modules.sales.domain.order import (
    MAX_ORDER_LINES,
    RESERVATION_TTL,
    DuplicateProductLine,
    InvalidOrderState,
    Order,
    OrderLine,
    OrderNotEditable,
    OrderStatus,
    ReservationExpired,
    TooManyOrderLines,
)
from stockpilot.platform.time.clock import FixedClock


def _line(qty: int = 2, price: int = 1000, product_id=None) -> OrderLine:
    return OrderLine(
        id=uuid4(),
        product_id=product_id or uuid4(),
        quantity=qty,
        product_sku=f"SKU-{uuid4().hex[:6]}",
        product_title="Item",
        unit_price_rial=price,
    )


def _draft(*lines: OrderLine) -> Order:
    return Order.new_draft(
        tenant_id=uuid4(),
        customer_id=uuid4(),
        lines=list(lines) if lines else [_line()],
    )


def test_total_is_sum_of_qty_times_unit_price() -> None:
    order = _draft(_line(qty=3, price=100), _line(qty=2, price=250))
    assert order.total().amount == 3 * 100 + 2 * 250
    assert order.total().currency == "IRR"


def test_duplicate_product_line_rejected() -> None:
    product_id = uuid4()
    with pytest.raises(DuplicateProductLine):
        _draft(_line(product_id=product_id), _line(product_id=product_id))


def test_more_than_20_lines_rejected() -> None:
    lines = [_line() for _ in range(MAX_ORDER_LINES + 1)]
    with pytest.raises(TooManyOrderLines):
        Order.new_draft(tenant_id=uuid4(), customer_id=uuid4(), lines=lines)


def test_legal_happy_path_transitions() -> None:
    clock = FixedClock(datetime(2026, 11, 11, 12, 0, tzinfo=UTC))
    order = _draft()
    order.reserve(clock.now())
    assert order.status == OrderStatus.RESERVED
    assert order.expires_at == clock.now() + RESERVATION_TTL
    order.confirm(clock.now() + timedelta(minutes=10))
    assert order.status == OrderStatus.CONFIRMED
    order.ship(clock.now() + timedelta(hours=1))
    assert order.status == OrderStatus.SHIPPED


def test_cancel_draft_and_reserved_and_confirmed() -> None:
    now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    draft = _draft()
    draft.cancel(now)
    assert draft.status == OrderStatus.CANCELLED

    reserved = _draft()
    reserved.reserve(now)
    reserved.cancel(now)
    assert reserved.status == OrderStatus.CANCELLED

    confirmed = _draft()
    confirmed.reserve(now)
    confirmed.confirm(now + timedelta(minutes=1))
    confirmed.cancel(now + timedelta(minutes=2))
    assert confirmed.status == OrderStatus.CANCELLED


def test_cannot_cancel_shipped() -> None:
    now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    order = _draft()
    order.reserve(now)
    order.confirm(now + timedelta(seconds=1))
    order.ship(now + timedelta(seconds=2))
    with pytest.raises(InvalidOrderState):
        order.cancel(now + timedelta(seconds=3))


def test_expire_only_from_reserved() -> None:
    now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    order = _draft()
    with pytest.raises(InvalidOrderState):
        order.expire(now)
    order.reserve(now)
    order.expire(now + RESERVATION_TTL)
    assert order.status == OrderStatus.EXPIRED
    with pytest.raises(InvalidOrderState):
        order.confirm(now + RESERVATION_TTL + timedelta(seconds=1))


def test_edit_draft_allowed_edit_reserved_rejected() -> None:
    now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    order = _draft()
    order.replace_lines([_line(qty=5)])
    assert order.lines[0].quantity == 5
    order.reserve(now)
    with pytest.raises(OrderNotEditable):
        order.replace_lines([_line(qty=1)])
    with pytest.raises(OrderNotEditable):
        order.set_customer(uuid4())


def test_confirm_after_expires_at_rejected_fixed_clock() -> None:
    clock = FixedClock(datetime(2026, 11, 11, 10, 0, tzinfo=UTC))
    order = _draft()
    order.reserve(clock.now())
    assert order.expires_at is not None
    clock.set(order.expires_at + timedelta(seconds=1))
    with pytest.raises(ReservationExpired):
        order.confirm(clock.now())
    assert order.status == OrderStatus.RESERVED


def test_confirm_exactly_before_expires_at_succeeds() -> None:
    clock = FixedClock(datetime(2026, 11, 11, 10, 0, tzinfo=UTC))
    order = _draft()
    order.reserve(clock.now())
    assert order.expires_at is not None
    clock.set(order.expires_at - timedelta(microseconds=1))
    order.confirm(clock.now())
    assert order.status == OrderStatus.CONFIRMED
    assert order.expires_at is None


def test_ship_from_draft_rejected() -> None:
    with pytest.raises(InvalidOrderState):
        _draft().ship(datetime(2026, 11, 11, tzinfo=UTC))
