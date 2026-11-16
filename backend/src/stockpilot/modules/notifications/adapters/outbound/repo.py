"""Notifications persistence (runtime role; RLS + least-privilege grants)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection


class NotificationRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def insert_notification(
        self,
        *,
        tenant_id: UUID,
        recipient_user_id: UUID,
        notification_type: str,
        data: dict[str, Any],
        inbox_consumer_name: str,
        inbox_event_id: UUID,
    ) -> UUID:
        notification_id = uuid4()
        self._conn.execute(
            text(
                """
                INSERT INTO notifications.notifications (
                  id, tenant_id, recipient_user_id, type, data,
                  inbox_consumer_name, inbox_event_id
                ) VALUES (
                  :id, :tenant_id, :recipient_user_id, :type, CAST(:data AS jsonb),
                  :inbox_consumer_name, :inbox_event_id
                )
                """
            ),
            {
                "id": str(notification_id),
                "tenant_id": str(tenant_id),
                "recipient_user_id": str(recipient_user_id),
                "type": notification_type,
                "data": json.dumps(data),
                "inbox_consumer_name": inbox_consumer_name,
                "inbox_event_id": str(inbox_event_id),
            },
        )
        return notification_id

    def list_for_recipient(
        self,
        *,
        tenant_id: UUID,
        recipient_user_id: UUID,
        limit: int,
        unread_only: bool,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> list[dict[str, Any]]:
        clauses = [
            "tenant_id = :tenant_id",
            "recipient_user_id = :recipient_user_id",
        ]
        params: dict[str, Any] = {
            "tenant_id": str(tenant_id),
            "recipient_user_id": str(recipient_user_id),
            "limit": limit,
        }
        if unread_only:
            clauses.append("read_at IS NULL")
        if cursor_created_at is not None and cursor_id is not None:
            clauses.append("(created_at, id) < (:cursor_created_at, :cursor_id)")
            params["cursor_created_at"] = cursor_created_at
            params["cursor_id"] = str(cursor_id)
        where = " AND ".join(clauses)
        rows = (
            self._conn.execute(
                text(
                    f"""
                    SELECT id, tenant_id, recipient_user_id, type, data,
                           read_at, created_at, inbox_event_id
                    FROM notifications.notifications
                    WHERE {where}
                    ORDER BY created_at DESC, id DESC
                    LIMIT :limit
                    """
                ),
                params,
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    def mark_read(
        self,
        *,
        tenant_id: UUID,
        recipient_user_id: UUID,
        notification_id: UUID,
    ) -> dict[str, Any] | None:
        row = (
            self._conn.execute(
                text(
                    """
                    UPDATE notifications.notifications
                    SET read_at = COALESCE(read_at, now())
                    WHERE id = :id
                      AND tenant_id = :tenant_id
                      AND recipient_user_id = :recipient_user_id
                    RETURNING id, tenant_id, recipient_user_id, type, data,
                              read_at, created_at, inbox_event_id
                    """
                ),
                {
                    "id": str(notification_id),
                    "tenant_id": str(tenant_id),
                    "recipient_user_id": str(recipient_user_id),
                },
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None
