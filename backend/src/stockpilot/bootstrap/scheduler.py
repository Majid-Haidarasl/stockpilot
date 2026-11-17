"""Reservation-expiry scheduler (tenant-scoped; no BYPASSRLS).

Processes one tenant at a time under the runtime app role with SET LOCAL
tenant context via UnitOfWork. Never uses migrator/owner/BYPASSRLS.
There is no public HTTP expire route.

Compose runs exactly one instance. Session-scoped pg_try_advisory_lock on a
dedicated connection neutralizes accidental concurrent copies.
"""

from __future__ import annotations

import logging
import signal
import time
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from stockpilot.modules.sales.adapters.outbound.order_cycle import OrderCycleService
from stockpilot.modules.sales.adapters.outbound.order_repo import OrderRepository
from stockpilot.platform.heartbeats.store import fetch_outbox_lag, upsert_heartbeat
from stockpilot.platform.persistence.session_roles import SESSION_ROLE_SCHEDULER
from stockpilot.platform.persistence.uow import UnitOfWork
from stockpilot.platform.settings import get_settings
from stockpilot.platform.time.clock import Clock, SystemClock

logger = logging.getLogger("stockpilot.scheduler")

# Session advisory lock key: hashtext('stockpilot.reservation_expiry')
ADVISORY_LOCK_KEY_SQL = "hashtext('stockpilot.reservation_expiry')"


@dataclass(slots=True)
class ExpireBatchResult:
    examined: int
    expired: int


@dataclass(slots=True)
class TickResult:
    lock_acquired: bool
    tenant_count: int = 0
    expired_count: int = 0
    failed_tenant_count: int = 0
    examined: int = 0
    unpublished_count: int | None = None
    oldest_unpublished_age_seconds: float | None = None


class ReservationExpiryScheduler:
    """Expire RESERVED orders past expires_at, one tenant transaction at a time."""

    def __init__(
        self,
        *,
        engine: Engine,
        clock: Clock | None = None,
        runtime_user_id: UUID | None = None,
        stop_flag: Callable[[], bool] | None = None,
    ) -> None:
        self._engine = engine
        self._clock = clock or SystemClock()
        self._runtime_user_id = runtime_user_id
        self._stop_flag = stop_flag or (lambda: False)

    def list_active_tenant_ids(self) -> list[UUID]:
        """Operational org list under role=scheduler (tenants_select_scheduler)."""
        with UnitOfWork(engine=self._engine, role=SESSION_ROLE_SCHEDULER) as uow:
            rows = uow.connection.execute(
                text("SELECT id FROM access.tenants ORDER BY id")
            ).fetchall()
            return [UUID(str(r[0])) for r in rows]

    def run_for_tenant(self, *, tenant_id: UUID, limit: int = 50) -> ExpireBatchResult:
        """Run expiry for a single tenant with SET LOCAL RLS context."""
        now = self._clock.now()
        with UnitOfWork(
            engine=self._engine,
            user_id=self._runtime_user_id,
            tenant_id=tenant_id,
            role=SESSION_ROLE_SCHEDULER,
        ) as uow:
            orders = OrderRepository(uow.connection)
            ids = orders.list_expired_reserved(tenant_id, now=now, limit=limit)
            cycle = OrderCycleService(uow.connection, clock=self._clock)
            expired = 0
            for order_id in ids:
                cycle.expire(tenant_id=tenant_id, order_id=order_id, actor_user_id=None)
                expired += 1
            return ExpireBatchResult(examined=len(ids), expired=expired)

    def run_tenants(self, tenant_ids: list[UUID], *, limit_per_tenant: int = 50) -> TickResult:
        """Process tenants sequentially with per-tenant error isolation."""
        total_examined = 0
        total_expired = 0
        failed = 0
        for tenant_id in tenant_ids:
            if self._stop_flag():
                logger.info("scheduler_stop_flag_set skipping_remaining_tenants")
                break
            try:
                result = self.run_for_tenant(tenant_id=tenant_id, limit=limit_per_tenant)
                total_examined += result.examined
                total_expired += result.expired
            except Exception:  # noqa: BLE001 — isolate tenant; continue others
                failed += 1
                logger.exception(
                    "scheduler_tenant_failed",
                    extra={"tenant_id": str(tenant_id)},
                )
        return TickResult(
            lock_acquired=True,
            tenant_count=len(tenant_ids),
            expired_count=total_expired,
            failed_tenant_count=failed,
            examined=total_examined,
        )


def try_advisory_lock(conn: Connection) -> bool:
    row = conn.execute(text(f"SELECT pg_try_advisory_lock({ADVISORY_LOCK_KEY_SQL})")).scalar()
    return bool(row)


def advisory_unlock(conn: Connection) -> bool:
    row = conn.execute(text(f"SELECT pg_advisory_unlock({ADVISORY_LOCK_KEY_SQL})")).scalar()
    return bool(row)


def _lock_connection_alive(conn: Connection) -> bool:
    try:
        conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False


def run_tick(
    *,
    engine: Engine,
    clock: Clock | None = None,
    limit_per_tenant: int = 50,
    stop_flag: Callable[[], bool] | None = None,
    record_heartbeat: bool = True,
) -> TickResult:
    """One scheduler tick: dedicated lock connection + tenant loop + heartbeat."""
    lock_conn = engine.connect()
    acquired = False
    try:
        acquired = try_advisory_lock(lock_conn)
        if not acquired:
            return TickResult(lock_acquired=False)

        if not _lock_connection_alive(lock_conn):
            logger.error("scheduler_lock_connection_lost_before_work")
            return TickResult(lock_acquired=False)

        scheduler = ReservationExpiryScheduler(engine=engine, clock=clock, stop_flag=stop_flag)
        tenant_ids = scheduler.list_active_tenant_ids()

        if not _lock_connection_alive(lock_conn):
            logger.error("scheduler_lock_connection_lost_abort_tick")
            return TickResult(lock_acquired=True, tenant_count=len(tenant_ids))

        result = scheduler.run_tenants(tenant_ids, limit_per_tenant=limit_per_tenant)

        if not _lock_connection_alive(lock_conn):
            logger.error("scheduler_lock_connection_lost_after_tenants")
            return result

        unpublished_count: int | None = None
        oldest_age: float | None = None
        if record_heartbeat:
            with engine.begin() as hb_conn:
                hb_conn.execute(
                    text("SELECT set_config('app.role', :v, true)"),
                    {"v": SESSION_ROLE_SCHEDULER},
                )
                unpublished_count, oldest_age = fetch_outbox_lag(hb_conn)
                upsert_heartbeat(
                    hb_conn,
                    service_name="scheduler",
                    details={
                        "expired_count": result.expired_count,
                        "failed_tenant_count": result.failed_tenant_count,
                        "tenant_count": result.tenant_count,
                        "unpublished_count": unpublished_count,
                        "oldest_unpublished_age_seconds": oldest_age,
                    },
                )
        result.unpublished_count = unpublished_count
        result.oldest_unpublished_age_seconds = oldest_age
        return result
    finally:
        if acquired:
            try:
                advisory_unlock(lock_conn)
            except Exception:  # noqa: BLE001
                logger.exception("scheduler_advisory_unlock_failed")
        lock_conn.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = get_settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    interval = settings.scheduler_interval_seconds
    stop = {"flag": False}

    def _handle_stop(signum: int, _frame: object) -> None:
        logger.info("scheduler_signal_received signal=%s", signum)
        stop["flag"] = True

    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    logger.info("scheduler_started interval_s=%s", interval)
    while not stop["flag"]:
        try:
            result = run_tick(
                engine=engine,
                stop_flag=lambda: stop["flag"],
            )
            if result.lock_acquired:
                logger.info(
                    "scheduler_tick expired=%s failed_tenants=%s tenants=%s unpublished=%s",
                    result.expired_count,
                    result.failed_tenant_count,
                    result.tenant_count,
                    result.unpublished_count,
                )
            else:
                logger.info("scheduler_tick lock_not_acquired")
        except Exception:  # noqa: BLE001 — keep loop alive
            logger.exception("scheduler_tick_failed")

        if stop["flag"]:
            break
        # Interruptible sleep so SIGTERM is noticed promptly.
        deadline = time.monotonic() + interval
        while time.monotonic() < deadline and not stop["flag"]:
            time.sleep(0.5)

    logger.info("scheduler_stopped")
    raise SystemExit(0)


if __name__ == "__main__":
    main()
