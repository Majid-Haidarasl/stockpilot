"""Publish-failure lease backoff (exponential + jitter, capped)."""

from __future__ import annotations

import random
from datetime import timedelta

# Base 2s, doubles each attempt; cap 5 minutes; +/-20% jitter.
_BASE_SECONDS = 2.0
_CAP_SECONDS = 300.0
_JITTER_RATIO = 0.2


def publish_failure_backoff(
    attempt_count: int,
    *,
    rng: random.Random | None = None,
) -> timedelta:
    """Return lease extension after a failed/unroutable publish.

    ``attempt_count`` is the value after the claim bump (must be >= 1).
    """
    if attempt_count < 1:
        attempt_count = 1
    exp = _BASE_SECONDS * (2 ** (attempt_count - 1))
    capped = min(exp, _CAP_SECONDS)
    generator = rng if rng is not None else random.Random()
    jitter = 1.0 + generator.uniform(-_JITTER_RATIO, _JITTER_RATIO)
    seconds = max(0.1, capped * jitter)
    return timedelta(seconds=seconds)
