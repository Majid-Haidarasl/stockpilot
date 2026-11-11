"""Organization member management."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from stockpilot.modules.access.adapters.inbound.deps import require_actor, require_csrf
from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.modules.access.domain.models import ActorContext, Role
from stockpilot.platform.http.problems import problem
from stockpilot.platform.persistence.uow import UnitOfWork

router = APIRouter(tags=["members"])


class PatchMemberBody(BaseModel):
    role: Literal["admin", "sales", "warehouse", "viewer"]
    expected_version: int | None = Field(default=None)


@router.get("/api/v1/tenants/{tenant_id}/members")
def list_members(
    tenant_id: UUID,
    actor: Annotated[ActorContext, Depends(require_actor)],
) -> list[dict[str, Any]] | Any:
    if actor.role != Role.ADMIN:
        return problem(
            status=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Admin role required",
        )
    with UnitOfWork(user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value) as uow:
        rows = AccessRepository(uow.connection).list_members(tenant_id)
    return [
        {
            "id": str(r["id"]),
            "user_id": str(r["user_id"]),
            "role": r["role"],
            "email": r.get("email"),
            "display_name": r.get("display_name"),
        }
        for r in rows
    ]


@router.patch("/api/v1/tenants/{tenant_id}/members/{member_id}")
def patch_member(
    tenant_id: UUID,
    member_id: UUID,
    body: PatchMemberBody,
    actor: Annotated[ActorContext, Depends(require_actor)],
    _: Annotated[Any, Depends(require_csrf)],
) -> dict[str, Any] | Any:
    if not actor.can_manage_members():
        return problem(
            status=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Admin role required",
        )

    new_role = Role(body.role)
    with UnitOfWork(user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value) as uow:
        repo = AccessRepository(uow.connection)
        repo.lock_tenant(tenant_id)
        members = repo.list_members(tenant_id)
        target = next((m for m in members if str(m["id"]) == str(member_id)), None)
        if target is None:
            return problem(status=404, code="NOT_FOUND", title="Not found")

        if (
            str(target["user_id"]) == str(actor.user_id)
            and target["role"] == Role.ADMIN.value
            and new_role != Role.ADMIN
        ):
            if repo.count_admins(tenant_id) <= 1:
                return problem(
                    status=409,
                    code="LAST_ADMIN",
                    title="Cannot remove the last admin",
                    detail="The last active admin cannot remove their own admin role.",
                )

        updated = repo.update_member_role(member_id, tenant_id, new_role)
        if updated is None:
            return problem(status=404, code="NOT_FOUND", title="Not found")
        repo.write_audit(
            tenant_id=tenant_id,
            actor_user_id=actor.user_id,
            action_type="membership.role_changed",
            entity_type="membership",
            entity_id=member_id,
            payload={"role": new_role.value},
        )
    return {
        "id": str(updated["id"]),
        "user_id": str(updated["user_id"]),
        "tenant_id": str(updated["tenant_id"]),
        "role": updated["role"],
    }
