"""Domain tests for reservation and reserve/release/consume counters."""

from __future__ import annotations

from uuid import uuid4

import pytest

from stockpilot.modules.inventory.domain.models import (
    Reservation,
    ReservationConflict,
    ReservationLine,
    ReservationStatus,
    StockInvariantViolation,
    StockPosition,
    reservation_expires_at,
)


def _position(*, on_hand: int = 10, reserved: int = 0) -> StockPosition:
    return StockPosition(
        id=uuid4(),
        tenant_id=uuid4(),
        warehouse_code="main",
        product_id=uuid4(),
        on_hand=on_hand,
        reserved=reserved,
        version=1,
    )


def test_apply_reserve_increases_reserved_and_reduces_available() -> None:
    position = _position(on_hand=10)
    position.apply_reserve(3)
    assert position.reserved == 3
    assert position.available == 7


def test_apply_reserve_beyond_available_rejected() -> None:
    position = _position(on_hand=5, reserved=2)
    with pytest.raises(StockInvariantViolation):
        position.apply_reserve(4)


def test_apply_release_and_consume() -> None:
    position = _position(on_hand=10, reserved=4)
    position.apply_release(2)
    assert position.reserved == 2
    assert position.on_hand == 10
    position.apply_consume(2)
    assert position.reserved == 0
    assert position.on_hand == 8


def test_reservation_status_transitions() -> None:
    reservation = Reservation(
        id=uuid4(),
        tenant_id=uuid4(),
        order_id=uuid4(),
        status=ReservationStatus.HELD,
        expires_at=reservation_expires_at(),
        version=1,
        lines=[ReservationLine(id=uuid4(), product_id=uuid4(), quantity=2)],
    )
    reservation.allocate()
    assert reservation.status == ReservationStatus.ALLOCATED
    assert reservation.expires_at is None
    reservation.consume()
    assert reservation.status == ReservationStatus.CONSUMED
    with pytest.raises(ReservationConflict):
        reservation.release()


def test_held_can_release_or_expire() -> None:
    held = Reservation(
        id=uuid4(),
        tenant_id=uuid4(),
        order_id=uuid4(),
        status=ReservationStatus.HELD,
        expires_at=reservation_expires_at(),
        version=1,
    )
    held.release()
    assert held.status == ReservationStatus.RELEASED

    held2 = Reservation(
        id=uuid4(),
        tenant_id=uuid4(),
        order_id=uuid4(),
        status=ReservationStatus.HELD,
        expires_at=reservation_expires_at(),
        version=1,
    )
    held2.expire()
    assert held2.status == ReservationStatus.EXPIRED
