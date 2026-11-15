"""Unit tests for publish-failure lease backoff."""

from __future__ import annotations

import random
from datetime import timedelta

from stockpilot.platform.outbox.backoff import publish_failure_backoff


def test_backoff_grows_exponentially_until_cap() -> None:
    rng = random.Random(0)
    d1 = publish_failure_backoff(1, rng=rng)
    rng = random.Random(0)
    d2 = publish_failure_backoff(2, rng=rng)
    rng = random.Random(0)
    d3 = publish_failure_backoff(3, rng=rng)
    assert d1 < d2 < d3
    # Without jitter, attempt 1 → 2s, 2 → 4s, 8 → 256s capped at 300s.
    # With ±20% jitter, still well below / at cap.
    assert d1 < timedelta(seconds=3)
    assert d2 < timedelta(seconds=6)


def test_backoff_capped_at_five_minutes() -> None:
    rng = random.Random(42)
    delay = publish_failure_backoff(20, rng=rng)
    assert delay <= timedelta(seconds=300 * 1.2 + 0.01)
    assert delay >= timedelta(seconds=300 * 0.8 - 0.01)


def test_backoff_attempt_zero_treated_as_one() -> None:
    rng = random.Random(1)
    a = publish_failure_backoff(0, rng=rng)
    rng = random.Random(1)
    b = publish_failure_backoff(1, rng=rng)
    assert a == b
