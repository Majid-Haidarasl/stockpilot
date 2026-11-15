"""Inventory list includes zero-stock and never-received active products."""

from __future__ import annotations

import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from stockpilot.bootstrap.app import create_app
from stockpilot.modules.access.adapters.inbound.deps import require_actor, require_csrf
from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.modules.access.domain.models import ActorContext, Role
from stockpilot.modules.catalog.adapters.outbound.repo import CatalogRepository
from stockpilot.modules.inventory.adapters.outbound.repo import InventoryRepository
from stockpilot.platform.persistence.uow import UnitOfWork

pytestmark = pytest.mark.skipif(
    not os.environ.get("STOCKPILOT_DATABASE_URL")
    or not os.environ.get("STOCKPILOT_MIGRATION_DATABASE_URL"),
    reason="Database URLs not configured",
)


def _migrator():
    return create_engine(os.environ["STOCKPILOT_MIGRATION_DATABASE_URL"], pool_pre_ping=True)


def _seed() -> tuple[UUID, UUID, ActorContext, UUID, UUID]:
    """Returns tenant, user, actor, never_received_product_id, zeroed_product_id."""
    with UnitOfWork(engine=_migrator()) as uow:
        access = AccessRepository(uow.connection)
        catalog = CatalogRepository(uow.connection)
        inventory = InventoryRepository(uow.connection)
        tenant_id = access.ensure_tenant(slug=f"invz-{uuid4().hex[:8]}", name="InvZ")
        user_id = access.upsert_user(
            issuer="test-issuer",
            subject=f"invz-{uuid4()}",
            email=f"invz-{uuid4().hex}@test",
            display_name="InvZ",
        )
        access.ensure_membership(tenant_id=tenant_id, user_id=user_id, role=Role.WAREHOUSE)
        never = catalog.create_product(
            tenant_id=tenant_id,
            sku=f"A-{uuid4().hex[:6]}",
            title="Never Received",
            unit_price_rial=1000,
        )
        zeroed = catalog.create_product(
            tenant_id=tenant_id,
            sku=f"B-{uuid4().hex[:6]}",
            title="Zeroed",
            unit_price_rial=2000,
        )
        inactive = catalog.create_product(
            tenant_id=tenant_id,
            sku=f"Z-{uuid4().hex[:6]}",
            title="Inactive",
            unit_price_rial=500,
            is_active=False,
        )
        _ = inactive
        zero_id = UUID(str(zeroed["id"]))
        position = inventory.ensure_position_for_update(tenant_id=tenant_id, product_id=zero_id)
        position.apply_receipt(5)
        inventory.save_position(position)
        inventory.insert_movement(
            tenant_id=tenant_id,
            product_id=zero_id,
            physical_delta=5,
            reserved_delta=0,
            reason="seed",
            reference=f"seed-{uuid4()}",
            actor_user_id=user_id,
        )
        position.apply_adjustment(-5)
        inventory.save_position(position)
        inventory.insert_movement(
            tenant_id=tenant_id,
            product_id=zero_id,
            physical_delta=-5,
            reserved_delta=0,
            reason="clear",
            reference=f"clear-{uuid4()}",
            actor_user_id=user_id,
        )
    actor = ActorContext(
        user_id=user_id,
        tenant_id=tenant_id,
        role=Role.WAREHOUSE,
        issuer="test-issuer",
        subject="invz",
    )
    return tenant_id, user_id, actor, UUID(str(never["id"])), zero_id


def _client(actor: ActorContext) -> TestClient:
    app = create_app()
    app.dependency_overrides[require_actor] = lambda: actor
    app.dependency_overrides[require_csrf] = lambda: None
    return TestClient(app)


def test_list_includes_never_received_and_zeroed_excludes_inactive() -> None:
    tenant_id, _, actor, never_id, zero_id = _seed()
    client = _client(actor)
    response = client.get(f"/api/v1/tenants/{tenant_id}/inventory")
    assert response.status_code == 200
    rows = response.json()
    by_id = {r["product_id"]: r for r in rows}
    assert str(never_id) in by_id
    assert by_id[str(never_id)]["on_hand"] == 0
    assert by_id[str(never_id)]["available"] == 0
    assert by_id[str(never_id)]["has_position"] is False
    assert by_id[str(never_id)]["version"] == 0
    assert str(zero_id) in by_id
    assert by_id[str(zero_id)]["on_hand"] == 0
    assert by_id[str(zero_id)]["has_position"] is True
    assert by_id[str(zero_id)]["version"] >= 1
    assert all(r["title"] != "Inactive" for r in rows)
    skus = [r["sku"] for r in rows]
    assert skus == sorted(skus)


def test_adjustment_decrease_without_position_returns_clear_error() -> None:
    tenant_id, _, actor, never_id, _ = _seed()
    client = _client(actor)
    response = client.post(
        f"/api/v1/tenants/{tenant_id}/inventory/adjustments",
        json={
            "product_id": str(never_id),
            "quantity": -1,
            "reason": "shrink attempt",
            "reference": f"adj-{uuid4()}",
        },
    )
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "STOCK_INVARIANT"
    assert "رسید" in body["title"]


def test_receipt_creates_position_for_never_received() -> None:
    tenant_id, _, actor, never_id, _ = _seed()
    client = _client(actor)
    response = client.post(
        f"/api/v1/tenants/{tenant_id}/inventory/receipts",
        json={
            "product_id": str(never_id),
            "quantity": 4,
            "reference": f"rcpt-{uuid4()}",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["on_hand"] == 4
    assert body["has_position"] is True
    assert body["version"] >= 1


def test_inventory_list_tenant_isolation() -> None:
    tenant_a, _, actor_a, never_a, _ = _seed()
    tenant_b, _, actor_b, never_b, _ = _seed()
    client_a = _client(actor_a)
    rows_a = client_a.get(f"/api/v1/tenants/{tenant_a}/inventory").json()
    ids_a = {r["product_id"] for r in rows_a}
    assert str(never_a) in ids_a
    assert str(never_b) not in ids_a
    client_b = _client(actor_b)
    # Cross-tenant path still scoped by actor tenant via RLS / UoW
    rows_b = client_b.get(f"/api/v1/tenants/{tenant_b}/inventory").json()
    ids_b = {r["product_id"] for r in rows_b}
    assert str(never_b) in ids_b
    assert str(never_a) not in ids_b
