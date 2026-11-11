"""Inventory HTTP API."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from stockpilot.modules.access.public import ActorContext, require_actor, require_csrf
from stockpilot.modules.inventory.adapters.outbound.repo import InventoryRepository
from stockpilot.modules.inventory.domain.models import (
    DEFAULT_WAREHOUSE,
    InvalidQuantity,
    StockInvariantViolation,
)
from stockpilot.platform.http.problems import problem
from stockpilot.platform.persistence.uow import UnitOfWork

router = APIRouter(tags=["inventory"])


class InventoryItemOut(BaseModel):
    product_id: str
    sku: str
    title: str
    warehouse_code: str
    on_hand: int
    reserved: int
    available: int
    stock_warning_threshold: int
    version: int


class MovementOut(BaseModel):
    id: str
    product_id: str
    sku: str
    title: str
    physical_delta: int
    reserved_delta: int
    reason: str
    reference: str | None
    created_at: str


class ReceiptBody(BaseModel):
    product_id: str
    quantity: int = Field(gt=0, le=1_000_000_000)
    reference: str = Field(min_length=1, max_length=200)
    warehouse_code: str = Field(default=DEFAULT_WAREHOUSE, max_length=64)


class AdjustmentBody(BaseModel):
    product_id: str
    quantity: int = Field(ge=-1_000_000_000, le=1_000_000_000)
    reason: str = Field(min_length=1, max_length=500)
    reference: str | None = Field(default=None, max_length=200)
    warehouse_code: str = Field(default=DEFAULT_WAREHOUSE, max_length=64)


def _position_out(row: dict[str, Any]) -> InventoryItemOut:
    on_hand = int(row["on_hand"])
    reserved = int(row["reserved"])
    return InventoryItemOut(
        product_id=str(row["product_id"]),
        sku=str(row["sku"]),
        title=str(row["title"]),
        warehouse_code=str(row["warehouse_code"]),
        on_hand=on_hand,
        reserved=reserved,
        available=on_hand - reserved,
        stock_warning_threshold=int(row["stock_warning_threshold"]),
        version=int(row["version"]),
    )


@router.get("/api/v1/tenants/{tenant_id}/inventory")
def list_inventory(
    tenant_id: UUID,
    actor: Annotated[ActorContext, Depends(require_actor)],
) -> list[InventoryItemOut]:
    with UnitOfWork(user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value) as uow:
        rows = InventoryRepository(uow.connection).list_positions(tenant_id)
    return [_position_out(r) for r in rows]


@router.get("/api/v1/tenants/{tenant_id}/inventory/movements")
def list_movements(
    tenant_id: UUID,
    actor: Annotated[ActorContext, Depends(require_actor)],
    product_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[MovementOut]:
    with UnitOfWork(user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value) as uow:
        rows = InventoryRepository(uow.connection).list_movements(
            tenant_id, product_id=product_id, limit=limit
        )
    return [
        MovementOut(
            id=str(r["id"]),
            product_id=str(r["product_id"]),
            sku=str(r["sku"]),
            title=str(r["title"]),
            physical_delta=int(r["physical_delta"]),
            reserved_delta=int(r["reserved_delta"]),
            reason=str(r["reason"]),
            reference=r.get("reference"),
            created_at=r["created_at"].isoformat(),
        )
        for r in rows
    ]


@router.post("/api/v1/tenants/{tenant_id}/inventory/receipts", status_code=201)
def create_receipt(
    tenant_id: UUID,
    body: ReceiptBody,
    actor: Annotated[ActorContext, Depends(require_actor)],
    _: Annotated[Any, Depends(require_csrf)],
) -> InventoryItemOut | Any:
    if not actor.can_manage_inventory():
        return problem(status=403, code="FORBIDDEN", title="Forbidden")
    try:
        product_uuid = UUID(body.product_id)
    except ValueError:
        return problem(status=422, code="INVALID_PRODUCT", title="Invalid product id")

    try:
        with UnitOfWork(
            user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value
        ) as uow:
            repo = InventoryRepository(uow.connection)
            if not repo.product_exists(tenant_id, product_uuid):
                return problem(status=404, code="NOT_FOUND", title="Not found")
            if repo.movement_exists(tenant_id, body.reference.strip()):
                return problem(
                    status=409,
                    code="IDEMPOTENCY_KEY_REUSED",
                    title="Receipt reference already used",
                )

            position = repo.ensure_position_for_update(
                tenant_id=tenant_id,
                product_id=product_uuid,
                warehouse_code=body.warehouse_code.strip() or DEFAULT_WAREHOUSE,
            )
            delta = position.apply_receipt(body.quantity)
            repo.save_position(position)
            repo.insert_movement(
                tenant_id=tenant_id,
                product_id=product_uuid,
                physical_delta=delta,
                reserved_delta=0,
                reason="receipt",
                reference=body.reference.strip(),
                actor_user_id=actor.user_id,
                warehouse_code=position.warehouse_code,
            )
            repo.write_audit(
                tenant_id=tenant_id,
                actor_user_id=actor.user_id,
                action_type="inventory.receipt",
                entity_id=position.id,
                payload={"product_id": body.product_id, "quantity": body.quantity},
            )
            rows = repo.list_positions(tenant_id)
    except (InvalidQuantity, StockInvariantViolation) as exc:
        return problem(status=409, code="STOCK_INVARIANT", title=str(exc))

    match = next((r for r in rows if str(r["product_id"]) == str(product_uuid)), None)
    if match is None:
        return problem(status=500, code="INTERNAL", title="Position missing after receipt")
    return _position_out(match)


@router.post("/api/v1/tenants/{tenant_id}/inventory/adjustments", status_code=201)
def create_adjustment(
    tenant_id: UUID,
    body: AdjustmentBody,
    actor: Annotated[ActorContext, Depends(require_actor)],
    _: Annotated[Any, Depends(require_csrf)],
) -> InventoryItemOut | Any:
    if not actor.can_manage_inventory():
        return problem(status=403, code="FORBIDDEN", title="Forbidden")
    if body.quantity == 0:
        return problem(status=422, code="INVALID_QUANTITY", title="Quantity cannot be zero")
    try:
        product_uuid = UUID(body.product_id)
    except ValueError:
        return problem(status=422, code="INVALID_PRODUCT", title="Invalid product id")

    try:
        with UnitOfWork(
            user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value
        ) as uow:
            repo = InventoryRepository(uow.connection)
            if not repo.product_exists(tenant_id, product_uuid):
                return problem(status=404, code="NOT_FOUND", title="Not found")
            reference = body.reference.strip() if body.reference else None
            if reference and repo.movement_exists(tenant_id, reference):
                return problem(
                    status=409,
                    code="IDEMPOTENCY_KEY_REUSED",
                    title="Adjustment reference already used",
                )
            position = repo.get_position_for_update(
                tenant_id,
                product_uuid,
                body.warehouse_code.strip() or DEFAULT_WAREHOUSE,
            )
            if position is None:
                if body.quantity < 0:
                    return problem(
                        status=409,
                        code="STOCK_INVARIANT",
                        title="No stock position to decrease",
                    )
                position = repo.ensure_position_for_update(
                    tenant_id=tenant_id,
                    product_id=product_uuid,
                    warehouse_code=body.warehouse_code.strip() or DEFAULT_WAREHOUSE,
                )

            delta = position.apply_adjustment(body.quantity)
            repo.save_position(position)
            repo.insert_movement(
                tenant_id=tenant_id,
                product_id=product_uuid,
                physical_delta=delta,
                reserved_delta=0,
                reason=body.reason.strip(),
                reference=reference,
                actor_user_id=actor.user_id,
                warehouse_code=position.warehouse_code,
            )
            repo.write_audit(
                tenant_id=tenant_id,
                actor_user_id=actor.user_id,
                action_type="inventory.adjustment",
                entity_id=position.id,
                payload={"product_id": body.product_id, "quantity": body.quantity},
            )
            rows = repo.list_positions(tenant_id)
    except (InvalidQuantity, StockInvariantViolation) as exc:
        return problem(status=409, code="STOCK_INVARIANT", title=str(exc))

    match = next((r for r in rows if str(r["product_id"]) == str(product_uuid)), None)
    if match is None:
        return problem(status=500, code="INTERNAL", title="Position missing after adjustment")
    return _position_out(match)
