"""Unit tests for Outbox event→task mapping and envelope."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from stockpilot.platform.outbox.envelope import build_envelope, build_traceparent
from stockpilot.platform.outbox.mapping import (
    EVENT_TO_TASK,
    KNOWN_EVENT_TYPES,
    UnknownEventTypeError,
    task_for_event_type,
)


def test_all_order_lifecycle_events_map_to_one_task() -> None:
    expected = {
        "OrderReserved",
        "OrderConfirmed",
        "OrderCancelled",
        "OrderShipped",
        "OrderExpired",
    }
    assert KNOWN_EVENT_TYPES == expected
    names = {task_for_event_type(t) for t in expected}
    assert names == {"stockpilot.notifications.deliver_order_lifecycle_event"}
    assert set(EVENT_TO_TASK) == expected


def test_unknown_event_type_fails_closed() -> None:
    with pytest.raises(UnknownEventTypeError):
        task_for_event_type("OrderUnknown")


def test_envelope_includes_versioned_fields_and_traceparent() -> None:
    event_id = uuid4()
    tenant_id = uuid4()
    aggregate_id = uuid4()
    trace = "abcdef0123456789abcdef0123456789"
    env = build_envelope(
        event_id=event_id,
        event_type="OrderReserved",
        event_version="v1",
        tenant_id=tenant_id,
        aggregate_type="order",
        aggregate_id=aggregate_id,
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        payload={"order_id": str(aggregate_id)},
        trace_id=trace,
    )
    assert env["event_version"] == "v1"
    assert env["event_type"] == "OrderReserved"
    assert env["traceparent"] == f"00-{trace}-0000000000000001-01"
    assert "payload" in env


def test_build_traceparent_rejects_non_hex() -> None:
    assert build_traceparent("not-a-trace") is None
    assert build_traceparent(None) is None
