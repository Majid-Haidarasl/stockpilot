"""Retry helpers for deadlock / retryable transaction failures."""

from __future__ import annotations

import random
import time
from collections.abc import Callable

from sqlalchemy.exc import DBAPIError, OperationalError


def is_retryable_tx_error(exc: BaseException) -> bool:
    if isinstance(exc, OperationalError):
        return True
    if isinstance(exc, DBAPIError) and getattr(exc, "connection_invalidated", False):
        return True
    msg = str(exc).lower()
    return "deadlock" in msg or "serialization" in msg or "could not serialize" in msg


def retry_on_deadlock[T](fn: Callable[[], T], *, attempts: int = 3) -> T:
    """Retry the whole callable up to `attempts` times on deadlock-like errors."""
    last: BaseException | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:
            if not is_retryable_tx_error(exc) or attempt >= attempts - 1:
                raise
            last = exc
            time.sleep(0.01 + random.random() * 0.05)
    assert last is not None
    raise last
