"""SQL adapters for access module."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from stockpilot.modules.access.domain.models import Role


class AccessRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def upsert_user(
        self,
        *,
        issuer: str,
        subject: str,
        email: str | None,
        display_name: str | None,
    ) -> UUID:
        # Link bootstrap placeholder rows (same email) to the real Keycloak subject.
        if email:
            linked = self._conn.execute(
                text(
                    """
                    UPDATE access.users
                    SET subject = :subject,
                        display_name = COALESCE(:display_name, display_name),
                        updated_at = now()
                    WHERE issuer = :issuer
                      AND lower(email) = lower(:email)
                      AND subject <> :subject
                    RETURNING id
                    """
                ),
                {
                    "issuer": issuer,
                    "subject": subject,
                    "email": email,
                    "display_name": display_name,
                },
            ).first()
            if linked:
                return UUID(str(linked[0]))

        row = self._conn.execute(
            text(
                """
                INSERT INTO access.users (id, issuer, subject, email, display_name)
                VALUES (:id, :issuer, :subject, :email, :display_name)
                ON CONFLICT (issuer, subject) DO UPDATE
                  SET email = COALESCE(EXCLUDED.email, access.users.email),
                      display_name = COALESCE(EXCLUDED.display_name, access.users.display_name),
                      updated_at = now()
                RETURNING id
                """
            ),
            {
                "id": str(uuid4()),
                "issuer": issuer,
                "subject": subject,
                "email": email,
                "display_name": display_name,
            },
        ).one()
        return UUID(str(row[0]))

    def get_user_by_issuer_subject(self, issuer: str, subject: str) -> dict[str, Any] | None:
        row = (
            self._conn.execute(
                text(
                    """
                SELECT id, issuer, subject, email, display_name
                FROM access.users
                WHERE issuer = :issuer AND subject = :subject
                """
                ),
                {"issuer": issuer, "subject": subject},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def get_user(self, user_id: UUID) -> dict[str, Any] | None:
        row = (
            self._conn.execute(
                text(
                    """
                SELECT id, issuer, subject, email, display_name
                FROM access.users WHERE id = :id
                """
                ),
                {"id": str(user_id)},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def create_login_attempt(
        self,
        *,
        state: str,
        nonce: str,
        code_verifier: str,
        redirect_uri: str,
        return_to: str,
        expires_at: datetime,
    ) -> UUID:
        attempt_id = uuid4()
        self._conn.execute(
            text(
                """
                INSERT INTO access.login_attempts
                  (id, state, nonce, code_verifier, redirect_uri, return_to, expires_at)
                VALUES
                  (:id, :state, :nonce, :code_verifier, :redirect_uri, :return_to, :expires_at)
                """
            ),
            {
                "id": str(attempt_id),
                "state": state,
                "nonce": nonce,
                "code_verifier": code_verifier,
                "redirect_uri": redirect_uri,
                "return_to": return_to,
                "expires_at": expires_at,
            },
        )
        return attempt_id

    def consume_login_attempt(self, state: str) -> dict[str, Any] | None:
        row = (
            self._conn.execute(
                text(
                    """
                UPDATE access.login_attempts
                SET consumed_at = now()
                WHERE state = :state
                  AND consumed_at IS NULL
                  AND expires_at > now()
                RETURNING id, state, nonce, code_verifier, redirect_uri, return_to
                """
                ),
                {"state": state},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def create_session(
        self,
        *,
        user_id: UUID,
        session_token_hash: str,
        csrf_token_hash: str,
        encrypted_refresh_token: str | None,
        encrypted_id_token: str | None,
        expires_at: datetime,
        idle_expires_at: datetime,
    ) -> UUID:
        session_id = uuid4()
        self._conn.execute(
            text(
                """
                INSERT INTO access.sessions (
                  id, session_token_hash, user_id, csrf_token_hash,
                  encrypted_refresh_token, encrypted_id_token,
                  expires_at, idle_expires_at
                ) VALUES (
                  :id, :session_token_hash, :user_id, :csrf_token_hash,
                  :encrypted_refresh_token, :encrypted_id_token,
                  :expires_at, :idle_expires_at
                )
                """
            ),
            {
                "id": str(session_id),
                "session_token_hash": session_token_hash,
                "user_id": str(user_id),
                "csrf_token_hash": csrf_token_hash,
                "encrypted_refresh_token": encrypted_refresh_token,
                "encrypted_id_token": encrypted_id_token,
                "expires_at": expires_at,
                "idle_expires_at": idle_expires_at,
            },
        )
        return session_id

    def get_session_by_token_hash(self, token_hash: str) -> dict[str, Any] | None:
        row = (
            self._conn.execute(
                text(
                    """
                SELECT s.*, u.issuer, u.subject, u.email, u.display_name
                FROM access.sessions s
                JOIN access.users u ON u.id = s.user_id
                WHERE s.session_token_hash = :hash
                  AND s.revoked_at IS NULL
                  AND s.expires_at > now()
                  AND s.idle_expires_at > now()
                """
                ),
                {"hash": token_hash},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def touch_session(self, session_id: UUID, idle_expires_at: datetime) -> None:
        self._conn.execute(
            text(
                """
                UPDATE access.sessions
                SET last_seen_at = now(), idle_expires_at = :idle
                WHERE id = :id AND revoked_at IS NULL
                """
            ),
            {"id": str(session_id), "idle": idle_expires_at},
        )

    def revoke_session(self, session_id: UUID) -> None:
        self._conn.execute(
            text(
                """
                UPDATE access.sessions
                SET revoked_at = now()
                WHERE id = :id AND revoked_at IS NULL
                """
            ),
            {"id": str(session_id)},
        )

    def list_memberships_for_user(self, user_id: UUID) -> list[dict[str, Any]]:
        rows = (
            self._conn.execute(
                text(
                    """
                SELECT m.id, m.tenant_id, m.role, t.slug, t.name
                FROM access.memberships m
                JOIN access.tenants t ON t.id = m.tenant_id
                WHERE m.user_id = :user_id
                ORDER BY t.name
                """
                ),
                {"user_id": str(user_id)},
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    def get_membership(self, user_id: UUID, tenant_id: UUID) -> dict[str, Any] | None:
        row = (
            self._conn.execute(
                text(
                    """
                SELECT m.id, m.tenant_id, m.user_id, m.role, t.slug, t.name
                FROM access.memberships m
                JOIN access.tenants t ON t.id = m.tenant_id
                WHERE m.user_id = :user_id AND m.tenant_id = :tenant_id
                """
                ),
                {"user_id": str(user_id), "tenant_id": str(tenant_id)},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def ensure_tenant(self, *, slug: str, name: str) -> UUID:
        existing = self._conn.execute(
            text("SELECT id FROM access.tenants WHERE slug = :slug"),
            {"slug": slug},
        ).first()
        if existing:
            self._conn.execute(
                text(
                    """
                    UPDATE access.tenants
                    SET name = :name, updated_at = now()
                    WHERE id = :id
                    """
                ),
                {"id": str(existing[0]), "name": name},
            )
            return UUID(str(existing[0]))
        tenant_id = uuid4()
        self._conn.execute(
            text(
                """
                INSERT INTO access.tenants (id, slug, name)
                VALUES (:id, :slug, :name)
                """
            ),
            {"id": str(tenant_id), "slug": slug, "name": name},
        )
        return tenant_id

    def ensure_membership(self, *, tenant_id: UUID, user_id: UUID, role: Role) -> UUID:
        existing = self._conn.execute(
            text(
                """
                SELECT id FROM access.memberships
                WHERE tenant_id = :tenant_id AND user_id = :user_id
                """
            ),
            {"tenant_id": str(tenant_id), "user_id": str(user_id)},
        ).first()
        if existing:
            self._conn.execute(
                text(
                    """
                    UPDATE access.memberships
                    SET role = :role, updated_at = now()
                    WHERE id = :id
                    """
                ),
                {"id": str(existing[0]), "role": role.value},
            )
            return UUID(str(existing[0]))
        membership_id = uuid4()
        self._conn.execute(
            text(
                """
                INSERT INTO access.memberships (id, tenant_id, user_id, role)
                VALUES (:id, :tenant_id, :user_id, :role)
                """
            ),
            {
                "id": str(membership_id),
                "tenant_id": str(tenant_id),
                "user_id": str(user_id),
                "role": role.value,
            },
        )
        return membership_id

    def list_members(self, tenant_id: UUID) -> list[dict[str, Any]]:
        rows = (
            self._conn.execute(
                text(
                    """
                SELECT m.id, m.user_id, m.role, u.email, u.display_name, u.issuer, u.subject
                FROM access.memberships m
                JOIN access.users u ON u.id = m.user_id
                WHERE m.tenant_id = :tenant_id
                ORDER BY u.email NULLS LAST, u.subject
                """
                ),
                {"tenant_id": str(tenant_id)},
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    def count_admins(self, tenant_id: UUID) -> int:
        row = self._conn.execute(
            text(
                """
                SELECT COUNT(*) FROM access.memberships
                WHERE tenant_id = :tenant_id AND role = 'admin'
                """
            ),
            {"tenant_id": str(tenant_id)},
        ).one()
        return int(row[0])

    def lock_tenant(self, tenant_id: UUID) -> None:
        self._conn.execute(
            text("SELECT id FROM access.tenants WHERE id = :id FOR UPDATE"),
            {"id": str(tenant_id)},
        )

    def update_member_role(
        self, membership_id: UUID, tenant_id: UUID, role: Role
    ) -> dict[str, Any] | None:
        row = (
            self._conn.execute(
                text(
                    """
                UPDATE access.memberships
                SET role = :role, updated_at = now()
                WHERE id = :id AND tenant_id = :tenant_id
                RETURNING id, user_id, tenant_id, role
                """
                ),
                {"id": str(membership_id), "tenant_id": str(tenant_id), "role": role.value},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def write_audit(
        self,
        *,
        tenant_id: UUID | None,
        actor_user_id: UUID | None,
        action_type: str,
        entity_type: str,
        entity_id: UUID | None,
        payload: dict[str, Any],
    ) -> None:
        # Audit insert for bootstrap may happen without tenant RLS context.
        self._conn.execute(
            text(
                """
                INSERT INTO platform.audit_log
                  (id, tenant_id, actor_user_id, action_type, entity_type, entity_id, payload_json)
                VALUES
                  (:id, :tenant_id, :actor_user_id, :action_type, :entity_type, :entity_id,
                   CAST(:payload AS jsonb))
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id) if tenant_id else str(uuid4()),
                "actor_user_id": str(actor_user_id) if actor_user_id else None,
                "action_type": action_type,
                "entity_type": entity_type,
                "entity_id": str(entity_id) if entity_id else None,
                "payload": __import__("json").dumps(payload),
            },
        )


def utcnow() -> datetime:
    return datetime.now(UTC)
