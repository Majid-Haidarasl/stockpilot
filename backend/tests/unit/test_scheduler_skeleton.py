"""Scheduler skeleton smoke test (no inventory, no HTTP expire)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from stockpilot.bootstrap.scheduler import ReservationExpiryScheduler
from stockpilot.platform.time.clock import FixedClock


class _FakePort:
    def __init__(self) -> None:
        self.expired: list[UUID] = []

    def list_expired_reservation_ids(
        self, *, tenant_id: UUID, now: datetime, limit: int
    ) -> list[UUID]:
        _ = tenant_id, now
        return [uuid4() for _ in range(min(2, limit))]

    def expire_order(self, *, tenant_id: UUID, order_id: UUID, now: datetime) -> None:
        _ = tenant_id, now
        self.expired.append(order_id)


def test_scheduler_run_once_expires_listed_orders() -> None:
    port = _FakePort()
    clock = FixedClock(datetime(2026, 11, 11, 12, 0, tzinfo=UTC))
    scheduler = ReservationExpiryScheduler(port, clock=clock)
    result = scheduler.run_once(tenant_id=uuid4(), limit=10)
    assert result.examined == 2
    assert result.expired == 2
    assert len(port.expired) == 2
