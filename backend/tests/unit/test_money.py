"""Sample domain unit tests for Money (no network/database)."""

from __future__ import annotations

import pytest

from stockpilot.modules.sales.domain.money import Money, MoneyError


def test_add_same_currency() -> None:
    total = Money(1_250_000).add(Money(750_000))
    assert total == Money(2_000_000, "IRR")


def test_refuse_different_currencies() -> None:
    with pytest.raises(MoneyError, match="different currencies"):
        Money(100, "IRR").add(Money(100, "USD"))


def test_rejects_invalid_currency_code() -> None:
    with pytest.raises(MoneyError, match="Invalid currency code"):
        Money(100, "IR")
