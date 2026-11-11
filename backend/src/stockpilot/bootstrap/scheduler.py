"""Reservation-expiry scheduler skeleton (T10).

Real batch expiry runs in T14 using the same Order.expire domain method and Clock.
There is no public HTTP expire route. This module must not call inventory (T11).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from stockpilot.platform.time.clock import Clock, SystemClock


class ExpirableOrderPort(Protocol):
    def list_expired_reservation_ids(
        self, *, tenant_id: UUID, now: datetime, limit: int
    ) -> list[UUID]: ...

    def expire_order(self, *, tenant_id: UUID, order_id: UUID, now: datetime) -> None: ...


@dataclass(slots=True)
class ExpireBatchResult:
    examined: int
    expired: int


class ReservationExpiryScheduler:
    """Skeleton: claim expired RESERVED orders in limited batches per tenant."""

    def __init__(self, port: ExpirableOrderPort, clock: Clock | None = None) -> None:
        self._port = port
        self._clock = clock or SystemClock()

    def run_once(self, *, tenant_id: UUID, limit: int = 50) -> ExpireBatchResult:
        now = self._clock.now()
        ids = self._port.list_expired_reservation_ids(
            tenant_id=tenant_id, now=now, limit=max(1, min(limit, 100))
        )
        expired = 0
        for order_id in ids:
            self._port.expire_order(tenant_id=tenant_id, order_id=order_id, now=now)
            expired += 1
        return ExpireBatchResult(examined=len(ids), expired=expired)
