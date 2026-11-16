"""Inbox consumer, failed_jobs privileges, and notification API isolation."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.modules.access.domain.models import Role
from stockpilot.modules.notifications.adapters.inbound.tasks import deliver_order_lifecycle_event
from stockpilot.modules.notifications.adapters.outbound.consume_service import (
    process_order_lifecycle_event,
    record_final_failure,
)
from stockpilot.modules.notifications.adapters.outbound.repo import NotificationRepository
from stockpilot.modules.notifications.application.errors import PermanentConsumeError
from stockpilot.platform.failed_jobs.writer import record_failed_job
from stockpilot.platform.outbox.mapping import ORDER_LIFECYCLE_TASK
from stockpilot.platform.persistence.session_roles import SESSION_ROLE_WORKER
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


def _seed_tenant_with_roles(
    *,
    include_admin: bool = True,
    include_sales: bool = True,
    include_warehouse: bool = True,
    include_viewer: bool = False,
) -> tuple[UUID, dict[str, UUID]]:
    users: dict[str, UUID] = {}
    with UnitOfWork(engine=_migrator()) as uow:
        access = AccessRepository(uow.connection)
        tenant_id = access.ensure_tenant(slug=f"ntf-{uuid4().hex[:8]}", name="Notify Org")
        role_map = []
        if include_admin:
            role_map.append(("admin", Role.ADMIN))
        if include_sales:
            role_map.append(("sales", Role.SALES))
        if include_warehouse:
            role_map.append(("warehouse", Role.WAREHOUSE))
        if include_viewer:
            role_map.append(("viewer", Role.VIEWER))
        for key, role in role_map:
            uid = access.upsert_user(
                issuer="test-issuer",
                subject=f"ntf-{key}-{uuid4()}",
                email=f"{key}-{uuid4().hex[:6]}@test",
                display_name=key,
            )
            access.ensure_membership(tenant_id=tenant_id, user_id=uid, role=role)
            users[key] = uid
    return tenant_id, users


def _envelope(
    *,
    tenant_id: UUID,
    event_type: str = "OrderReserved",
    event_id: UUID | None = None,
) -> dict[str, Any]:
    eid = event_id or uuid4()
    order_id = uuid4()
    return {
        "event_id": str(eid),
        "event_type": event_type,
        "event_version": "v1",
        "tenant_id": str(tenant_id),
        "aggregate_type": "order",
        "aggregate_id": str(order_id),
        "occurred_at": datetime.now(UTC).isoformat(),
        "payload": {"order_id": str(order_id)},
    }


def _count_notifications(tenant_id: UUID) -> int:
    with UnitOfWork(engine=_migrator()) as uow:
        row = uow.connection.execute(
            text("SELECT COUNT(*) FROM notifications.notifications WHERE tenant_id = :t"),
            {"t": str(tenant_id)},
        ).one()
    return int(row[0])


def _count_inbox(event_id: UUID) -> int:
    with UnitOfWork(engine=_migrator()) as uow:
        row = uow.connection.execute(
            text("SELECT COUNT(*) FROM platform.inbox WHERE event_id = :e"),
            {"e": str(event_id)},
        ).one()
    return int(row[0])


def test_worker_session_role_is_not_a_membership_role() -> None:
    assert SESSION_ROLE_WORKER == "worker"
    assert SESSION_ROLE_WORKER not in {r.value for r in Role}
    with pytest.raises(ValueError):
        Role(SESSION_ROLE_WORKER)


def test_worker_can_select_own_tenant_memberships_only() -> None:
    tenant_a, users_a = _seed_tenant_with_roles()
    tenant_b, users_b = _seed_tenant_with_roles()
    with UnitOfWork(engine=_app(), tenant_id=tenant_a, role=SESSION_ROLE_WORKER) as uow:
        own = uow.connection.execute(
            text(
                """
                SELECT user_id FROM access.memberships
                WHERE tenant_id = :t
                """
            ),
            {"t": str(tenant_a)},
        ).all()
        other = uow.connection.execute(
            text(
                """
                SELECT user_id FROM access.memberships
                WHERE tenant_id = :t
                """
            ),
            {"t": str(tenant_b)},
        ).all()
    assert len(own) >= 2
    assert {UUID(str(r[0])) for r in own} >= {users_a["admin"], users_a["sales"]}
    assert other == []
    assert users_b["admin"]  # seeded; invisible under tenant_a worker context


def test_worker_cannot_mutate_memberships() -> None:
    tenant_id, users = _seed_tenant_with_roles()
    with UnitOfWork(engine=_app(), tenant_id=tenant_id, role=SESSION_ROLE_WORKER) as uow:
        with pytest.raises((ProgrammingError, DBAPIError, Exception)):
            uow.connection.exec_driver_sql(
                """
                INSERT INTO access.memberships (id, tenant_id, user_id, role)
                VALUES (%s, %s, %s, 'viewer')
                """,
                (str(uuid4()), str(tenant_id), str(users["admin"])),
            )
    with UnitOfWork(engine=_app(), tenant_id=tenant_id, role=SESSION_ROLE_WORKER) as uow:
        mid = uow.connection.execute(
            text(
                """
                SELECT id FROM access.memberships
                WHERE tenant_id = :t AND user_id = :u
                """
            ),
            {"t": str(tenant_id), "u": str(users["sales"])},
        ).first()
        assert mid is not None
        # SELECT policy only — UPDATE/DELETE match no write policy for worker.
        updated = uow.connection.execute(
            text(
                """
                UPDATE access.memberships SET role = 'viewer'
                WHERE id = :id AND tenant_id = :t
                """
            ),
            {"id": str(mid[0]), "t": str(tenant_id)},
        )
        assert updated.rowcount == 0
        deleted = uow.connection.execute(
            text(
                """
                DELETE FROM access.memberships
                WHERE id = :id AND tenant_id = :t
                """
            ),
            {"id": str(mid[0]), "t": str(tenant_id)},
        )
        assert deleted.rowcount == 0


def test_duplicate_message_creates_one_notification_set() -> None:
    tenant_id, users = _seed_tenant_with_roles()
    event_id = uuid4()
    env = _envelope(tenant_id=tenant_id, event_id=event_id)
    first = process_order_lifecycle_event(env, engine=_app())
    second = process_order_lifecycle_event(env, engine=_app())
    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert _count_inbox(event_id) == 1
    # admin + sales only for OrderReserved
    assert _count_notifications(tenant_id) == 2
    assert first["notifications"] == 2
    assert second["notifications"] == 0
    assert users["admin"] and users["sales"]


def test_empty_recipients_inserts_inbox_zero_notifications() -> None:
    tenant_id, _users = _seed_tenant_with_roles(
        include_admin=False,
        include_sales=False,
        include_warehouse=True,
        include_viewer=True,
    )
    event_id = uuid4()
    env = _envelope(tenant_id=tenant_id, event_type="OrderReserved", event_id=event_id)
    result = process_order_lifecycle_event(env, engine=_app())
    assert result["accepted"] is True
    assert result["notifications"] == 0
    assert _count_inbox(event_id) == 1
    assert _count_notifications(tenant_id) == 0


def test_order_confirmed_includes_warehouse_shipped_does_not() -> None:
    tenant_id, users = _seed_tenant_with_roles()
    confirmed = process_order_lifecycle_event(
        _envelope(tenant_id=tenant_id, event_type="OrderConfirmed"),
        engine=_app(),
    )
    assert confirmed["notifications"] == 3
    shipped_id = uuid4()
    shipped = process_order_lifecycle_event(
        _envelope(tenant_id=tenant_id, event_type="OrderShipped", event_id=shipped_id),
        engine=_app(),
    )
    assert shipped["notifications"] == 2
    with UnitOfWork(engine=_migrator()) as uow:
        wh_rows = uow.connection.execute(
            text(
                """
                SELECT COUNT(*) FROM notifications.notifications
                WHERE tenant_id = :t AND recipient_user_id = :u AND type = 'OrderShipped'
                """
            ),
            {"t": str(tenant_id), "u": str(users["warehouse"])},
        ).one()
        conf_wh = uow.connection.execute(
            text(
                """
                SELECT COUNT(*) FROM notifications.notifications
                WHERE tenant_id = :t AND recipient_user_id = :u AND type = 'OrderConfirmed'
                """
            ),
            {"t": str(tenant_id), "u": str(users["warehouse"])},
        ).one()
    assert int(wh_rows[0]) == 0
    assert int(conf_wh[0]) == 1


def test_poison_unknown_type_writes_failed_jobs() -> None:
    tenant_id, _ = _seed_tenant_with_roles()
    env = _envelope(tenant_id=tenant_id, event_type="OrderReserved")
    env["event_type"] = "NotARealEvent"
    with pytest.raises(PermanentConsumeError):
        process_order_lifecycle_event(env, engine=_app())
    record_final_failure(
        envelope=env,
        error=PermanentConsumeError("Unknown event type"),
        attempts=1,
        engine=_app(),
    )
    with UnitOfWork(engine=_migrator()) as uow:
        row = (
            uow.connection.execute(
                text(
                    """
                SELECT task_name, attempts, error_message
                FROM platform.failed_jobs
                WHERE event_id = :e
                """
                ),
                {"e": env["event_id"]},
            )
            .mappings()
            .first()
        )
    assert row is not None
    assert row["task_name"] == ORDER_LIFECYCLE_TASK
    assert int(row["attempts"]) == 1
    assert "Unknown" in row["error_message"] or "event" in row["error_message"].lower()


def test_failed_jobs_write_failure_propagates() -> None:
    """If failed_jobs INSERT fails, record_final_failure raises (task must not ack)."""
    with pytest.raises((ProgrammingError, DBAPIError, Exception)):
        # Force failure by using a bogus engine URL that cannot connect after dispose.
        broken = create_engine("postgresql+psycopg://invalid:invalid@127.0.0.1:1/none")
        try:
            record_failed_job(
                engine=broken,
                task_name=ORDER_LIFECYCLE_TASK,
                error_message="boom",
                attempts=5,
                tenant_id=None,
                event_id=None,
            )
        finally:
            broken.dispose()


def _priv(conn: object, table: str, priv: str) -> bool:
    return bool(
        conn.execute(  # type: ignore[union-attr]
            text("SELECT has_table_privilege('stockpilot_app', :t, :p)"),
            {"t": table, "p": priv},
        ).scalar()
    )


def test_app_cannot_select_update_delete_failed_jobs() -> None:
    tenant_id, _ = _seed_tenant_with_roles()
    job_id = uuid4()
    scoped_id = uuid4()
    with UnitOfWork(engine=_migrator()) as uow:
        assert _priv(uow.connection, "platform.failed_jobs", "SELECT") is False
        assert _priv(uow.connection, "platform.failed_jobs", "INSERT") is True
        assert _priv(uow.connection, "platform.failed_jobs", "UPDATE") is False
        assert _priv(uow.connection, "platform.failed_jobs", "DELETE") is False
        uow.connection.execute(
            text(
                """
                INSERT INTO platform.failed_jobs (
                  id, tenant_id, event_id, task_name, error_message, attempts
                ) VALUES (:id, NULL, NULL, :task, 'x', 1)
                """
            ),
            {"id": str(job_id), "task": ORDER_LIFECYCLE_TASK},
        )
        uow.connection.execute(
            text(
                """
                INSERT INTO platform.failed_jobs (
                  id, tenant_id, event_id, task_name, error_message, attempts
                ) VALUES (:id, :tenant, NULL, :task, 'y', 1)
                """
            ),
            {
                "id": str(scoped_id),
                "tenant": str(tenant_id),
                "task": ORDER_LIFECYCLE_TASK,
            },
        )

    # App-style sessions: SELECT/UPDATE/DELETE must fail (incl. null-tenant rows).
    with UnitOfWork(engine=_app(), tenant_id=tenant_id, role="admin") as uow:
        with pytest.raises((ProgrammingError, DBAPIError, Exception)):
            uow.connection.exec_driver_sql(
                "SELECT id FROM platform.failed_jobs WHERE id = %s",
                (str(job_id),),
            )
    with UnitOfWork(engine=_app()) as uow:
        with pytest.raises((ProgrammingError, DBAPIError, Exception)):
            uow.connection.exec_driver_sql(
                "SELECT id FROM platform.failed_jobs WHERE id = %s",
                (str(job_id),),
            )

    with UnitOfWork(engine=_app(), tenant_id=tenant_id, role="admin") as uow:
        with pytest.raises((ProgrammingError, DBAPIError, Exception)):
            uow.connection.exec_driver_sql(
                "UPDATE platform.failed_jobs SET error_message = 'z' WHERE id = %s",
                (str(scoped_id),),
            )

    with UnitOfWork(engine=_app()) as uow:
        with pytest.raises((ProgrammingError, DBAPIError, Exception)):
            uow.connection.exec_driver_sql(
                "DELETE FROM platform.failed_jobs WHERE id = %s",
                (str(job_id),),
            )


def test_inbox_and_notifications_privilege_matrix() -> None:
    tenant_id, users = _seed_tenant_with_roles()
    with UnitOfWork(engine=_migrator()) as uow:
        assert _priv(uow.connection, "platform.inbox", "SELECT") is True
        assert _priv(uow.connection, "platform.inbox", "INSERT") is True
        assert _priv(uow.connection, "platform.inbox", "UPDATE") is False
        assert _priv(uow.connection, "platform.inbox", "DELETE") is False
        assert _priv(uow.connection, "notifications.notifications", "SELECT") is True
        assert _priv(uow.connection, "notifications.notifications", "INSERT") is True
        assert _priv(uow.connection, "notifications.notifications", "DELETE") is False
        # Column-level UPDATE(read_at): table UPDATE may be false; column grant checked below.

    event_id = uuid4()
    process_order_lifecycle_event(
        _envelope(tenant_id=tenant_id, event_id=event_id),
        engine=_app(),
    )
    with UnitOfWork(engine=_app(), tenant_id=tenant_id, role="admin") as uow:
        row = uow.connection.execute(
            text("SELECT event_id FROM platform.inbox WHERE event_id = :e"),
            {"e": str(event_id)},
        ).first()
        assert row is not None

    with UnitOfWork(engine=_app(), tenant_id=tenant_id, role="admin") as uow:
        with pytest.raises((ProgrammingError, DBAPIError, Exception)):
            uow.connection.exec_driver_sql(
                "UPDATE platform.inbox SET processed_at = now() WHERE event_id = %s",
                (str(event_id),),
            )

    with UnitOfWork(engine=_app(), tenant_id=tenant_id, role="admin") as uow:
        with pytest.raises((ProgrammingError, DBAPIError, Exception)):
            uow.connection.exec_driver_sql(
                "DELETE FROM platform.inbox WHERE event_id = %s",
                (str(event_id),),
            )

    with UnitOfWork(engine=_app(), tenant_id=tenant_id, role="admin") as uow:
        ntf = uow.connection.execute(
            text(
                """
                SELECT id FROM notifications.notifications
                WHERE tenant_id = :t AND recipient_user_id = :u
                LIMIT 1
                """
            ),
            {"t": str(tenant_id), "u": str(users["admin"])},
        ).first()
        assert ntf is not None
        nid = ntf[0]
        uow.connection.execute(
            text("UPDATE notifications.notifications SET read_at = now() WHERE id = :id"),
            {"id": str(nid)},
        )

    with UnitOfWork(engine=_app(), tenant_id=tenant_id, role="admin") as uow:
        with pytest.raises((ProgrammingError, DBAPIError, Exception)):
            uow.connection.exec_driver_sql(
                "UPDATE notifications.notifications SET type = 'x' WHERE id = %s",
                (str(nid),),
            )

    with UnitOfWork(engine=_app(), tenant_id=tenant_id, role="admin") as uow:
        with pytest.raises((ProgrammingError, DBAPIError, Exception)):
            uow.connection.exec_driver_sql(
                "DELETE FROM notifications.notifications WHERE id = %s",
                (str(nid),),
            )


def test_list_and_mark_read_isolation() -> None:
    tenant_id, users = _seed_tenant_with_roles()
    other_tenant, other_users = _seed_tenant_with_roles()
    process_order_lifecycle_event(
        _envelope(tenant_id=tenant_id, event_type="OrderReserved"),
        engine=_app(),
    )
    process_order_lifecycle_event(
        _envelope(tenant_id=other_tenant, event_type="OrderReserved"),
        engine=_app(),
    )

    with UnitOfWork(
        engine=_app(), user_id=users["admin"], tenant_id=tenant_id, role="admin"
    ) as uow:
        mine = NotificationRepository(uow.connection).list_for_recipient(
            tenant_id=tenant_id,
            recipient_user_id=users["admin"],
            limit=50,
            unread_only=True,
            cursor_created_at=None,
            cursor_id=None,
        )
        assert len(mine) >= 1
        nid = UUID(str(mine[0]["id"]))
        marked = NotificationRepository(uow.connection).mark_read(
            tenant_id=tenant_id,
            recipient_user_id=users["admin"],
            notification_id=nid,
        )
        assert marked is not None
        assert marked["read_at"] is not None
        # idempotent
        marked2 = NotificationRepository(uow.connection).mark_read(
            tenant_id=tenant_id,
            recipient_user_id=users["admin"],
            notification_id=nid,
        )
        assert marked2 is not None

        # other user in same tenant cannot mark
        stolen = NotificationRepository(uow.connection).mark_read(
            tenant_id=tenant_id,
            recipient_user_id=users["sales"],
            notification_id=nid,
        )
        assert stolen is None

    # cross-tenant context cannot see other tenant's rows
    with UnitOfWork(
        engine=_app(),
        user_id=other_users["admin"],
        tenant_id=other_tenant,
        role="admin",
    ) as uow:
        cross = NotificationRepository(uow.connection).list_for_recipient(
            tenant_id=tenant_id,
            recipient_user_id=users["admin"],
            limit=50,
            unread_only=False,
            cursor_created_at=None,
            cursor_id=None,
        )
        assert cross == []


def test_pagination_newest_first() -> None:
    tenant_id, users = _seed_tenant_with_roles()
    for _ in range(3):
        process_order_lifecycle_event(
            _envelope(tenant_id=tenant_id, event_type="OrderReserved"),
            engine=_app(),
        )
    with UnitOfWork(
        engine=_app(), user_id=users["admin"], tenant_id=tenant_id, role="admin"
    ) as uow:
        page1 = NotificationRepository(uow.connection).list_for_recipient(
            tenant_id=tenant_id,
            recipient_user_id=users["admin"],
            limit=2,
            unread_only=False,
            cursor_created_at=None,
            cursor_id=None,
        )
        assert len(page1) == 2
        assert page1[0]["created_at"] >= page1[1]["created_at"]
        page2 = NotificationRepository(uow.connection).list_for_recipient(
            tenant_id=tenant_id,
            recipient_user_id=users["admin"],
            limit=2,
            unread_only=False,
            cursor_created_at=page1[-1]["created_at"],
            cursor_id=UUID(str(page1[-1]["id"])),
        )
        ids1 = {str(r["id"]) for r in page1}
        ids2 = {str(r["id"]) for r in page2}
        assert ids1.isdisjoint(ids2)


def test_task_permanent_failure_records_and_returns() -> None:
    env = {"not": "an envelope"}
    result = deliver_order_lifecycle_event.run(env)
    assert result["failed"] is True


def test_http_list_read_pagination_and_isolation() -> None:
    from fastapi import HTTPException
    from fastapi.testclient import TestClient

    from stockpilot.bootstrap.app import create_app
    from stockpilot.modules.access.adapters.inbound.deps import require_actor, require_csrf
    from stockpilot.modules.access.domain.models import ActorContext

    tenant_id, users = _seed_tenant_with_roles()
    other_tenant, _other = _seed_tenant_with_roles()
    for _ in range(3):
        process_order_lifecycle_event(
            _envelope(tenant_id=tenant_id, event_type="OrderReserved"),
            engine=_app(),
        )

    actor = ActorContext(
        user_id=users["admin"],
        tenant_id=tenant_id,
        role=Role.ADMIN,
        issuer="test-issuer",
        subject="admin",
    )
    app = create_app()
    app.dependency_overrides[require_actor] = lambda: actor
    app.dependency_overrides[require_csrf] = lambda: None
    client = TestClient(app)

    listed = client.get(
        f"/api/v1/tenants/{tenant_id}/notifications",
        params={"limit": 2, "unread_only": True},
    )
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 2
    assert body[0]["created_at"] >= body[1]["created_at"]

    page2 = client.get(
        f"/api/v1/tenants/{tenant_id}/notifications",
        params={
            "limit": 2,
            "cursor_created_at": body[-1]["created_at"],
            "cursor_id": body[-1]["id"],
        },
    )
    assert page2.status_code == 200
    assert {r["id"] for r in page2.json()}.isdisjoint({r["id"] for r in body})

    nid = body[0]["id"]
    read1 = client.post(f"/api/v1/tenants/{tenant_id}/notifications/{nid}/read")
    assert read1.status_code == 200
    assert read1.json()["read_at"] is not None
    read2 = client.post(f"/api/v1/tenants/{tenant_id}/notifications/{nid}/read")
    assert read2.status_code == 200

    # other user's notification id → 404
    sales_actor = ActorContext(
        user_id=users["sales"],
        tenant_id=tenant_id,
        role=Role.SALES,
        issuer="test-issuer",
        subject="sales",
    )
    app.dependency_overrides[require_actor] = lambda: sales_actor
    stolen = client.post(f"/api/v1/tenants/{tenant_id}/notifications/{nid}/read")
    assert stolen.status_code == 404

    # cross-tenant membership denied → 404
    def deny() -> ActorContext:
        raise HTTPException(status_code=404, detail="Not found")

    app.dependency_overrides[require_actor] = deny
    cross = client.get(f"/api/v1/tenants/{other_tenant}/notifications")
    assert cross.status_code == 404
