"""Domain tests for stock position invariants."""

from __future__ import annotations

from uuid import uuid4

import pytest

from stockpilot.modules.inventory.domain.models import (
    MAX_ON_HAND,
    InvalidQuantity,
    StockInvariantViolation,
    StockPosition,
)


def _position(*, on_hand: int = 0, reserved: int = 0) -> StockPosition:
    return StockPosition(
        id=uuid4(),
        tenant_id=uuid4(),
        warehouse_code="main",
        product_id=uuid4(),
        on_hand=on_hand,
        reserved=reserved,
        version=1,
    )


def test_receipt_increases_on_hand_and_available() -> None:
    position = _position()
    position.apply_receipt(10)
    assert position.on_hand == 10
    assert position.reserved == 0
    assert position.available == 10


def test_decreasing_adjustment_blocked_below_reserved() -> None:
    position = _position(on_hand=10, reserved=4)
    with pytest.raises(StockInvariantViolation):
        position.apply_adjustment(-7)


def test_negative_on_hand_rejected() -> None:
    position = _position(on_hand=3)
    with pytest.raises(StockInvariantViolation):
        position.apply_adjustment(-5)


def test_receipt_rejects_non_positive() -> None:
    position = _position()
    with pytest.raises(InvalidQuantity):
        position.apply_receipt(0)


def test_on_hand_cap_enforced() -> None:
    position = _position(on_hand=MAX_ON_HAND - 1)
    with pytest.raises(StockInvariantViolation):
        position.apply_receipt(2)
