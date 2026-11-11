"""Tenant isolation for catalog using the runtime DB role."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.modules.access.domain.models import Role
from stockpilot.modules.catalog.adapters.outbound.repo import CatalogRepository
from stockpilot.platform.persistence.uow import UnitOfWork

pytestmark = pytest.mark.skipif(
    not os.environ.get("STOCKPILOT_DATABASE_URL")
    or not os.environ.get("STOCKPILOT_MIGRATION_DATABASE_URL"),
    reason="Database URLs not configured",
)


def test_same_sku_allowed_in_two_tenants_and_rls_hides_cross_tenant() -> None:
    migrator = create_engine(os.environ["STOCKPILOT_MIGRATION_DATABASE_URL"], pool_pre_ping=True)
    runtime = create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)

    with UnitOfWork(engine=migrator) as uow:
        access = AccessRepository(uow.connection)
        aftab = access.ensure_tenant(slug=f"aftab-{uuid4().hex[:8]}", name="Aftab Temp")
        baran = access.ensure_tenant(slug=f"baran-{uuid4().hex[:8]}", name="Baran Temp")
        user_a = access.upsert_user(
            issuer="test-issuer",
            subject=f"a-{uuid4()}",
            email=f"a-{uuid4().hex}@test",
            display_name="A",
        )
        user_b = access.upsert_user(
            issuer="test-issuer",
            subject=f"b-{uuid4()}",
            email=f"b-{uuid4().hex}@test",
            display_name="B",
        )
        access.ensure_membership(tenant_id=aftab, user_id=user_a, role=Role.ADMIN)
        access.ensure_membership(tenant_id=baran, user_id=user_b, role=Role.ADMIN)

    with UnitOfWork(engine=runtime, user_id=user_a, tenant_id=aftab, role="admin") as uow:
        CatalogRepository(uow.connection).create_product(
            tenant_id=aftab,
            sku="SKU-100",
            title="Aftab Item",
            unit_price_rial=1000,
        )

    with UnitOfWork(engine=runtime, user_id=user_b, tenant_id=baran, role="admin") as uow:
        CatalogRepository(uow.connection).create_product(
            tenant_id=baran,
            sku="SKU-100",
            title="Baran Item",
            unit_price_rial=2000,
        )
        rows = CatalogRepository(uow.connection).list_products(baran)
        assert len(rows) == 1
        assert rows[0]["title"] == "Baran Item"

    with UnitOfWork(engine=runtime, user_id=user_a, tenant_id=aftab, role="admin") as uow:
        # Cross-tenant id should not be visible under RLS.
        foreign = uow.connection.execute(
            text("SELECT count(*) FROM catalog.products WHERE tenant_id = :tid"),
            {"tid": str(baran)},
        ).scalar_one()
        assert int(foreign) == 0
