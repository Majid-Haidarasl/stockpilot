"""Recipient role sets for order lifecycle notifications."""

from __future__ import annotations

from stockpilot.platform.outbox.mapping import EVENT_TO_TASK

_BASE_ROLES: frozenset[str] = frozenset({"admin", "sales"})
_CONFIRMED_EXTRA: frozenset[str] = frozenset({"warehouse"})


def recipient_roles_for_event(event_type: str) -> frozenset[str]:
    if event_type not in EVENT_TO_TASK:
        raise ValueError(f"Unknown event type: {event_type}")
    if event_type == "OrderConfirmed":
        return _BASE_ROLES | _CONFIRMED_EXTRA
    return _BASE_ROLES
