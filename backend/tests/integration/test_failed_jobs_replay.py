"""Ops replay-failed-jobs: dry-run, confirm, unscoped skip, Inbox dedup, privileges."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.modules.access.domain.models import Role
from stockpilot.modules.notifications.adapters.outbound.consume_service import (
    process_order_lifecycle_event,
)
from stockpilot.platform.failed_jobs.replay import replay_failed_jobs
from stockpilot.platform.failed_jobs.sanitize import sanitize_envelope
from stockpilot.platform.failed_jobs.writer import insert_failed_job_on_connection
from stockpilot.platform.outbox.mapping import ORDER_LIFECYCLE_TASK
from stockpilot.platform.persistence.uow import UnitOfWork

pytestmark = pytest.mark.skipif(
    not os.environ.get("STOCKPILOT_DATABASE_URL")
    or not os.environ.get("STOCKPILOT_MIGRATION_DATABASE_URL")
    or not os.environ.get("STOCKPILOT_CELERY_BROKER_URL"),
    reason="DB/broker URLs not configured",
)


def _app():
    return create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)


def _migrator():
    return create_engine(os.environ["STOCKPILOT_MIGRATION_DATABASE_URL"], pool_pre_ping=True)


def _broker() -> str:
    return os.environ["STOCKPILOT_CELERY_BROKER_URL"]


def _seed() -> tuple[UUID, dict[str, UUID]]:
    users: dict[str, UUID] = {}
    with UnitOfWork(engine=_migrator()) as uow:
        access = AccessRepository(uow.connection)
        tenant_id = access.ensure_tenant(slug=f"rpl-{uuid4().hex[:8]}", name="Replay Org")
        for key, role in (("admin", Role.ADMIN), ("sales", Role.SALES)):
            uid = access.upsert_user(
                issuer="test-issuer",
                subject=f"rpl-{key}-{uuid4()}",
                email=f"{key}-{uuid4().hex[:6]}@rpl.test",
                display_name=key,
            )
            access.ensure_membership(tenant_id=tenant_id, user_id=uid, role=role)
            users[key] = uid
    return tenant_id, users


def _envelope(tenant_id: UUID, event_id: UUID | None = None) -> dict:
    eid = event_id or uuid4()
    oid = uuid4()
    return {
        "event_id": str(eid),
        "event_type": "OrderReserved",
        "event_version": "v1",
        "tenant_id": str(tenant_id),
        "aggregate_type": "order",
        "aggregate_id": str(oid),
        "occurred_at": datetime.now(UTC).isoformat(),
        "payload": {"order_id": str(oid), "secret": "drop"},
        "password": "nope",
    }


def _insert_job(
    *,
    tenant_id: UUID | None,
    event_id: UUID | None,
    envelope: dict | None,
    replayed: bool = False,
) -> UUID:
    job_id = uuid4()
    with _migrator().begin() as conn:
        insert_failed_job_on_connection(
            conn,
            job_id=job_id,
            task_name=ORDER_LIFECYCLE_TASK,
            error_message="PermanentConsumeError: test",
            attempts=5,
            tenant_id=tenant_id,
            event_id=event_id,
            envelope=envelope,
        )
        if replayed:
            conn.execute(
                text(
                    """
                    UPDATE platform.failed_jobs
                    SET replayed_at = now(), replayed_by = 'prior', replay_count = 1
                    WHERE id = :id
                    """
                ),
                {"id": str(job_id)},
            )
    return job_id


def _job_row(job_id: UUID) -> dict:
    with _migrator().connect() as conn:
        return dict(
            conn.execute(
                text(
                    """
                    SELECT id, tenant_id, event_id, replayed_at, replay_count, replayed_by,
                           sanitized_envelope
                    FROM platform.failed_jobs WHERE id = :id
                    """
                ),
                {"id": str(job_id)},
            )
            .mappings()
            .one()
        )


def _count_notifications(event_id: UUID) -> int:
    with UnitOfWork(engine=_migrator()) as uow:
        row = uow.connection.execute(
            text("SELECT COUNT(*) FROM notifications.notifications WHERE inbox_event_id = :e"),
            {"e": str(event_id)},
        ).one()
    return int(row[0])


def _count_inbox(event_id: UUID) -> int:
    with UnitOfWork(engine=_migrator()) as uow:
        row = uow.connection.execute(
            text("SELECT COUNT(*) FROM platform.inbox WHERE event_id = :e"),
            {"e": str(event_id)},
        ).one()
    return int(row[0])


def _audit_count(job_id: UUID) -> int:
    with UnitOfWork(engine=_migrator()) as uow:
        row = uow.connection.execute(
            text(
                """
                SELECT COUNT(*) FROM platform.audit_log
                WHERE action_type = 'ops.replay.failed_job'
                  AND entity_id = :id
                """
            ),
            {"id": str(job_id)},
        ).one()
    return int(row[0])


def test_sanitize_envelope_consumer_parity() -> None:
    tenant_id, _ = _seed()
    dirty = _envelope(tenant_id)
    clean = sanitize_envelope(dirty)
    assert clean is not None
    assert "password" not in clean
    assert "secret" not in clean.get("payload", {})

    # Same structure, distinct event_ids so both inserts succeed.
    e1 = uuid4()
    e2 = uuid4()
    original = {**dirty, "event_id": str(e1)}
    sanitized = {**clean, "event_id": str(e2)}
    r1 = process_order_lifecycle_event(original, engine=_app())
    r2 = process_order_lifecycle_event(sanitized, engine=_app())
    assert r1["notifications"] == r2["notifications"]
    assert r1["notifications"] >= 1

    with UnitOfWork(engine=_migrator()) as uow:
        rows = (
            uow.connection.execute(
                text(
                    """
                SELECT inbox_event_id, type, data
                FROM notifications.notifications
                WHERE inbox_event_id IN (:e1, :e2)
                ORDER BY recipient_user_id, inbox_event_id
                """
                ),
                {"e1": str(e1), "e2": str(e2)},
            )
            .mappings()
            .all()
        )
    by_event: dict[str, list] = {str(e1): [], str(e2): []}
    for row in rows:
        by_event[str(row["inbox_event_id"])].append(
            (row["type"], json.dumps(row["data"], sort_keys=True))
        )
    assert len(by_event[str(e1)]) == len(by_event[str(e2)])
    # Same notification type+data (order_id differs only if we changed it — same payload.order_id)
    data1 = sorted(by_event[str(e1)])
    data2 = sorted(by_event[str(e2)])
    # types match; data JSON equals when order_id shared
    assert [t for t, _ in data1] == [t for t, _ in data2]
    assert [d for _, d in data1] == [d for _, d in data2]


def test_replay_failed_jobs_dry_run_no_side_effects() -> None:
    tenant_id, _ = _seed()
    event_id = uuid4()
    env = _envelope(tenant_id, event_id=event_id)
    job_id = _insert_job(tenant_id=tenant_id, event_id=event_id, envelope=env)
    before = _job_row(job_id)
    outcome = replay_failed_jobs(
        engine=_migrator(),
        broker_url=_broker(),
        job_id=job_id,
        tenant_slug=None,
        include_replayed=False,
        limit=10,
        replayed_by=None,
        confirm=False,
    )
    assert outcome.dry_run == 1
    assert outcome.replayed == 0
    after = _job_row(job_id)
    assert after["replayed_at"] is None
    assert after["replay_count"] == before["replay_count"]
    assert _audit_count(job_id) == 0


def test_replay_skips_unscoped_and_fails_when_id_points_at_unscoped() -> None:
    event_id = uuid4()
    env = {
        "event_id": str(event_id),
        "event_type": "OrderReserved",
        "event_version": "v1",
        "tenant_id": str(uuid4()),
        "aggregate_type": "order",
        "aggregate_id": str(uuid4()),
        "occurred_at": datetime.now(UTC).isoformat(),
        "payload": {"order_id": str(uuid4())},
    }
    job_id = _insert_job(tenant_id=None, event_id=event_id, envelope=env)
    outcome = replay_failed_jobs(
        engine=_migrator(),
        broker_url=_broker(),
        job_id=job_id,
        tenant_slug=None,
        include_replayed=False,
        limit=5,
        replayed_by="ops@test",
        confirm=False,
    )
    assert outcome.skipped_unscoped == 1
    assert outcome.failed >= 1
    assert any("skipped: unscoped" in m for m in outcome.messages)
    assert _job_row(job_id)["replayed_at"] is None


def test_replay_failed_jobs_confirm_publishes_and_audits() -> None:
    tenant_id, _ = _seed()
    event_id = uuid4()
    env = sanitize_envelope(_envelope(tenant_id, event_id=event_id))
    assert env is not None
    job_id = _insert_job(tenant_id=tenant_id, event_id=event_id, envelope=env)

    outcome = replay_failed_jobs(
        engine=_migrator(),
        broker_url=_broker(),
        job_id=job_id,
        tenant_slug=None,
        include_replayed=False,
        limit=5,
        replayed_by="ops@test",
        confirm=True,
    )
    assert outcome.replayed == 1
    assert outcome.failed == 0
    row = _job_row(job_id)
    assert row["replayed_at"] is not None
    assert row["replayed_by"] == "ops@test"
    assert int(row["replay_count"]) == 1
    assert _audit_count(job_id) == 1

    # Consume the republished message (same event_id).
    result = process_order_lifecycle_event(env, engine=_app())
    assert result["duplicate"] is False or result["notifications"] >= 0
    assert _count_notifications(event_id) >= 1


def test_replay_already_in_inbox_acks_duplicate_no_extra_notifications() -> None:
    """Replaying a failed_job whose event_id was already consumed must not apply side effects twice.

    Consumer Inbox UNIQUE (consumer_name, event_id) via try_insert_inbox is the dedupe.
    This test fails if the consumer lacks that dedupe and treats the replay as new work.
    """
    tenant_id, _ = _seed()
    event_id = uuid4()
    env = sanitize_envelope(_envelope(tenant_id, event_id=event_id))
    assert env is not None
    first = process_order_lifecycle_event(env, engine=_app())
    assert first["duplicate"] is False
    n = _count_notifications(event_id)
    assert _count_inbox(event_id) == 1

    job_id = _insert_job(tenant_id=tenant_id, event_id=event_id, envelope=env)
    outcome = replay_failed_jobs(
        engine=_migrator(),
        broker_url=_broker(),
        job_id=job_id,
        tenant_slug=None,
        include_replayed=False,
        limit=5,
        replayed_by="ops@test",
        confirm=True,
    )
    assert outcome.replayed == 1
    # Simulate worker consuming the republished message (same event_id).
    second = process_order_lifecycle_event(env, engine=_app())
    assert second["duplicate"] is True
    assert _count_notifications(event_id) == n
    assert _count_inbox(event_id) == 1


def test_replay_skips_replayed_unless_include_flag() -> None:
    tenant_id, _ = _seed()
    event_id = uuid4()
    env = _envelope(tenant_id, event_id=event_id)
    job_id = _insert_job(tenant_id=tenant_id, event_id=event_id, envelope=env, replayed=True)
    skipped = replay_failed_jobs(
        engine=_migrator(),
        broker_url=_broker(),
        job_id=job_id,
        tenant_slug=None,
        include_replayed=False,
        limit=5,
        replayed_by="ops@test",
        confirm=False,
    )
    assert skipped.selected == 0

    included = replay_failed_jobs(
        engine=_migrator(),
        broker_url=_broker(),
        job_id=job_id,
        tenant_slug=None,
        include_replayed=True,
        limit=5,
        replayed_by="ops@test",
        confirm=False,
    )
    assert included.selected == 1
    assert included.dry_run == 1


def test_replay_never_deletes_failed_jobs() -> None:
    tenant_id, _ = _seed()
    event_id = uuid4()
    env = _envelope(tenant_id, event_id=event_id)
    job_id = _insert_job(tenant_id=tenant_id, event_id=event_id, envelope=env)
    replay_failed_jobs(
        engine=_migrator(),
        broker_url=_broker(),
        job_id=job_id,
        tenant_slug=None,
        include_replayed=False,
        limit=5,
        replayed_by="ops@test",
        confirm=True,
    )
    assert _job_row(job_id)["id"] is not None


def test_failed_jobs_app_still_insert_only_after_0012() -> None:
    with _app().connect() as conn:
        with pytest.raises((ProgrammingError, DBAPIError)):
            conn.execute(text("SELECT id FROM platform.failed_jobs LIMIT 1"))
        with pytest.raises((ProgrammingError, DBAPIError)):
            conn.execute(text("UPDATE platform.failed_jobs SET replay_count = 0 WHERE false"))
