"""Test-only hang hook for cut-point / killed-worker tests.

Active only when STOCKPILOT_ENVIRONMENT=test AND STOCKPILOT_TEST_HANG_EVENT_ID
matches the envelope event_id. Never configure the hang env var in Compose files.
"""

from __future__ import annotations

import os
import time
from typing import Any

from stockpilot.platform.settings import get_settings


def maybe_hang_after_commit(envelope: dict[str, Any]) -> None:
    """Block forever after a successful consume commit when hang env matches.

    No-op unless settings.environment == \"test\".
    """
    if get_settings().environment != "test":
        return
    hang_id = os.environ.get("STOCKPILOT_TEST_HANG_EVENT_ID", "").strip()
    if not hang_id:
        return
    event_id = str(envelope.get("event_id", ""))
    if event_id != hang_id:
        return
    # Intentional infinite wait so the worker can be killed before Celery acks.
    while True:
        time.sleep(3600)
