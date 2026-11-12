"""Order timeline read API: ordered events, cross-tenant 404, unknown order 404."""

from __future__ import annotations

import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from stockpilot.bootstrap.app import create_app
from stockpilot.modules.access.adapters.inbound.deps import require_actor
from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.modules.access.domain.models import ActorContext, Role
from stockpilot.modules.catalog.adapters.outbound.repo import CatalogRepository
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


def _seed_org(*, display_name: str = "Timeline Actor") -> tuple[UUID, UUID, UUID, UUID]:
    with UnitOfWork(engine=_migrator()) as uow:
        access = AccessRepository(uow.connection)
        catalog = CatalogRepository(uow.connection)
        customers = CustomerRepository(uow.connection)
        tenant_id = access.ensure_tenant(slug=f"tl-{uuid4().hex[:8]}", name="Timeline Org")
        user_id = access.upsert_user(
            issuer="test-issuer",
            subject=f"tl-{uuid4()}",
            email=f"tl-{uuid4().hex}@test",
            display_name=display_name,
        )
        access.ensure_membership(tenant_id=tenant_id, user_id=user_id, role=Role.VIEWER)
        product = catalog.create_product(
            tenant_id=tenant_id,
            sku=f"SKU-{uuid4().hex[:6]}",
            title="Timeline Item",
            unit_price_rial=2000,
        )
        customer = customers.create_customer(
            tenant_id=tenant_id, name="Buyer", phone=None, email=None, notes=None
        )
    return tenant_id, user_id, UUID(str(product["id"])), UUID(str(customer["id"]))


def _actor(user_id: UUID, tenant_id: UUID, role: Role = Role.VIEWER) -> ActorContext:
    return ActorContext(
        user_id=user_id,
        tenant_id=tenant_id,
        role=role,
        issuer="test-issuer",
        subject="tl-sub",
        display_name="Timeline Actor",
    )


def _client_for(actor: ActorContext) -> TestClient:
    app = create_app()
    app.dependency_overrides[require_actor] = lambda: actor
    return TestClient(app)


def test_timeline_returns_events_in_order() -> None:
    tenant_id, user_id, product_id, customer_id = _seed_org(display_name="سارا فروش")
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
                    quantity=1,
                    product_sku=str(snap["sku"]),
                    product_title=str(snap["title"]),
                    unit_price_rial=int(snap["unit_price_rial"]),
                )
            ],
        )
        orders.insert_order(order)
        orders.write_audit(
            tenant_id=tenant_id,
            actor_user_id=user_id,
            action_type="order.draft_created",
            entity_id=order.id,
            payload={"from_status": None, "to_status": "DRAFT"},
        )
        orders.write_audit(
            tenant_id=tenant_id,
            actor_user_id=user_id,
            action_type="order.draft_updated",
            entity_id=order.id,
            payload={"from_status": "DRAFT", "to_status": "DRAFT"},
        )
        order_id = order.id

    client = _client_for(_actor(user_id, tenant_id))
    response = client.get(f"/api/v1/tenants/{tenant_id}/orders/{order_id}/timeline")
    assert response.status_code == 200
    events = response.json()
    assert [e["event_type"] for e in events] == [
        "order.draft_created",
        "order.draft_updated",
    ]
    assert events[0]["to_status"] == "DRAFT"
    assert events[0]["from_status"] is None
    assert events[0]["actor_display_name"] == "سارا فروش"
    assert events[1]["from_status"] == "DRAFT"
    assert events[1]["to_status"] == "DRAFT"
    assert "payload" not in events[0]
    assert set(events[0].keys()) <= {
        "event_type",
        "occurred_at",
        "actor_display_name",
        "from_status",
        "to_status",
    }


def test_timeline_other_tenant_order_returns_404() -> None:
    tenant_a, user_a, product_a, customer_a = _seed_org()
    tenant_b, user_b, product_b, customer_b = _seed_org()

    with UnitOfWork(engine=_runtime(), user_id=user_b, tenant_id=tenant_b, role="viewer") as uow:
        orders = OrderRepository(uow.connection)
        snap = orders.get_product_snapshot(tenant_b, product_b)
        assert snap is not None
        order = Order.new_draft(
            tenant_id=tenant_b,
            customer_id=customer_b,
            lines=[
                OrderLine(
                    id=uuid4(),
                    product_id=product_b,
                    quantity=1,
                    product_sku=str(snap["sku"]),
                    product_title=str(snap["title"]),
                    unit_price_rial=int(snap["unit_price_rial"]),
                )
            ],
        )
        orders.insert_order(order)
        foreign_order_id = order.id

    # Actor of tenant A asking under tenant A path for tenant B's order id.
    client = _client_for(_actor(user_a, tenant_a))
    response = client.get(f"/api/v1/tenants/{tenant_a}/orders/{foreign_order_id}/timeline")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"
    _ = product_a, customer_a


def test_timeline_unknown_order_returns_404() -> None:
    tenant_id, user_id, _product_id, _customer_id = _seed_org()
    client = _client_for(_actor(user_id, tenant_id))
    missing = uuid4()
    response = client.get(f"/api/v1/tenants/{tenant_id}/orders/{missing}/timeline")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"
