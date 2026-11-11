"""Customer persistence."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection


class CustomerRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def list_customers(self, tenant_id: UUID) -> list[dict[str, Any]]:
        rows = (
            self._conn.execute(
                text(
                    """
                SELECT id, tenant_id, name, phone, email, notes, version, created_at, updated_at
                FROM sales.customers
                WHERE tenant_id = :tenant_id
                ORDER BY name
                """
                ),
                {"tenant_id": str(tenant_id)},
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    def create_customer(
        self,
        *,
        tenant_id: UUID,
        name: str,
        phone: str | None,
        email: str | None,
        notes: str | None,
    ) -> dict[str, Any]:
        customer_id = uuid4()
        row = (
            self._conn.execute(
                text(
                    """
                INSERT INTO sales.customers (id, tenant_id, name, phone, email, notes)
                VALUES (:id, :tenant_id, :name, :phone, :email, :notes)
                RETURNING id, tenant_id, name, phone, email, notes, version, created_at, updated_at
                """
                ),
                {
                    "id": str(customer_id),
                    "tenant_id": str(tenant_id),
                    "name": name,
                    "phone": phone,
                    "email": email,
                    "notes": notes,
                },
            )
            .mappings()
            .one()
        )
        return dict(row)

    def update_customer(
        self,
        *,
        tenant_id: UUID,
        customer_id: UUID,
        expected_version: int,
        name: str | None,
        phone: str | None,
        email: str | None,
        notes: str | None,
    ) -> dict[str, Any] | None:
        current = (
            self._conn.execute(
                text(
                    """
                SELECT id, version FROM sales.customers
                WHERE tenant_id = :tenant_id AND id = :id
                """
                ),
                {"tenant_id": str(tenant_id), "id": str(customer_id)},
            )
            .mappings()
            .first()
        )
        if current is None:
            return None
        if int(current["version"]) != expected_version:
            return {"__conflict__": True}

        row = (
            self._conn.execute(
                text(
                    """
                UPDATE sales.customers
                SET name = COALESCE(:name, name),
                    phone = COALESCE(:phone, phone),
                    email = COALESCE(:email, email),
                    notes = COALESCE(:notes, notes),
                    version = version + 1,
                    updated_at = now()
                WHERE tenant_id = :tenant_id AND id = :id AND version = :expected_version
                RETURNING id, tenant_id, name, phone, email, notes, version, created_at, updated_at
                """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "id": str(customer_id),
                    "expected_version": expected_version,
                    "name": name,
                    "phone": phone,
                    "email": email,
                    "notes": notes,
                },
            )
            .mappings()
            .first()
        )
        return dict(row) if row else {"__conflict__": True}

    def write_audit(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        action_type: str,
        entity_id: UUID,
        payload: dict[str, Any],
    ) -> None:
        self._conn.execute(
            text(
                """
                INSERT INTO platform.audit_log
                  (id, tenant_id, actor_user_id, action_type, entity_type, entity_id, payload_json)
                VALUES
                  (:id, :tenant_id, :actor_user_id, :action_type, 'customer', :entity_id,
                   CAST(:payload AS jsonb))
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "actor_user_id": str(actor_user_id),
                "action_type": action_type,
                "entity_id": str(entity_id),
                "payload": json.dumps(payload),
            },
        )
