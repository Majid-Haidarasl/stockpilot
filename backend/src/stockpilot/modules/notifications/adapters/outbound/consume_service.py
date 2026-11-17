"""Consume order-lifecycle envelopes into Inbox + notifications."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.engine import Engine

from stockpilot.modules.access.public import list_member_user_ids_for_roles, tenant_exists
from stockpilot.modules.notifications.adapters.outbound.repo import NotificationRepository
from stockpilot.modules.notifications.application.errors import PermanentConsumeError
from stockpilot.modules.notifications.application.recipients import recipient_roles_for_event
from stockpilot.platform.failed_jobs.writer import record_failed_job
from stockpilot.platform.heartbeats.store import upsert_heartbeat
from stockpilot.platform.inbox.writer import CONSUMER_ORDER_LIFECYCLE, try_insert_inbox
from stockpilot.platform.outbox.mapping import EVENT_TO_TASK, ORDER_LIFECYCLE_TASK
from stockpilot.platform.persistence.db import get_engine
from stockpilot.platform.persistence.session_roles import SESSION_ROLE_WORKER
from stockpilot.platform.persistence.uow import UnitOfWork

logger = logging.getLogger("stockpilot.notifications.consume")

_REQUIRED_KEYS = (
    "event_id",
    "event_type",
    "event_version",
    "tenant_id",
    "aggregate_type",
    "aggregate_id",
    "occurred_at",
    "payload",
)


def _parse_uuid(value: object, field: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise PermanentConsumeError(f"Invalid {field}") from exc


def validate_envelope(envelope: dict[str, Any]) -> tuple[UUID, UUID, str]:
    missing = [key for key in _REQUIRED_KEYS if key not in envelope]
    if missing:
        raise PermanentConsumeError(f"Invalid envelope; missing keys: {missing}")
    event_type = str(envelope["event_type"])
    if event_type not in EVENT_TO_TASK:
        raise PermanentConsumeError(f"Unknown event type: {event_type}")
    event_id = _parse_uuid(envelope["event_id"], "event_id")
    tenant_id = _parse_uuid(envelope["tenant_id"], "tenant_id")
    return event_id, tenant_id, event_type


def process_order_lifecycle_event(
    envelope: dict[str, Any],
    *,
    engine: Engine | None = None,
) -> dict[str, Any]:
    """Write Inbox + notifications in one transaction. Raises PermanentConsumeError or DB errors."""
    eng = engine or get_engine()
    event_id, tenant_id, event_type = validate_envelope(envelope)

    with UnitOfWork(engine=eng, tenant_id=tenant_id, role=SESSION_ROLE_WORKER) as uow:
        if not tenant_exists(uow.connection, tenant_id):
            raise PermanentConsumeError("Unknown tenant_id")

        inserted = try_insert_inbox(
            uow.connection,
            consumer_name=CONSUMER_ORDER_LIFECYCLE,
            event_id=event_id,
            tenant_id=tenant_id,
        )
        if not inserted:
            return {
                "accepted": True,
                "duplicate": True,
                "event_id": str(event_id),
                "notifications": 0,
            }

        roles = recipient_roles_for_event(event_type)
        recipients = list_member_user_ids_for_roles(uow.connection, tenant_id, roles)
        if not recipients:
            logger.warning(
                "notifications_empty_recipients",
                extra={
                    "event_id": str(event_id),
                    "tenant_id": str(tenant_id),
                    "event_type": event_type,
                    "consumer_name": CONSUMER_ORDER_LIFECYCLE,
                },
            )
            upsert_heartbeat(
                uow.connection,
                service_name="worker",
                details={"event_id": str(event_id), "notifications": 0},
            )
            return {
                "accepted": True,
                "duplicate": False,
                "event_id": str(event_id),
                "notifications": 0,
            }

        payload = envelope.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}
        data = {
            "order_id": payload.get("order_id") or str(envelope["aggregate_id"]),
            "event_type": event_type,
            "occurred_at": envelope["occurred_at"],
        }
        repo = NotificationRepository(uow.connection)
        for user_id in recipients:
            repo.insert_notification(
                tenant_id=tenant_id,
                recipient_user_id=user_id,
                notification_type=event_type,
                data=data,
                inbox_consumer_name=CONSUMER_ORDER_LIFECYCLE,
                inbox_event_id=event_id,
            )
        # Cheap last-activity; same UoW already has app.role=worker for RLS.
        upsert_heartbeat(
            uow.connection,
            service_name="worker",
            details={"event_id": str(event_id), "notifications": len(recipients)},
        )
        return {
            "accepted": True,
            "duplicate": False,
            "event_id": str(event_id),
            "notifications": len(recipients),
        }


def record_final_failure(
    *,
    envelope: dict[str, Any] | None,
    error: BaseException,
    attempts: int,
    engine: Engine | None = None,
) -> None:
    """Insert failed_jobs. Raises if insert fails (caller must not ack)."""
    eng = engine or get_engine()
    tenant_id: UUID | None = None
    event_id: UUID | None = None
    if isinstance(envelope, dict):
        raw_tenant = envelope.get("tenant_id")
        raw_event = envelope.get("event_id")
        if raw_tenant is not None:
            try:
                tenant_id = UUID(str(raw_tenant))
            except (TypeError, ValueError):
                tenant_id = None
        if raw_event is not None:
            try:
                event_id = UUID(str(raw_event))
            except (TypeError, ValueError):
                event_id = None
    reason = type(error).__name__
    detail = str(error)[:200]
    record_failed_job(
        engine=eng,
        task_name=ORDER_LIFECYCLE_TASK,
        error_message=f"{reason}: {detail}",
        attempts=max(1, attempts),
        tenant_id=tenant_id,
        event_id=event_id,
        envelope=envelope if isinstance(envelope, dict) else None,
    )
