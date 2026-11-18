"""ops-exporter knows the backup heartbeat service."""

from __future__ import annotations

from datetime import UTC, datetime

from stockpilot.platform.observability.ops_metrics import (
    KNOWN_SERVICES,
    apply_heartbeat_row,
    apply_scrape_snapshot,
    render_ops_metrics,
)


def test_known_services_includes_backup() -> None:
    assert "backup" in KNOWN_SERVICES


def test_backup_heartbeat_appears_in_metrics() -> None:
    now = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)
    apply_scrape_snapshot(
        unpublished_count=0,
        oldest_age_seconds=None,
        failed_jobs_unreplayed=0,
        stale_reserved_orders=0,
        heartbeats={"backup": now, "scheduler": now, "relay": now, "worker": now},
        now=now,
    )
    apply_heartbeat_row(service_name="backup", last_success_at=now, now=now)
    body = render_ops_metrics().decode()
    assert 'stockpilot_heartbeat_present{service_name="backup"}' in body
    assert 'stockpilot_heartbeat_last_success_age_seconds{service_name="backup"}' in body
