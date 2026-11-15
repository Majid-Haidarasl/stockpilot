"""Outbox lease claim and idempotent mark-published (relay role)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from stockpilot.platform.outbox.backoff import publish_failure_backoff


@dataclass(frozen=True, slots=True)
class ClaimedOutboxRow:
    event_id: UUID
    tenant_id: UUID
    event_type: str
    event_version: str
    aggregate_type: str
    aggregate_id: UUID
    payload_json: dict[str, Any]
    trace_id: str | None
    created_at: datetime
    attempt_count: int


def claim_batch(
    conn: Connection,
    *,
    lease_owner: str,
    lease_ttl: timedelta,
    limit: int,
    now: datetime | None = None,
) -> list[ClaimedOutboxRow]:
    """Lease unpublished rows in the caller's short transaction; commit outside."""
    clock = now or datetime.now(UTC)
    lease_expires = clock + lease_ttl
    rows = (
        conn.execute(
            text(
                """
            WITH picked AS (
              SELECT event_id
              FROM platform.outbox
              WHERE published_at IS NULL
                AND (lease_expires_at IS NULL OR lease_expires_at < :now)
              ORDER BY created_at ASC
              FOR UPDATE SKIP LOCKED
              LIMIT :limit
            )
            UPDATE platform.outbox AS o
            SET lease_owner = :owner,
                lease_expires_at = :lease_expires,
                attempt_count = o.attempt_count + 1,
                last_error = NULL
            FROM picked
            WHERE o.event_id = picked.event_id
            RETURNING
              o.event_id, o.tenant_id, o.event_type, o.event_version,
              o.aggregate_type, o.aggregate_id, o.payload_json, o.trace_id,
              o.created_at, o.attempt_count
            """
            ),
            {
                "now": clock,
                "limit": limit,
                "owner": lease_owner,
                "lease_expires": lease_expires,
            },
        )
        .mappings()
        .all()
    )
    return [
        ClaimedOutboxRow(
            event_id=UUID(str(r["event_id"])),
            tenant_id=UUID(str(r["tenant_id"])),
            event_type=str(r["event_type"]),
            event_version=str(r["event_version"]),
            aggregate_type=str(r["aggregate_type"]),
            aggregate_id=UUID(str(r["aggregate_id"])),
            payload_json=dict(r["payload_json"]),
            trace_id=str(r["trace_id"]) if r["trace_id"] is not None else None,
            created_at=r["created_at"],
            attempt_count=int(r["attempt_count"]),
        )
        for r in rows
    ]


def mark_published(conn: Connection, *, event_id: UUID) -> bool:
    """Idempotent success mark. Returns True if this call set published_at."""
    result = conn.execute(
        text(
            """
            UPDATE platform.outbox
            SET published_at = now(),
                lease_owner = NULL,
                lease_expires_at = NULL,
                last_error = NULL
            WHERE event_id = :event_id
              AND published_at IS NULL
            """
        ),
        {"event_id": str(event_id)},
    )
    return bool(result.rowcount)


def record_publish_failure(
    conn: Connection,
    *,
    event_id: UUID,
    attempt_count: int,
    error: str,
    now: datetime | None = None,
    rng: Any = None,
) -> None:
    """Leave unpublished; set last_error; hold lease until backoff expires."""
    clock = now or datetime.now(UTC)
    delay = publish_failure_backoff(attempt_count, rng=rng)
    truncated = error[:2000]
    conn.execute(
        text(
            """
            UPDATE platform.outbox
            SET last_error = :error,
                lease_owner = NULL,
                lease_expires_at = :lease_expires
            WHERE event_id = :event_id
              AND published_at IS NULL
            """
        ),
        {
            "event_id": str(event_id),
            "error": truncated,
            "lease_expires": clock + delay,
        },
    )
