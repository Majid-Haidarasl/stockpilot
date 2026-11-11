"""Draft order API/repo integration on stockpilot_test (no inventory wiring)."""

from __future__ import annotations

import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text

from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.modules.access.domain.models import ActorContext, Role
from stockpilot.modules.catalog.adapters.outbound.repo import CatalogRepository
from stockpilot.modules.sales.adapters.outbound.customer_repo import CustomerRepository
from stockpilot.modules.sales.adapters.outbound.order_repo import OrderRepository
from stockpilot.modules.sales.domain.order import Order, OrderLine, OrderStatus
from stockpilot.platform.persistence.uow import UnitOfWork

pytestmark = pytest.mark.skipif(
    not os.environ.get("STOCKPILOT_DATABASE_URL")
    or not os.environ.get("STOCKPILOT_MIGRATION_DATABASE_URL"),
    reason="Database URLs not configured",
)


def _seed() -> tuple[UUID, UUID, UUID, UUID]:
    migrator = create_engine(os.environ["STOCKPILOT_MIGRATION_DATABASE_URL"], pool_pre_ping=True)
    with UnitOfWork(engine=migrator) as uow:
        access = AccessRepository(uow.connection)
        catalog = CatalogRepository(uow.connection)
        customers = CustomerRepository(uow.connection)
        tenant_id = access.ensure_tenant(slug=f"ord-{uuid4().hex[:8]}", name="Order Org")
        user_id = access.upsert_user(
            issuer="test-issuer",
            subject=f"ord-{uuid4()}",
            email=f"ord-{uuid4().hex}@test",
            display_name="Ord",
        )
        access.ensure_membership(tenant_id=tenant_id, user_id=user_id, role=Role.SALES)
        product = catalog.create_product(
            tenant_id=tenant_id,
            sku=f"SKU-{uuid4().hex[:6]}",
            title="Order Item",
            unit_price_rial=1500,
        )
        customer = customers.create_customer(
            tenant_id=tenant_id, name="Buyer", phone=None, email=None, notes=None
        )
    return tenant_id, user_id, UUID(str(product["id"])), UUID(str(customer["id"]))


def test_draft_create_and_patch_without_inventory_side_effects() -> None:
    tenant_id, user_id, product_id, customer_id = _seed()
    runtime = create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)

    with UnitOfWork(engine=runtime, user_id=user_id, tenant_id=tenant_id, role="sales") as uow:
        repo = OrderRepository(uow.connection)
        snap = repo.get_product_snapshot(tenant_id, product_id)
        assert snap is not None
        order = Order.new_draft(
            tenant_id=tenant_id,
            customer_id=customer_id,
            lines=[
                OrderLine(
                    id=uuid4(),
                    product_id=product_id,
                    quantity=2,
                    product_sku=str(snap["sku"]),
                    product_title=str(snap["title"]),
                    unit_price_rial=int(snap["unit_price_rial"]),
                )
            ],
        )
        repo.insert_order(order)
        order_id = order.id

    with UnitOfWork(engine=runtime, user_id=user_id, tenant_id=tenant_id, role="sales") as uow:
        repo = OrderRepository(uow.connection)
        loaded = repo.get_order(tenant_id, order_id)
        assert loaded is not None
        assert loaded.status == OrderStatus.DRAFT
        assert loaded.total().amount == 3000
        expected = loaded.version
        loaded.replace_lines(
            [
                OrderLine(
                    id=uuid4(),
                    product_id=product_id,
                    quantity=5,
                    product_sku=loaded.lines[0].product_sku,
                    product_title=loaded.lines[0].product_title,
                    unit_price_rial=loaded.lines[0].unit_price_rial,
                )
            ]
        )
        assert repo.save_order(loaded, expected_version=expected)
        mov = uow.connection.execute(
            text("SELECT count(*) FROM inventory.movements WHERE tenant_id = :t"),
            {"t": str(tenant_id)},
        ).scalar()
        rsv = uow.connection.execute(
            text("SELECT count(*) FROM inventory.reservations WHERE tenant_id = :t"),
            {"t": str(tenant_id)},
        ).scalar()
        assert int(mov or 0) == 0
        assert int(rsv or 0) == 0


def test_warehouse_cannot_edit_drafts_helper() -> None:
    actor = ActorContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        role=Role.WAREHOUSE,
        issuer="test",
        subject="wh",
    )
    assert actor.can_view_orders()
    assert not actor.can_edit_draft_orders()
    sales = ActorContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        role=Role.SALES,
        issuer="test",
        subject="sales",
    )
    assert sales.can_edit_draft_orders()
