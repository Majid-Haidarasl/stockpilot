"""Compose healthcheck: scheduler heartbeat freshness."""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime

from sqlalchemy import create_engine

from stockpilot.platform.heartbeats.store import read_heartbeat
from stockpilot.platform.settings import get_settings

logger = logging.getLogger("stockpilot.scheduler_health")


def heartbeat_is_fresh(
    *,
    last_success_at: datetime | None,
    stale_seconds: float,
    now: datetime | None = None,
) -> bool:
    if last_success_at is None:
        return False
    clock = now or datetime.now(UTC)
    if last_success_at.tzinfo is None:
        last = last_success_at.replace(tzinfo=UTC)
    else:
        last = last_success_at
    age = (clock - last).total_seconds()
    return age <= stale_seconds


def check(*, database_url: str, stale_seconds: float) -> int:
    """Return 0 if healthy, 1 otherwise."""
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            # SELECT policy is open; no app.role required for read.
            row = read_heartbeat(conn, "scheduler")
    except Exception:  # noqa: BLE001
        logger.exception("scheduler_health_db_error")
        return 1
    finally:
        engine.dispose()

    last = None if row is None else row.get("last_success_at")
    if not isinstance(last, datetime):
        last = None
    if heartbeat_is_fresh(last_success_at=last, stale_seconds=stale_seconds):
        return 0
    return 1


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    settings = get_settings()
    code = check(
        database_url=settings.database_url,
        stale_seconds=settings.scheduler_heartbeat_stale_seconds,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
