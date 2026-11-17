"""Ops metrics snapshot helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from stockpilot.platform.observability.ops_metrics import (
    age_seconds,
    apply_scrape_snapshot,
    render_ops_metrics,
)


def test_age_seconds_non_negative() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    past = now - timedelta(seconds=42)
    assert age_seconds(past, now=now) == 42.0
    assert age_seconds(None) == float("inf")


def test_empty_outbox_age_rendered_as_zero() -> None:
    apply_scrape_snapshot(
        unpublished_count=0,
        oldest_age_seconds=None,
        failed_jobs_unreplayed=0,
        stale_reserved_orders=0,
        heartbeats={"scheduler": None, "relay": None, "worker": None},
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )
    body = render_ops_metrics().decode()
    assert "stockpilot_outbox_oldest_unpublished_age_seconds 0.0" in body
    assert "stockpilot_outbox_unpublished_count 0.0" in body
