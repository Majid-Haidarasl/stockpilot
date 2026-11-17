"""Ops replay of durable failed_jobs (migrator role + publisher confirms)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.platform.outbox.publisher import publish_celery_task

logger = logging.getLogger("stockpilot.ops.replay")


class _AbortReplayRow(Exception):
    """Roll back the current row transaction without aborting the whole batch."""


@dataclass(slots=True)
class FailedJobRow:
    id: UUID
    tenant_id: UUID | None
    event_id: UUID | None
    task_name: str
    error_message: str
    attempts: int
    replay_count: int
    replayed_at: Any
    sanitized_envelope: dict[str, Any] | None


@dataclass
class ReplayOutcome:
    selected: int = 0
    dry_run: int = 0
    replayed: int = 0
    skipped_unscoped: int = 0
    skipped_replayed: int = 0
    skipped_no_envelope: int = 0
    failed: int = 0
    messages: list[str] = field(default_factory=list)


def _parse_envelope(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return loaded if isinstance(loaded, dict) else None
    return None


def _row_from_mapping(row: Any) -> FailedJobRow:
    env = _parse_envelope(row.sanitized_envelope)
    return FailedJobRow(
        id=UUID(str(row.id)),
        tenant_id=UUID(str(row.tenant_id)) if row.tenant_id is not None else None,
        event_id=UUID(str(row.event_id)) if row.event_id is not None else None,
        task_name=str(row.task_name),
        error_message=str(row.error_message),
        attempts=int(row.attempts),
        replay_count=int(row.replay_count),
        replayed_at=row.replayed_at,
        sanitized_envelope=env,
    )


def resolve_tenant_id(conn: Connection, tenant_slug: str | None) -> UUID | None:
    if not tenant_slug:
        return None
    row = conn.execute(
        text("SELECT id FROM access.tenants WHERE slug = :slug"),
        {"slug": tenant_slug},
    ).first()
    if row is None:
        raise ValueError(f"unknown tenant slug: {tenant_slug}")
    return UUID(str(row.id))


def select_failed_jobs(
    conn: Connection,
    *,
    job_id: UUID | None,
    tenant_id: UUID | None,
    include_replayed: bool,
    limit: int,
    for_update: bool,
) -> list[FailedJobRow]:
    """Select candidate failed_jobs. When for_update, use SKIP LOCKED."""
    clauses: list[str] = ["1=1"]
    params: dict[str, Any] = {"limit": limit}
    if job_id is not None:
        clauses.append("id = :job_id")
        params["job_id"] = str(job_id)
    if tenant_id is not None:
        clauses.append("tenant_id = :tenant_id")
        params["tenant_id"] = str(tenant_id)
    if not include_replayed:
        clauses.append("replayed_at IS NULL")
    lock = " FOR UPDATE SKIP LOCKED" if for_update else ""
    sql = f"""
        SELECT id, tenant_id, event_id, task_name, error_message, attempts,
               replay_count, replayed_at, sanitized_envelope
        FROM platform.failed_jobs
        WHERE {" AND ".join(clauses)}
        ORDER BY last_failed_at DESC
        LIMIT :limit
        {lock}
    """
    result = conn.execute(text(sql), params)
    return [_row_from_mapping(r) for r in result]


def _mark_replayed_and_audit(
    conn: Connection,
    *,
    job: FailedJobRow,
    replayed_by: str,
) -> int:
    """UPDATE replay columns + INSERT audit in the current transaction."""
    updated = conn.execute(
        text(
            """
            UPDATE platform.failed_jobs
            SET replayed_at = now(),
                replayed_by = :replayed_by,
                replay_count = replay_count + 1
            WHERE id = :id
            RETURNING replay_count
            """
        ),
        {"id": str(job.id), "replayed_by": replayed_by},
    ).one()
    new_count = int(updated.replay_count)
    if job.tenant_id is None:
        raise RuntimeError("unscoped job cannot be audited")
    repo = AccessRepository(conn)
    repo.write_audit(
        tenant_id=job.tenant_id,
        actor_user_id=None,
        action_type="ops.replay.failed_job",
        entity_type="failed_job",
        entity_id=job.id,
        payload={
            "event_id": str(job.event_id) if job.event_id else None,
            "task_name": job.task_name,
            "replay_count": new_count,
            "replayed_by": replayed_by,
        },
    )
    return new_count


def replay_failed_jobs(
    *,
    engine: Engine,
    broker_url: str | None,
    job_id: UUID | None,
    tenant_slug: str | None,
    include_replayed: bool,
    limit: int,
    replayed_by: str | None,
    confirm: bool,
) -> ReplayOutcome:
    """Dry-run or confirm replay. Unscoped (null tenant) jobs are always skipped."""
    outcome = ReplayOutcome()

    with engine.connect() as conn:
        try:
            tenant_id = resolve_tenant_id(conn, tenant_slug)
        except ValueError as exc:
            outcome.messages.append(str(exc))
            outcome.failed += 1
            return outcome

        if not confirm:
            rows = select_failed_jobs(
                conn,
                job_id=job_id,
                tenant_id=tenant_id,
                include_replayed=include_replayed,
                limit=limit,
                for_update=False,
            )
            outcome.selected = len(rows)
            for job in rows:
                if job.tenant_id is None:
                    outcome.skipped_unscoped += 1
                    outcome.messages.append(f"{job.id}: skipped: unscoped")
                    if job_id is not None:
                        outcome.failed += 1
                    continue
                if job.sanitized_envelope is None:
                    outcome.skipped_no_envelope += 1
                    outcome.messages.append(f"{job.id}: skipped: no sanitized_envelope")
                    continue
                outcome.dry_run += 1
                outcome.messages.append(
                    f"{job.id}: dry-run event_id={job.event_id} "
                    f"task={job.task_name} replay_count={job.replay_count}"
                )
            return outcome

        candidates = select_failed_jobs(
            conn,
            job_id=job_id,
            tenant_id=tenant_id,
            include_replayed=include_replayed,
            limit=limit,
            for_update=False,
        )
        outcome.selected = len(candidates)
        candidate_ids = [j.id for j in candidates]

    if not broker_url:
        outcome.messages.append("STOCKPILOT_CELERY_BROKER_URL is required with --confirm")
        outcome.failed += 1
        return outcome
    if not replayed_by:
        outcome.messages.append("--replayed-by is required with --confirm")
        outcome.failed += 1
        return outcome

    for cid in candidate_ids:
        try:
            with engine.begin() as conn:
                locked = select_failed_jobs(
                    conn,
                    job_id=cid,
                    tenant_id=None,
                    include_replayed=True,
                    limit=1,
                    for_update=True,
                )
                if not locked:
                    outcome.messages.append(
                        f"{cid}: skipped: locked by another operator or missing"
                    )
                    continue
                job = locked[0]
                if not include_replayed and job.replayed_at is not None:
                    outcome.skipped_replayed += 1
                    outcome.messages.append(f"{job.id}: skipped: already replayed")
                    continue
                if job.tenant_id is None:
                    outcome.skipped_unscoped += 1
                    outcome.messages.append(f"{job.id}: skipped: unscoped")
                    if job_id is not None:
                        outcome.failed += 1
                    continue
                if not job.sanitized_envelope:
                    outcome.skipped_no_envelope += 1
                    outcome.messages.append(f"{job.id}: skipped: no sanitized_envelope")
                    outcome.failed += 1
                    continue
                env = job.sanitized_envelope
                if job.event_id is not None and str(env.get("event_id")) != str(job.event_id):
                    outcome.failed += 1
                    outcome.messages.append(
                        f"{job.id}: failed: envelope event_id mismatch "
                        "(refusing to mint/replace event_id)"
                    )
                    continue

                result = publish_celery_task(
                    broker_url=broker_url,
                    task_name=job.task_name,
                    envelope=env,
                )
                if not result.ok:
                    outcome.failed += 1
                    outcome.messages.append(
                        f"{job.id}: publish failed: {result.error}; row untouched (rollback)"
                    )
                    raise _AbortReplayRow()

                try:
                    new_count = _mark_replayed_and_audit(conn, job=job, replayed_by=replayed_by)
                except Exception as exc:
                    outcome.failed += 1
                    outcome.messages.append(
                        f"{job.id}: publish succeeded but mark/audit failed: {exc}. "
                        "Re-replay is safe (Inbox dedups on event_id)."
                    )
                    raise

                outcome.replayed += 1
                outcome.messages.append(
                    f"{job.id}: replayed event_id={job.event_id} replay_count={new_count}"
                )
        except _AbortReplayRow:
            continue

    return outcome
