"""Scheduler processes tenants one-by-one with SET LOCAL (no BYPASSRLS)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from stockpilot.bootstrap.scheduler import ExpireBatchResult, ReservationExpiryScheduler
from stockpilot.platform.time.clock import FixedClock


def test_scheduler_run_tenants_processes_sequentially(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = FixedClock(datetime(2026, 11, 11, 12, 0, tzinfo=UTC))
    scheduler = ReservationExpiryScheduler(engine=MagicMock(), clock=clock)
    calls: list[UUID] = []

    def fake_run_for_tenant(*, tenant_id: UUID, limit: int = 50) -> ExpireBatchResult:
        _ = limit
        calls.append(tenant_id)
        return ExpireBatchResult(examined=1, expired=1)

    monkeypatch.setattr(scheduler, "run_for_tenant", fake_run_for_tenant)
    t1, t2 = uuid4(), uuid4()
    result = scheduler.run_tenants([t1, t2], limit_per_tenant=10)
    assert calls == [t1, t2]
    assert result.examined == 2
    assert result.expired == 2
