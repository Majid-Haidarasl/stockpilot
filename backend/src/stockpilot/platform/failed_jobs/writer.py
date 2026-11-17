"""Insert-only failed_jobs recorder (no RETURNING; id allocated in Python)."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from stockpilot.platform.failed_jobs.sanitize import sanitize_envelope
from stockpilot.platform.persistence.uow import UnitOfWork

_MAX_ERROR_LEN = 500


def sanitize_error(message: str) -> str:
    cleaned = " ".join(message.split())
    if len(cleaned) > _MAX_ERROR_LEN:
        return cleaned[: _MAX_ERROR_LEN - 3] + "..."
    return cleaned


def record_failed_job(
    *,
    engine: Engine,
    task_name: str,
    error_message: str,
    attempts: int,
    tenant_id: UUID | None,
    event_id: UUID | None,
    envelope: dict[str, Any] | None = None,
) -> UUID:
    """Persist a failed job. Raises if the INSERT cannot commit (caller must not ack)."""
    job_id = uuid4()
    sanitized = sanitize_error(error_message)
    env = sanitize_envelope(envelope)
    with UnitOfWork(engine=engine, tenant_id=tenant_id) as uow:
        uow.connection.execute(
            text(
                """
                INSERT INTO platform.failed_jobs (
                  id, tenant_id, event_id, task_name, error_message,
                  attempts, first_failed_at, last_failed_at, sanitized_envelope
                ) VALUES (
                  :id, :tenant_id, :event_id, :task_name, :error_message,
                  :attempts, now(), now(), CAST(:sanitized_envelope AS jsonb)
                )
                """
            ),
            {
                "id": str(job_id),
                "tenant_id": str(tenant_id) if tenant_id is not None else None,
                "event_id": str(event_id) if event_id is not None else None,
                "task_name": task_name,
                "error_message": sanitized,
                "attempts": attempts,
                "sanitized_envelope": json.dumps(env) if env is not None else None,
            },
        )
    return job_id


def insert_failed_job_on_connection(
    conn: Connection,
    *,
    job_id: UUID,
    task_name: str,
    error_message: str,
    attempts: int,
    tenant_id: UUID | None,
    event_id: UUID | None,
    envelope: dict[str, Any] | None = None,
) -> None:
    """Low-level insert for tests that already hold a connection/transaction."""
    env = sanitize_envelope(envelope)
    conn.execute(
        text(
            """
            INSERT INTO platform.failed_jobs (
              id, tenant_id, event_id, task_name, error_message,
              attempts, first_failed_at, last_failed_at, sanitized_envelope
            ) VALUES (
              :id, :tenant_id, :event_id, :task_name, :error_message,
              :attempts, now(), now(), CAST(:sanitized_envelope AS jsonb)
            )
            """
        ),
        {
            "id": str(job_id),
            "tenant_id": str(tenant_id) if tenant_id is not None else None,
            "event_id": str(event_id) if event_id is not None else None,
            "task_name": task_name,
            "error_message": sanitize_error(error_message),
            "attempts": attempts,
            "sanitized_envelope": json.dumps(env) if env is not None else None,
        },
    )
