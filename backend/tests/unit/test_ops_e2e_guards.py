"""Environment guards for e2e ops commands."""

from __future__ import annotations

import pytest

from stockpilot.bootstrap import ops
from stockpilot.platform.settings import Settings


def test_seed_e2e_refuses_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ops,
        "get_settings",
        lambda: Settings.model_construct(environment="production"),
    )
    with pytest.raises(SystemExit, match="seed-e2e"):
        ops.cmd_seed_e2e("production")


def test_seed_e2e_refuses_when_settings_are_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ops,
        "get_settings",
        lambda: Settings.model_construct(environment="production"),
    )
    with pytest.raises(SystemExit, match="seed-e2e"):
        ops.cmd_seed_e2e("development")


def test_e2e_backdate_refuses_staging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ops,
        "get_settings",
        lambda: Settings.model_construct(environment="staging"),
    )
    with pytest.raises(SystemExit, match="e2e-backdate-reservation"):
        ops.cmd_e2e_backdate_reservation("staging", "00000000-0000-0000-0000-000000000001")


def test_assert_dev_or_test_allows_test(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ops,
        "get_settings",
        lambda: Settings.model_construct(environment="test"),
    )
    ops._assert_dev_or_test("test", command="seed-e2e")
