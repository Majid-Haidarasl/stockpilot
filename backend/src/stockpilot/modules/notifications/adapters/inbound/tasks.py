"""Celery tasks for notifications (stub consumer in Run 5.1; Inbox in 5.2)."""

from __future__ import annotations

from typing import Any

from stockpilot.bootstrap.celery_app import celery_app
from stockpilot.platform.outbox.mapping import ORDER_LIFECYCLE_TASK


@celery_app.task(name=ORDER_LIFECYCLE_TASK)  # type: ignore[untyped-decorator]
def deliver_order_lifecycle_event(envelope: dict[str, Any]) -> dict[str, Any]:
    """Acknowledge receipt of a versioned envelope.

    Run 5.1: stub only (validates shape). Run 5.2 writes Inbox + notification.
    """
    required = (
        "event_id",
        "event_type",
        "event_version",
        "tenant_id",
        "aggregate_type",
        "aggregate_id",
        "occurred_at",
        "payload",
    )
    missing = [key for key in required if key not in envelope]
    if missing:
        raise ValueError(f"Invalid envelope; missing keys: {missing}")
    return {"accepted": True, "event_id": envelope["event_id"]}
