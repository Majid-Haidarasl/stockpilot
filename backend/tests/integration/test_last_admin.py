"""Last-admin protection under concurrent role demotion."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine

from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.modules.access.domain.models import Role
from stockpilot.platform.persistence.uow import UnitOfWork

pytestmark = pytest.mark.skipif(
    not os.environ.get("STOCKPILOT_DATABASE_URL")
    or not os.environ.get("STOCKPILOT_MIGRATION_DATABASE_URL"),
    reason="Database URLs not configured",
)


def test_concurrent_last_admin_demotion_keeps_one_admin() -> None:
    migrator = create_engine(os.environ["STOCKPILOT_MIGRATION_DATABASE_URL"], pool_pre_ping=True)
    runtime = create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)

    with UnitOfWork(engine=migrator) as uow:
        access = AccessRepository(uow.connection)
        tenant_id = access.ensure_tenant(slug=f"solo-{uuid4().hex[:8]}", name="Solo Org")
        user_id = access.upsert_user(
            issuer="test-issuer",
            subject=f"solo-{uuid4()}",
            email=f"solo-{uuid4().hex}@test",
            display_name="Solo Admin",
        )
        membership_id = access.ensure_membership(
            tenant_id=tenant_id,
            user_id=user_id,
            role=Role.ADMIN,
        )

    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    lock = threading.Lock()

    def attempt_demote() -> None:
        barrier.wait(timeout=10)
        with UnitOfWork(engine=runtime, user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
            repo = AccessRepository(uow.connection)
            repo.lock_tenant(tenant_id)
            if repo.count_admins(tenant_id) <= 1:
                with lock:
                    outcomes.append("blocked")
                return
            repo.update_member_role(membership_id, tenant_id, Role.VIEWER)
            with lock:
                outcomes.append("demoted")

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: attempt_demote(), range(2)))

    assert outcomes.count("demoted") == 0
    assert outcomes.count("blocked") == 2

    with UnitOfWork(engine=runtime, user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        assert AccessRepository(uow.connection).count_admins(tenant_id) == 1
