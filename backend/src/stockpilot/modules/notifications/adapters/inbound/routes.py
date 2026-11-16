"""HTTP API for in-app notifications."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from stockpilot.modules.access.public import ActorContext, require_actor, require_csrf
from stockpilot.modules.notifications.adapters.outbound.repo import NotificationRepository
from stockpilot.platform.http.problems import problem
from stockpilot.platform.persistence.uow import UnitOfWork

router = APIRouter(tags=["notifications"])


class NotificationOut(BaseModel):
    id: str
    tenant_id: str
    type: str
    data: dict[str, Any] = Field(default_factory=dict)
    read_at: datetime | None = None
    created_at: datetime | None = None


def _row_out(row: dict[str, Any]) -> NotificationOut:
    data = row.get("data") or {}
    if not isinstance(data, dict):
        data = {}
    return NotificationOut(
        id=str(row["id"]),
        tenant_id=str(row["tenant_id"]),
        type=str(row["type"]),
        data=data,
        read_at=row.get("read_at"),
        created_at=row.get("created_at"),
    )


@router.get("/api/v1/tenants/{tenant_id}/notifications")
def list_notifications(
    tenant_id: UUID,
    actor: Annotated[ActorContext, Depends(require_actor)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    unread_only: Annotated[bool, Query()] = False,
    cursor_created_at: Annotated[datetime | None, Query()] = None,
    cursor_id: Annotated[UUID | None, Query()] = None,
) -> list[NotificationOut] | Any:
    with UnitOfWork(user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value) as uow:
        rows = NotificationRepository(uow.connection).list_for_recipient(
            tenant_id=tenant_id,
            recipient_user_id=actor.user_id,
            limit=limit,
            unread_only=unread_only,
            cursor_created_at=cursor_created_at,
            cursor_id=cursor_id,
        )
    return [_row_out(r) for r in rows]


@router.post("/api/v1/tenants/{tenant_id}/notifications/{notification_id}/read")
def mark_notification_read(
    tenant_id: UUID,
    notification_id: UUID,
    actor: Annotated[ActorContext, Depends(require_actor)],
    _: Annotated[Any, Depends(require_csrf)],
) -> NotificationOut | Any:
    with UnitOfWork(user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value) as uow:
        row = NotificationRepository(uow.connection).mark_read(
            tenant_id=tenant_id,
            recipient_user_id=actor.user_id,
            notification_id=notification_id,
        )
    if row is None:
        return problem(status=404, code="NOT_FOUND", title="Not found")
    return _row_out(row)
