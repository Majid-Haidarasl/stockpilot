"""Unit tests for consume retry backoff."""

from __future__ import annotations

import random

from stockpilot.platform.outbox.consume_backoff import consume_backoff_seconds


def test_consume_backoff_grows_and_caps() -> None:
    rng = random.Random(0)
    first = consume_backoff_seconds(1, rng=rng)
    later = consume_backoff_seconds(10, rng=rng)
    assert 1.0 <= first <= 3.0
    assert later <= 300.0 * 1.2


def test_celery_confirm_publish_enabled() -> None:
    from stockpilot.bootstrap.celery_app import celery_app

    opts = celery_app.conf.broker_transport_options or {}
    assert opts.get("confirm_publish") is True
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True
    assert celery_app.conf.worker_prefetch_multiplier == 1
    assert celery_app.conf.worker_enable_remote_control is False
    # AMQP broker heartbeat stays on; compose `--without-heartbeat` only
    # disables Celery worker *event* heartbeats (pidbox/events), not this.
    assert celery_app.conf.broker_heartbeat == 30.0
