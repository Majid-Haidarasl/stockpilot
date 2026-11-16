"""Celery tasks for order-lifecycle notifications (Inbox + failed_jobs)."""

from __future__ import annotations

from typing import Any

from celery.exceptions import MaxRetriesExceededError, Reject

from stockpilot.bootstrap.celery_app import celery_app
from stockpilot.modules.notifications.adapters.outbound.consume_service import (
    process_order_lifecycle_event,
    record_final_failure,
)
from stockpilot.modules.notifications.application.errors import PermanentConsumeError
from stockpilot.platform.outbox.consume_backoff import consume_backoff_seconds
from stockpilot.platform.outbox.mapping import ORDER_LIFECYCLE_TASK

# Five consume attempts total => max_retries=4 after the first try.
_MAX_RETRIES = 4


@celery_app.task(  # type: ignore[untyped-decorator]
    name=ORDER_LIFECYCLE_TASK,
    bind=True,
    max_retries=_MAX_RETRIES,
    acks_late=True,
)
def deliver_order_lifecycle_event(self: Any, envelope: dict[str, Any]) -> dict[str, Any]:
    """Process envelope; ack only after Inbox commit or durable failed_jobs insert."""
    attempt = int(getattr(self.request, "retries", 0)) + 1
    try:
        if not isinstance(envelope, dict):
            raise PermanentConsumeError("Envelope must be an object")
        return process_order_lifecycle_event(envelope)
    except PermanentConsumeError as exc:
        env = envelope if isinstance(envelope, dict) else None
        try:
            record_final_failure(envelope=env, error=exc, attempts=attempt)
        except Exception:
            # failed_jobs insert failed — do not ack.
            raise
        return {"accepted": False, "failed": True, "reason": str(exc)}
    except Exception as exc:
        env = envelope if isinstance(envelope, dict) else None
        if attempt > _MAX_RETRIES + 1:
            # Defensive; Celery should have stopped earlier.
            try:
                record_final_failure(envelope=env, error=exc, attempts=attempt)
            except Exception:
                raise
            return {"accepted": False, "failed": True, "reason": str(exc)}
        try:
            countdown = consume_backoff_seconds(attempt)
            raise self.retry(exc=exc, countdown=countdown)
        except MaxRetriesExceededError:
            try:
                record_final_failure(
                    envelope=env,
                    error=exc,
                    attempts=_MAX_RETRIES + 1,
                )
            except Exception:
                # Do not ack if failure cannot be recorded.
                raise Reject(str(exc), requeue=True) from exc
            return {"accepted": False, "failed": True, "reason": str(exc)}
