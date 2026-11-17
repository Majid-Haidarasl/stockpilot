"""Scheduler processes tenants one-by-one with SET LOCAL (no BYPASSRLS)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from stockpilot.bootstrap.scheduler import ExpireBatchResult, ReservationExpiryScheduler
from stockpilot.bootstrap.scheduler_health import heartbeat_is_fresh
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
    assert result.expired_count == 2
    assert result.failed_tenant_count == 0
    assert result.tenant_count == 2


def test_scheduler_run_tenants_isolates_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = FixedClock(datetime(2026, 11, 11, 12, 0, tzinfo=UTC))
    scheduler = ReservationExpiryScheduler(engine=MagicMock(), clock=clock)
    t1, t2, t3 = uuid4(), uuid4(), uuid4()

    def fake_run_for_tenant(*, tenant_id: UUID, limit: int = 50) -> ExpireBatchResult:
        _ = limit
        if tenant_id == t2:
            raise RuntimeError("boom")
        return ExpireBatchResult(examined=1, expired=1)

    monkeypatch.setattr(scheduler, "run_for_tenant", fake_run_for_tenant)
    result = scheduler.run_tenants([t1, t2, t3], limit_per_tenant=10)
    assert result.expired_count == 2
    assert result.failed_tenant_count == 1
    assert result.tenant_count == 3


def test_scheduler_stop_flag_skips_remaining_tenants(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = FixedClock(datetime(2026, 11, 11, 12, 0, tzinfo=UTC))
    stop = {"flag": False}
    scheduler = ReservationExpiryScheduler(
        engine=MagicMock(),
        clock=clock,
        stop_flag=lambda: stop["flag"],
    )
    calls: list[UUID] = []
    t1, t2, t3 = uuid4(), uuid4(), uuid4()

    def fake_run_for_tenant(*, tenant_id: UUID, limit: int = 50) -> ExpireBatchResult:
        _ = limit
        calls.append(tenant_id)
        if tenant_id == t1:
            stop["flag"] = True
        return ExpireBatchResult(examined=1, expired=1)

    monkeypatch.setattr(scheduler, "run_for_tenant", fake_run_for_tenant)
    result = scheduler.run_tenants([t1, t2, t3], limit_per_tenant=10)
    assert calls == [t1]
    assert result.expired_count == 1
    assert result.tenant_count == 3


def test_heartbeat_is_fresh_threshold() -> None:
    now = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)
    fresh = datetime(2026, 11, 17, 11, 58, tzinfo=UTC)
    stale = datetime(2026, 11, 17, 11, 56, tzinfo=UTC)
    assert heartbeat_is_fresh(last_success_at=fresh, stale_seconds=180, now=now) is True
    assert heartbeat_is_fresh(last_success_at=stale, stale_seconds=180, now=now) is False
    assert heartbeat_is_fresh(last_success_at=None, stale_seconds=180, now=now) is False
