"""Insert Inbox rows with uniqueness on (consumer_name, event_id)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

CONSUMER_ORDER_LIFECYCLE = "notifications.order_lifecycle"


def try_insert_inbox(
    conn: Connection,
    *,
    consumer_name: str,
    event_id: UUID,
    tenant_id: UUID,
) -> bool:
    """Insert Inbox row. Returns True if this is the first insert, False if duplicate."""
    row = conn.execute(
        text(
            """
            INSERT INTO platform.inbox (consumer_name, event_id, tenant_id)
            VALUES (:consumer_name, :event_id, :tenant_id)
            ON CONFLICT (consumer_name, event_id) DO NOTHING
            RETURNING event_id
            """
        ),
        {
            "consumer_name": consumer_name,
            "event_id": str(event_id),
            "tenant_id": str(tenant_id),
        },
    ).first()
    return row is not None
