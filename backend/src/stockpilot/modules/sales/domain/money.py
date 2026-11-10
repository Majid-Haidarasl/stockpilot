"""Integer money value object. See ADR-007."""

from __future__ import annotations

from dataclasses import dataclass


class MoneyError(ValueError):
    """Raised when money rules are violated."""


@dataclass(frozen=True, slots=True)
class Money:
    """Amount as a 64-bit integer with a currency code.

    v1 commercial flows only create ``IRR``. The value object still refuses
    summing different currencies so the rule is enforced in one place.
    """

    amount: int
    currency: str = "IRR"

    def __post_init__(self) -> None:
        if not isinstance(self.amount, int) or isinstance(self.amount, bool):
            raise MoneyError("Money.amount must be a plain int")
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise MoneyError(f"Invalid currency code: {self.currency}")

    def add(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise MoneyError(
                f"Cannot add different currencies: {self.currency} and {other.currency}"
            )
        return Money(self.amount + other.amount, self.currency)

    def __add__(self, other: object) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        return self.add(other)
