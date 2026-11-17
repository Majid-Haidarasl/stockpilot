"""Killed worker: acks_late + task_reject_on_worker_lost => one successful process."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text

from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.modules.access.domain.models import Role
from stockpilot.platform.outbox.mapping import ORDER_LIFECYCLE_TASK
from stockpilot.platform.outbox.publisher import publish_celery_task
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


def _seed() -> tuple[UUID, dict[str, UUID]]:
    users: dict[str, UUID] = {}
    with UnitOfWork(engine=_migrator()) as uow:
        access = AccessRepository(uow.connection)
        tenant_id = access.ensure_tenant(slug=f"kill-{uuid4().hex[:8]}", name="Kill Org")
        for key, role in (
            ("admin", Role.ADMIN),
            ("sales", Role.SALES),
        ):
            uid = access.upsert_user(
                issuer="test-issuer",
                subject=f"kill-{key}-{uuid4()}",
                email=f"{key}-{uuid4().hex[:6]}@kill.test",
                display_name=key,
            )
            access.ensure_membership(tenant_id=tenant_id, user_id=uid, role=role)
            users[key] = uid
    return tenant_id, users


def _count(event_id: UUID) -> int:
    with UnitOfWork(engine=_migrator()) as uow:
        row = uow.connection.execute(
            text("SELECT COUNT(*) FROM notifications.notifications WHERE inbox_event_id = :e"),
            {"e": str(event_id)},
        ).one()
    return int(row[0])


def _inbox(event_id: UUID) -> int:
    with UnitOfWork(engine=_migrator()) as uow:
        row = uow.connection.execute(
            text("SELECT COUNT(*) FROM platform.inbox WHERE event_id = :e"),
            {"e": str(event_id)},
        ).one()
    return int(row[0])


def _start_worker(*, hang_event_id: str | None) -> subprocess.Popen[bytes]:
    from pathlib import Path

    env = {**os.environ, "STOCKPILOT_ENVIRONMENT": "test"}
    if hang_event_id:
        env["STOCKPILOT_TEST_HANG_EVENT_ID"] = hang_event_id
    else:
        env.pop("STOCKPILOT_TEST_HANG_EVENT_ID", None)
    log_path = f"/tmp/celery-kill-{uuid4().hex[:8]}.log"
    log_f = open(log_path, "w", encoding="utf-8")  # noqa: SIM115
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
            f"kill-{uuid4().hex[:8]}@localhost",
            "--without-heartbeat",
            "--without-mingle",
            "--without-gossip",
        ],
        env=env,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        text=True,
    )
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
        _kill(proc)
        raise AssertionError(f"celery worker did not become ready:\n{body}")
    return proc


def _kill(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    proc.send_signal(signal.SIGKILL)
    proc.wait(timeout=30)


def test_killed_worker_redelivers_once() -> None:
    tenant_id, _users = _seed()
    event_id = uuid4()
    order_id = uuid4()
    env = {
        "event_id": str(event_id),
        "event_type": "OrderReserved",
        "event_version": "v1",
        "tenant_id": str(tenant_id),
        "aggregate_type": "order",
        "aggregate_id": str(order_id),
        "occurred_at": datetime.now(UTC).isoformat(),
        "payload": {"order_id": str(order_id)},
    }
    assert publish_celery_task(
        broker_url=os.environ["STOCKPILOT_CELERY_BROKER_URL"],
        task_name=ORDER_LIFECYCLE_TASK,
        envelope=env,
    ).ok

    hung = _start_worker(hang_event_id=str(event_id))
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if _count(event_id) >= 1:
                break
            time.sleep(0.25)
        assert _count(event_id) >= 1
        n = _count(event_id)
        assert _inbox(event_id) == 1
        _kill(hung)
        hung = None

        worker = _start_worker(hang_event_id=None)
        try:
            time.sleep(5)
            assert _inbox(event_id) == 1
            assert _count(event_id) == n
        finally:
            _kill(worker)
    finally:
        if hung is not None:
            _kill(hung)

    # Prove app engine still usable (sanity).
    assert _app() is not None
