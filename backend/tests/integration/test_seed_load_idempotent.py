"""seed-load idempotent rerun against the isolated test database."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from stockpilot.bootstrap import seed_load
from stockpilot.platform.persistence.uow import UnitOfWork
from stockpilot.platform.settings import Settings

pytestmark = pytest.mark.skipif(
    not os.environ.get("STOCKPILOT_MIGRATION_DATABASE_URL"),
    reason="STOCKPILOT_MIGRATION_DATABASE_URL not configured",
)


def test_seed_load_idempotent_rerun(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        seed_load,
        "get_settings",
        lambda: Settings.model_construct(
            environment="production",
            oidc_issuer="http://keycloak:8080/realms/stockpilot",
        ),
    )
    monkeypatch.setenv("STOCKPILOT_ALLOW_LOAD_SEED", "true")
    monkeypatch.setenv("STOCKPILOT_LOAD_TENANT_COUNT", "1")
    monkeypatch.setenv("STOCKPILOT_LOAD_PRODUCTS_PER_TENANT", "3")
    monkeypatch.setenv("STOCKPILOT_LOAD_ORDERS_PER_TENANT", "2")
    monkeypatch.setenv("STOCKPILOT_LOAD_ORDER_LINES", "1")
    monkeypatch.setenv("STOCKPILOT_LOAD_STOCK_QTY", "10")
    subjects = {
        "admin@load-01.test": str(uuid4()),
        "sales@load-01.test": str(uuid4()),
    }
    monkeypatch.setenv("STOCKPILOT_LOAD_SUBJECTS_JSON", __import__("json").dumps(subjects))

    engine = create_engine(os.environ["STOCKPILOT_MIGRATION_DATABASE_URL"], pool_pre_ping=True)

    def _factory():
        return engine

    seed_load.cmd_seed_load("production", migration_engine_factory=_factory)
    seed_load.cmd_seed_load("production", migration_engine_factory=_factory)

    with UnitOfWork(engine=engine) as uow:
        products = uow.connection.execute(
            text(
                """
                SELECT COUNT(*) FROM catalog.products p
                JOIN access.tenants t ON t.id = p.tenant_id
                WHERE t.slug = 'load-01'
                """
            )
        ).scalar_one()
        drafts = uow.connection.execute(
            text(
                """
                SELECT COUNT(*) FROM sales.orders o
                JOIN access.tenants t ON t.id = o.tenant_id
                WHERE t.slug = 'load-01' AND o.status = 'DRAFT'
                """
            )
        ).scalar_one()
    assert int(products) == 3
    assert int(drafts) == 2
