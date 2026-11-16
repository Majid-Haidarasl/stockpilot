"""Consume-retry backoff (exponential + jitter), sibling to publish_failure_backoff."""

from __future__ import annotations

import random

_BASE_SECONDS = 2.0
_CAP_SECONDS = 300.0
_JITTER_RATIO = 0.2


def consume_backoff_seconds(
    attempt_count: int,
    *,
    rng: random.Random | None = None,
) -> float:
    """Seconds to wait before the next consume attempt.

    ``attempt_count`` is 1-based (first retry after failure uses 1).
    """
    if attempt_count < 1:
        attempt_count = 1
    exp = _BASE_SECONDS * (2 ** (attempt_count - 1))
    capped = min(exp, _CAP_SECONDS)
    generator = rng if rng is not None else random.Random()
    jitter = 1.0 + generator.uniform(-_JITTER_RATIO, _JITTER_RATIO)
    return float(max(0.1, capped * jitter))
