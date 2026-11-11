"""Product HTTP API."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from stockpilot.modules.access.public import ActorContext, Role, require_actor, require_csrf
from stockpilot.modules.catalog.adapters.outbound.repo import CatalogRepository
from stockpilot.platform.http.problems import problem
from stockpilot.platform.persistence.uow import UnitOfWork

router = APIRouter(tags=["products"])

MAX_PRICE = 10**12


class MoneyOut(BaseModel):
    amount: str
    currency: str = "IRR"


class ProductOut(BaseModel):
    id: str
    tenant_id: str
    sku: str
    title: str
    unit_price: MoneyOut
    is_active: bool
    stock_warning_threshold: int
    version: int


class CreateProductBody(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    unit_price_rial: str = Field(description="Integer rial as digit string")
    is_active: bool = True
    stock_warning_threshold: int = Field(default=0, ge=0)


class PatchProductBody(BaseModel):
    expected_version: int
    title: str | None = Field(default=None, min_length=1, max_length=200)
    unit_price_rial: str | None = None
    is_active: bool | None = None
    stock_warning_threshold: int | None = Field(default=None, ge=0)


def _parse_price(raw: str) -> int | Any:
    if not raw.isdigit():
        return problem(
            status=422,
            code="INVALID_MONEY",
            title="Invalid money",
            detail="unit_price_rial must be a string of decimal digits",
        )
    value = int(raw)
    if value > MAX_PRICE:
        return problem(
            status=422,
            code="PRICE_LIMIT",
            title="Price exceeds limit",
            detail=f"Maximum unit price is {MAX_PRICE} IRR",
        )
    return value


def _to_out(row: dict[str, Any]) -> ProductOut:
    return ProductOut(
        id=str(row["id"]),
        tenant_id=str(row["tenant_id"]),
        sku=str(row["sku"]),
        title=str(row["title"]),
        unit_price=MoneyOut(amount=str(row["unit_price_rial"]), currency=str(row["currency"])),
        is_active=bool(row["is_active"]),
        stock_warning_threshold=int(row["stock_warning_threshold"]),
        version=int(row["version"]),
    )


@router.get("/api/v1/tenants/{tenant_id}/products")
def list_products(
    tenant_id: UUID,
    actor: Annotated[ActorContext, Depends(require_actor)],
) -> list[ProductOut]:
    with UnitOfWork(user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value) as uow:
        rows = CatalogRepository(uow.connection).list_products(tenant_id)
    return [_to_out(r) for r in rows]


@router.post("/api/v1/tenants/{tenant_id}/products", status_code=201)
def create_product(
    tenant_id: UUID,
    body: CreateProductBody,
    actor: Annotated[ActorContext, Depends(require_actor)],
    _: Annotated[Any, Depends(require_csrf)],
) -> ProductOut | Any:
    if actor.role == Role.VIEWER or actor.role == Role.WAREHOUSE:
        return problem(status=403, code="FORBIDDEN", title="Forbidden")
    if not actor.can_manage_catalog_writes():
        return problem(status=403, code="FORBIDDEN", title="Forbidden")

    price = _parse_price(body.unit_price_rial)
    if not isinstance(price, int):
        return price
    if body.stock_warning_threshold and not actor.can_set_stock_warning_threshold():
        return problem(
            status=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Only admin can set stock warning threshold",
        )

    try:
        with UnitOfWork(
            user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value
        ) as uow:
            repo = CatalogRepository(uow.connection)
            row = repo.create_product(
                tenant_id=tenant_id,
                sku=body.sku.strip(),
                title=body.title.strip(),
                unit_price_rial=price,
                is_active=body.is_active,
                stock_warning_threshold=body.stock_warning_threshold,
            )
            repo.write_audit(
                tenant_id=tenant_id,
                actor_user_id=actor.user_id,
                action_type="product.created",
                entity_id=UUID(str(row["id"])),
                payload={"sku": body.sku},
            )
    except Exception:
        return problem(
            status=409,
            code="SKU_CONFLICT",
            title="SKU already exists in this organization",
        )
    return _to_out(row)


@router.patch("/api/v1/tenants/{tenant_id}/products/{product_id}")
def patch_product(
    tenant_id: UUID,
    product_id: UUID,
    body: PatchProductBody,
    actor: Annotated[ActorContext, Depends(require_actor)],
    _: Annotated[Any, Depends(require_csrf)],
) -> ProductOut | Any:
    if actor.role == Role.VIEWER:
        return problem(status=403, code="FORBIDDEN", title="Forbidden")
    if body.unit_price_rial is not None and actor.role == Role.WAREHOUSE:
        return problem(
            status=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Warehouse cannot change prices",
        )
    if body.unit_price_rial is not None and not actor.can_change_product_price():
        return problem(status=403, code="FORBIDDEN", title="Forbidden")
    if body.stock_warning_threshold is not None and not actor.can_set_stock_warning_threshold():
        return problem(status=403, code="FORBIDDEN", title="Forbidden")

    price: int | None = None
    if body.unit_price_rial is not None:
        parsed = _parse_price(body.unit_price_rial)
        if not isinstance(parsed, int):
            return parsed
        price = parsed

    with UnitOfWork(user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value) as uow:
        repo = CatalogRepository(uow.connection)
        result = repo.update_product(
            tenant_id=tenant_id,
            product_id=product_id,
            expected_version=body.expected_version,
            title=body.title,
            unit_price_rial=price,
            is_active=body.is_active,
            stock_warning_threshold=body.stock_warning_threshold,
        )
        if result is None:
            return problem(status=404, code="NOT_FOUND", title="Not found")
        if result.get("__conflict__"):
            return problem(
                status=409,
                code="VERSION_CONFLICT",
                title="Version conflict",
                detail="Reload the product and retry",
            )
        repo.write_audit(
            tenant_id=tenant_id,
            actor_user_id=actor.user_id,
            action_type="product.updated",
            entity_id=product_id,
            payload={"expected_version": body.expected_version},
        )
    return _to_out(result)
