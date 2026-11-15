"""Versioned integration-event envelope for Celery task bodies."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID


def build_traceparent(trace_id: str | None) -> str | None:
    """Build a W3C traceparent when a 32-hex trace id is available."""
    if not trace_id:
        return None
    cleaned = trace_id.replace("-", "").lower()
    if len(cleaned) == 32 and all(c in "0123456789abcdef" for c in cleaned):
        return f"00-{cleaned}-0000000000000001-01"
    # Non-W3C ids (legacy outbox.trace_id) are still propagated as-is in a vendor field.
    return None


def build_envelope(
    *,
    event_id: UUID,
    event_type: str,
    event_version: str,
    tenant_id: UUID,
    aggregate_type: str,
    aggregate_id: UUID,
    occurred_at: datetime,
    payload: dict[str, Any],
    trace_id: str | None,
) -> dict[str, Any]:
    envelope: dict[str, Any] = {
        "event_id": str(event_id),
        "event_type": event_type,
        "event_version": event_version,
        "tenant_id": str(tenant_id),
        "aggregate_type": aggregate_type,
        "aggregate_id": str(aggregate_id),
        "occurred_at": occurred_at.astimezone().isoformat(),
        "payload": payload,
    }
    traceparent = build_traceparent(trace_id)
    if traceparent is not None:
        envelope["traceparent"] = traceparent
    elif trace_id:
        envelope["trace_id"] = trace_id
    return envelope
