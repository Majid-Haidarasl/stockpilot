"""Allow-list sanitization for failed_jobs envelopes (replay-safe)."""

from __future__ import annotations

from typing import Any

# Top-level keys required/used by notifications consume (validate + process).
ENVELOPE_ALLOW_KEYS = frozenset(
    {
        "event_id",
        "event_type",
        "event_version",
        "tenant_id",
        "aggregate_type",
        "aggregate_id",
        "occurred_at",
        "payload",
        "traceparent",
        "trace_id",
    }
)

# Fields read from envelope["payload"] in process_order_lifecycle_event
# (order_id, with aggregate_id fallback at envelope top-level).
PAYLOAD_ALLOW_KEYS = frozenset({"order_id"})


def sanitize_envelope(envelope: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return an allow-listed copy suitable for durable failed_jobs + replay.

    Preserves the original event_id when present. Never invents a new event_id.
    """
    if not isinstance(envelope, dict):
        return None
    out: dict[str, Any] = {}
    for key in ENVELOPE_ALLOW_KEYS:
        if key not in envelope:
            continue
        if key == "payload":
            raw = envelope.get("payload")
            if isinstance(raw, dict):
                out["payload"] = {k: raw[k] for k in PAYLOAD_ALLOW_KEYS if k in raw}
            else:
                out["payload"] = {}
        else:
            out[key] = envelope[key]
    return out
