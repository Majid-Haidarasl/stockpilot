"""Kombu publisher with confirms + mandatory + on_return (unroutable detection)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from kombu import Connection, Exchange, Producer, Queue
from kombu.exceptions import OperationalError

CELERY_EXCHANGE_NAME = "celery"
CELERY_ROUTING_KEY = "celery"
CELERY_QUEUE_NAME = "celery"

# Non-blocking poll for basic.return after each publish; short end-of-batch wait.
_RETURN_POLL_TIMEOUT_S = 0.0
_BATCH_RETURN_DRAIN_TIMEOUT_S = 0.15


@dataclass(slots=True)
class PublishResult:
    """Outcome for one message.

    ``ok`` is True only when the broker **confirmed** this publish
    (``confirm_publish``) and no ``basic.return`` was observed for its
    ``correlation_id`` / task id. Unconfirmed, nacked, returned, or
    never-attempted messages have ``ok=False``.
    """

    task_id: str
    ok: bool
    error: str | None = None


@dataclass(frozen=True, slots=True)
class PublishRequest:
    task_name: str
    envelope: dict[str, Any]


def _celery_protocol_body(envelope: dict[str, Any]) -> list[Any]:
    # Celery protocol v2 body: [args, kwargs, embed]
    return [
        [envelope],
        {},
        {"callbacks": None, "errbacks": None, "chain": None, "chord": None},
    ]


def _correlation_id_from_return_message(message: Any) -> str | None:
    if message is None:
        return None
    props = getattr(message, "properties", None)
    if isinstance(props, dict):
        corr = props.get("correlation_id")
        if corr:
            return str(corr)
    corr = getattr(message, "correlation_id", None)
    return str(corr) if corr else None


def _drain(conn: Connection, timeout: float) -> None:
    try:
        conn.drain_events(timeout=timeout)
    except Exception:  # noqa: BLE001 — idle timeout / no events expected
        pass


def _is_connection_failure(error: str | None) -> bool:
    if not error:
        return False
    return error.startswith(("broker_operational:", "broker_os:")) or error.startswith(
        "batch_aborted_after_connection_error:"
    )


def _open_celery_producer(
    broker_url: str,
    *,
    connect_timeout: float,
    declare_celery_queue: bool,
) -> tuple[Connection, Producer, dict[str, str]]:
    """Open a confirm-mode channel. Returns (conn, producer, returns_by_corr)."""
    exchange = Exchange(CELERY_EXCHANGE_NAME, type="direct", durable=True)
    queue = Queue(
        CELERY_QUEUE_NAME,
        exchange=exchange,
        routing_key=CELERY_ROUTING_KEY,
        durable=True,
    )
    returns_by_corr: dict[str, str] = {}

    def on_return(
        exception: BaseException | None,
        exchange_name: str | bytes | None,
        rk: str | bytes | None,
        message: Any,
    ) -> None:
        ex = exchange_name.decode() if isinstance(exchange_name, bytes) else str(exchange_name)
        key = rk.decode() if isinstance(rk, bytes) else str(rk)
        detail = str(exception) if exception else "unroutable"
        err = f"basic.return exchange={ex} rk={key}: {detail}"
        corr = _correlation_id_from_return_message(message)
        if corr:
            returns_by_corr[corr] = err
        else:
            returns_by_corr[f"__orphan_{len(returns_by_corr)}"] = err

    conn = Connection(
        broker_url,
        connect_timeout=connect_timeout,
        # Publisher confirms: producer.publish() waits for ack/nack.
        transport_options={"confirm_publish": True},
    )
    conn.ensure_connection(max_retries=1)
    opts = getattr(conn, "transport_options", None) or {}
    if opts.get("confirm_publish") is not True:
        raise RuntimeError("confirm_publish must be enabled for outbox batch publish")

    channel = conn.default_channel
    if declare_celery_queue:
        queue(channel).declare()
    else:
        exchange(channel).declare()
    producer = Producer(channel, exchange=exchange, serializer="json")
    producer.on_return = on_return
    return conn, producer, returns_by_corr


def _publish_one_confirmed(
    *,
    conn: Connection,
    producer: Producer,
    routing_key: str,
    body: Any,
    headers: dict[str, Any],
    task_id: str,
    returns_by_corr: dict[str, str],
    poll_timeout: float,
) -> PublishResult:
    """Publish one message; ok only after broker confirm and no return for task_id.

    With ``confirm_publish=True``, ``producer.publish`` blocks until the broker
    acks or nacks. A nack/connection error raises and yields ``ok=False``.
    """
    try:
        # Do not pass content_type/content_encoding with serializer=json —
        # that combination can leave the AMQP body as str and raise
        # struct.error: argument for 's' must be a bytes object.
        producer.publish(
            body,
            routing_key=routing_key,
            declare=[],
            mandatory=True,
            delivery_mode=2,
            correlation_id=task_id,
            headers=headers,
            retry=False,
        )
        # publish() returned => broker confirmed this delivery (confirm_publish).
        _drain(conn, poll_timeout)
    except OperationalError as exc:
        return PublishResult(task_id=task_id, ok=False, error=f"broker_operational: {exc}")
    except OSError as exc:
        return PublishResult(task_id=task_id, ok=False, error=f"broker_os: {exc}")
    except Exception as exc:  # noqa: BLE001 — nack / transport / serialize
        return PublishResult(task_id=task_id, ok=False, error=f"publish_failed: {exc}")

    if task_id in returns_by_corr:
        return PublishResult(task_id=task_id, ok=False, error=returns_by_corr.pop(task_id))
    return PublishResult(task_id=task_id, ok=True)


def _apply_late_returns(
    results: list[PublishResult], returns_by_corr: dict[str, str]
) -> list[PublishResult]:
    """Flip confirmed results that received a late basic.return (by correlation_id)."""
    out: list[PublishResult] = []
    for r in results:
        if r.ok and r.task_id in returns_by_corr:
            out.append(
                PublishResult(
                    task_id=r.task_id,
                    ok=False,
                    error=returns_by_corr.pop(r.task_id),
                )
            )
        else:
            out.append(r)
    return out


def publish_celery_tasks(
    *,
    broker_url: str,
    requests: Sequence[PublishRequest],
    connect_timeout: float = 5.0,
) -> list[PublishResult]:
    """Publish many Celery tasks on one confirm-mode AMQP connection.

    Marking outbox rows published is the caller's job and must use only
    ``result.ok`` ids (confirmed and not returned). On a mid-batch connection
    error, already-confirmed results stay ``ok=True``; the failing message and
    all never-attempted messages are ``ok=False``.
    """
    if not requests:
        return []
    try:
        conn, producer, returns_by_corr = _open_celery_producer(
            broker_url,
            connect_timeout=connect_timeout,
            declare_celery_queue=True,
        )
    except OperationalError as exc:
        err = f"broker_operational: {exc}"
        return [PublishResult(task_id=str(uuid4()), ok=False, error=err) for _ in requests]
    except OSError as exc:
        err = f"broker_os: {exc}"
        return [PublishResult(task_id=str(uuid4()), ok=False, error=err) for _ in requests]
    except Exception as exc:  # noqa: BLE001
        err = f"publish_failed: {exc}"
        return [PublishResult(task_id=str(uuid4()), ok=False, error=err) for _ in requests]

    results: list[PublishResult] = []
    aborted: str | None = None
    try:
        with conn:
            for req in requests:
                if aborted is not None:
                    results.append(PublishResult(task_id=str(uuid4()), ok=False, error=aborted))
                    continue
                task_id = str(uuid4())
                headers = {
                    "lang": "py",
                    "task": req.task_name,
                    "id": task_id,
                    "root_id": task_id,
                }
                one = _publish_one_confirmed(
                    conn=conn,
                    producer=producer,
                    routing_key=CELERY_ROUTING_KEY,
                    body=_celery_protocol_body(req.envelope),
                    headers=headers,
                    task_id=task_id,
                    returns_by_corr=returns_by_corr,
                    poll_timeout=_RETURN_POLL_TIMEOUT_S,
                )
                results.append(one)
                # Transport loss: do not attempt further publishes in this batch.
                if not one.ok and _is_connection_failure(one.error):
                    aborted = f"batch_aborted_after_connection_error: {one.error}"
            _drain(conn, _BATCH_RETURN_DRAIN_TIMEOUT_S)
            results = _apply_late_returns(results, returns_by_corr)
    except Exception as exc:  # noqa: BLE001 — connection drop outside publish()
        err = f"batch_aborted_after_connection_error: {exc}"
        while len(results) < len(requests):
            results.append(PublishResult(task_id=str(uuid4()), ok=False, error=err))
    return results


def publish_celery_task(
    *,
    broker_url: str,
    task_name: str,
    envelope: dict[str, Any],
    connect_timeout: float = 5.0,
) -> PublishResult:
    """Publish a named Celery task with publisher confirms and mandatory=True."""
    return publish_celery_tasks(
        broker_url=broker_url,
        requests=[PublishRequest(task_name=task_name, envelope=envelope)],
        connect_timeout=connect_timeout,
    )[0]


def publish_unroutable_for_test(
    *,
    broker_url: str,
    envelope: dict[str, Any],
    connect_timeout: float = 5.0,
) -> PublishResult:
    """Publish mandatory to Celery exchange with an unbound routing key."""
    task_id = str(uuid4())
    headers = {
        "lang": "py",
        "task": "stockpilot.notifications.deliver_order_lifecycle_event",
        "id": task_id,
        "root_id": task_id,
    }
    try:
        conn, producer, returns_by_corr = _open_celery_producer(
            broker_url,
            connect_timeout=connect_timeout,
            declare_celery_queue=True,
        )
    except Exception as exc:  # noqa: BLE001
        return PublishResult(task_id=task_id, ok=False, error=f"publish_failed: {exc}")

    with conn:
        result = _publish_one_confirmed(
            conn=conn,
            producer=producer,
            routing_key="stockpilot.missing.route",
            body=_celery_protocol_body(envelope),
            headers=headers,
            task_id=task_id,
            returns_by_corr=returns_by_corr,
            poll_timeout=0.75,  # allow time for basic.return in the unroutable test
        )
        _drain(conn, 0.75)
        if task_id in returns_by_corr and result.ok:
            result = PublishResult(task_id=task_id, ok=False, error=returns_by_corr.pop(task_id))
    if result.ok:
        return PublishResult(
            task_id=task_id,
            ok=False,
            error="unroutable: no queue bound for routing key stockpilot.missing.route",
        )
    return result
