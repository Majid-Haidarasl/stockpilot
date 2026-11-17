"""Phase 5.4 scheduler: advisory lock, heartbeats, lag, RLS, RabbitMQ independence."""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from stockpilot.bootstrap.relay import run_once
from stockpilot.bootstrap.scheduler import (
    advisory_unlock,
    run_tick,
    try_advisory_lock,
)
from stockpilot.bootstrap.scheduler_health import check as health_check
from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.modules.access.domain.models import Role
from stockpilot.modules.catalog.adapters.outbound.repo import CatalogRepository
from stockpilot.modules.inventory.adapters.outbound.repo import InventoryRepository
from stockpilot.modules.sales.adapters.outbound.customer_repo import CustomerRepository
from stockpilot.modules.sales.adapters.outbound.order_cycle import OrderCycleService
from stockpilot.modules.sales.adapters.outbound.order_repo import OrderRepository
from stockpilot.modules.sales.domain.order import Order, OrderLine, OrderStatus
from stockpilot.platform.heartbeats.store import fetch_outbox_lag, read_heartbeat, upsert_heartbeat
from stockpilot.platform.outbox.writer import enqueue
from stockpilot.platform.persistence.session_roles import SESSION_ROLE_SCHEDULER
from stockpilot.platform.persistence.uow import UnitOfWork
from stockpilot.platform.time.clock import FixedClock

pytestmark = pytest.mark.skipif(
    not os.environ.get("STOCKPILOT_DATABASE_URL")
    or not os.environ.get("STOCKPILOT_MIGRATION_DATABASE_URL"),
    reason="Database URLs not configured",
)


def _runtime():
    return create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)


def _migrator():
    return create_engine(os.environ["STOCKPILOT_MIGRATION_DATABASE_URL"], pool_pre_ping=True)


def _seed(*, on_hand: int = 10) -> tuple[UUID, UUID, UUID, UUID]:
    with UnitOfWork(engine=_migrator()) as uow:
        access = AccessRepository(uow.connection)
        catalog = CatalogRepository(uow.connection)
        customers = CustomerRepository(uow.connection)
        inventory = InventoryRepository(uow.connection)
        tenant_id = access.ensure_tenant(slug=f"sch-{uuid4().hex[:8]}", name="Sched Org")
        user_id = access.upsert_user(
            issuer="test-issuer",
            subject=f"sch-{uuid4()}",
            email=f"sch-{uuid4().hex}@test",
            display_name="Sch",
        )
        access.ensure_membership(tenant_id=tenant_id, user_id=user_id, role=Role.ADMIN)
        product = catalog.create_product(
            tenant_id=tenant_id,
            sku=f"SKU-{uuid4().hex[:6]}",
            title="Sched Item",
            unit_price_rial=1000,
        )
        product_id = UUID(str(product["id"]))
        customer = customers.create_customer(
            tenant_id=tenant_id, name="Buyer", phone=None, email=None, notes=None
        )
        if on_hand > 0:
            position = inventory.ensure_position_for_update(
                tenant_id=tenant_id, product_id=product_id
            )
            position.apply_receipt(on_hand)
            inventory.save_position(position)
            inventory.insert_movement(
                tenant_id=tenant_id,
                product_id=product_id,
                physical_delta=on_hand,
                reserved_delta=0,
                reason="seed",
                reference=f"seed-{uuid4()}",
                actor_user_id=user_id,
            )
    return tenant_id, user_id, product_id, UUID(str(customer["id"]))


def _draft_and_reserve(
    *,
    tenant_id: UUID,
    user_id: UUID,
    customer_id: UUID,
    product_id: UUID,
    quantity: int = 1,
    clock: FixedClock,
) -> Order:
    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        orders = OrderRepository(uow.connection)
        snap = orders.get_product_snapshot(tenant_id, product_id)
        assert snap is not None
        order = Order.new_draft(
            tenant_id=tenant_id,
            customer_id=customer_id,
            lines=[
                OrderLine(
                    id=uuid4(),
                    product_id=product_id,
                    quantity=quantity,
                    product_sku=str(snap["sku"]),
                    product_title=str(snap["title"]),
                    unit_price_rial=int(snap["unit_price_rial"]),
                )
            ],
        )
        orders.insert_order(order)
        reserved = (
            OrderCycleService(uow.connection, clock=clock)
            .reserve(
                tenant_id=tenant_id,
                order_id=order.id,
                actor_user_id=user_id,
                expected_version=order.version,
            )
            .order
        )
        return reserved


def test_parallel_ticks_expire_once() -> None:
    tenant_id, user_id, product_id, customer_id = _seed(on_hand=4)
    t0 = datetime(2026, 11, 17, 8, 0, tzinfo=UTC)
    order = _draft_and_reserve(
        tenant_id=tenant_id,
        user_id=user_id,
        customer_id=customer_id,
        product_id=product_id,
        clock=FixedClock(t0),
    )
    t_late = FixedClock(t0 + timedelta(minutes=31))
    barrier = threading.Barrier(2)
    results: list = []

    def one_tick() -> None:
        # Hold at barrier so both try the advisory lock together.
        barrier.wait(timeout=10)
        engine = create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)
        results.append(run_tick(engine=engine, clock=t_late, record_heartbeat=True))

    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(one_tick), pool.submit(one_tick)]
        for f in futs:
            f.result(timeout=60)

    acquired = [r for r in results if r.lock_acquired]
    skipped = [r for r in results if not r.lock_acquired]
    assert len(acquired) == 1
    assert len(skipped) == 1
    assert sum(r.expired_count for r in acquired) >= 1

    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        loaded = OrderRepository(uow.connection).get_order(tenant_id, order.id)
        assert loaded is not None
        assert loaded.status == OrderStatus.EXPIRED
        count = uow.connection.execute(
            text(
                """
                SELECT count(*) FROM platform.outbox
                WHERE tenant_id = :t AND event_type = 'OrderExpired'
                  AND aggregate_id = :oid
                """
            ),
            {"t": str(tenant_id), "oid": str(order.id)},
        ).scalar()
        assert int(count or 0) == 1


def test_advisory_lock_released_after_tick_and_exception() -> None:
    engine = _runtime()
    # Normal tick releases lock.
    run_tick(engine=engine, record_heartbeat=True)
    with engine.connect() as conn:
        assert try_advisory_lock(conn) is True
        assert advisory_unlock(conn) is True

    # Exception mid-tick still unlocks (simulate by forcing list failure after lock).
    from stockpilot.bootstrap import scheduler as sched_mod

    original = sched_mod.ReservationExpiryScheduler.list_active_tenant_ids

    def boom(self):  # noqa: ANN001
        raise RuntimeError("forced")

    sched_mod.ReservationExpiryScheduler.list_active_tenant_ids = boom  # type: ignore[method-assign]
    try:
        with pytest.raises(RuntimeError, match="forced"):
            run_tick(engine=engine, record_heartbeat=False)
    finally:
        sched_mod.ReservationExpiryScheduler.list_active_tenant_ids = original  # type: ignore[method-assign]

    with engine.connect() as conn:
        assert try_advisory_lock(conn) is True
        assert advisory_unlock(conn) is True


def test_scheduler_expire_writes_outbox_without_broker_then_relay_publishes() -> None:
    if not os.environ.get("STOCKPILOT_RELAY_DATABASE_URL") or not os.environ.get(
        "STOCKPILOT_CELERY_BROKER_URL"
    ):
        pytest.skip("Relay/broker URLs not configured")

    tenant_id, user_id, product_id, customer_id = _seed(on_hand=3)
    t0 = datetime(2026, 11, 17, 9, 0, tzinfo=UTC)
    order = _draft_and_reserve(
        tenant_id=tenant_id,
        user_id=user_id,
        customer_id=customer_id,
        product_id=product_id,
        clock=FixedClock(t0),
    )
    result = run_tick(
        engine=_runtime(),
        clock=FixedClock(t0 + timedelta(minutes=31)),
        record_heartbeat=True,
    )
    assert result.lock_acquired is True
    assert result.expired_count >= 1

    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        event_id = uow.connection.execute(
            text(
                """
                SELECT event_id FROM platform.outbox
                WHERE tenant_id = :t AND event_type = 'OrderExpired'
                  AND aggregate_id = :oid
                """
            ),
            {"t": str(tenant_id), "oid": str(order.id)},
        ).scalar_one()
        published = uow.connection.execute(
            text("SELECT published_at FROM platform.outbox WHERE event_id = :id"),
            {"id": str(event_id)},
        ).scalar_one()
    assert published is None

    # Isolate so relay claims this row; publish when broker available.
    with _migrator().begin() as conn:
        conn.execute(
            text(
                """
                UPDATE platform.outbox
                SET lease_owner = 'test-hold',
                    lease_expires_at = now() + interval '1 day'
                WHERE published_at IS NULL AND event_id <> :id
                """
            ),
            {"id": str(event_id)},
        )
        conn.execute(
            text(
                """
                UPDATE platform.outbox
                SET lease_owner = NULL, lease_expires_at = NULL, last_error = NULL
                WHERE event_id = :id
                """
            ),
            {"id": str(event_id)},
        )

    after = None
    deadline = time.time() + 30
    while time.time() < deadline:
        run_once(
            database_url=os.environ["STOCKPILOT_RELAY_DATABASE_URL"],
            broker_url=os.environ["STOCKPILOT_CELERY_BROKER_URL"],
            batch_size=50,
            lease_seconds=30,
        )
        with create_engine(os.environ["STOCKPILOT_RELAY_DATABASE_URL"]).connect() as conn:
            after = conn.execute(
                text("SELECT published_at FROM platform.outbox WHERE event_id = :id"),
                {"id": str(event_id)},
            ).scalar_one()
        if after is not None:
            break
        time.sleep(0.5)
    assert after is not None


def test_heartbeat_updated_after_tick() -> None:
    result = run_tick(engine=_runtime(), record_heartbeat=True)
    assert result.lock_acquired is True
    with _runtime().connect() as conn:
        row = read_heartbeat(conn, "scheduler")
    assert row is not None
    details = row["details"]
    assert "expired_count" in details
    assert "failed_tenant_count" in details
    assert "tenant_count" in details
    assert "unpublished_count" in details


def test_scheduler_healthcheck_stale_and_fresh() -> None:
    url = os.environ["STOCKPILOT_DATABASE_URL"]
    # Ensure a fresh heartbeat exists.
    run_tick(engine=_runtime(), record_heartbeat=True)
    assert health_check(database_url=url, stale_seconds=180) == 0

    # Force stale timestamp via migrator.
    with _migrator().begin() as conn:
        conn.execute(
            text(
                """
                UPDATE platform.heartbeats
                SET last_success_at = now() - interval '10 minutes'
                WHERE service_name = 'scheduler'
                """
            )
        )
    assert health_check(database_url=url, stale_seconds=180) == 1


def test_outbox_lag_for_known_unpublished_set() -> None:
    tenant_id, user_id, _, _ = _seed(on_hand=1)
    # Insert three unpublished rows with known ages via migrator timestamps.
    ids = [uuid4() for _ in range(3)]
    with UnitOfWork(engine=_runtime(), tenant_id=tenant_id, role="admin") as uow:
        for eid in ids:
            enqueue(
                uow.connection,
                tenant_id=tenant_id,
                event_type="OrderCancelled",
                event_version="v1",
                aggregate_type="order",
                aggregate_id=uuid4(),
                payload={"order_id": str(uuid4())},
                event_id=eid,
            )
    with _migrator().begin() as conn:
        conn.execute(
            text(
                """
                UPDATE platform.outbox
                SET created_at = now() - interval '120 seconds'
                WHERE event_id = :id
                """
            ),
            {"id": str(ids[0])},
        )
        conn.execute(
            text(
                """
                UPDATE platform.outbox
                SET created_at = now() - interval '60 seconds'
                WHERE event_id = :id
                """
            ),
            {"id": str(ids[1])},
        )

    with _runtime().connect() as conn:
        # Count only our three? Lag is global — capture before/after delta.
        before_count, _ = fetch_outbox_lag(conn)

    # Re-fetch; our rows are included. Age of oldest among ALL unpublished may be older.
    with _runtime().connect() as conn:
        count, age = fetch_outbox_lag(conn)
    assert count >= before_count
    assert count >= 3
    assert age is not None
    assert age >= 100  # oldest of our set is ~120s; global oldest may be older


def test_scheduler_cannot_select_other_tenant_outbox() -> None:
    tenant_a, user_a, _, _ = _seed(on_hand=1)
    tenant_b, _, _, _ = _seed(on_hand=1)
    event_b = uuid4()
    with UnitOfWork(engine=_runtime(), tenant_id=tenant_b, role="admin") as uow:
        enqueue(
            uow.connection,
            tenant_id=tenant_b,
            event_type="OrderCancelled",
            event_version="v1",
            aggregate_type="order",
            aggregate_id=uuid4(),
            payload={},
            event_id=event_b,
        )

    with UnitOfWork(engine=_runtime(), tenant_id=tenant_a, role=SESSION_ROLE_SCHEDULER) as uow:
        seen = uow.connection.execute(
            text("SELECT event_id FROM platform.outbox WHERE event_id = :id"),
            {"id": str(event_b)},
        ).first()
        assert seen is None
        # Lag function still works without row SELECT.
        count, _age = fetch_outbox_lag(uow.connection)
        assert count >= 1


def test_normal_tenant_session_cannot_write_heartbeat() -> None:
    tenant_id, user_id, _, _ = _seed(on_hand=0)
    with pytest.raises((ProgrammingError, DBAPIError)):
        with UnitOfWork(
            engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin"
        ) as uow:
            upsert_heartbeat(
                uow.connection,
                service_name="scheduler",
                details={"probe": True},
            )


def test_per_tenant_error_isolation() -> None:
    tenant_ok, user_ok, product_ok, customer_ok = _seed(on_hand=3)
    tenant_bad, user_bad, product_bad, customer_bad = _seed(on_hand=3)
    t0 = datetime(2026, 11, 17, 10, 0, tzinfo=UTC)
    order_ok = _draft_and_reserve(
        tenant_id=tenant_ok,
        user_id=user_ok,
        customer_id=customer_ok,
        product_id=product_ok,
        clock=FixedClock(t0),
    )
    order_bad = _draft_and_reserve(
        tenant_id=tenant_bad,
        user_id=user_bad,
        customer_id=customer_bad,
        product_id=product_bad,
        clock=FixedClock(t0),
    )

    from stockpilot.bootstrap.scheduler import ReservationExpiryScheduler

    real_run = ReservationExpiryScheduler.run_for_tenant

    def flaky(self, *, tenant_id: UUID, limit: int = 50):  # noqa: ANN001
        if tenant_id == tenant_bad:
            raise RuntimeError("forced tenant failure")
        return real_run(self, tenant_id=tenant_id, limit=limit)

    ReservationExpiryScheduler.run_for_tenant = flaky  # type: ignore[method-assign]
    try:
        result = run_tick(
            engine=_runtime(),
            clock=FixedClock(t0 + timedelta(minutes=31)),
            record_heartbeat=True,
        )
    finally:
        ReservationExpiryScheduler.run_for_tenant = real_run  # type: ignore[method-assign]

    assert result.lock_acquired is True
    assert result.failed_tenant_count >= 1
    assert result.expired_count >= 1

    with UnitOfWork(engine=_runtime(), user_id=user_ok, tenant_id=tenant_ok, role="admin") as uow:
        loaded_ok = OrderRepository(uow.connection).get_order(tenant_ok, order_ok.id)
        assert loaded_ok is not None
        assert loaded_ok.status == OrderStatus.EXPIRED

    with UnitOfWork(engine=_runtime(), user_id=user_bad, tenant_id=tenant_bad, role="admin") as uow:
        loaded_bad = OrderRepository(uow.connection).get_order(tenant_bad, order_bad.id)
        assert loaded_bad is not None
        assert loaded_bad.status == OrderStatus.RESERVED

    with _runtime().connect() as conn:
        hb = read_heartbeat(conn, "scheduler")
    assert hb is not None
    assert int(hb["details"].get("failed_tenant_count", 0)) >= 1
