"""Kombu publisher with confirms + mandatory + on_return (unroutable detection)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from kombu import Connection, Exchange, Producer, Queue
from kombu.exceptions import OperationalError

CELERY_EXCHANGE_NAME = "celery"
CELERY_ROUTING_KEY = "celery"
CELERY_QUEUE_NAME = "celery"


@dataclass(slots=True)
class PublishResult:
    task_id: str
    ok: bool
    error: str | None = None


def _celery_protocol_body(envelope: dict[str, Any]) -> list[Any]:
    # Celery protocol v2 body: [args, kwargs, embed]
    return [
        [envelope],
        {},
        {"callbacks": None, "errbacks": None, "chain": None, "chord": None},
    ]


def _publish_mandatory(
    *,
    broker_url: str,
    routing_key: str,
    body: Any,
    headers: dict[str, Any],
    task_id: str,
    declare_celery_queue: bool,
    connect_timeout: float,
) -> PublishResult:
    exchange = Exchange(CELERY_EXCHANGE_NAME, type="direct", durable=True)
    queue = Queue(
        CELERY_QUEUE_NAME,
        exchange=exchange,
        routing_key=CELERY_ROUTING_KEY,
        durable=True,
    )
    returned: list[str] = []

    def on_return(
        exception: BaseException | None,
        exchange_name: str | bytes | None,
        rk: str | bytes | None,
        message: Any,
    ) -> None:
        ex = exchange_name.decode() if isinstance(exchange_name, bytes) else str(exchange_name)
        key = rk.decode() if isinstance(rk, bytes) else str(rk)
        detail = str(exception) if exception else "unroutable"
        returned.append(f"basic.return exchange={ex} rk={key}: {detail}")

    try:
        with Connection(
            broker_url,
            connect_timeout=connect_timeout,
            transport_options={"confirm_publish": True},
        ) as conn:
            conn.ensure_connection(max_retries=1)
            channel = conn.default_channel
            if declare_celery_queue:
                queue(channel).declare()
            else:
                exchange(channel).declare()

            producer = Producer(channel, exchange=exchange, serializer="json")
            # Register return callback on the producer (kombu invokes this on basic.return).
            producer.on_return = on_return

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
            try:
                conn.drain_events(timeout=0.75)
            except Exception:  # noqa: BLE001 — idle timeout expected
                pass
    except OperationalError as exc:
        return PublishResult(task_id=task_id, ok=False, error=f"broker_operational: {exc}")
    except OSError as exc:
        return PublishResult(task_id=task_id, ok=False, error=f"broker_os: {exc}")
    except Exception as exc:  # noqa: BLE001 — surface to Relay failure path
        return PublishResult(task_id=task_id, ok=False, error=f"publish_failed: {exc}")

    if returned:
        return PublishResult(task_id=task_id, ok=False, error="; ".join(returned))
    return PublishResult(task_id=task_id, ok=True)


def publish_celery_task(
    *,
    broker_url: str,
    task_name: str,
    envelope: dict[str, Any],
    connect_timeout: float = 5.0,
) -> PublishResult:
    """Publish a named Celery task with publisher confirms and mandatory=True."""
    task_id = str(uuid4())
    headers = {
        "lang": "py",
        "task": task_name,
        "id": task_id,
        "root_id": task_id,
    }
    return _publish_mandatory(
        broker_url=broker_url,
        routing_key=CELERY_ROUTING_KEY,
        body=_celery_protocol_body(envelope),
        headers=headers,
        task_id=task_id,
        declare_celery_queue=True,
        connect_timeout=connect_timeout,
    )


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
    result = _publish_mandatory(
        broker_url=broker_url,
        routing_key="stockpilot.missing.route",
        body=_celery_protocol_body(envelope),
        headers=headers,
        task_id=task_id,
        declare_celery_queue=True,
        connect_timeout=connect_timeout,
    )
    if result.ok:
        # Broker accepted but we required a return — treat as unroutable for the test.
        return PublishResult(
            task_id=task_id,
            ok=False,
            error="unroutable: no queue bound for routing key stockpilot.missing.route",
        )
    return result
