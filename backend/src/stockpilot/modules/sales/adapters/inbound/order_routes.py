"""Order draft CRUD and cycle commands (reserve/confirm/cancel/ship)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from stockpilot.modules.access.public import ActorContext, require_actor, require_csrf
from stockpilot.modules.inventory.public import (
    InactiveProduct,
    InsufficientStock,
    ReservationConflict,
)
from stockpilot.modules.sales.adapters.outbound.order_cycle import (
    OrderCycleService,
    OrderNotFound,
    VersionConflict,
)
from stockpilot.modules.sales.adapters.outbound.order_repo import OrderRepository
from stockpilot.modules.sales.domain.order import (
    DuplicateProductLine,
    InvalidLineQuantity,
    InvalidOrderState,
    Order,
    OrderLine,
    OrderNotEditable,
    TooManyOrderLines,
)
from stockpilot.platform.http.problems import problem
from stockpilot.platform.persistence.idempotency import (
    IdempotencyInProgress,
    IdempotencyKeyReused,
    IdempotencyStore,
    StoredResponse,
    fingerprint,
)
from stockpilot.platform.persistence.retry import retry_on_deadlock
from stockpilot.platform.persistence.uow import UnitOfWork

router = APIRouter(tags=["orders"])

_ALLOWED_STATUS_FILTERS = frozenset(
    {"DRAFT", "RESERVED", "CONFIRMED", "SHIPPED", "CANCELLED", "EXPIRED"}
)


class MoneyOut(BaseModel):
    amount: str
    currency: str = "IRR"


class OrderLineIn(BaseModel):
    product_id: UUID
    quantity: int = Field(ge=1, le=100_000)


class OrderLineOut(BaseModel):
    id: str
    product_id: str
    quantity: int
    product_sku: str
    product_title: str
    unit_price: MoneyOut


class OrderOut(BaseModel):
    id: str
    tenant_id: str
    customer_id: str
    status: str
    version: int
    lines: list[OrderLineOut]
    total: MoneyOut
    total_is_estimate: bool
    reserved_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class OrderListItemOut(BaseModel):
    id: str
    tenant_id: str
    customer_id: str
    status: str
    version: int
    created_at: datetime | None = None
    expires_at: datetime | None = None


class CreateOrderBody(BaseModel):
    customer_id: UUID
    lines: list[OrderLineIn] = Field(min_length=1, max_length=20)


class PatchOrderBody(BaseModel):
    expected_version: int
    customer_id: UUID | None = None
    lines: list[OrderLineIn] | None = Field(default=None, min_length=1, max_length=20)


class CycleBody(BaseModel):
    expected_version: int


CONTRACT_VERSION = "v1"


def _order_out(order: Order) -> OrderOut:
    total = order.total()
    return OrderOut(
        id=str(order.id),
        tenant_id=str(order.tenant_id),
        customer_id=str(order.customer_id),
        status=order.status.value,
        version=order.version,
        lines=[
            OrderLineOut(
                id=str(line.id),
                product_id=str(line.product_id),
                quantity=line.quantity,
                product_sku=line.product_sku,
                product_title=line.product_title,
                unit_price=MoneyOut(amount=str(line.unit_price_rial), currency=line.currency),
            )
            for line in order.lines
        ],
        total=MoneyOut(amount=str(total.amount), currency=total.currency),
        total_is_estimate=order.status.value == "DRAFT",
        reserved_at=order.reserved_at,
        expires_at=order.expires_at,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def _build_lines(
    *,
    tenant_id: UUID,
    items: list[OrderLineIn],
    orders: OrderRepository,
) -> list[OrderLine] | Any:
    lines: list[OrderLine] = []
    for item in items:
        product = orders.get_product_snapshot(tenant_id, item.product_id)
        if product is None:
            return problem(
                status=404,
                code="NOT_FOUND",
                title="Product not found",
                detail=str(item.product_id),
            )
        if not bool(product["is_active"]):
            return problem(
                status=409,
                code="PRODUCT_INACTIVE",
                title="Cannot add inactive product to a draft order",
                detail=str(product["sku"]),
            )
        lines.append(
            OrderLine(
                id=uuid4(),
                product_id=item.product_id,
                quantity=item.quantity,
                product_sku=str(product["sku"]),
                product_title=str(product["title"]),
                unit_price_rial=int(product["unit_price_rial"]),
                currency=str(product.get("currency") or "IRR"),
            )
        )
    return lines


@router.get("/api/v1/tenants/{tenant_id}/orders")
def list_orders(
    tenant_id: UUID,
    actor: Annotated[ActorContext, Depends(require_actor)],
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor_created_at: Annotated[datetime | None, Query()] = None,
    cursor_id: Annotated[UUID | None, Query()] = None,
) -> list[OrderListItemOut] | Any:
    if not actor.can_view_orders():
        return problem(status=403, code="FORBIDDEN", title="Forbidden")
    if status is not None and status not in _ALLOWED_STATUS_FILTERS:
        return problem(status=422, code="VALIDATION_ERROR", title="Invalid status filter")
    with UnitOfWork(user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value) as uow:
        rows = OrderRepository(uow.connection).list_orders(
            tenant_id,
            status=status,
            limit=limit,
            cursor_created_at=cursor_created_at,
            cursor_id=cursor_id,
        )
    return [
        OrderListItemOut(
            id=str(r["id"]),
            tenant_id=str(r["tenant_id"]),
            customer_id=str(r["customer_id"]),
            status=str(r["status"]),
            version=int(r["version"]),
            created_at=r.get("created_at"),
            expires_at=r.get("expires_at"),
        )
        for r in rows
    ]


@router.post("/api/v1/tenants/{tenant_id}/orders", status_code=201)
def create_order(
    tenant_id: UUID,
    body: CreateOrderBody,
    actor: Annotated[ActorContext, Depends(require_actor)],
    _: Annotated[Any, Depends(require_csrf)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> OrderOut | Any:
    _ = idempotency_key  # Hook for T11 idempotency store
    if not actor.can_edit_draft_orders():
        return problem(status=403, code="FORBIDDEN", title="Forbidden")
    with UnitOfWork(user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value) as uow:
        orders = OrderRepository(uow.connection)
        if not orders.customer_exists(tenant_id, body.customer_id):
            return problem(status=404, code="NOT_FOUND", title="Customer not found")
        built = _build_lines(tenant_id=tenant_id, items=body.lines, orders=orders)
        if not isinstance(built, list):
            return built
        try:
            order = Order.new_draft(tenant_id=tenant_id, customer_id=body.customer_id, lines=built)
        except (DuplicateProductLine, TooManyOrderLines, InvalidLineQuantity) as exc:
            return problem(status=422, code="VALIDATION_ERROR", title=str(exc))
        orders.insert_order(order)
        orders.write_audit(
            tenant_id=tenant_id,
            actor_user_id=actor.user_id,
            action_type="order.draft_created",
            entity_id=order.id,
            payload={"customer_id": str(body.customer_id), "lines": len(built)},
        )
        saved = orders.get_order(tenant_id, order.id)
    assert saved is not None
    return _order_out(saved)


@router.get("/api/v1/tenants/{tenant_id}/orders/{order_id}")
def get_order(
    tenant_id: UUID,
    order_id: UUID,
    actor: Annotated[ActorContext, Depends(require_actor)],
) -> OrderOut | Any:
    if not actor.can_view_orders():
        return problem(status=403, code="FORBIDDEN", title="Forbidden")
    with UnitOfWork(user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value) as uow:
        order = OrderRepository(uow.connection).get_order(tenant_id, order_id)
    if order is None:
        return problem(status=404, code="NOT_FOUND", title="Order not found")
    return _order_out(order)


@router.patch("/api/v1/tenants/{tenant_id}/orders/{order_id}")
def patch_order(
    tenant_id: UUID,
    order_id: UUID,
    body: PatchOrderBody,
    actor: Annotated[ActorContext, Depends(require_actor)],
    _: Annotated[Any, Depends(require_csrf)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> OrderOut | Any:
    _ = idempotency_key  # Hook for T11 idempotency store
    if not actor.can_edit_draft_orders():
        return problem(status=403, code="FORBIDDEN", title="Forbidden")
    with UnitOfWork(user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value) as uow:
        orders = OrderRepository(uow.connection)
        order = orders.get_order(tenant_id, order_id)
        if order is None:
            return problem(status=404, code="NOT_FOUND", title="Order not found")
        if order.version != body.expected_version:
            return problem(
                status=409,
                code="VERSION_CONFLICT",
                title="Order version conflict",
            )
        expected = order.version
        try:
            if body.customer_id is not None:
                if not orders.customer_exists(tenant_id, body.customer_id):
                    return problem(status=404, code="NOT_FOUND", title="Customer not found")
                order.set_customer(body.customer_id)
            if body.lines is not None:
                built = _build_lines(tenant_id=tenant_id, items=body.lines, orders=orders)
                if not isinstance(built, list):
                    return built
                order.replace_lines(built)
        except OrderNotEditable as exc:
            return problem(status=409, code="ORDER_NOT_EDITABLE", title=str(exc))
        except (DuplicateProductLine, TooManyOrderLines, InvalidLineQuantity) as exc:
            return problem(status=422, code="VALIDATION_ERROR", title=str(exc))
        if not orders.save_order(order, expected_version=expected):
            return problem(
                status=409,
                code="VERSION_CONFLICT",
                title="Order version conflict",
            )
        orders.write_audit(
            tenant_id=tenant_id,
            actor_user_id=actor.user_id,
            action_type="order.draft_updated",
            entity_id=order.id,
            payload={"expected_version": body.expected_version},
        )
        saved = orders.get_order(tenant_id, order.id)
    assert saved is not None
    return _order_out(saved)


def _cycle_response(result: Any) -> OrderOut | Any:
    if result.problem_code:
        return problem(
            status=result.http_status,
            code=result.problem_code,
            title=result.problem_title or result.problem_code,
            errors=result.problem_errors,
        )
    return _order_out(result.order)


def _run_cycle(
    *,
    tenant_id: UUID,
    order_id: UUID,
    actor: ActorContext,
    body: CycleBody,
    operation: str,
    idempotency_key: str | None,
    path: str,
    permission_ok: bool,
    work: Callable[[OrderCycleService], Any],
) -> Any:
    if not permission_ok:
        return problem(status=403, code="FORBIDDEN", title="Forbidden")
    if not idempotency_key:
        return problem(
            status=422,
            code="VALIDATION_ERROR",
            title="Idempotency-Key header is required",
        )
    fp = fingerprint(
        method="POST",
        path=path,
        contract_version=CONTRACT_VERSION,
        body=body.model_dump(mode="json"),
    )

    def once() -> Any:
        with UnitOfWork(
            user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value
        ) as uow:
            store = IdempotencyStore(uow.connection)
            try:
                prior = store.begin(
                    tenant_id=tenant_id,
                    user_id=actor.user_id,
                    operation=operation,
                    key=idempotency_key,
                    fp=fp,
                )
            except IdempotencyKeyReused:
                return problem(
                    status=409,
                    code="IDEMPOTENCY_KEY_REUSED",
                    title="Idempotency-Key reused with a different body",
                )
            except IdempotencyInProgress as exc:
                headers = {"Retry-After": str(exc.retry_after)}
                resp = problem(
                    status=409,
                    code="IDEMPOTENCY_IN_PROGRESS",
                    title="Request with this Idempotency-Key is still in progress",
                )
                for hk, hv in headers.items():
                    resp.headers[hk] = hv
                return resp
            if prior is not None:
                if prior.status >= 400:
                    return problem(
                        status=prior.status,
                        code=str(prior.body.get("code", "REPLAY")),
                        title=str(prior.body.get("title", "Replayed response")),
                        detail=prior.body.get("detail"),
                        errors=prior.body.get("errors"),
                    )
                return OrderOut.model_validate(prior.body)

            cycle = OrderCycleService(uow.connection)
            try:
                result = work(cycle)
            except OrderNotFound:
                return problem(status=404, code="NOT_FOUND", title="Order not found")
            except VersionConflict:
                return problem(status=409, code="VERSION_CONFLICT", title="Order version conflict")
            except InsufficientStock as exc:
                errors = [
                    {
                        "sku": s.sku,
                        "requested": s.requested,
                        "available": s.available,
                    }
                    for s in exc.shortfalls
                ]
                store.complete(
                    tenant_id=tenant_id,
                    user_id=actor.user_id,
                    operation=operation,
                    key=idempotency_key,
                    response=StoredResponse(
                        status=409,
                        body={
                            "code": "INSUFFICIENT_STOCK",
                            "title": "Insufficient stock for reservation",
                            "errors": errors,
                        },
                        headers={},
                    ),
                )
                return problem(
                    status=409,
                    code="INSUFFICIENT_STOCK",
                    title="Insufficient stock for reservation",
                    errors=errors,
                )
            except (InactiveProduct, InvalidOrderState, ReservationConflict) as exc:
                return problem(status=409, code="CONFLICT", title=str(exc))

            out = _cycle_response(result)
            if result.problem_code:
                store.complete(
                    tenant_id=tenant_id,
                    user_id=actor.user_id,
                    operation=operation,
                    key=idempotency_key,
                    response=StoredResponse(
                        status=result.http_status,
                        body={
                            "code": result.problem_code,
                            "title": result.problem_title,
                        },
                        headers={},
                    ),
                )
                return out
            payload = _order_out(result.order).model_dump(mode="json")
            store.complete(
                tenant_id=tenant_id,
                user_id=actor.user_id,
                operation=operation,
                key=idempotency_key,
                response=StoredResponse(status=200, body=payload, headers={}),
            )
            return out

    return retry_on_deadlock(once)


@router.post("/api/v1/tenants/{tenant_id}/orders/{order_id}/reserve")
def reserve_order(
    tenant_id: UUID,
    order_id: UUID,
    body: CycleBody,
    actor: Annotated[ActorContext, Depends(require_actor)],
    _: Annotated[Any, Depends(require_csrf)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> OrderOut | Any:
    path = f"/api/v1/tenants/{tenant_id}/orders/{order_id}/reserve"
    return _run_cycle(
        tenant_id=tenant_id,
        order_id=order_id,
        actor=actor,
        body=body,
        operation="orders.reserve",
        idempotency_key=idempotency_key,
        path=path,
        permission_ok=actor.can_reserve_orders(),
        work=lambda c: c.reserve(
            tenant_id=tenant_id,
            order_id=order_id,
            actor_user_id=actor.user_id,
            expected_version=body.expected_version,
        ),
    )


@router.post("/api/v1/tenants/{tenant_id}/orders/{order_id}/confirm")
def confirm_order(
    tenant_id: UUID,
    order_id: UUID,
    body: CycleBody,
    actor: Annotated[ActorContext, Depends(require_actor)],
    _: Annotated[Any, Depends(require_csrf)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> OrderOut | Any:
    path = f"/api/v1/tenants/{tenant_id}/orders/{order_id}/confirm"
    return _run_cycle(
        tenant_id=tenant_id,
        order_id=order_id,
        actor=actor,
        body=body,
        operation="orders.confirm",
        idempotency_key=idempotency_key,
        path=path,
        permission_ok=actor.can_confirm_orders(),
        work=lambda c: c.confirm(
            tenant_id=tenant_id,
            order_id=order_id,
            actor_user_id=actor.user_id,
            expected_version=body.expected_version,
        ),
    )


@router.post("/api/v1/tenants/{tenant_id}/orders/{order_id}/cancel")
def cancel_order(
    tenant_id: UUID,
    order_id: UUID,
    body: CycleBody,
    actor: Annotated[ActorContext, Depends(require_actor)],
    _: Annotated[Any, Depends(require_csrf)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> OrderOut | Any:
    path = f"/api/v1/tenants/{tenant_id}/orders/{order_id}/cancel"
    return _run_cycle(
        tenant_id=tenant_id,
        order_id=order_id,
        actor=actor,
        body=body,
        operation="orders.cancel",
        idempotency_key=idempotency_key,
        path=path,
        permission_ok=actor.can_cancel_orders(),
        work=lambda c: c.cancel(
            tenant_id=tenant_id,
            order_id=order_id,
            actor_user_id=actor.user_id,
            expected_version=body.expected_version,
        ),
    )


@router.post("/api/v1/tenants/{tenant_id}/orders/{order_id}/ship")
def ship_order(
    tenant_id: UUID,
    order_id: UUID,
    body: CycleBody,
    actor: Annotated[ActorContext, Depends(require_actor)],
    _: Annotated[Any, Depends(require_csrf)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> OrderOut | Any:
    path = f"/api/v1/tenants/{tenant_id}/orders/{order_id}/ship"
    return _run_cycle(
        tenant_id=tenant_id,
        order_id=order_id,
        actor=actor,
        body=body,
        operation="orders.ship",
        idempotency_key=idempotency_key,
        path=path,
        permission_ok=actor.can_ship_orders(),
        work=lambda c: c.ship(
            tenant_id=tenant_id,
            order_id=order_id,
            actor_user_id=actor.user_id,
            expected_version=body.expected_version,
        ),
    )
