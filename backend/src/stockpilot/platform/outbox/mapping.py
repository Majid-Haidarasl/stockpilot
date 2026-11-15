"""Single event-type → Celery task mapping (integration-tested)."""

from __future__ import annotations

ORDER_LIFECYCLE_TASK = "stockpilot.notifications.deliver_order_lifecycle_event"

# All T11 order Outbox event types map to one notification task in v1.
EVENT_TO_TASK: dict[str, str] = {
    "OrderReserved": ORDER_LIFECYCLE_TASK,
    "OrderConfirmed": ORDER_LIFECYCLE_TASK,
    "OrderCancelled": ORDER_LIFECYCLE_TASK,
    "OrderShipped": ORDER_LIFECYCLE_TASK,
    "OrderExpired": ORDER_LIFECYCLE_TASK,
}

KNOWN_EVENT_TYPES: frozenset[str] = frozenset(EVENT_TO_TASK)


class UnknownEventTypeError(ValueError):
    """Raised when Relay cannot map an Outbox event_type to a Celery task."""


def task_for_event_type(event_type: str) -> str:
    try:
        return EVENT_TO_TASK[event_type]
    except KeyError as exc:
        raise UnknownEventTypeError(f"No Celery task mapped for event_type={event_type!r}") from exc
