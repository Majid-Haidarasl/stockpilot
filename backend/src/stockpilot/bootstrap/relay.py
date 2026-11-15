"""Outbox Relay: short lease claim, publish with confirms, mark published."""

from __future__ import annotations

import logging
import os
import socket
import time
import uuid
from datetime import timedelta

from sqlalchemy import create_engine

from stockpilot.platform.outbox.claim import claim_batch, mark_published, record_publish_failure
from stockpilot.platform.outbox.envelope import build_envelope
from stockpilot.platform.outbox.mapping import UnknownEventTypeError, task_for_event_type
from stockpilot.platform.outbox.publisher import publish_celery_task
from stockpilot.platform.settings import get_settings

logger = logging.getLogger("stockpilot.relay")


def _lease_owner() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


def run_once(
    *,
    database_url: str,
    broker_url: str,
    batch_size: int,
    lease_seconds: int,
) -> int:
    """Claim and publish one batch. Returns number of successfully marked rows."""
    engine = create_engine(database_url, pool_pre_ping=True)
    owner = _lease_owner()
    with engine.begin() as conn:
        claimed = claim_batch(
            conn,
            lease_owner=owner,
            lease_ttl=timedelta(seconds=lease_seconds),
            limit=batch_size,
        )
    published = 0
    for row in claimed:
        try:
            task_name = task_for_event_type(row.event_type)
        except UnknownEventTypeError as exc:
            with engine.begin() as conn:
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
        result = publish_celery_task(
            broker_url=broker_url,
            task_name=task_name,
            envelope=envelope,
        )
        if not result.ok:
            with engine.begin() as conn:
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

        with engine.begin() as conn:
            if mark_published(conn, event_id=row.event_id):
                published += 1
            else:
                # Peer already marked — at-least-once double publish possible; Inbox in 5.2.
                logger.info("already_published event_id=%s", row.event_id)
                published += 1
    return published


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = get_settings()
    broker_url = os.environ.get("STOCKPILOT_CELERY_BROKER_URL")
    if not broker_url:
        raise SystemExit("STOCKPILOT_CELERY_BROKER_URL is required for relay")
    batch_size = settings.outbox_batch_size
    lease_seconds = settings.outbox_lease_seconds
    poll_seconds = settings.relay_poll_seconds
    logger.info(
        "relay_started batch=%s lease_s=%s poll_s=%s",
        batch_size,
        lease_seconds,
        poll_seconds,
    )
    while True:
        try:
            n = run_once(
                database_url=settings.database_url,
                broker_url=broker_url,
                batch_size=batch_size,
                lease_seconds=lease_seconds,
            )
            if n:
                logger.info("relay_published count=%s", n)
        except Exception:  # noqa: BLE001 — keep loop alive; surface next cycle
            logger.exception("relay_cycle_failed")
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
