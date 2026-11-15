"""Outbox Relay integration: mapping publish, privilege, lease, unroutable, outage."""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from stockpilot.bootstrap.relay import run_once
from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.platform.outbox.claim import claim_batch, mark_published, record_publish_failure
from stockpilot.platform.outbox.envelope import build_envelope
from stockpilot.platform.outbox.mapping import ORDER_LIFECYCLE_TASK, task_for_event_type
from stockpilot.platform.outbox.publisher import publish_celery_task, publish_unroutable_for_test
from stockpilot.platform.outbox.writer import enqueue
from stockpilot.platform.persistence.uow import UnitOfWork

pytestmark = pytest.mark.skipif(
    not os.environ.get("STOCKPILOT_DATABASE_URL")
    or not os.environ.get("STOCKPILOT_MIGRATION_DATABASE_URL")
    or not os.environ.get("STOCKPILOT_RELAY_DATABASE_URL")
    or not os.environ.get("STOCKPILOT_CELERY_BROKER_URL"),
    reason="Relay/DB/broker URLs not configured",
)


def _app() -> object:
    return create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)


def _migrator() -> object:
    return create_engine(os.environ["STOCKPILOT_MIGRATION_DATABASE_URL"], pool_pre_ping=True)


def _relay() -> object:
    return create_engine(os.environ["STOCKPILOT_RELAY_DATABASE_URL"], pool_pre_ping=True)


def _broker() -> str:
    return os.environ["STOCKPILOT_CELERY_BROKER_URL"]


def _seed_tenant() -> object:
    with UnitOfWork(engine=_migrator()) as uow:
        access = AccessRepository(uow.connection)
        return access.ensure_tenant(slug=f"obx-{uuid4().hex[:8]}", name="Outbox Org")


def _insert_outbox(*, tenant_id: object, event_type: str = "OrderReserved") -> object:
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


def _isolate_event(event_id: object) -> None:
    """Hold other unpublished rows so claim/publish tests see only this event."""
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


def test_mapping_integration_publish_and_mark() -> None:
    tenant_id = _seed_tenant()
    event_id = _insert_outbox(tenant_id=tenant_id)
    _isolate_event(event_id)
    assert task_for_event_type("OrderReserved") == ORDER_LIFECYCLE_TASK

    n = run_once(
        database_url=os.environ["STOCKPILOT_RELAY_DATABASE_URL"],
        broker_url=_broker(),
        batch_size=50,
        lease_seconds=30,
    )
    assert n >= 1
    with _relay().connect() as conn:
        row = (
            conn.execute(
                text("SELECT published_at, last_error FROM platform.outbox WHERE event_id = :id"),
                {"id": str(event_id)},
            )
            .mappings()
            .one()
        )
    assert row["published_at"] is not None
    assert row["last_error"] is None


def test_relay_cannot_read_commercial_schemas_or_update_payload() -> None:
    for schema, table in (
        ("sales", "orders"),
        ("catalog", "products"),
        ("inventory", "stock_positions"),
    ):
        with _relay().connect() as conn:
            with pytest.raises((ProgrammingError, DBAPIError)):
                conn.execute(text(f"SELECT 1 FROM {schema}.{table} LIMIT 1"))

    tenant_id = _seed_tenant()
    event_id = _insert_outbox(tenant_id=tenant_id)
    with _relay().connect() as conn:
        with pytest.raises((ProgrammingError, DBAPIError)):
            conn.execute(
                text(
                    "UPDATE platform.outbox SET payload_json = CAST(:p AS jsonb) "
                    "WHERE event_id = :id"
                ),
                {"p": json.dumps({"x": 1}), "id": str(event_id)},
            )
    # Relay may still update lease columns.
    with _relay().begin() as conn:
        conn.execute(
            text(
                "UPDATE platform.outbox SET last_error = :e WHERE event_id = :id "
                "AND published_at IS NULL"
            ),
            {"e": "privilege-check", "id": str(event_id)},
        )


def test_dual_claim_after_lease_expiry_publishes_once() -> None:
    tenant_id = _seed_tenant()
    event_id = _insert_outbox(tenant_id=tenant_id)
    _isolate_event(event_id)
    # Expire any lease immediately so both "relays" can claim.
    with _relay().begin() as conn:
        conn.execute(
            text(
                "UPDATE platform.outbox SET lease_expires_at = :past, lease_owner = 'stale' "
                "WHERE event_id = :id"
            ),
            {"past": datetime.now(UTC) - timedelta(seconds=5), "id": str(event_id)},
        )

    with _relay().begin() as conn:
        first = claim_batch(
            conn,
            lease_owner="relay-a",
            lease_ttl=timedelta(seconds=30),
            limit=10,
        )
    with _relay().begin() as conn:
        # Force lease expiry so second claim can take the same row.
        conn.execute(
            text("UPDATE platform.outbox SET lease_expires_at = :past WHERE event_id = :id"),
            {"past": datetime.now(UTC) - timedelta(seconds=1), "id": str(event_id)},
        )
        second = claim_batch(
            conn,
            lease_owner="relay-b",
            lease_ttl=timedelta(seconds=30),
            limit=10,
        )

    claimed_ids = {r.event_id for r in first + second}
    assert event_id in claimed_ids
    assert any(r.event_id == event_id for r in first)
    assert any(r.event_id == event_id for r in second)

    # Simulate two relays finishing publish: first mark wins; second is idempotent.
    # Clear lease so a single publish cycle can proceed, then double-mark.
    with _relay().begin() as conn:
        conn.execute(
            text(
                "UPDATE platform.outbox SET lease_expires_at = NULL, lease_owner = NULL "
                "WHERE event_id = :id"
            ),
            {"id": str(event_id)},
        )
    run_once(
        database_url=os.environ["STOCKPILOT_RELAY_DATABASE_URL"],
        broker_url=_broker(),
        batch_size=10,
        lease_seconds=30,
    )
    with _relay().begin() as conn:
        first_mark = mark_published(conn, event_id=event_id)
        second_mark = mark_published(conn, event_id=event_id)
    assert first_mark is False  # already published by run_once
    assert second_mark is False

    with _relay().connect() as conn:
        row = (
            conn.execute(
                text(
                    "SELECT published_at, attempt_count FROM platform.outbox WHERE event_id = :id"
                ),
                {"id": str(event_id)},
            )
            .mappings()
            .one()
        )
    assert row["published_at"] is not None
    assert int(row["attempt_count"]) >= 2  # claimed at least twice before publish


def test_unroutable_leaves_unpublished_with_last_error() -> None:
    tenant_id = _seed_tenant()
    event_id = _insert_outbox(tenant_id=tenant_id)
    with _migrator().connect() as conn:
        row = (
            conn.execute(
                text(
                    "SELECT event_type, event_version, tenant_id, aggregate_type, "
                    "aggregate_id, payload_json, trace_id, created_at "
                    "FROM platform.outbox WHERE event_id = :id"
                ),
                {"id": str(event_id)},
            )
            .mappings()
            .one()
        )

    envelope = build_envelope(
        event_id=event_id,
        event_type=str(row["event_type"]),
        event_version=str(row["event_version"]),
        tenant_id=row["tenant_id"],
        aggregate_type=str(row["aggregate_type"]),
        aggregate_id=row["aggregate_id"],
        occurred_at=row["created_at"],
        payload=dict(row["payload_json"]),
        trace_id=row["trace_id"],
    )
    result = publish_unroutable_for_test(broker_url=_broker(), envelope=envelope)
    assert result.ok is False
    assert result.error

    with _relay().begin() as conn:
        record_publish_failure(
            conn,
            event_id=event_id,
            attempt_count=1,
            error=result.error or "unroutable",
        )

    with _relay().connect() as conn:
        out = (
            conn.execute(
                text(
                    "SELECT published_at, last_error, lease_expires_at "
                    "FROM platform.outbox WHERE event_id = :id"
                ),
                {"id": str(event_id)},
            )
            .mappings()
            .one()
        )
    assert out["published_at"] is None
    assert out["last_error"]
    assert out["lease_expires_at"] is not None
    assert out["lease_expires_at"] > datetime.now(UTC)


def test_publish_celery_task_happy_path() -> None:
    envelope = build_envelope(
        event_id=uuid4(),
        event_type="OrderConfirmed",
        event_version="v1",
        tenant_id=uuid4(),
        aggregate_type="order",
        aggregate_id=uuid4(),
        occurred_at=datetime.now(UTC),
        payload={"order_id": str(uuid4())},
        trace_id=None,
    )
    result = publish_celery_task(
        broker_url=_broker(),
        task_name=ORDER_LIFECYCLE_TASK,
        envelope=envelope,
    )
    assert result.ok is True


def test_outage_recovery_publishes_after_broker_available() -> None:
    """Order Outbox row written without requiring broker; relay publishes when up."""
    tenant_id = _seed_tenant()
    event_id = _insert_outbox(tenant_id=tenant_id, event_type="OrderCancelled")
    _isolate_event(event_id)
    with _relay().connect() as conn:
        before = conn.execute(
            text("SELECT published_at FROM platform.outbox WHERE event_id = :id"),
            {"id": str(event_id)},
        ).scalar_one()
    assert before is None

    # Broker is up in backend-checks; simulate "after recovery" by running relay.
    after = None
    deadline = time.time() + 30
    while time.time() < deadline:
        run_once(
            database_url=os.environ["STOCKPILOT_RELAY_DATABASE_URL"],
            broker_url=_broker(),
            batch_size=50,
            lease_seconds=30,
        )
        with _relay().connect() as conn:
            after = conn.execute(
                text("SELECT published_at FROM platform.outbox WHERE event_id = :id"),
                {"id": str(event_id)},
            ).scalar_one()
        if after is not None:
            break
        time.sleep(0.5)
    assert after is not None
