"""Read-only ops metrics HTTP server (stockpilot_metrics role)."""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from stockpilot.platform.heartbeats.store import fetch_outbox_lag
from stockpilot.platform.observability.ops_metrics import (
    KNOWN_SERVICES,
    apply_scrape_snapshot,
    mark_scrape_failure,
    render_ops_metrics,
)

logger = logging.getLogger("stockpilot.ops_exporter")

DEFAULT_PORT = 9108
DEFAULT_INTERVAL = 15.0


def _metrics_engine() -> Engine:
    url = os.environ.get("STOCKPILOT_METRICS_DATABASE_URL")
    if not url:
        raise SystemExit("STOCKPILOT_METRICS_DATABASE_URL is required for ops-exporter")
    return create_engine(url, pool_pre_ping=True)


def fetch_failed_jobs_unreplayed(conn: Any) -> int:
    row = conn.execute(text("SELECT * FROM platform.failed_jobs_metrics()")).mappings().one()
    return int(row["unreplayed_count"] or 0)


def fetch_stale_reserved(conn: Any) -> int:
    row = (
        conn.execute(text("SELECT * FROM platform.stale_reserved_orders_metrics()"))
        .mappings()
        .one()
    )
    return int(row["stale_count"] or 0)


def fetch_heartbeats(conn: Any) -> dict[str, datetime | None]:
    rows = (
        conn.execute(
            text(
                """
                SELECT service_name, last_success_at
                FROM platform.heartbeats
                WHERE service_name = ANY(:names)
                """
            ),
            {"names": list(KNOWN_SERVICES)},
        )
        .mappings()
        .all()
    )
    found = {str(r["service_name"]): r["last_success_at"] for r in rows}
    return {name: found.get(name) for name in KNOWN_SERVICES}


def scrape_once(engine: Engine) -> None:
    with engine.connect() as conn:
        unpublished, oldest = fetch_outbox_lag(conn)
        failed = fetch_failed_jobs_unreplayed(conn)
        stale = fetch_stale_reserved(conn)
        heartbeats = fetch_heartbeats(conn)
    apply_scrape_snapshot(
        unpublished_count=unpublished,
        oldest_age_seconds=oldest,
        failed_jobs_unreplayed=failed,
        stale_reserved_orders=stale,
        heartbeats=heartbeats,
    )


def _poll_loop(engine: Engine, interval_seconds: float, stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            scrape_once(engine)
        except Exception:  # noqa: BLE001 — keep exporter up
            logger.exception("ops_exporter_scrape_failed")
            mark_scrape_failure()
        stop.wait(timeout=interval_seconds)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] != "/metrics":
            self.send_response(404)
            self.end_headers()
            return
        body = render_ops_metrics()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        logger.debug("ops_exporter_http " + format, *args)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    port = int(os.environ.get("STOCKPILOT_OPS_EXPORTER_PORT", str(DEFAULT_PORT)))
    interval = float(
        os.environ.get("STOCKPILOT_OPS_EXPORTER_INTERVAL_SECONDS", str(DEFAULT_INTERVAL))
    )
    engine = _metrics_engine()
    stop = threading.Event()
    try:
        scrape_once(engine)
    except Exception:  # noqa: BLE001
        logger.exception("ops_exporter_initial_scrape_failed")
        mark_scrape_failure()
    poller = threading.Thread(
        target=_poll_loop,
        args=(engine, interval, stop),
        name="ops-exporter-poll",
        daemon=True,
    )
    poller.start()
    server = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    logger.info("ops_exporter_listening port=%s interval=%s", port, interval)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        stop.set()
        server.shutdown()


if __name__ == "__main__":
    main()
