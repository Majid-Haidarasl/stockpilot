"""Migration 0014 ops metrics: DEFINER aggregates, metrics role, cross-tenant counts."""

from __future__ import annotations

import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.modules.sales.adapters.outbound.customer_repo import CustomerRepository
from stockpilot.platform.failed_jobs.writer import insert_failed_job_on_connection
from stockpilot.platform.outbox.mapping import ORDER_LIFECYCLE_TASK
from stockpilot.platform.persistence.uow import UnitOfWork

pytestmark = pytest.mark.skipif(
    not os.environ.get("STOCKPILOT_DATABASE_URL")
    or not os.environ.get("STOCKPILOT_MIGRATION_DATABASE_URL"),
    reason="Database URLs not configured",
)


def _app():
    return create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)


def _migrator():
    return create_engine(os.environ["STOCKPILOT_MIGRATION_DATABASE_URL"], pool_pre_ping=True)


def _metrics():
    url = os.environ.get("STOCKPILOT_METRICS_DATABASE_URL")
    if not url:
        # Derive from app URL host; password from env default used in compose checks.
        password = os.environ.get("STOCKPILOT_METRICS_PASSWORD", "metrics_dev_change_me")
        app_url = os.environ["STOCKPILOT_DATABASE_URL"]
        # postgresql+psycopg://stockpilot_app:...@host:port/db
        after_at = app_url.split("@", 1)[1]
        url = f"postgresql+psycopg://stockpilot_metrics:{password}@{after_at}"
    return create_engine(url, pool_pre_ping=True)


def _seed_tenant_customer() -> tuple[UUID, UUID]:
    with UnitOfWork(engine=_migrator()) as uow:
        access = AccessRepository(uow.connection)
        customers = CustomerRepository(uow.connection)
        tenant_id = access.ensure_tenant(slug=f"met-{uuid4().hex[:8]}", name="Metrics Org")
        customer = customers.create_customer(
            tenant_id=tenant_id, name="Buyer", phone=None, email=None, notes=None
        )
    return tenant_id, UUID(str(customer["id"]))


def _insert_stale_reserved(tenant_id: UUID, customer_id: UUID) -> UUID:
    order_id = uuid4()
    with _migrator().begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO sales.orders (
                  id, tenant_id, customer_id, status, version,
                  reserved_at, expires_at, created_at, updated_at
                ) VALUES (
                  :id, :tenant_id, :customer_id, 'RESERVED', 1,
                  now() - interval '1 hour',
                  now() - interval '10 minutes',
                  now(), now()
                )
                """
            ),
            {
                "id": str(order_id),
                "tenant_id": str(tenant_id),
                "customer_id": str(customer_id),
            },
        )
    return order_id


def test_metrics_role_can_execute_aggregates_and_select_heartbeats() -> None:
    with _metrics().connect() as conn:
        lag = conn.execute(text("SELECT * FROM platform.outbox_lag()")).mappings().one()
        assert "unpublished_count" in lag
        fj = conn.execute(text("SELECT * FROM platform.failed_jobs_metrics()")).mappings().one()
        assert "unreplayed_count" in fj
        stale = (
            conn.execute(text("SELECT * FROM platform.stale_reserved_orders_metrics()"))
            .mappings()
            .one()
        )
        assert "stale_count" in stale
        conn.execute(text("SELECT service_name FROM platform.heartbeats LIMIT 1"))


def test_metrics_role_cannot_select_sensitive_tables() -> None:
    with _metrics().connect() as conn:
        for sql in (
            "SELECT event_id FROM platform.outbox LIMIT 1",
            "SELECT id FROM platform.failed_jobs LIMIT 1",
            "SELECT id FROM sales.orders LIMIT 1",
        ):
            with pytest.raises((ProgrammingError, DBAPIError)):
                conn.execute(text(sql))


def test_failed_jobs_metrics_counts_two_tenants() -> None:
    t1, _ = _seed_tenant_customer()
    t2, _ = _seed_tenant_customer()
    with _metrics().connect() as conn:
        before = int(
            conn.execute(
                text("SELECT unreplayed_count FROM platform.failed_jobs_metrics()")
            ).scalar_one()
        )
    for tenant_id in (t1, t2):
        with _migrator().begin() as conn:
            insert_failed_job_on_connection(
                conn,
                job_id=uuid4(),
                task_name=ORDER_LIFECYCLE_TASK,
                error_message="metrics test",
                attempts=5,
                tenant_id=tenant_id,
                event_id=uuid4(),
                envelope={"event_id": str(uuid4()), "tenant_id": str(tenant_id)},
            )
    with _metrics().connect() as conn:
        after = int(
            conn.execute(
                text("SELECT unreplayed_count FROM platform.failed_jobs_metrics()")
            ).scalar_one()
        )
    assert after == before + 2


def test_stale_reserved_metrics_counts_two_tenants() -> None:
    t1, c1 = _seed_tenant_customer()
    t2, c2 = _seed_tenant_customer()
    with _metrics().connect() as conn:
        before = int(
            conn.execute(
                text("SELECT stale_count FROM platform.stale_reserved_orders_metrics()")
            ).scalar_one()
        )
    _insert_stale_reserved(t1, c1)
    _insert_stale_reserved(t2, c2)
    with _metrics().connect() as conn:
        after = int(
            conn.execute(
                text("SELECT stale_count FROM platform.stale_reserved_orders_metrics()")
            ).scalar_one()
        )
    assert after == before + 2


def test_app_still_cannot_select_failed_jobs() -> None:
    with _app().connect() as conn:
        with pytest.raises((ProgrammingError, DBAPIError)):
            conn.execute(text("SELECT id FROM platform.failed_jobs LIMIT 1"))
