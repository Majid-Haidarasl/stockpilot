"""Celery application (worker uses this; Relay publishes via kombu onto the same topology)."""

from __future__ import annotations

import os

from celery import Celery

from stockpilot.platform.outbox.mapping import ORDER_LIFECYCLE_TASK

BROKER_URL_ENV = "STOCKPILOT_CELERY_BROKER_URL"


def create_celery_app(broker_url: str | None = None) -> Celery:
    url = broker_url or os.environ.get(BROKER_URL_ENV, "amqp://guest:guest@rabbitmq:5672//")
    app = Celery("stockpilot", broker=url)
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        task_default_queue="celery",
        task_default_exchange="celery",
        task_default_routing_key="celery",
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        broker_transport_options={"confirm_publish": True},
        # No result backend in v1 — business truth stays in PostgreSQL.
        result_backend=None,
        task_ignore_result=True,
        imports=("stockpilot.modules.notifications.adapters.inbound.tasks",),
    )
    return app


celery_app = create_celery_app()

# Re-export mapped name for discoverability / tests.
__all__ = ["ORDER_LIFECYCLE_TASK", "celery_app", "create_celery_app"]
