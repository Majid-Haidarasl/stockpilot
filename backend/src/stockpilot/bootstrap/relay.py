"""Outbox Relay: short lease claim, publish with confirms, mark published."""

from __future__ import annotations

import logging
import os
import socket
import time
import uuid
from datetime import timedelta

from sqlalchemy import Engine, create_engine

from stockpilot.platform.heartbeats.store import upsert_heartbeat
from stockpilot.platform.outbox.claim import (
    ClaimedOutboxRow,
    claim_batch,
    mark_published_many,
    record_publish_failure,
)
from stockpilot.platform.outbox.envelope import build_envelope
from stockpilot.platform.outbox.mapping import UnknownEventTypeError, task_for_event_type
from stockpilot.platform.outbox.publisher import PublishRequest, publish_celery_tasks
from stockpilot.platform.settings import get_settings

logger = logging.getLogger("stockpilot.relay")


def _lease_owner() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


def run_once(
    *,
    database_url: str | None = None,
    broker_url: str,
    batch_size: int,
    lease_seconds: int,
    engine: Engine | None = None,
) -> int:
    """Claim and publish one batch. Returns number of successfully marked rows.

    Prefer passing a long-lived ``engine`` from the relay process. When only
    ``database_url`` is given (tests), a one-shot engine is created and disposed.
    """
    if engine is None:
        if not database_url:
            raise ValueError("database_url or engine is required")
        eng = create_engine(database_url, pool_pre_ping=True)
        own_engine = True
    else:
        eng = engine
        own_engine = False

    try:
        owner = _lease_owner()
        with eng.begin() as conn:
            claimed = claim_batch(
                conn,
                lease_owner=owner,
                lease_ttl=timedelta(seconds=lease_seconds),
                limit=batch_size,
            )
        if not claimed:
            return 0

        requests: list[PublishRequest] = []
        row_by_index: list[ClaimedOutboxRow] = []
        for row in claimed:
            try:
                task_name = task_for_event_type(row.event_type)
            except UnknownEventTypeError as exc:
                with eng.begin() as conn:
                    record_publish_failure(
                        conn,
                        event_id=row.event_id,
                        attempt_count=row.attempt_count,
                        error=str(exc),
                    )
                logger.warning("unknown_event_type event_id=%s error=%s", row.event_id, exc)
                continue
            envelope = build_envelope(
                event_id=row.event_id,
                event_type=row.event_type,
                event_version=row.event_version,
                tenant_id=row.tenant_id,
                aggregate_type=row.aggregate_type,
                aggregate_id=row.aggregate_id,
                occurred_at=row.created_at,
                payload=row.payload_json,
                trace_id=row.trace_id,
            )
            requests.append(PublishRequest(task_name=task_name, envelope=envelope))
            row_by_index.append(row)

        if not requests:
            return 0

        results = publish_celery_tasks(broker_url=broker_url, requests=requests)
        # Safety: mark published ONLY for results with ok=True (broker confirmed
        # that specific message and no basic.return). Returned / nacked /
        # unconfirmed / never-attempted rows stay unpublished for retry.
        ok_ids = []
        for row, result in zip(row_by_index, results, strict=True):
            if not result.ok:
                with eng.begin() as conn:
                    record_publish_failure(
                        conn,
                        event_id=row.event_id,
                        attempt_count=row.attempt_count,
                        error=result.error or "publish_failed",
                    )
                logger.warning(
                    "publish_failed event_id=%s error=%s",
                    row.event_id,
                    result.error,
                )
                continue
            ok_ids.append(row.event_id)

        published = 0
        if ok_ids:
            with eng.begin() as conn:
                mark_published_many(conn, event_ids=ok_ids)
            published = len(ok_ids)

        try:
            with eng.begin() as conn:
                upsert_heartbeat(conn, service_name="relay", details={"published": published})
        except Exception:  # noqa: BLE001 — heartbeat must not break relay
            logger.exception("relay_heartbeat_failed")
        return published
    finally:
        if own_engine:
            eng.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = get_settings()
    broker_url = os.environ.get("STOCKPILOT_CELERY_BROKER_URL")
    if not broker_url:
        raise SystemExit("STOCKPILOT_CELERY_BROKER_URL is required for relay")
    batch_size = settings.outbox_batch_size
    lease_seconds = settings.outbox_lease_seconds
    poll_seconds = settings.relay_poll_seconds
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    logger.info(
        "relay_started batch=%s lease_s=%s poll_s=%s",
        batch_size,
        lease_seconds,
        poll_seconds,
    )
    try:
        while True:
            try:
                n = run_once(
                    engine=engine,
                    broker_url=broker_url,
                    batch_size=batch_size,
                    lease_seconds=lease_seconds,
                )
                if n:
                    logger.info("relay_published count=%s", n)
                    # Keep pulling while backlog remains (still sleep briefly to yield).
                    if n >= batch_size:
                        continue
            except Exception:  # noqa: BLE001 — keep loop alive; surface next cycle
                logger.exception("relay_cycle_failed")
            time.sleep(poll_seconds)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
