"""Testable clock port (UTC)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Return the current instant in UTC."""
        ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """Injectable clock for domain and scheduler tests."""

    def __init__(self, instant: datetime) -> None:
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=UTC)
        self._instant = instant

    def now(self) -> datetime:
        return self._instant

    def set(self, instant: datetime) -> None:
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=UTC)
        self._instant = instant

    def advance(self, *, seconds: float = 0) -> datetime:
        from datetime import timedelta

        self._instant = self._instant + timedelta(seconds=seconds)
        return self._instant
