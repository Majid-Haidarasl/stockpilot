"""Customer HTTP API: create/patch, validation, roles, tenant isolation."""

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
from stockpilot.modules.sales.adapters.outbound.customer_repo import CustomerRepository
from stockpilot.platform.persistence.uow import UnitOfWork

pytestmark = pytest.mark.skipif(
    not os.environ.get("STOCKPILOT_DATABASE_URL")
    or not os.environ.get("STOCKPILOT_MIGRATION_DATABASE_URL"),
    reason="Database URLs not configured",
)


def _migrator():
    return create_engine(os.environ["STOCKPILOT_MIGRATION_DATABASE_URL"], pool_pre_ping=True)


def _seed(role: Role = Role.SALES) -> tuple[UUID, UUID, ActorContext]:
    with UnitOfWork(engine=_migrator()) as uow:
        access = AccessRepository(uow.connection)
        tenant_id = access.ensure_tenant(slug=f"cust-{uuid4().hex[:8]}", name="Cust Org")
        user_id = access.upsert_user(
            issuer="test-issuer",
            subject=f"cust-{uuid4()}",
            email=f"cust-{uuid4().hex}@test",
            display_name="Cust",
        )
        access.ensure_membership(tenant_id=tenant_id, user_id=user_id, role=role)
    actor = ActorContext(
        user_id=user_id,
        tenant_id=tenant_id,
        role=role,
        issuer="test-issuer",
        subject="cust",
    )
    return tenant_id, user_id, actor


def _client(actor: ActorContext) -> TestClient:
    app = create_app()
    app.dependency_overrides[require_actor] = lambda: actor
    app.dependency_overrides[require_csrf] = lambda: None
    return TestClient(app)


def test_patch_customer_happy_path() -> None:
    tenant_id, _user_id, actor = _seed(Role.SALES)
    with UnitOfWork(engine=_migrator()) as uow:
        row = CustomerRepository(uow.connection).create_customer(
            tenant_id=tenant_id, name="Old", phone="09120000000", email=None, notes=None
        )
    client = _client(actor)
    response = client.patch(
        f"/api/v1/tenants/{tenant_id}/customers/{row['id']}",
        json={"expected_version": int(row["version"]), "name": "New", "phone": "09121111111"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "New"
    assert body["phone"] == "09121111111"
    assert body["version"] == int(row["version"]) + 1


def test_patch_customer_validation_empty_name() -> None:
    tenant_id, _, actor = _seed(Role.ADMIN)
    with UnitOfWork(engine=_migrator()) as uow:
        row = CustomerRepository(uow.connection).create_customer(
            tenant_id=tenant_id, name="Valid", phone=None, email=None, notes=None
        )
    client = _client(actor)
    response = client.patch(
        f"/api/v1/tenants/{tenant_id}/customers/{row['id']}",
        json={"expected_version": int(row["version"]), "name": ""},
    )
    assert response.status_code == 422


def test_patch_customer_viewer_forbidden() -> None:
    tenant_id, _, actor = _seed(Role.VIEWER)
    with UnitOfWork(engine=_migrator()) as uow:
        row = CustomerRepository(uow.connection).create_customer(
            tenant_id=tenant_id, name="X", phone=None, email=None, notes=None
        )
    client = _client(actor)
    response = client.patch(
        f"/api/v1/tenants/{tenant_id}/customers/{row['id']}",
        json={"expected_version": int(row["version"]), "name": "Y"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


def test_patch_customer_cross_tenant_404() -> None:
    tenant_a, _, actor_a = _seed(Role.SALES)
    tenant_b, _, _ = _seed(Role.SALES)
    with UnitOfWork(engine=_migrator()) as uow:
        row = CustomerRepository(uow.connection).create_customer(
            tenant_id=tenant_b, name="Other", phone=None, email=None, notes=None
        )
    client = _client(actor_a)
    response = client.patch(
        f"/api/v1/tenants/{tenant_a}/customers/{row['id']}",
        json={"expected_version": 1, "name": "Hijack"},
    )
    assert response.status_code == 404


def test_patch_customer_version_conflict() -> None:
    tenant_id, _, actor = _seed(Role.SALES)
    with UnitOfWork(engine=_migrator()) as uow:
        row = CustomerRepository(uow.connection).create_customer(
            tenant_id=tenant_id, name="V", phone=None, email=None, notes=None
        )
    client = _client(actor)
    response = client.patch(
        f"/api/v1/tenants/{tenant_id}/customers/{row['id']}",
        json={"expected_version": int(row["version"]) + 5, "name": "Nope"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "VERSION_CONFLICT"
