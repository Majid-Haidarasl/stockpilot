"""Critical reservation concurrency tests on real PostgreSQL (non-removable)."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.modules.access.domain.models import Role
from stockpilot.modules.catalog.adapters.outbound.repo import CatalogRepository
from stockpilot.modules.inventory.adapters.outbound.commands import SqlInventoryCommands
from stockpilot.modules.inventory.adapters.outbound.repo import InventoryRepository
from stockpilot.modules.inventory.public import (
    InactiveProduct,
    InsufficientStock,
    RequestedStock,
    ReserveStock,
)
from stockpilot.platform.persistence.retry import retry_on_deadlock
from stockpilot.platform.persistence.uow import UnitOfWork

# These tests require Compose backend-checks env (stockpilot_test). Do not skip when present.
pytestmark = pytest.mark.skipif(
    not os.environ.get("STOCKPILOT_DATABASE_URL")
    or not os.environ.get("STOCKPILOT_MIGRATION_DATABASE_URL"),
    reason="Database URLs not configured",
)

CONCURRENT_LAST_STOCK_ITERATIONS = 20


def _seed_tenant_with_stock(
    *,
    products: list[tuple[str, int]],
    product_active: bool = True,
) -> tuple[UUID, UUID, dict[str, UUID]]:
    migrator = create_engine(os.environ["STOCKPILOT_MIGRATION_DATABASE_URL"], pool_pre_ping=True)
    with UnitOfWork(engine=migrator) as uow:
        access = AccessRepository(uow.connection)
        catalog = CatalogRepository(uow.connection)
        inventory = InventoryRepository(uow.connection)
        tenant_id = access.ensure_tenant(slug=f"rsv-{uuid4().hex[:8]}", name="Reserve Org")
        user_id = access.upsert_user(
            issuer="test-issuer",
            subject=f"rsv-{uuid4()}",
            email=f"rsv-{uuid4().hex}@test",
            display_name="Rsv",
        )
        access.ensure_membership(tenant_id=tenant_id, user_id=user_id, role=Role.SALES)
        product_ids: dict[str, UUID] = {}
        for sku, on_hand in products:
            product = catalog.create_product(
                tenant_id=tenant_id,
                sku=sku,
                title=sku,
                unit_price_rial=1000,
                is_active=product_active,
            )
            product_id = UUID(str(product["id"]))
            product_ids[sku] = product_id
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
                    reference=f"seed-{sku}-{uuid4()}",
                    actor_user_id=user_id,
                )
    return tenant_id, user_id, product_ids


def _run_concurrent_last_stock_once() -> None:
    """Two independent connections race for last stock; exactly one wins."""
    tenant_id, user_id, products = _seed_tenant_with_stock(products=[("SKU-LAST", 10)])
    product_id = products["SKU-LAST"]
    barrier = threading.Barrier(2)
    results: list[str] = []
    lock = threading.Lock()

    def attempt(order_id: UUID) -> None:
        engine = create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)

        def run() -> None:
            with UnitOfWork(
                engine=engine, user_id=user_id, tenant_id=tenant_id, role="sales"
            ) as uow:
                cmds = SqlInventoryCommands(uow.connection)
                barrier.wait(timeout=10)
                cmds.reserve_all(
                    ReserveStock(
                        tenant_id=tenant_id,
                        order_id=order_id,
                        actor_user_id=user_id,
                        items=(
                            RequestedStock(
                                product_id=product_id,
                                quantity=7,
                                sku="SKU-LAST",
                                is_active=True,
                            ),
                        ),
                    )
                )

        try:
            retry_on_deadlock(run)
            with lock:
                results.append("ok")
        except InsufficientStock:
            with lock:
                results.append("short")

    order_a, order_b = uuid4(), uuid4()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(attempt, [order_a, order_b]))

    assert results.count("ok") == 1, results
    assert results.count("short") == 1, results

    runtime = create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)
    with UnitOfWork(engine=runtime, user_id=user_id, tenant_id=tenant_id, role="sales") as uow:
        positions = InventoryRepository(uow.connection).list_positions(tenant_id)
        assert len(positions) == 1
        on_hand = int(positions[0]["on_hand"])
        reserved = int(positions[0]["reserved"])
        assert on_hand == 10
        assert reserved == 7
        assert reserved <= on_hand
        assert on_hand - reserved >= 0
        report = InventoryRepository(uow.connection).balance_report(tenant_id)
        assert report[0]["physical_ok"] and report[0]["reserved_ok"]
        assert report[0]["reservation_ok"]


def test_concurrent_last_stock_reserve_only_one_succeeds() -> None:
    """Non-removable: repeat the race so a single lucky pass is not enough."""
    for iteration in range(CONCURRENT_LAST_STOCK_ITERATIONS):
        try:
            _run_concurrent_last_stock_once()
        except AssertionError as exc:
            raise AssertionError(
                f"concurrent last-stock failed on iteration "
                f"{iteration + 1}/{CONCURRENT_LAST_STOCK_ITERATIONS}"
            ) from exc


def test_multiline_shortfall_reserves_nothing() -> None:
    """Non-removable: one short line means no line is reserved."""
    tenant_id, user_id, products = _seed_tenant_with_stock(
        products=[("SKU-OK", 10), ("SKU-SHORT", 2)]
    )
    runtime = create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)
    order_id = uuid4()

    with UnitOfWork(engine=runtime, user_id=user_id, tenant_id=tenant_id, role="sales") as uow:
        cmds = SqlInventoryCommands(uow.connection)
        with pytest.raises(InsufficientStock) as excinfo:
            cmds.reserve_all(
                ReserveStock(
                    tenant_id=tenant_id,
                    order_id=order_id,
                    actor_user_id=user_id,
                    items=(
                        RequestedStock(
                            product_id=products["SKU-OK"],
                            quantity=5,
                            sku="SKU-OK",
                            is_active=True,
                        ),
                        RequestedStock(
                            product_id=products["SKU-SHORT"],
                            quantity=5,
                            sku="SKU-SHORT",
                            is_active=True,
                        ),
                    ),
                )
            )
        assert any(s.sku == "SKU-SHORT" for s in excinfo.value.shortfalls)

    with UnitOfWork(engine=runtime, user_id=user_id, tenant_id=tenant_id, role="sales") as uow:
        repo = InventoryRepository(uow.connection)
        assert repo.count_reservations_for_order(tenant_id, order_id) == 0
        positions = {p["sku"]: p for p in repo.list_positions(tenant_id)}
        assert int(positions["SKU-OK"]["on_hand"]) == 10
        assert int(positions["SKU-OK"]["reserved"]) == 0
        assert int(positions["SKU-SHORT"]["on_hand"]) == 2
        assert int(positions["SKU-SHORT"]["reserved"]) == 0


def test_inactive_product_reserve_rejected_with_no_writes() -> None:
    """Reserving an inactive product fails before any stock/reservation writes."""
    tenant_id, user_id, products = _seed_tenant_with_stock(
        products=[("SKU-OFF", 10)],
        product_active=False,
    )
    runtime = create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)
    order_id = uuid4()

    with UnitOfWork(engine=runtime, user_id=user_id, tenant_id=tenant_id, role="sales") as uow:
        cmds = SqlInventoryCommands(uow.connection)
        with pytest.raises(InactiveProduct):
            cmds.reserve_all(
                ReserveStock(
                    tenant_id=tenant_id,
                    order_id=order_id,
                    actor_user_id=user_id,
                    items=(
                        RequestedStock(
                            product_id=products["SKU-OFF"],
                            quantity=3,
                            sku="SKU-OFF",
                            is_active=False,
                        ),
                    ),
                )
            )

    with UnitOfWork(engine=runtime, user_id=user_id, tenant_id=tenant_id, role="sales") as uow:
        repo = InventoryRepository(uow.connection)
        assert repo.count_reservations_for_order(tenant_id, order_id) == 0
        positions = repo.list_positions(tenant_id)
        assert int(positions[0]["on_hand"]) == 10
        assert int(positions[0]["reserved"]) == 0
        mov_count = uow.connection.execute(
            text(
                "SELECT count(*) FROM inventory.movements "
                "WHERE tenant_id = :t AND reason = 'reserve'"
            ),
            {"t": str(tenant_id)},
        ).scalar()
        assert int(mov_count or 0) == 0


def test_held_reservation_matches_reserved_counter() -> None:
    tenant_id, user_id, products = _seed_tenant_with_stock(products=[("SKU-BAL", 8)])
    runtime = create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)
    order_id = uuid4()

    with UnitOfWork(engine=runtime, user_id=user_id, tenant_id=tenant_id, role="sales") as uow:
        cmds = SqlInventoryCommands(uow.connection)
        reservation_id = cmds.reserve_all(
            ReserveStock(
                tenant_id=tenant_id,
                order_id=order_id,
                actor_user_id=user_id,
                items=(
                    RequestedStock(
                        product_id=products["SKU-BAL"],
                        quantity=3,
                        sku="SKU-BAL",
                        is_active=True,
                    ),
                ),
            )
        )
        report = InventoryRepository(uow.connection).balance_report(tenant_id)
        assert report[0]["reservation_ok"] is True
        assert report[0]["reserved"] == 3
        assert reservation_id is not None


def test_duplicate_order_reservation_rejected_without_double_apply() -> None:
    tenant_id, user_id, products = _seed_tenant_with_stock(products=[("SKU-DUP", 10)])
    runtime = create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)
    order_id = uuid4()

    with UnitOfWork(engine=runtime, user_id=user_id, tenant_id=tenant_id, role="sales") as uow:
        cmds = SqlInventoryCommands(uow.connection)
        cmds.reserve_all(
            ReserveStock(
                tenant_id=tenant_id,
                order_id=order_id,
                actor_user_id=user_id,
                items=(
                    RequestedStock(
                        product_id=products["SKU-DUP"],
                        quantity=4,
                        sku="SKU-DUP",
                        is_active=True,
                    ),
                ),
            )
        )

    with UnitOfWork(engine=runtime, user_id=user_id, tenant_id=tenant_id, role="sales") as uow:
        cmds = SqlInventoryCommands(uow.connection)
        with pytest.raises(IntegrityError):
            cmds.reserve_all(
                ReserveStock(
                    tenant_id=tenant_id,
                    order_id=order_id,
                    actor_user_id=user_id,
                    items=(
                        RequestedStock(
                            product_id=products["SKU-DUP"],
                            quantity=4,
                            sku="SKU-DUP",
                            is_active=True,
                        ),
                    ),
                )
            )

    with UnitOfWork(engine=runtime, user_id=user_id, tenant_id=tenant_id, role="sales") as uow:
        repo = InventoryRepository(uow.connection)
        assert repo.count_reservations_for_order(tenant_id, order_id) == 1
        positions = repo.list_positions(tenant_id)
        assert int(positions[0]["reserved"]) == 4
        mov_count = uow.connection.execute(
            text(
                "SELECT count(*) FROM inventory.movements "
                "WHERE tenant_id = :t AND reason = 'reserve'"
            ),
            {"t": str(tenant_id)},
        ).scalar()
        assert int(mov_count or 0) == 1
