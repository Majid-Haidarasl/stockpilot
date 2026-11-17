"""Messaging cut-point tests: outbox/relay/worker crash seams (Postgres + RabbitMQ)."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text

from stockpilot.bootstrap.relay import run_once
from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.modules.access.domain.models import Role
from stockpilot.modules.notifications.adapters.outbound.consume_service import (
    process_order_lifecycle_event,
)
from stockpilot.platform.outbox.claim import claim_batch
from stockpilot.platform.outbox.envelope import build_envelope
from stockpilot.platform.outbox.mapping import ORDER_LIFECYCLE_TASK
from stockpilot.platform.outbox.publisher import publish_celery_task
from stockpilot.platform.outbox.writer import enqueue
from stockpilot.platform.persistence.uow import UnitOfWork

pytestmark = pytest.mark.skipif(
    not os.environ.get("STOCKPILOT_DATABASE_URL")
    or not os.environ.get("STOCKPILOT_MIGRATION_DATABASE_URL")
    or not os.environ.get("STOCKPILOT_RELAY_DATABASE_URL")
    or not os.environ.get("STOCKPILOT_CELERY_BROKER_URL"),
    reason="Relay/DB/broker URLs not configured",
)


def _app():
    return create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)


def _migrator():
    return create_engine(os.environ["STOCKPILOT_MIGRATION_DATABASE_URL"], pool_pre_ping=True)


def _relay():
    return create_engine(os.environ["STOCKPILOT_RELAY_DATABASE_URL"], pool_pre_ping=True)


def _broker() -> str:
    return os.environ["STOCKPILOT_CELERY_BROKER_URL"]


def _seed_tenant_with_roles() -> tuple[UUID, dict[str, UUID]]:
    users: dict[str, UUID] = {}
    with UnitOfWork(engine=_migrator()) as uow:
        access = AccessRepository(uow.connection)
        tenant_id = access.ensure_tenant(slug=f"cut-{uuid4().hex[:8]}", name="Cut Org")
        for key, role in (
            ("admin", Role.ADMIN),
            ("sales", Role.SALES),
            ("warehouse", Role.WAREHOUSE),
        ):
            uid = access.upsert_user(
                issuer="test-issuer",
                subject=f"cut-{key}-{uuid4()}",
                email=f"{key}-{uuid4().hex[:6]}@cut.test",
                display_name=key,
            )
            access.ensure_membership(tenant_id=tenant_id, user_id=uid, role=role)
            users[key] = uid
    return tenant_id, users


def _insert_outbox(*, tenant_id: UUID, event_type: str = "OrderReserved") -> UUID:
    with UnitOfWork(engine=_app(), tenant_id=tenant_id, user_id=None, role="admin") as uow:
        return enqueue(
            uow.connection,
            tenant_id=tenant_id,
            event_type=event_type,
            event_version="v1",
            aggregate_type="order",
            aggregate_id=uuid4(),
            payload={"order_id": str(uuid4())},
            trace_id="abcdef0123456789abcdef0123456789",
        )


def _isolate_event(event_id: UUID) -> None:
    with _migrator().begin() as conn:
        conn.execute(
            text(
                """
                UPDATE platform.outbox
                SET lease_owner = 'test-hold',
                    lease_expires_at = now() + interval '1 day'
                WHERE published_at IS NULL
                  AND event_id <> :id
                """
            ),
            {"id": str(event_id)},
        )
        conn.execute(
            text(
                """
                UPDATE platform.outbox
                SET lease_owner = NULL,
                    lease_expires_at = NULL,
                    last_error = NULL
                WHERE event_id = :id
                """
            ),
            {"id": str(event_id)},
        )


def _load_outbox_row(event_id: UUID) -> dict[str, Any]:
    with _migrator().connect() as conn:
        row = (
            conn.execute(
                text(
                    """
                    SELECT event_id, event_type, event_version, tenant_id,
                           aggregate_type, aggregate_id, payload_json, created_at,
                           trace_id, published_at
                    FROM platform.outbox WHERE event_id = :id
                    """
                ),
                {"id": str(event_id)},
            )
            .mappings()
            .one()
        )
    return dict(row)


def _envelope_from_outbox(row: dict[str, Any]) -> dict[str, Any]:
    return build_envelope(
        event_id=UUID(str(row["event_id"])),
        event_type=str(row["event_type"]),
        event_version=str(row["event_version"]),
        tenant_id=UUID(str(row["tenant_id"])),
        aggregate_type=str(row["aggregate_type"]),
        aggregate_id=UUID(str(row["aggregate_id"])),
        occurred_at=row["created_at"],
        payload=row["payload_json"] if isinstance(row["payload_json"], dict) else {},
        trace_id=row.get("trace_id"),
    )


def _count_notifications_for_event(event_id: UUID) -> int:
    with UnitOfWork(engine=_migrator()) as uow:
        row = uow.connection.execute(
            text(
                """
                SELECT COUNT(*) FROM notifications.notifications
                WHERE inbox_event_id = :e
                """
            ),
            {"e": str(event_id)},
        ).one()
    return int(row[0])


def _inbox_count(event_id: UUID) -> int:
    with UnitOfWork(engine=_migrator()) as uow:
        row = uow.connection.execute(
            text(
                """
                SELECT COUNT(*) FROM platform.inbox
                WHERE event_id = :e
                """
            ),
            {"e": str(event_id)},
        ).one()
    return int(row[0])


def _expire_lease(event_id: UUID) -> None:
    with _relay().begin() as conn:
        conn.execute(
            text(
                """
                UPDATE platform.outbox
                SET lease_expires_at = :past, lease_owner = 'dead'
                WHERE event_id = :id
                """
            ),
            {"past": datetime.now(UTC) - timedelta(seconds=5), "id": str(event_id)},
        )


def _start_worker(*, hang_event_id: str | None = None) -> subprocess.Popen[bytes]:
    env = {
        **os.environ,
        "STOCKPILOT_ENVIRONMENT": "test",
    }
    if hang_event_id:
        env["STOCKPILOT_TEST_HANG_EVENT_ID"] = hang_event_id
    else:
        env.pop("STOCKPILOT_TEST_HANG_EVENT_ID", None)
    log_path = f"/tmp/celery-cut-{uuid4().hex[:8]}.log"
    log_f = open(log_path, "w", encoding="utf-8")  # noqa: SIM115 — kept for worker lifetime
    proc = subprocess.Popen(
        [
            "celery",
            "-A",
            "stockpilot.bootstrap.celery_app.celery_app",
            "worker",
            "--pool=solo",
            "--concurrency=1",
            "--loglevel=INFO",
            "-n",
            f"cut-{uuid4().hex[:8]}@localhost",
            "-Q",
            "celery",
            "--without-heartbeat",
            "--without-mingle",
            "--without-gossip",
        ],
        env=env,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        text=True,
    )
    # Wait until Celery reports ready (or process dies).
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            log_f.flush()
            body = Path(log_path).read_text(encoding="utf-8", errors="replace")
            raise AssertionError(f"celery worker exited early:\n{body}")
        log_f.flush()
        body = Path(log_path).read_text(encoding="utf-8", errors="replace")
        if "ready." in body.lower() or "celery@" in body:
            break
        time.sleep(0.2)
    else:
        log_f.flush()
        body = Path(log_path).read_text(encoding="utf-8", errors="replace")
        _kill_worker(proc)
        raise AssertionError(f"celery worker did not become ready:\n{body}")
    proc._stockpilot_log = log_f  # type: ignore[attr-defined]
    return proc


def _kill_worker(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    proc.send_signal(signal.SIGKILL)
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)


def _wait_until(predicate, *, timeout: float = 45.0, interval: float = 0.25) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise AssertionError(f"condition not met within {timeout}s")


def test_cutpoint_after_outbox_before_publish_recovers_once() -> None:
    tenant_id, _users = _seed_tenant_with_roles()
    event_id = _insert_outbox(tenant_id=tenant_id, event_type="OrderConfirmed")
    _isolate_event(event_id)

    # Crash after claim, before publish.
    with _relay().begin() as conn:
        claimed = claim_batch(
            conn,
            lease_owner="dead-relay",
            lease_ttl=timedelta(seconds=60),
            limit=10,
        )
    assert any(r.event_id == event_id for r in claimed)
    _expire_lease(event_id)

    n = run_once(
        database_url=os.environ["STOCKPILOT_RELAY_DATABASE_URL"],
        broker_url=_broker(),
        batch_size=10,
        lease_seconds=30,
    )
    assert n >= 1
    row = _load_outbox_row(event_id)
    assert row["published_at"] is not None

    env = _envelope_from_outbox(row)
    result = process_order_lifecycle_event(env, engine=_app())
    assert result["duplicate"] is False
    assert _inbox_count(event_id) == 1
    assert _count_notifications_for_event(event_id) >= 1
    # Re-process: still one set.
    again = process_order_lifecycle_event(env, engine=_app())
    assert again["duplicate"] is True
    assert _count_notifications_for_event(event_id) == result["notifications"]


def test_cutpoint_after_publish_before_mark_dedups() -> None:
    tenant_id, _users = _seed_tenant_with_roles()
    event_id = _insert_outbox(tenant_id=tenant_id, event_type="OrderConfirmed")
    _isolate_event(event_id)

    with _relay().begin() as conn:
        claimed = claim_batch(
            conn,
            lease_owner="relay-cut-b",
            lease_ttl=timedelta(seconds=60),
            limit=10,
        )
    row_claimed = next(r for r in claimed if r.event_id == event_id)
    env = build_envelope(
        event_id=row_claimed.event_id,
        event_type=row_claimed.event_type,
        event_version=row_claimed.event_version,
        tenant_id=row_claimed.tenant_id,
        aggregate_type=row_claimed.aggregate_type,
        aggregate_id=row_claimed.aggregate_id,
        occurred_at=row_claimed.created_at,
        payload=row_claimed.payload_json,
        trace_id=row_claimed.trace_id,
    )
    # Publish once but crash before mark_published.
    pub = publish_celery_task(
        broker_url=_broker(),
        task_name=ORDER_LIFECYCLE_TASK,
        envelope=env,
    )
    assert pub.ok
    assert _load_outbox_row(event_id)["published_at"] is None
    _expire_lease(event_id)

    # Relay recovers: second publish (at-least-once).
    n = run_once(
        database_url=os.environ["STOCKPILOT_RELAY_DATABASE_URL"],
        broker_url=_broker(),
        batch_size=10,
        lease_seconds=30,
    )
    assert n >= 1
    assert _load_outbox_row(event_id)["published_at"] is not None

    first = process_order_lifecycle_event(env, engine=_app())
    second = process_order_lifecycle_event(env, engine=_app())
    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert _inbox_count(event_id) == 1
    assert _count_notifications_for_event(event_id) == first["notifications"]


def test_cutpoint_after_inbox_before_ack_redelivery_dedups() -> None:
    """Real Celery path: commit Inbox+notifications, abort before ack, RMQ redelivers."""
    tenant_id, _users = _seed_tenant_with_roles()
    event_id = uuid4()
    order_id = uuid4()
    env = {
        "event_id": str(event_id),
        "event_type": "OrderConfirmed",
        "event_version": "v1",
        "tenant_id": str(tenant_id),
        "aggregate_type": "order",
        "aggregate_id": str(order_id),
        "occurred_at": datetime.now(UTC).isoformat(),
        "payload": {"order_id": str(order_id)},
    }
    pub = publish_celery_task(
        broker_url=_broker(),
        task_name=ORDER_LIFECYCLE_TASK,
        envelope=env,
    )
    assert pub.ok

    hung = _start_worker(hang_event_id=str(event_id))
    try:
        _wait_until(lambda: _count_notifications_for_event(event_id) >= 1, timeout=60)
        n_after_commit = _count_notifications_for_event(event_id)
        assert _inbox_count(event_id) == 1
        assert n_after_commit >= 1
        # Kill before Celery can ack (acks_late).
        _kill_worker(hung)
        hung = None

        # Fresh worker without hang: redelivery must dedup.
        worker = _start_worker(hang_event_id=None)
        try:
            # Allow redelivery + duplicate ack; counts must stay stable.
            time.sleep(8)
            assert _inbox_count(event_id) == 1
            assert _count_notifications_for_event(event_id) == n_after_commit
        finally:
            _kill_worker(worker)
    finally:
        if hung is not None:
            _kill_worker(hung)
