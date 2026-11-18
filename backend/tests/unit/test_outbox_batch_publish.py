"""Batch publish: one connection, confirms, mid-batch abort, return handling."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

from stockpilot.platform.outbox.claim import mark_published_many
from stockpilot.platform.outbox.publisher import PublishRequest, publish_celery_tasks


def _requests(n: int) -> list[PublishRequest]:
    task = "stockpilot.notifications.deliver_order_lifecycle_event"
    return [PublishRequest(task_name=task, envelope={"i": i}) for i in range(n)]


def test_publish_celery_tasks_opens_one_connection_for_batch() -> None:
    requests = _requests(5)
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_producer = MagicMock()
    returns: dict[str, str] = {}

    with patch(
        "stockpilot.platform.outbox.publisher._open_celery_producer",
        return_value=(mock_conn, mock_producer, returns),
    ) as open_conn:
        results = publish_celery_tasks(broker_url="amqp://guest@localhost//", requests=requests)

    assert open_conn.call_count == 1
    assert len(results) == 5
    assert all(r.ok for r in results)
    assert mock_producer.publish.call_count == 5


def test_publish_celery_tasks_empty() -> None:
    assert publish_celery_tasks(broker_url="amqp://x", requests=[]) == []


def test_mark_published_many_empty() -> None:
    conn = MagicMock()
    assert mark_published_many(conn, event_ids=[]) == 0
    conn.execute.assert_not_called()


def test_returned_message_in_middle_of_batch_not_ok() -> None:
    """A basic.return for message 2 of 5 must yield ok=False only for that message."""
    requests = _requests(5)
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_producer = MagicMock()
    returns: dict[str, str] = {}
    call_n = {"n": 0}

    def publish_side_effect(*_a: object, **kwargs: object) -> None:
        call_n["n"] += 1
        corr = str(kwargs.get("correlation_id") or "")
        if call_n["n"] == 2:
            returns[corr] = "basic.return exchange=celery rk=celery: unroutable"

    mock_producer.publish.side_effect = publish_side_effect

    with patch(
        "stockpilot.platform.outbox.publisher._open_celery_producer",
        return_value=(mock_conn, mock_producer, returns),
    ):
        results = publish_celery_tasks(broker_url="amqp://guest@localhost//", requests=requests)

    assert len(results) == 5
    assert results[0].ok is True
    assert results[1].ok is False
    assert results[1].error is not None and "basic.return" in results[1].error
    assert results[2].ok is True
    assert results[3].ok is True
    assert results[4].ok is True


def test_connection_error_after_k_of_n_leaves_rest_unpublished() -> None:
    """After k confirmed publishes, a connection error must not mark N-k as ok."""
    n, k = 5, 3
    requests = _requests(n)
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_producer = MagicMock()
    returns: dict[str, str] = {}
    call_n = {"n": 0}

    def publish_side_effect(*_a: object, **_kwargs: object) -> None:
        call_n["n"] += 1
        if call_n["n"] > k:
            raise OSError("connection reset by peer")

    mock_producer.publish.side_effect = publish_side_effect

    with patch(
        "stockpilot.platform.outbox.publisher._open_celery_producer",
        return_value=(mock_conn, mock_producer, returns),
    ):
        results = publish_celery_tasks(broker_url="amqp://guest@localhost//", requests=requests)

    assert len(results) == n
    assert all(r.ok for r in results[:k])
    assert results[k].ok is False
    assert results[k].error is not None and "broker_os:" in results[k].error
    for r in results[k + 1 :]:
        assert r.ok is False
        assert r.error is not None
        assert "batch_aborted_after_connection_error" in r.error


def test_open_producer_requires_confirm_publish() -> None:
    from stockpilot.platform.outbox import publisher as pub

    fake_conn = MagicMock()
    fake_conn.transport_options = {"confirm_publish": False}
    fake_conn.default_channel = MagicMock()

    with (
        patch.object(pub, "Connection", return_value=fake_conn),
        patch.object(pub, "Exchange"),
        patch.object(pub, "Queue"),
        patch.object(pub, "Producer"),
    ):
        try:
            pub._open_celery_producer(
                "amqp://guest@localhost//",
                connect_timeout=1.0,
                declare_celery_queue=True,
            )
            raised = False
        except RuntimeError as exc:
            raised = True
            assert "confirm_publish" in str(exc)
    assert raised


def test_relay_marks_only_ok_results(monkeypatch: object) -> None:
    """mark_published_many receives only confirmed ids (unit of relay selection)."""
    from datetime import UTC, datetime

    from stockpilot.bootstrap import relay as relay_mod
    from stockpilot.platform.outbox.claim import ClaimedOutboxRow
    from stockpilot.platform.outbox.publisher import PublishResult

    eid_ok = uuid4()
    eid_bad = uuid4()
    now = datetime.now(UTC)
    rows = [
        ClaimedOutboxRow(
            event_id=eid_ok,
            tenant_id=uuid4(),
            event_type="OrderReserved",
            event_version="v1",
            aggregate_type="order",
            aggregate_id=uuid4(),
            payload_json={},
            trace_id=None,
            created_at=now,
            attempt_count=1,
        ),
        ClaimedOutboxRow(
            event_id=eid_bad,
            tenant_id=uuid4(),
            event_type="OrderReserved",
            event_version="v1",
            aggregate_type="order",
            aggregate_id=uuid4(),
            payload_json={},
            trace_id=None,
            created_at=now,
            attempt_count=1,
        ),
    ]

    marked: list[list] = []

    def fake_claim(*_a: object, **_k: object) -> list:
        return rows

    def fake_publish(**_k: object) -> list[PublishResult]:
        return [
            PublishResult(task_id="t1", ok=True),
            PublishResult(task_id="t2", ok=False, error="basic.return ..."),
        ]

    def fake_mark(_conn: object, *, event_ids: list) -> int:
        marked.append(list(event_ids))
        return len(event_ids)

    eng = MagicMock()
    # eng.begin() context manager yielding a mock connection
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=MagicMock())
    cm.__exit__ = MagicMock(return_value=False)
    eng.begin.return_value = cm

    monkeypatch.setattr(relay_mod, "claim_batch", fake_claim)
    monkeypatch.setattr(relay_mod, "publish_celery_tasks", fake_publish)
    monkeypatch.setattr(relay_mod, "mark_published_many", fake_mark)
    monkeypatch.setattr(relay_mod, "record_publish_failure", MagicMock())
    monkeypatch.setattr(relay_mod, "upsert_heartbeat", MagicMock())
    monkeypatch.setattr(relay_mod, "task_for_event_type", lambda _t: "task")
    monkeypatch.setattr(
        relay_mod,
        "build_envelope",
        lambda **_k: {"event_id": str(_k["event_id"])},
    )

    n = relay_mod.run_once(
        engine=eng,
        broker_url="amqp://x",
        batch_size=10,
        lease_seconds=30,
    )
    assert n == 1
    assert marked == [[eid_ok]]
