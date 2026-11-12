"""Dashboard read API: shape, date validation, tenant isolation."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from stockpilot.bootstrap.app import create_app
from stockpilot.modules.access.adapters.inbound.deps import require_actor
from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.modules.access.domain.models import ActorContext, Role
from stockpilot.modules.catalog.adapters.outbound.repo import CatalogRepository
from stockpilot.modules.inventory.adapters.outbound.repo import InventoryRepository
from stockpilot.modules.sales.adapters.outbound.customer_repo import CustomerRepository
from stockpilot.modules.sales.adapters.outbound.order_repo import OrderRepository
from stockpilot.modules.sales.domain.order import Order, OrderLine
from stockpilot.platform.persistence.uow import UnitOfWork

pytestmark = pytest.mark.skipif(
    not os.environ.get("STOCKPILOT_DATABASE_URL")
    or not os.environ.get("STOCKPILOT_MIGRATION_DATABASE_URL"),
    reason="Database URLs not configured",
)


def _migrator():
    return create_engine(os.environ["STOCKPILOT_MIGRATION_DATABASE_URL"], pool_pre_ping=True)


def _runtime():
    return create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)


def _seed(*, with_stock: bool = True) -> tuple[UUID, UUID, UUID, UUID, str]:
    with UnitOfWork(engine=_migrator()) as uow:
        access = AccessRepository(uow.connection)
        catalog = CatalogRepository(uow.connection)
        customers = CustomerRepository(uow.connection)
        inventory = InventoryRepository(uow.connection)
        tenant_id = access.ensure_tenant(slug=f"dash-{uuid4().hex[:8]}", name="Dash Org")
        user_id = access.upsert_user(
            issuer="test-issuer",
            subject=f"dash-{uuid4()}",
            email=f"dash-{uuid4().hex}@test",
            display_name="Dash",
        )
        access.ensure_membership(tenant_id=tenant_id, user_id=user_id, role=Role.VIEWER)
        sku = f"SKU-{uuid4().hex[:6]}"
        product = catalog.create_product(
            tenant_id=tenant_id,
            sku=sku,
            title="Low Stock Item",
            unit_price_rial=5000,
            stock_warning_threshold=10,
        )
        product_id = UUID(str(product["id"]))
        customer = customers.create_customer(
            tenant_id=tenant_id, name="Buyer", phone=None, email=None, notes=None
        )
        if with_stock:
            position = inventory.ensure_position_for_update(
                tenant_id=tenant_id, product_id=product_id
            )
            position.apply_receipt(3)
            inventory.save_position(position)
            inventory.insert_movement(
                tenant_id=tenant_id,
                product_id=product_id,
                physical_delta=3,
                reserved_delta=0,
                reason="seed",
                reference=f"seed-{uuid4()}",
                actor_user_id=user_id,
            )
    return tenant_id, user_id, product_id, UUID(str(customer["id"])), sku


def _actor(user_id: UUID, tenant_id: UUID) -> ActorContext:
    return ActorContext(
        user_id=user_id,
        tenant_id=tenant_id,
        role=Role.VIEWER,
        issuer="test-issuer",
        subject="dash",
    )


def _client(actor: ActorContext) -> TestClient:
    app = create_app()
    app.dependency_overrides[require_actor] = lambda: actor
    return TestClient(app)


def _insert_shipped(
    *,
    tenant_id: UUID,
    user_id: UUID,
    product_id: UUID,
    customer_id: UUID,
    quantity: int,
    shipped_at: datetime,
) -> None:
    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="viewer") as uow:
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
        uow.connection.execute(
            text(
                """
                UPDATE sales.orders
                SET status = 'SHIPPED', shipped_at = :shipped_at
                WHERE id = :id AND tenant_id = :tenant_id
                """
            ),
            {
                "id": str(order.id),
                "tenant_id": str(tenant_id),
                "shipped_at": shipped_at,
            },
        )


def test_dashboard_returns_counts_shipped_total_and_low_stock() -> None:
    tenant_id, user_id, product_id, customer_id, _sku = _seed()
    shipped_at = datetime.now(tz=UTC) - timedelta(hours=1)

    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="viewer") as uow:
        orders = OrderRepository(uow.connection)
        snap = orders.get_product_snapshot(tenant_id, product_id)
        assert snap is not None
        draft = Order.new_draft(
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
        orders.insert_order(draft)

    _insert_shipped(
        tenant_id=tenant_id,
        user_id=user_id,
        product_id=product_id,
        customer_id=customer_id,
        quantity=2,
        shipped_at=shipped_at,
    )

    range_from = (shipped_at - timedelta(days=1)).isoformat()
    range_to = (shipped_at + timedelta(days=1)).isoformat()
    client = _client(_actor(user_id, tenant_id))
    response = client.get(
        f"/api/v1/tenants/{tenant_id}/dashboard",
        params={"from": range_from, "to": range_to},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["order_counts_by_status"]["DRAFT"] >= 1
    assert body["order_counts_by_status"]["SHIPPED"] >= 1
    assert body["shipped_total"]["currency"] == "IRR"
    assert body["shipped_total"]["amount"] == "10000"
    assert any(item["available"] == 3 for item in body["low_stock"])
    assert all(item["available"] <= item["stock_warning_threshold"] for item in body["low_stock"])


def test_dashboard_rejects_from_after_to() -> None:
    tenant_id, user_id, _product_id, _customer_id, _sku = _seed(with_stock=False)
    client = _client(_actor(user_id, tenant_id))
    later = datetime.now(tz=UTC)
    earlier = later - timedelta(days=1)
    response = client.get(
        f"/api/v1/tenants/{tenant_id}/dashboard",
        params={"from": later.isoformat(), "to": earlier.isoformat()},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_dashboard_does_not_leak_other_tenant_data() -> None:
    tenant_a, user_a, product_a, customer_a, sku_a = _seed()
    tenant_b, user_b, _product_b, _customer_b, sku_b = _seed(with_stock=False)
    shipped_at = datetime.now(tz=UTC) - timedelta(hours=2)
    _insert_shipped(
        tenant_id=tenant_a,
        user_id=user_a,
        product_id=product_a,
        customer_id=customer_a,
        quantity=2,
        shipped_at=shipped_at,
    )

    range_from = (shipped_at - timedelta(days=1)).isoformat()
    range_to = (shipped_at + timedelta(days=1)).isoformat()
    client_b = _client(_actor(user_b, tenant_b))
    response = client_b.get(
        f"/api/v1/tenants/{tenant_b}/dashboard",
        params={"from": range_from, "to": range_to},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["shipped_total"]["amount"] == "0"
    assert all(item["sku"] != sku_a for item in body["low_stock"])
    assert body["order_counts_by_status"]["SHIPPED"] == 0
    _ = sku_b


def test_dashboard_cross_tenant_membership_denied_is_404() -> None:
    _tenant_a, user_a, _pa, _ca, _sa = _seed(with_stock=False)
    tenant_b, _user_b, _pb, _cb, _sb = _seed(with_stock=False)
    app = create_app()

    def deny_foreign() -> ActorContext:
        raise HTTPException(status_code=404, detail="Not found")

    app.dependency_overrides[require_actor] = deny_foreign
    client = TestClient(app)
    now = datetime.now(tz=UTC)
    response = client.get(
        f"/api/v1/tenants/{tenant_b}/dashboard",
        params={
            "from": (now - timedelta(days=1)).isoformat(),
            "to": now.isoformat(),
        },
    )
    assert response.status_code == 404
    _ = user_a
