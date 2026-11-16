"""Public contract for the access module."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.engine import Connection

from stockpilot.modules.access.adapters.inbound.deps import (
    SessionPrincipal,
    require_actor,
    require_csrf,
    require_session,
)
from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.modules.access.domain.models import (
    AccessError,
    ActorContext,
    Conflict,
    NotFound,
    PermissionDenied,
    Role,
)


def list_member_user_ids_for_roles(
    conn: Connection,
    tenant_id: UUID,
    roles: frozenset[str] | set[str],
) -> list[UUID]:
    """Return user ids with any of the given roles in the tenant (RLS applies)."""
    return AccessRepository(conn).list_user_ids_for_roles(tenant_id, roles)


def tenant_exists(conn: Connection, tenant_id: UUID) -> bool:
    return AccessRepository(conn).tenant_exists(tenant_id)


__all__ = [
    "AccessError",
    "ActorContext",
    "Conflict",
    "NotFound",
    "PermissionDenied",
    "Role",
    "SessionPrincipal",
    "list_member_user_ids_for_roles",
    "require_actor",
    "require_csrf",
    "require_session",
    "tenant_exists",
]
