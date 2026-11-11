"""T11 critical order-cycle tests on stockpilot_test (non-removable)."""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text

from stockpilot.bootstrap.scheduler import ReservationExpiryScheduler
from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.modules.access.domain.models import Role
from stockpilot.modules.catalog.adapters.outbound.repo import CatalogRepository
from stockpilot.modules.inventory.adapters.outbound.repo import InventoryRepository
from stockpilot.modules.inventory.public import InsufficientStock, ReservationConflict
from stockpilot.modules.sales.adapters.outbound.customer_repo import CustomerRepository
from stockpilot.modules.sales.adapters.outbound.order_cycle import (
    OrderCycleService,
    OrderNotFound,
    VersionConflict,
)
from stockpilot.modules.sales.adapters.outbound.order_repo import OrderRepository
from stockpilot.modules.sales.domain.order import (
    InvalidOrderState,
    Order,
    OrderLine,
    OrderStatus,
)
from stockpilot.platform.persistence.idempotency import (
    IdempotencyInProgress,
    IdempotencyStore,
    fingerprint,
)
from stockpilot.platform.persistence.retry import retry_on_deadlock
from stockpilot.platform.persistence.uow import UnitOfWork
from stockpilot.platform.time.clock import FixedClock

pytestmark = pytest.mark.skipif(
    not os.environ.get("STOCKPILOT_DATABASE_URL")
    or not os.environ.get("STOCKPILOT_MIGRATION_DATABASE_URL"),
    reason="Database URLs not configured",
)

CONCURRENT_LAST_STOCK_ITERATIONS = 20


def _runtime() -> object:
    return create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)


def _migrator() -> object:
    return create_engine(os.environ["STOCKPILOT_MIGRATION_DATABASE_URL"], pool_pre_ping=True)


def _seed(
    *,
    on_hand: int = 10,
    unit_price_rial: int = 1000,
    sku: str | None = None,
) -> tuple[UUID, UUID, UUID, UUID]:
    with UnitOfWork(engine=_migrator()) as uow:
        access = AccessRepository(uow.connection)
        catalog = CatalogRepository(uow.connection)
        customers = CustomerRepository(uow.connection)
        inventory = InventoryRepository(uow.connection)
        tenant_id = access.ensure_tenant(slug=f"cyc-{uuid4().hex[:8]}", name="Cycle Org")
        user_id = access.upsert_user(
            issuer="test-issuer",
            subject=f"cyc-{uuid4()}",
            email=f"cyc-{uuid4().hex}@test",
            display_name="Cyc",
        )
        access.ensure_membership(tenant_id=tenant_id, user_id=user_id, role=Role.ADMIN)
        product = catalog.create_product(
            tenant_id=tenant_id,
            sku=sku or f"SKU-{uuid4().hex[:6]}",
            title="Cycle Item",
            unit_price_rial=unit_price_rial,
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


def _draft_order(
    *,
    tenant_id: UUID,
    user_id: UUID,
    customer_id: UUID,
    product_id: UUID,
    quantity: int,
    unit_price_rial: int = 1000,
    sku: str = "SKU",
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
                    unit_price_rial=int(snap.get("unit_price_rial") or unit_price_rial),
                )
            ],
        )
        orders.insert_order(order)
        return order


def _position(tenant_id: UUID, user_id: UUID) -> tuple[int, int]:
    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        rows = InventoryRepository(uow.connection).list_positions(tenant_id)
        assert len(rows) == 1
        return int(rows[0]["on_hand"]), int(rows[0]["reserved"])


def _run_concurrent_cycle_last_stock_once() -> None:
    """Two draft orders race for last stock via OrderCycleService.reserve."""
    tenant_id, user_id, product_id, customer_id = _seed(on_hand=10)
    order_a = _draft_order(
        tenant_id=tenant_id,
        user_id=user_id,
        customer_id=customer_id,
        product_id=product_id,
        quantity=7,
    )
    order_b = _draft_order(
        tenant_id=tenant_id,
        user_id=user_id,
        customer_id=customer_id,
        product_id=product_id,
        quantity=7,
    )
    barrier = threading.Barrier(2)
    results: list[str] = []
    lock = threading.Lock()

    def attempt(order: Order) -> None:
        engine = create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)

        def run() -> None:
            with UnitOfWork(
                engine=engine, user_id=user_id, tenant_id=tenant_id, role="admin"
            ) as uow:
                cycle = OrderCycleService(uow.connection)
                barrier.wait(timeout=10)
                cycle.reserve(
                    tenant_id=tenant_id,
                    order_id=order.id,
                    actor_user_id=user_id,
                    expected_version=order.version,
                )

        try:
            retry_on_deadlock(run)
            with lock:
                results.append("ok")
        except InsufficientStock:
            with lock:
                results.append("short")

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(attempt, [order_a, order_b]))

    assert results.count("ok") == 1, results
    assert results.count("short") == 1, results
    on_hand, reserved = _position(tenant_id, user_id)
    assert on_hand == 10
    assert reserved == 7


def test_concurrent_last_stock_order_cycle_only_one_succeeds() -> None:
    for iteration in range(CONCURRENT_LAST_STOCK_ITERATIONS):
        try:
            _run_concurrent_cycle_last_stock_once()
        except AssertionError as exc:
            raise AssertionError(
                f"order-cycle concurrent last-stock failed on iteration "
                f"{iteration + 1}/{CONCURRENT_LAST_STOCK_ITERATIONS}"
            ) from exc


def test_multiline_shortfall_via_cycle_reserves_nothing() -> None:
    tenant_id, user_id, product_id, customer_id = _seed(on_hand=3)
    with UnitOfWork(engine=_migrator()) as uow:
        catalog = CatalogRepository(uow.connection)
        inventory = InventoryRepository(uow.connection)
        other = catalog.create_product(
            tenant_id=tenant_id,
            sku=f"SKU-B-{uuid4().hex[:4]}",
            title="B",
            unit_price_rial=500,
        )
        other_id = UUID(str(other["id"]))
        pos = inventory.ensure_position_for_update(tenant_id=tenant_id, product_id=other_id)
        pos.apply_receipt(1)
        inventory.save_position(pos)
        inventory.insert_movement(
            tenant_id=tenant_id,
            product_id=other_id,
            physical_delta=1,
            reserved_delta=0,
            reason="seed",
            reference=f"seed-{uuid4()}",
            actor_user_id=user_id,
        )

    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        orders = OrderRepository(uow.connection)
        snap_a = orders.get_product_snapshot(tenant_id, product_id)
        snap_b = orders.get_product_snapshot(tenant_id, other_id)
        assert snap_a and snap_b
        order = Order.new_draft(
            tenant_id=tenant_id,
            customer_id=customer_id,
            lines=[
                OrderLine(
                    id=uuid4(),
                    product_id=product_id,
                    quantity=5,
                    product_sku=str(snap_a["sku"]),
                    product_title=str(snap_a["title"]),
                    unit_price_rial=int(snap_a["unit_price_rial"]),
                ),
                OrderLine(
                    id=uuid4(),
                    product_id=other_id,
                    quantity=2,
                    product_sku=str(snap_b["sku"]),
                    product_title=str(snap_b["title"]),
                    unit_price_rial=int(snap_b["unit_price_rial"]),
                ),
            ],
        )
        orders.insert_order(order)
        order_id = order.id
        version = order.version

    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        cycle = OrderCycleService(uow.connection)
        with pytest.raises(InsufficientStock) as excinfo:
            cycle.reserve(
                tenant_id=tenant_id,
                order_id=order_id,
                actor_user_id=user_id,
                expected_version=version,
            )
        assert len(excinfo.value.shortfalls) >= 1

    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        loaded = OrderRepository(uow.connection).get_order(tenant_id, order_id)
        assert loaded is not None
        assert loaded.status == OrderStatus.DRAFT
        rsv = uow.connection.execute(
            text("SELECT count(*) FROM inventory.reservations WHERE tenant_id = :t"),
            {"t": str(tenant_id)},
        ).scalar()
        assert int(rsv or 0) == 0
        for row in InventoryRepository(uow.connection).list_positions(tenant_id):
            assert int(row["reserved"]) == 0


def test_idempotent_replay_same_key_no_double_reserve() -> None:
    tenant_id, user_id, product_id, customer_id = _seed(on_hand=5)
    order = _draft_order(
        tenant_id=tenant_id,
        user_id=user_id,
        customer_id=customer_id,
        product_id=product_id,
        quantity=2,
    )
    key = f"idem-{uuid4()}"
    path = f"/api/v1/tenants/{tenant_id}/orders/{order.id}/reserve"
    body = {"expected_version": order.version}
    fp = fingerprint(method="POST", path=path, contract_version="v1", body=body)

    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        store = IdempotencyStore(uow.connection)
        assert (
            store.begin(
                tenant_id=tenant_id,
                user_id=user_id,
                operation="orders.reserve",
                key=key,
                fp=fp,
            )
            is None
        )
        result = OrderCycleService(uow.connection).reserve(
            tenant_id=tenant_id,
            order_id=order.id,
            actor_user_id=user_id,
            expected_version=order.version,
        )
        payload = {
            "id": str(result.order.id),
            "status": result.order.status.value,
            "version": result.order.version,
        }
        from stockpilot.platform.persistence.idempotency import StoredResponse

        store.complete(
            tenant_id=tenant_id,
            user_id=user_id,
            operation="orders.reserve",
            key=key,
            response=StoredResponse(status=200, body=payload, headers={}),
        )
        first_version = result.order.version

    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        store = IdempotencyStore(uow.connection)
        prior = store.begin(
            tenant_id=tenant_id,
            user_id=user_id,
            operation="orders.reserve",
            key=key,
            fp=fp,
        )
        assert prior is not None
        assert prior.status == 200
        assert prior.body["version"] == first_version
        _, reserved = _position(tenant_id, user_id)
    assert reserved == 2


def test_concurrent_same_idempotency_key_retry_after_no_double_apply() -> None:
    tenant_id, user_id, product_id, customer_id = _seed(on_hand=5)
    order = _draft_order(
        tenant_id=tenant_id,
        user_id=user_id,
        customer_id=customer_id,
        product_id=product_id,
        quantity=1,
    )
    key = f"race-key-{uuid4()}"
    path = f"/api/v1/tenants/{tenant_id}/orders/{order.id}/reserve"
    body = {"expected_version": order.version}
    fp = fingerprint(method="POST", path=path, contract_version="v1", body=body)
    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    lock = threading.Lock()
    hold = threading.Event()

    def first() -> None:
        engine = create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)
        with UnitOfWork(engine=engine, user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
            store = IdempotencyStore(uow.connection)
            assert (
                store.begin(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    operation="orders.reserve",
                    key=key,
                    fp=fp,
                    wait_seconds=0.05,
                )
                is None
            )
            barrier.wait(timeout=10)
            result = OrderCycleService(uow.connection).reserve(
                tenant_id=tenant_id,
                order_id=order.id,
                actor_user_id=user_id,
                expected_version=order.version,
            )
            from stockpilot.platform.persistence.idempotency import StoredResponse

            store.complete(
                tenant_id=tenant_id,
                user_id=user_id,
                operation="orders.reserve",
                key=key,
                response=StoredResponse(
                    status=200,
                    body={"id": str(result.order.id), "status": result.order.status.value},
                    headers={},
                ),
            )
            # Hold the open txn (and unique-index lock) until peer times out.
            hold.wait(timeout=10)
            with lock:
                outcomes.append("first_ok")

    def second() -> None:
        engine = create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)
        barrier.wait(timeout=10)
        # Peer still holds the uncommitted claim → lock_timeout → Retry-After.
        try:
            with UnitOfWork(
                engine=engine, user_id=user_id, tenant_id=tenant_id, role="admin"
            ) as uow:
                store = IdempotencyStore(uow.connection)
                store.begin(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    operation="orders.reserve",
                    key=key,
                    fp=fp,
                    wait_seconds=0.2,
                )
                with lock:
                    outcomes.append("second_unexpected")
        except IdempotencyInProgress as exc:
            assert exc.retry_after >= 1
            with lock:
                outcomes.append("retry_after")
        finally:
            hold.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(first)
        f2 = pool.submit(second)
        f1.result(timeout=30)
        f2.result(timeout=30)

    assert "first_ok" in outcomes
    assert "retry_after" in outcomes
    assert "second_unexpected" not in outcomes
    _, reserved = _position(tenant_id, user_id)
    assert reserved == 1
    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        count = uow.connection.execute(
            text("SELECT count(*) FROM inventory.reservations WHERE tenant_id = :t"),
            {"t": str(tenant_id)},
        ).scalar()
        assert int(count or 0) == 1


def test_second_cancel_does_not_increase_stock() -> None:
    tenant_id, user_id, product_id, customer_id = _seed(on_hand=8)
    order = _draft_order(
        tenant_id=tenant_id,
        user_id=user_id,
        customer_id=customer_id,
        product_id=product_id,
        quantity=3,
    )
    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        cycle = OrderCycleService(uow.connection)
        reserved = cycle.reserve(
            tenant_id=tenant_id,
            order_id=order.id,
            actor_user_id=user_id,
            expected_version=order.version,
        ).order
        cancelled = cycle.cancel(
            tenant_id=tenant_id,
            order_id=order.id,
            actor_user_id=user_id,
            expected_version=reserved.version,
        ).order
    on_hand, reserved_qty = _position(tenant_id, user_id)
    assert reserved_qty == 0
    assert on_hand == 8

    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        cycle = OrderCycleService(uow.connection)
        again = cycle.cancel(
            tenant_id=tenant_id,
            order_id=order.id,
            actor_user_id=user_id,
            expected_version=cancelled.version,
        ).order
        assert again.status == OrderStatus.CANCELLED
    _, reserved_qty2 = _position(tenant_id, user_id)
    assert reserved_qty2 == 0


def test_confirm_after_expiry_commits_expiry_and_returns_409() -> None:
    tenant_id, user_id, product_id, customer_id = _seed(on_hand=4)
    order = _draft_order(
        tenant_id=tenant_id,
        user_id=user_id,
        customer_id=customer_id,
        product_id=product_id,
        quantity=1,
    )
    t0 = datetime(2026, 11, 11, 10, 0, tzinfo=UTC)
    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        cycle = OrderCycleService(uow.connection, clock=FixedClock(t0))
        reserved = cycle.reserve(
            tenant_id=tenant_id,
            order_id=order.id,
            actor_user_id=user_id,
            expected_version=order.version,
        ).order
        assert reserved.expires_at is not None

    t_expired = reserved.expires_at + timedelta(seconds=1)
    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        cycle = OrderCycleService(uow.connection, clock=FixedClock(t_expired))
        result = cycle.confirm(
            tenant_id=tenant_id,
            order_id=order.id,
            actor_user_id=user_id,
            expected_version=reserved.version,
        )
        assert result.http_status == 409
        assert result.problem_code == "RESERVATION_EXPIRED"
        assert result.order.status == OrderStatus.EXPIRED

    _, reserved_qty = _position(tenant_id, user_id)
    assert reserved_qty == 0
    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        loaded = OrderRepository(uow.connection).get_order(tenant_id, order.id)
        assert loaded is not None
        assert loaded.status == OrderStatus.EXPIRED
        outbox = uow.connection.execute(
            text(
                "SELECT count(*) FROM platform.outbox "
                "WHERE tenant_id = :t AND event_type = 'OrderExpired'"
            ),
            {"t": str(tenant_id)},
        ).scalar()
        assert int(outbox or 0) == 1


def test_expire_vs_confirm_race() -> None:
    tenant_id, user_id, product_id, customer_id = _seed(on_hand=5)
    order = _draft_order(
        tenant_id=tenant_id,
        user_id=user_id,
        customer_id=customer_id,
        product_id=product_id,
        quantity=2,
    )
    t0 = datetime(2026, 11, 11, 9, 0, tzinfo=UTC)
    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        reserved = (
            OrderCycleService(uow.connection, clock=FixedClock(t0))
            .reserve(
                tenant_id=tenant_id,
                order_id=order.id,
                actor_user_id=user_id,
                expected_version=order.version,
            )
            .order
        )
    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    lock = threading.Lock()
    t_late = t0 + timedelta(minutes=31)

    def do_confirm() -> None:
        engine = create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)

        def run() -> None:
            with UnitOfWork(
                engine=engine, user_id=user_id, tenant_id=tenant_id, role="admin"
            ) as uow:
                cycle = OrderCycleService(uow.connection, clock=FixedClock(t_late))
                barrier.wait(timeout=10)
                result = cycle.confirm(
                    tenant_id=tenant_id,
                    order_id=order.id,
                    actor_user_id=user_id,
                    expected_version=reserved.version,
                )
                with lock:
                    if result.problem_code == "RESERVATION_EXPIRED":
                        outcomes.append("confirm_expired")
                    elif result.order.status == OrderStatus.CONFIRMED:
                        outcomes.append("confirmed")
                    else:
                        outcomes.append(f"confirm_{result.order.status.value}")

        try:
            retry_on_deadlock(run)
        except (ReservationConflict, OrderNotFound, VersionConflict, InvalidOrderState) as exc:
            with lock:
                outcomes.append(f"confirm_err:{type(exc).__name__}")

    def do_expire() -> None:
        engine = create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)

        def run() -> None:
            with UnitOfWork(
                engine=engine, user_id=user_id, tenant_id=tenant_id, role="admin"
            ) as uow:
                cycle = OrderCycleService(uow.connection, clock=FixedClock(t_late))
                barrier.wait(timeout=10)
                result = cycle.expire(tenant_id=tenant_id, order_id=order.id, actor_user_id=user_id)
                with lock:
                    outcomes.append(f"expire_{result.order.status.value}")

        try:
            retry_on_deadlock(run)
        except (ReservationConflict, OrderNotFound, VersionConflict, InvalidOrderState) as exc:
            with lock:
                outcomes.append(f"expire_err:{type(exc).__name__}")

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda fn: fn(), [do_confirm, do_expire]))

    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        loaded = OrderRepository(uow.connection).get_order(tenant_id, order.id)
        assert loaded is not None
        assert loaded.status in {OrderStatus.EXPIRED, OrderStatus.CONFIRMED}
        # Confirm-at-expiry path expires rather than confirming.
        if any(o.startswith("confirm_expired") or o.startswith("expire_EXPIRED") for o in outcomes):
            assert loaded.status == OrderStatus.EXPIRED
        _, reserved_qty = _position(tenant_id, user_id)
        if loaded.status == OrderStatus.EXPIRED:
            assert reserved_qty == 0
        else:
            assert reserved_qty == 2


def test_cancel_vs_ship_race() -> None:
    tenant_id, user_id, product_id, customer_id = _seed(on_hand=6)
    order = _draft_order(
        tenant_id=tenant_id,
        user_id=user_id,
        customer_id=customer_id,
        product_id=product_id,
        quantity=2,
    )
    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        cycle = OrderCycleService(uow.connection)
        reserved = cycle.reserve(
            tenant_id=tenant_id,
            order_id=order.id,
            actor_user_id=user_id,
            expected_version=order.version,
        ).order
        confirmed = cycle.confirm(
            tenant_id=tenant_id,
            order_id=order.id,
            actor_user_id=user_id,
            expected_version=reserved.version,
        ).order

    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    lock = threading.Lock()

    def do_cancel() -> None:
        engine = create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)

        def run() -> None:
            with UnitOfWork(
                engine=engine, user_id=user_id, tenant_id=tenant_id, role="admin"
            ) as uow:
                cycle = OrderCycleService(uow.connection)
                barrier.wait(timeout=10)
                result = cycle.cancel(
                    tenant_id=tenant_id,
                    order_id=order.id,
                    actor_user_id=user_id,
                    expected_version=confirmed.version,
                )
                with lock:
                    outcomes.append(f"cancel_{result.order.status.value}")

        try:
            retry_on_deadlock(run)
        except Exception as exc:  # noqa: BLE001 — race outcomes recorded
            with lock:
                outcomes.append(f"cancel_err:{type(exc).__name__}")

    def do_ship() -> None:
        engine = create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)

        def run() -> None:
            with UnitOfWork(
                engine=engine, user_id=user_id, tenant_id=tenant_id, role="admin"
            ) as uow:
                cycle = OrderCycleService(uow.connection)
                barrier.wait(timeout=10)
                result = cycle.ship(
                    tenant_id=tenant_id,
                    order_id=order.id,
                    actor_user_id=user_id,
                    expected_version=confirmed.version,
                )
                with lock:
                    outcomes.append(f"ship_{result.order.status.value}")

        try:
            retry_on_deadlock(run)
        except Exception as exc:  # noqa: BLE001 — race outcomes recorded
            with lock:
                outcomes.append(f"ship_err:{type(exc).__name__}")

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda fn: fn(), [do_cancel, do_ship]))

    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        loaded = OrderRepository(uow.connection).get_order(tenant_id, order.id)
        assert loaded is not None
        assert loaded.status in {OrderStatus.CANCELLED, OrderStatus.SHIPPED}
        on_hand, reserved_qty = _position(tenant_id, user_id)
        assert reserved_qty == 0
        if loaded.status == OrderStatus.SHIPPED:
            assert on_hand == 4
        else:
            assert on_hand == 6
    assert any(o.startswith("cancel_") or o.startswith("ship_") for o in outcomes)


def test_price_change_during_reserve_freezes_locked_price() -> None:
    tenant_id, user_id, product_id, customer_id = _seed(on_hand=5, unit_price_rial=1000)
    order = _draft_order(
        tenant_id=tenant_id,
        user_id=user_id,
        customer_id=customer_id,
        product_id=product_id,
        quantity=1,
        unit_price_rial=1000,
    )
    barrier = threading.Barrier(2)
    frozen: list[int] = []
    updated: list[int] = []

    def do_reserve() -> None:
        engine = create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)
        with UnitOfWork(engine=engine, user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
            cycle = OrderCycleService(uow.connection)
            barrier.wait(timeout=10)
            result = cycle.reserve(
                tenant_id=tenant_id,
                order_id=order.id,
                actor_user_id=user_id,
                expected_version=order.version,
            )
            frozen.append(result.order.lines[0].unit_price_rial)

    def do_price_update() -> None:
        engine = create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)
        with UnitOfWork(engine=engine, user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
            catalog = CatalogRepository(uow.connection)
            current = catalog.get_product(tenant_id, product_id)
            assert current is not None
            barrier.wait(timeout=10)
            # Brief pause so reserve can take the product lock first when scheduling allows.
            time.sleep(0.05)
            row = catalog.update_product(
                tenant_id=tenant_id,
                product_id=product_id,
                expected_version=int(current["version"]),
                title=None,
                unit_price_rial=2500,
                is_active=None,
                stock_warning_threshold=None,
            )
            assert row is not None
            assert "__conflict__" not in row
            updated.append(int(row["unit_price_rial"]))

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda fn: fn(), [do_reserve, do_price_update]))

    assert frozen and updated
    assert frozen[0] in {1000, 2500}
    assert updated[0] == 2500
    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        loaded = OrderRepository(uow.connection).get_order(tenant_id, order.id)
        assert loaded is not None
        assert loaded.status == OrderStatus.RESERVED
        assert loaded.lines[0].unit_price_rial == frozen[0]


def test_cross_tenant_order_request_not_found() -> None:
    tenant_a, user_a, product_id, customer_id = _seed(on_hand=3)
    order = _draft_order(
        tenant_id=tenant_a,
        user_id=user_a,
        customer_id=customer_id,
        product_id=product_id,
        quantity=1,
    )
    tenant_b, user_b, _, _ = _seed(on_hand=1)
    with UnitOfWork(engine=_runtime(), user_id=user_b, tenant_id=tenant_b, role="admin") as uow:
        cycle = OrderCycleService(uow.connection)
        with pytest.raises(OrderNotFound):
            cycle.reserve(
                tenant_id=tenant_b,
                order_id=order.id,
                actor_user_id=user_b,
                expected_version=order.version,
            )


def test_rollback_when_outbox_write_fails() -> None:
    tenant_id, user_id, product_id, customer_id = _seed(on_hand=5)
    order = _draft_order(
        tenant_id=tenant_id,
        user_id=user_id,
        customer_id=customer_id,
        product_id=product_id,
        quantity=2,
    )

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("outbox failed")

    import stockpilot.modules.sales.adapters.outbound.order_cycle as cycle_mod

    original = cycle_mod.enqueue
    cycle_mod.enqueue = boom  # type: ignore[assignment]
    try:
        # Exception must escape the UoW so the transaction rolls back.
        with pytest.raises(RuntimeError, match="outbox failed"):
            with UnitOfWork(
                engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin"
            ) as uow:
                OrderCycleService(uow.connection).reserve(
                    tenant_id=tenant_id,
                    order_id=order.id,
                    actor_user_id=user_id,
                    expected_version=order.version,
                )
    finally:
        cycle_mod.enqueue = original  # type: ignore[assignment]

    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        loaded = OrderRepository(uow.connection).get_order(tenant_id, order.id)
        assert loaded is not None
        assert loaded.status == OrderStatus.DRAFT
        _, reserved = _position(tenant_id, user_id)
        assert reserved == 0
        rsv = uow.connection.execute(
            text("SELECT count(*) FROM inventory.reservations WHERE tenant_id = :t"),
            {"t": str(tenant_id)},
        ).scalar()
        assert int(rsv or 0) == 0


def test_scheduler_expire_uses_tenant_local_context() -> None:
    tenant_id, user_id, product_id, customer_id = _seed(on_hand=4)
    order = _draft_order(
        tenant_id=tenant_id,
        user_id=user_id,
        customer_id=customer_id,
        product_id=product_id,
        quantity=1,
    )
    t0 = datetime(2026, 11, 11, 8, 0, tzinfo=UTC)
    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        reserved = (
            OrderCycleService(uow.connection, clock=FixedClock(t0))
            .reserve(
                tenant_id=tenant_id,
                order_id=order.id,
                actor_user_id=user_id,
                expected_version=order.version,
            )
            .order
        )

    t_late = t0 + timedelta(minutes=31)
    scheduler = ReservationExpiryScheduler(
        engine=_runtime(),  # type: ignore[arg-type]
        clock=FixedClock(t_late),
        runtime_user_id=user_id,
    )
    result = scheduler.run_for_tenant(tenant_id=tenant_id, limit=10)
    assert result.expired == 1
    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        loaded = OrderRepository(uow.connection).get_order(tenant_id, order.id)
        assert loaded is not None
        assert loaded.status == OrderStatus.EXPIRED
        assert loaded.version == reserved.version + 1
    _, reserved_qty = _position(tenant_id, user_id)
    assert reserved_qty == 0
