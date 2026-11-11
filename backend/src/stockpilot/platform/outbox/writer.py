"""Transactional Outbox writer (Relay is T13)."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection


def enqueue(
    conn: Connection,
    *,
    tenant_id: UUID,
    event_type: str,
    event_version: str,
    aggregate_type: str,
    aggregate_id: UUID,
    payload: dict[str, Any],
    trace_id: str | None = None,
    event_id: UUID | None = None,
) -> UUID:
    eid = event_id or uuid4()
    conn.execute(
        text(
            """
            INSERT INTO platform.outbox (
              event_id, tenant_id, event_type, event_version,
              aggregate_type, aggregate_id, payload_json, trace_id
            ) VALUES (
              :event_id, :tenant_id, :event_type, :event_version,
              :aggregate_type, :aggregate_id, CAST(:payload AS jsonb), :trace_id
            )
            """
        ),
        {
            "event_id": str(eid),
            "tenant_id": str(tenant_id),
            "event_type": event_type,
            "event_version": event_version,
            "aggregate_type": aggregate_type,
            "aggregate_id": str(aggregate_id),
            "payload": json.dumps(payload),
            "trace_id": trace_id,
        },
    )
    return eid
