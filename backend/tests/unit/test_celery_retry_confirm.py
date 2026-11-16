"""Concrete test: Celery retry must use confirm_publish; failed confirm must not ack."""

from __future__ import annotations

import inspect
from typing import Any
from unittest.mock import patch

import pytest
from amqp.exceptions import RecoverableConnectionError
from celery.app.task import Task

from stockpilot.bootstrap.celery_app import celery_app
from stockpilot.modules.notifications.adapters.inbound.tasks import deliver_order_lifecycle_event


def _real_task() -> Any:
    # Celery may wrap the task in PromiseProxy until first use.
    return deliver_order_lifecycle_event._get_current_object()


def test_retry_raises_when_retry_publish_confirm_fails() -> None:
    """Celery Task.retry republishes via apply_async on this app (confirm_publish=True).

    Simulate broker confirm failure on that republish path: the task must raise and must
    not return a success payload (acks_late ⇒ original delivery stays unacked).
    """
    assert celery_app.conf.broker_transport_options.get("confirm_publish") is True
    task = _real_task()
    assert task.app is celery_app

    envelope = {
        "event_id": "11111111-1111-1111-1111-111111111111",
        "event_type": "OrderReserved",
        "event_version": "v1",
        "tenant_id": "22222222-2222-2222-2222-222222222222",
        "aggregate_type": "order",
        "aggregate_id": "33333333-3333-3333-3333-333333333333",
        "occurred_at": "2026-11-16T12:00:00+00:00",
        "payload": {"order_id": "33333333-3333-3333-3333-333333333333"},
    }

    def retry_via_apply_async(self: Any, *args: Any, **kwargs: Any) -> Any:
        return self.apply_async(
            args=(),
            kwargs={"envelope": envelope},
            countdown=kwargs.get("countdown"),
        )

    with (
        patch(
            "stockpilot.modules.notifications.adapters.inbound.tasks.process_order_lifecycle_event",
            side_effect=RuntimeError("transient db blip"),
        ),
        patch.object(
            task,
            "apply_async",
            side_effect=RecoverableConnectionError("publisher confirm failed"),
        ) as mock_apply,
        patch.object(task.__class__, "retry", retry_via_apply_async),
    ):
        task.push_request(id="task-id", retries=0, hostname="test@worker")
        try:
            with pytest.raises(RecoverableConnectionError, match="publisher confirm failed"):
                task.run(envelope)
            mock_apply.assert_called()
        finally:
            task.pop_request()


def test_retry_uses_apply_async_which_inherits_confirm_publish() -> None:
    """retry() -> apply_async() on the same app that has confirm_publish=True."""
    opts: dict[str, Any] = dict(celery_app.conf.broker_transport_options or {})
    assert opts.get("confirm_publish") is True
    assert _real_task().app is celery_app
    source = inspect.getsource(Task.retry)
    assert "apply_async" in source
