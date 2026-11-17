"""Allow-list sanitization for failed_jobs envelopes."""

from __future__ import annotations

from uuid import uuid4

from stockpilot.platform.failed_jobs.sanitize import sanitize_envelope


def test_sanitize_envelope_allow_list_strips_unknown_and_keeps_event_id() -> None:
    event_id = str(uuid4())
    order_id = str(uuid4())
    raw = {
        "event_id": event_id,
        "event_type": "OrderConfirmed",
        "event_version": "v1",
        "tenant_id": str(uuid4()),
        "aggregate_type": "order",
        "aggregate_id": order_id,
        "occurred_at": "2026-11-16T12:00:00+00:00",
        "payload": {
            "order_id": order_id,
            "secret_token": "drop-me",
            "extra": "nope",
        },
        "password": "drop-top",
        "authorization": "Bearer x",
        "trace_id": "abcdef0123456789abcdef0123456789",
    }
    cleaned = sanitize_envelope(raw)
    assert cleaned is not None
    assert cleaned["event_id"] == event_id
    assert "password" not in cleaned
    assert "authorization" not in cleaned
    assert cleaned["payload"] == {"order_id": order_id}
    assert cleaned["trace_id"] == raw["trace_id"]


def test_sanitize_envelope_none_and_non_dict() -> None:
    assert sanitize_envelope(None) is None
    assert sanitize_envelope("x") is None  # type: ignore[arg-type]
