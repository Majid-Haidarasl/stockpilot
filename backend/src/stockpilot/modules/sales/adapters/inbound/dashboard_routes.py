"""Limited tenant dashboard read API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from stockpilot.modules.access.public import ActorContext, require_actor
from stockpilot.modules.sales.adapters.outbound.dashboard_queries import DashboardQueries
from stockpilot.platform.http.problems import problem
from stockpilot.platform.persistence.uow import UnitOfWork

router = APIRouter(tags=["dashboard"])

_STATUSES = ("DRAFT", "RESERVED", "CONFIRMED", "SHIPPED", "CANCELLED", "EXPIRED")


class MoneyOut(BaseModel):
    amount: str
    currency: str = "IRR"


class LowStockItemOut(BaseModel):
    product_id: str
    sku: str
    title: str
    available: int
    stock_warning_threshold: int


class DashboardOut(BaseModel):
    order_counts_by_status: dict[str, int] = Field(
        description="Counts for each order status in the tenant",
    )
    shipped_total: MoneyOut
    low_stock: list[LowStockItemOut]
    range_from: datetime
    range_to: datetime


@router.get("/api/v1/tenants/{tenant_id}/dashboard")
def get_dashboard(
    tenant_id: UUID,
    actor: Annotated[ActorContext, Depends(require_actor)],
    range_from: Annotated[datetime, Query(alias="from")],
    range_to: Annotated[datetime, Query(alias="to")],
) -> DashboardOut | Any:
    if not actor.can_view_orders():
        return problem(status=403, code="FORBIDDEN", title="Forbidden")
    if range_from > range_to:
        return problem(
            status=422,
            code="VALIDATION_ERROR",
            title="Invalid date range",
            detail="from must be less than or equal to to",
        )

    with UnitOfWork(user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value) as uow:
        queries = DashboardQueries(uow.connection)
        counts_raw = queries.order_counts_by_status(tenant_id)
        shipped_amount = queries.shipped_total_rial(
            tenant_id, range_from=range_from, range_to=range_to
        )
        low = queries.products_below_threshold(tenant_id)

    counts = {status: int(counts_raw.get(status, 0)) for status in _STATUSES}
    return DashboardOut(
        order_counts_by_status=counts,
        shipped_total=MoneyOut(amount=str(shipped_amount), currency="IRR"),
        low_stock=[
            LowStockItemOut(
                product_id=str(row["product_id"]),
                sku=str(row["sku"]),
                title=str(row["title"]),
                available=int(row["available"]),
                stock_warning_threshold=int(row["stock_warning_threshold"]),
            )
            for row in low
        ],
        range_from=range_from,
        range_to=range_to,
    )
