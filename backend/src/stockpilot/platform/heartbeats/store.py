"""platform.heartbeats upsert/read and platform.outbox_lag()."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine


def upsert_heartbeat(
    conn: Connection,
    *,
    service_name: str,
    details: dict[str, Any] | None = None,
    last_success_at: datetime | None = None,
) -> None:
    """Insert or update one heartbeat row. Caller must satisfy RLS (app.role / relay)."""
    payload = details if details is not None else {}
    if last_success_at is None:
        conn.execute(
            text(
                """
                INSERT INTO platform.heartbeats (
                  service_name, last_success_at, details, updated_at
                ) VALUES (
                  :service_name, now(), CAST(:details AS jsonb), now()
                )
                ON CONFLICT (service_name) DO UPDATE SET
                  last_success_at = EXCLUDED.last_success_at,
                  details = EXCLUDED.details,
                  updated_at = now()
                """
            ),
            {"service_name": service_name, "details": json.dumps(payload)},
        )
    else:
        conn.execute(
            text(
                """
                INSERT INTO platform.heartbeats (
                  service_name, last_success_at, details, updated_at
                ) VALUES (
                  :service_name, :last_success_at, CAST(:details AS jsonb), now()
                )
                ON CONFLICT (service_name) DO UPDATE SET
                  last_success_at = EXCLUDED.last_success_at,
                  details = EXCLUDED.details,
                  updated_at = now()
                """
            ),
            {
                "service_name": service_name,
                "last_success_at": last_success_at,
                "details": json.dumps(payload),
            },
        )


def read_heartbeat(conn: Connection, service_name: str) -> dict[str, Any] | None:
    row = (
        conn.execute(
            text(
                """
                SELECT service_name, last_success_at, details, updated_at
                FROM platform.heartbeats
                WHERE service_name = :service_name
                """
            ),
            {"service_name": service_name},
        )
        .mappings()
        .first()
    )
    return dict(row) if row is not None else None


def fetch_outbox_lag(conn: Connection) -> tuple[int, float | None]:
    """Call SECURITY DEFINER platform.outbox_lag(). Returns (count, age_seconds|None)."""
    row = conn.execute(text("SELECT * FROM platform.outbox_lag()")).mappings().one()
    count = int(row["unpublished_count"] or 0)
    age = row["oldest_unpublished_age_seconds"]
    return count, (float(age) if age is not None else None)


def upsert_service_heartbeat(
    engine: Engine,
    *,
    service_name: str,
    role: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Upsert using a short transaction; set app.role when writing as stockpilot_app."""
    with engine.begin() as conn:
        if role is not None:
            conn.execute(
                text("SELECT set_config('app.role', :v, true)"),
                {"v": role},
            )
        upsert_heartbeat(conn, service_name=service_name, details=details)
