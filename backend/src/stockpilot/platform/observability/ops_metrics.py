"""Ops-exporter gauge definitions (DB aggregates; no tenant labels)."""

from __future__ import annotations

from datetime import UTC, datetime

from prometheus_client import CollectorRegistry, Gauge, generate_latest

from stockpilot.platform.observability.http_metrics import assert_no_tenant_labels

REGISTRY = CollectorRegistry()

OUTBOX_UNPUBLISHED = Gauge(
    "stockpilot_outbox_unpublished_count",
    "Unpublished Outbox row count",
    registry=REGISTRY,
)
OUTBOX_OLDEST_AGE = Gauge(
    "stockpilot_outbox_oldest_unpublished_age_seconds",
    "Age in seconds of oldest unpublished Outbox row (0 if empty)",
    registry=REGISTRY,
)
HEARTBEAT_AGE = Gauge(
    "stockpilot_heartbeat_last_success_age_seconds",
    "Seconds since last successful heartbeat",
    labelnames=("service_name",),
    registry=REGISTRY,
)
HEARTBEAT_PRESENT = Gauge(
    "stockpilot_heartbeat_present",
    "1 if heartbeat row exists, else 0",
    labelnames=("service_name",),
    registry=REGISTRY,
)
FAILED_JOBS_UNREPLAYED = Gauge(
    "stockpilot_failed_jobs_unreplayed_count",
    "Count of failed_jobs with replayed_at IS NULL",
    registry=REGISTRY,
)
STALE_RESERVED = Gauge(
    "stockpilot_stale_reserved_orders_count",
    "RESERVED orders still held more than 2 minutes after expires_at",
    registry=REGISTRY,
)
SCRAPE_SUCCESS = Gauge(
    "stockpilot_ops_exporter_scrape_success",
    "1 if last DB scrape succeeded",
    registry=REGISTRY,
)
SCRAPE_TIMESTAMP = Gauge(
    "stockpilot_ops_exporter_scrape_timestamp",
    "Unix timestamp of last successful scrape",
    registry=REGISTRY,
)

KNOWN_SERVICES = ("scheduler", "relay", "worker")


def age_seconds(last_success_at: datetime | None, *, now: datetime | None = None) -> float:
    if last_success_at is None:
        return float("inf")
    current = now or datetime.now(UTC)
    if last_success_at.tzinfo is None:
        last_success_at = last_success_at.replace(tzinfo=UTC)
    return max(0.0, (current - last_success_at).total_seconds())


def apply_heartbeat_row(
    *,
    service_name: str,
    last_success_at: datetime | None,
    now: datetime | None = None,
) -> None:
    assert_no_tenant_labels(("service_name",))
    if service_name not in KNOWN_SERVICES:
        return
    if last_success_at is None:
        HEARTBEAT_PRESENT.labels(service_name=service_name).set(0)
        HEARTBEAT_AGE.labels(service_name=service_name).set(1e9)
        return
    HEARTBEAT_PRESENT.labels(service_name=service_name).set(1)
    HEARTBEAT_AGE.labels(service_name=service_name).set(age_seconds(last_success_at, now=now))


def apply_scrape_snapshot(
    *,
    unpublished_count: int,
    oldest_age_seconds: float | None,
    failed_jobs_unreplayed: int,
    stale_reserved_orders: int,
    heartbeats: dict[str, datetime | None],
    now: datetime | None = None,
) -> None:
    OUTBOX_UNPUBLISHED.set(unpublished_count)
    OUTBOX_OLDEST_AGE.set(0.0 if oldest_age_seconds is None else float(oldest_age_seconds))
    FAILED_JOBS_UNREPLAYED.set(failed_jobs_unreplayed)
    STALE_RESERVED.set(stale_reserved_orders)
    for name in KNOWN_SERVICES:
        apply_heartbeat_row(
            service_name=name,
            last_success_at=heartbeats.get(name),
            now=now,
        )
    SCRAPE_SUCCESS.set(1)
    SCRAPE_TIMESTAMP.set((now or datetime.now(UTC)).timestamp())


def mark_scrape_failure() -> None:
    SCRAPE_SUCCESS.set(0)


def render_ops_metrics() -> bytes:
    return generate_latest(REGISTRY)
