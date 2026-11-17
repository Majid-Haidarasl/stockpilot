"""Hang hook must be a no-op outside STOCKPILOT_ENVIRONMENT=test."""

from __future__ import annotations

from uuid import uuid4

from stockpilot.modules.notifications.adapters.inbound.hang import maybe_hang_after_commit


def test_hang_hook_noop_when_environment_not_test(monkeypatch) -> None:
    event_id = str(uuid4())
    monkeypatch.setenv("STOCKPILOT_ENVIRONMENT", "development")
    monkeypatch.setenv("STOCKPILOT_TEST_HANG_EVENT_ID", event_id)
    # Must return immediately (no hang) even though hang id matches.
    maybe_hang_after_commit({"event_id": event_id})


def test_hang_hook_noop_when_event_id_mismatches(monkeypatch) -> None:
    monkeypatch.setenv("STOCKPILOT_ENVIRONMENT", "test")
    monkeypatch.setenv("STOCKPILOT_TEST_HANG_EVENT_ID", str(uuid4()))
    maybe_hang_after_commit({"event_id": str(uuid4())})
