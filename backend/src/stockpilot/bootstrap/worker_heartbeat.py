"""Idle worker heartbeat: keep platform.heartbeats.worker fresh without messages."""

from __future__ import annotations

import logging
import threading
from typing import Any

from sqlalchemy.engine import Engine

from stockpilot.platform.heartbeats.store import upsert_service_heartbeat
from stockpilot.platform.persistence.db import get_engine
from stockpilot.platform.persistence.session_roles import SESSION_ROLE_WORKER

logger = logging.getLogger("stockpilot.worker_heartbeat")

DEFAULT_IDLE_INTERVAL_SECONDS = 60.0

_lock = threading.Lock()
_thread: threading.Thread | None = None
_stop = threading.Event()


def refresh_worker_heartbeat(
    engine: Engine | None = None,
    *,
    details: dict[str, Any] | None = None,
) -> None:
    """Upsert worker heartbeat with app.role=worker (RLS). Safe when idle."""
    eng = engine or get_engine()
    payload = details if details is not None else {"source": "idle"}
    upsert_service_heartbeat(
        eng,
        service_name="worker",
        role=SESSION_ROLE_WORKER,
        details=payload,
    )


def _loop(engine: Engine, interval_seconds: float) -> None:
    while not _stop.wait(timeout=interval_seconds):
        try:
            refresh_worker_heartbeat(engine, details={"source": "idle"})
        except Exception:  # noqa: BLE001 — never crash the worker process
            logger.exception("worker_idle_heartbeat_failed")


def start_idle_heartbeat_thread(
    *,
    engine: Engine | None = None,
    interval_seconds: float = DEFAULT_IDLE_INTERVAL_SECONDS,
) -> threading.Thread | None:
    """Start one daemon thread that refreshes the worker heartbeat while idle.

    Idempotent: a second call is a no-op. Interval must stay well under the
    180s stale alert threshold (default 60s).
    """
    global _thread
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")
    with _lock:
        if _thread is not None and _thread.is_alive():
            return _thread
        _stop.clear()
        eng = engine or get_engine()
        # Immediate pulse so a freshly started idle worker is not stale.
        try:
            refresh_worker_heartbeat(eng, details={"source": "idle_start"})
        except Exception:  # noqa: BLE001
            logger.exception("worker_idle_heartbeat_start_failed")
        t = threading.Thread(
            target=_loop,
            args=(eng, interval_seconds),
            name="stockpilot-worker-idle-heartbeat",
            daemon=True,
        )
        t.start()
        _thread = t
        return t


def stop_idle_heartbeat_thread(*, join_timeout: float = 2.0) -> None:
    """Stop the idle heartbeat thread (tests)."""
    global _thread
    with _lock:
        _stop.set()
        t = _thread
        _thread = None
    if t is not None and t.is_alive():
        t.join(timeout=join_timeout)
