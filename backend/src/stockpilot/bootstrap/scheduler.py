"""Reservation-expiry scheduler (tenant-scoped; no BYPASSRLS).

Processes one tenant at a time under the runtime app role with SET LOCAL
tenant context via UnitOfWork. Never uses migrator/owner/BYPASSRLS.
There is no public HTTP expire route.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.engine import Engine

from stockpilot.modules.sales.adapters.outbound.order_cycle import OrderCycleService
from stockpilot.modules.sales.adapters.outbound.order_repo import OrderRepository
from stockpilot.platform.persistence.uow import UnitOfWork
from stockpilot.platform.time.clock import Clock, SystemClock


@dataclass(slots=True)
class ExpireBatchResult:
    examined: int
    expired: int


class ReservationExpiryScheduler:
    """Expire RESERVED orders past expires_at, one tenant transaction at a time."""

    def __init__(
        self,
        *,
        engine: Engine,
        clock: Clock | None = None,
        runtime_user_id: UUID | None = None,
    ) -> None:
        self._engine = engine
        self._clock = clock or SystemClock()
        self._runtime_user_id = runtime_user_id

    def run_for_tenant(self, *, tenant_id: UUID, limit: int = 50) -> ExpireBatchResult:
        """Run expiry for a single tenant with SET LOCAL RLS context."""
        now = self._clock.now()
        with UnitOfWork(
            engine=self._engine,
            user_id=self._runtime_user_id,
            tenant_id=tenant_id,
            role="admin",
        ) as uow:
            orders = OrderRepository(uow.connection)
            ids = orders.list_expired_reserved(tenant_id, now=now, limit=limit)
            cycle = OrderCycleService(uow.connection, clock=self._clock)
            expired = 0
            for order_id in ids:
                cycle.expire(tenant_id=tenant_id, order_id=order_id, actor_user_id=None)
                expired += 1
            return ExpireBatchResult(examined=len(ids), expired=expired)

    def run_tenants(
        self, tenant_ids: list[UUID], *, limit_per_tenant: int = 50
    ) -> ExpireBatchResult:
        """Process tenants sequentially — never one cross-tenant owner session."""
        total_examined = 0
        total_expired = 0
        for tenant_id in tenant_ids:
            result = self.run_for_tenant(tenant_id=tenant_id, limit=limit_per_tenant)
            total_examined += result.examined
            total_expired += result.expired
        return ExpireBatchResult(examined=total_examined, expired=total_expired)
