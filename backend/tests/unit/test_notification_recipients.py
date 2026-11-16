"""Recipient role sets for order lifecycle events."""

from __future__ import annotations

import pytest

from stockpilot.modules.notifications.application.recipients import recipient_roles_for_event


@pytest.mark.parametrize(
    ("event_type", "expected"),
    [
        ("OrderReserved", frozenset({"admin", "sales"})),
        ("OrderCancelled", frozenset({"admin", "sales"})),
        ("OrderShipped", frozenset({"admin", "sales"})),
        ("OrderExpired", frozenset({"admin", "sales"})),
        ("OrderConfirmed", frozenset({"admin", "sales", "warehouse"})),
    ],
)
def test_recipient_roles(event_type: str, expected: frozenset[str]) -> None:
    assert recipient_roles_for_event(event_type) == expected


def test_unknown_event_type_rejected() -> None:
    with pytest.raises(ValueError):
        recipient_roles_for_event("OrderSomethingElse")
