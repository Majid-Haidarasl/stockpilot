"""Idle worker heartbeat refresh keeps platform.heartbeats.worker fresh."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text

from stockpilot.bootstrap.scheduler_health import heartbeat_is_fresh
from stockpilot.bootstrap.worker_heartbeat import (
    refresh_worker_heartbeat,
    start_idle_heartbeat_thread,
    stop_idle_heartbeat_thread,
)
from stockpilot.platform.heartbeats.store import read_heartbeat

pytestmark = pytest.mark.skipif(
    not os.environ.get("STOCKPILOT_DATABASE_URL")
    or not os.environ.get("STOCKPILOT_MIGRATION_DATABASE_URL"),
    reason="Database URLs not configured",
)


def _runtime():
    return create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)


def _migrator():
    return create_engine(os.environ["STOCKPILOT_MIGRATION_DATABASE_URL"], pool_pre_ping=True)


def test_idle_worker_refresh_keeps_fresh_heartbeat() -> None:
    engine = _runtime()
    # Backdate worker row (or create stale via migrator).
    with _migrator().begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO platform.heartbeats (
                  service_name, last_success_at, details, updated_at
                ) VALUES (
                  'worker', now() - interval '10 minutes', '{}'::jsonb, now()
                )
                ON CONFLICT (service_name) DO UPDATE SET
                  last_success_at = EXCLUDED.last_success_at,
                  updated_at = now()
                """
            )
        )

    with engine.connect() as conn:
        before = read_heartbeat(conn, "worker")
    assert before is not None
    assert not heartbeat_is_fresh(
        last_success_at=before["last_success_at"],
        stale_seconds=180,
    )

    refresh_worker_heartbeat(engine, details={"source": "idle_test"})

    with engine.connect() as conn:
        after = read_heartbeat(conn, "worker")
    assert after is not None
    assert heartbeat_is_fresh(
        last_success_at=after["last_success_at"],
        stale_seconds=180,
    )
    assert after["details"].get("source") == "idle_test"


def test_idle_heartbeat_thread_refreshes_while_idle() -> None:
    engine = _runtime()
    stop_idle_heartbeat_thread()
    with _migrator().begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO platform.heartbeats (
                  service_name, last_success_at, details, updated_at
                ) VALUES (
                  'worker', :ts, '{}'::jsonb, now()
                )
                ON CONFLICT (service_name) DO UPDATE SET
                  last_success_at = EXCLUDED.last_success_at
                """
            ),
            {"ts": datetime.now(UTC) - timedelta(minutes=10)},
        )

    start_idle_heartbeat_thread(engine=engine, interval_seconds=0.2)
    try:
        deadline = time.time() + 3.0
        fresh = False
        while time.time() < deadline:
            with engine.connect() as conn:
                row = read_heartbeat(conn, "worker")
            if row is not None and heartbeat_is_fresh(
                last_success_at=row["last_success_at"],
                stale_seconds=180,
            ):
                fresh = True
                break
            time.sleep(0.1)
        assert fresh
    finally:
        stop_idle_heartbeat_thread()
