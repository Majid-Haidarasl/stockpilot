"""Customer HTTP API."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from stockpilot.modules.access.public import ActorContext, require_actor, require_csrf
from stockpilot.modules.sales.adapters.outbound.customer_repo import CustomerRepository
from stockpilot.platform.http.problems import problem
from stockpilot.platform.persistence.uow import UnitOfWork

router = APIRouter(tags=["customers"])


class CustomerOut(BaseModel):
    id: str
    tenant_id: str
    name: str
    phone: str | None = None
    email: str | None = None
    notes: str | None = None
    version: int


class CreateCustomerBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)


class PatchCustomerBody(BaseModel):
    expected_version: int
    name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)


def _to_out(row: dict[str, Any]) -> CustomerOut:
    return CustomerOut(
        id=str(row["id"]),
        tenant_id=str(row["tenant_id"]),
        name=str(row["name"]),
        phone=row.get("phone"),
        email=row.get("email"),
        notes=row.get("notes"),
        version=int(row["version"]),
    )


@router.get("/api/v1/tenants/{tenant_id}/customers")
def list_customers(
    tenant_id: UUID,
    actor: Annotated[ActorContext, Depends(require_actor)],
) -> list[CustomerOut]:
    with UnitOfWork(user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value) as uow:
        rows = CustomerRepository(uow.connection).list_customers(tenant_id)
    return [_to_out(r) for r in rows]


@router.post("/api/v1/tenants/{tenant_id}/customers", status_code=201)
def create_customer(
    tenant_id: UUID,
    body: CreateCustomerBody,
    actor: Annotated[ActorContext, Depends(require_actor)],
    _: Annotated[Any, Depends(require_csrf)],
) -> CustomerOut | Any:
    if not actor.can_manage_customers():
        return problem(status=403, code="FORBIDDEN", title="Forbidden")
    with UnitOfWork(user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value) as uow:
        repo = CustomerRepository(uow.connection)
        row = repo.create_customer(
            tenant_id=tenant_id,
            name=body.name.strip(),
            phone=body.phone,
            email=body.email,
            notes=body.notes,
        )
        repo.write_audit(
            tenant_id=tenant_id,
            actor_user_id=actor.user_id,
            action_type="customer.created",
            entity_id=UUID(str(row["id"])),
            payload={"name": body.name},
        )
    return _to_out(row)


@router.patch("/api/v1/tenants/{tenant_id}/customers/{customer_id}")
def patch_customer(
    tenant_id: UUID,
    customer_id: UUID,
    body: PatchCustomerBody,
    actor: Annotated[ActorContext, Depends(require_actor)],
    _: Annotated[Any, Depends(require_csrf)],
) -> CustomerOut | Any:
    if not actor.can_manage_customers():
        return problem(status=403, code="FORBIDDEN", title="Forbidden")
    with UnitOfWork(user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value) as uow:
        repo = CustomerRepository(uow.connection)
        result = repo.update_customer(
            tenant_id=tenant_id,
            customer_id=customer_id,
            expected_version=body.expected_version,
            name=body.name,
            phone=body.phone,
            email=body.email,
            notes=body.notes,
        )
        if result is None:
            return problem(status=404, code="NOT_FOUND", title="Not found")
        if result.get("__conflict__"):
            return problem(status=409, code="VERSION_CONFLICT", title="Version conflict")
        repo.write_audit(
            tenant_id=tenant_id,
            actor_user_id=actor.user_id,
            action_type="customer.updated",
            entity_id=customer_id,
            payload={"expected_version": body.expected_version},
        )
    return _to_out(result)
