"""Inventory integration tests as the runtime DB role."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine

from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.modules.access.domain.models import Role
from stockpilot.modules.catalog.adapters.outbound.repo import CatalogRepository
from stockpilot.modules.inventory.adapters.outbound.repo import InventoryRepository
from stockpilot.modules.inventory.domain.models import StockInvariantViolation
from stockpilot.platform.persistence.uow import UnitOfWork

pytestmark = pytest.mark.skipif(
    not os.environ.get("STOCKPILOT_DATABASE_URL")
    or not os.environ.get("STOCKPILOT_MIGRATION_DATABASE_URL"),
    reason="Database URLs not configured",
)


def _seed_tenant_product(role: Role = Role.WAREHOUSE) -> tuple[object, object, object]:
    migrator = create_engine(os.environ["STOCKPILOT_MIGRATION_DATABASE_URL"], pool_pre_ping=True)
    with UnitOfWork(engine=migrator) as uow:
        access = AccessRepository(uow.connection)
        catalog = CatalogRepository(uow.connection)
        tenant_id = access.ensure_tenant(slug=f"inv-{uuid4().hex[:8]}", name="Inv Org")
        user_id = access.upsert_user(
            issuer="test-issuer",
            subject=f"inv-{uuid4()}",
            email=f"inv-{uuid4().hex}@test",
            display_name="Inv",
        )
        access.ensure_membership(tenant_id=tenant_id, user_id=user_id, role=role)
        product = catalog.create_product(
            tenant_id=tenant_id,
            sku=f"SKU-{uuid4().hex[:6]}",
            title="Test Item",
            unit_price_rial=1000,
        )
    return tenant_id, user_id, product["id"]


def test_ledger_sums_match_counters_after_receipts_and_adjustments() -> None:
    runtime = create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)
    tenant_id, user_id, product_id = _seed_tenant_product()

    with UnitOfWork(engine=runtime, user_id=user_id, tenant_id=tenant_id, role="warehouse") as uow:
        repo = InventoryRepository(uow.connection)
        position = repo.create_position(tenant_id=tenant_id, product_id=product_id)
        position.apply_receipt(20)
        repo.save_position(position)
        repo.insert_movement(
            tenant_id=tenant_id,
            product_id=product_id,
            physical_delta=20,
            reserved_delta=0,
            reason="receipt",
            reference=f"r-{uuid4()}",
            actor_user_id=user_id,
        )
        position.apply_adjustment(-5)
        repo.save_position(position)
        repo.insert_movement(
            tenant_id=tenant_id,
            product_id=product_id,
            physical_delta=-5,
            reserved_delta=0,
            reason="shrink",
            reference=f"a-{uuid4()}",
            actor_user_id=user_id,
        )
        report = repo.balance_report(tenant_id)

    assert len(report) == 1
    assert report[0]["physical_ok"] is True
    assert report[0]["reserved_ok"] is True
    assert report[0]["on_hand"] == 15


def test_adjustment_below_reserved_rejected() -> None:
    runtime = create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)
    tenant_id, user_id, product_id = _seed_tenant_product()

    with UnitOfWork(engine=runtime, user_id=user_id, tenant_id=tenant_id, role="warehouse") as uow:
        repo = InventoryRepository(uow.connection)
        position = repo.create_position(
            tenant_id=tenant_id, product_id=product_id, on_hand=10, reserved=6
        )
        # Keep counters ledger-aligned so shared-dev balance-check stays clean.
        repo.insert_movement(
            tenant_id=tenant_id,
            product_id=product_id,
            physical_delta=10,
            reserved_delta=6,
            reason="fixture reserved stock",
            reference=f"fixture-{uuid4()}",
            actor_user_id=user_id,
        )
        with pytest.raises(StockInvariantViolation):
            position.apply_adjustment(-5)


def test_concurrent_first_receipt_creates_one_position() -> None:
    runtime = create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)
    tenant_id, user_id, product_id = _seed_tenant_product()

    def receive_once(index: int) -> None:
        with UnitOfWork(
            engine=runtime, user_id=user_id, tenant_id=tenant_id, role="warehouse"
        ) as uow:
            repo = InventoryRepository(uow.connection)
            position = repo.ensure_position_for_update(tenant_id=tenant_id, product_id=product_id)
            position.apply_receipt(3)
            repo.save_position(position)
            repo.insert_movement(
                tenant_id=tenant_id,
                product_id=product_id,
                physical_delta=3,
                reserved_delta=0,
                reason="receipt",
                reference=f"concurrent-{index}-{uuid4()}",
                actor_user_id=user_id,
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(receive_once, range(2)))

    with UnitOfWork(engine=runtime, user_id=user_id, tenant_id=tenant_id, role="warehouse") as uow:
        rows = InventoryRepository(uow.connection).list_positions(tenant_id)
    assert len(rows) == 1
    assert int(rows[0]["on_hand"]) == 6


def test_viewer_role_helper_cannot_manage_inventory() -> None:
    from stockpilot.modules.access.domain.models import ActorContext

    actor = ActorContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        role=Role.VIEWER,
        issuer="test",
        subject="viewer",
    )
    assert not actor.can_manage_inventory()
    sales = ActorContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        role=Role.SALES,
        issuer="test",
        subject="sales",
    )
    assert not sales.can_manage_inventory()
