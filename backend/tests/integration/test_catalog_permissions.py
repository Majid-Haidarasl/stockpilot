"""Catalog permission samples against the runtime role (no HTTP stack)."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine

from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.modules.access.domain.models import ActorContext, Role
from stockpilot.modules.catalog.adapters.outbound.repo import CatalogRepository
from stockpilot.platform.persistence.uow import UnitOfWork

pytestmark = pytest.mark.skipif(
    not os.environ.get("STOCKPILOT_DATABASE_URL")
    or not os.environ.get("STOCKPILOT_MIGRATION_DATABASE_URL"),
    reason="Database URLs not configured",
)


def _seed_tenant_with_role(role: Role) -> tuple[object, object, ActorContext]:
    migrator = create_engine(os.environ["STOCKPILOT_MIGRATION_DATABASE_URL"], pool_pre_ping=True)
    with UnitOfWork(engine=migrator) as uow:
        access = AccessRepository(uow.connection)
        tenant_id = access.ensure_tenant(slug=f"perm-{uuid4().hex[:8]}", name="Perm Org")
        user_id = access.upsert_user(
            issuer="test-issuer",
            subject=f"{role.value}-{uuid4()}",
            email=f"{role.value}-{uuid4().hex}@test",
            display_name=role.value,
        )
        access.ensure_membership(tenant_id=tenant_id, user_id=user_id, role=role)
    actor = ActorContext(
        user_id=user_id,
        tenant_id=tenant_id,
        role=role,
        issuer="test-issuer",
        subject="sub",
    )
    return tenant_id, user_id, actor


def test_viewer_matrix_blocks_catalog_writes() -> None:
    _tenant_id, _user_id, actor = _seed_tenant_with_role(Role.VIEWER)
    assert not actor.can_manage_catalog_writes()
    assert not actor.can_change_product_price()


def test_warehouse_cannot_change_price_helper() -> None:
    _tenant_id, _user_id, actor = _seed_tenant_with_role(Role.WAREHOUSE)
    assert not actor.can_change_product_price()


def test_product_version_conflict() -> None:
    migrator = create_engine(os.environ["STOCKPILOT_MIGRATION_DATABASE_URL"], pool_pre_ping=True)
    runtime = create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)

    with UnitOfWork(engine=migrator) as uow:
        access = AccessRepository(uow.connection)
        tenant_id = access.ensure_tenant(slug=f"ver-{uuid4().hex[:8]}", name="Version Org")
        user_id = access.upsert_user(
            issuer="test-issuer",
            subject=f"ver-{uuid4()}",
            email=f"ver-{uuid4().hex}@test",
            display_name="Admin",
        )
        access.ensure_membership(tenant_id=tenant_id, user_id=user_id, role=Role.ADMIN)

    with UnitOfWork(engine=runtime, user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        repo = CatalogRepository(uow.connection)
        created = repo.create_product(
            tenant_id=tenant_id,
            sku="SKU-V1",
            title="Versioned",
            unit_price_rial=500,
        )
        conflict = repo.update_product(
            tenant_id=tenant_id,
            product_id=created["id"],
            expected_version=created["version"] + 5,
            title="Stale",
            unit_price_rial=None,
            is_active=None,
            stock_warning_threshold=None,
        )
        assert conflict is not None
        assert conflict.get("__conflict__") is True
