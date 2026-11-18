"""Guards for seed-load (flag + slug allow-list)."""

from __future__ import annotations

import pytest

from stockpilot.bootstrap import seed_load
from stockpilot.platform.settings import Settings


def test_seed_load_refuses_without_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        seed_load,
        "get_settings",
        lambda: Settings.model_construct(environment="production"),
    )
    monkeypatch.delenv("STOCKPILOT_ALLOW_LOAD_SEED", raising=False)
    with pytest.raises(SystemExit, match="STOCKPILOT_ALLOW_LOAD_SEED"):
        seed_load.assert_load_seed_allowed(environment="production")


def test_seed_load_refuses_development_even_with_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        seed_load,
        "get_settings",
        lambda: Settings.model_construct(environment="development"),
    )
    monkeypatch.setenv("STOCKPILOT_ALLOW_LOAD_SEED", "true")
    with pytest.raises(SystemExit, match="production"):
        seed_load.assert_load_seed_allowed(environment="development")


def test_seed_load_allows_production_with_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        seed_load,
        "get_settings",
        lambda: Settings.model_construct(environment="production"),
    )
    monkeypatch.setenv("STOCKPILOT_ALLOW_LOAD_SEED", "true")
    seed_load.assert_load_seed_allowed(environment="production")


def test_assert_load_tenant_slug_refuses_non_load() -> None:
    with pytest.raises(SystemExit, match="non-load slug"):
        seed_load.assert_load_tenant_slug("aftab")
    with pytest.raises(SystemExit, match="non-load slug"):
        seed_load.assert_load_tenant_slug("load-99")
    seed_load.assert_load_tenant_slug("load-01")
    seed_load.assert_load_tenant_slug("load-10")


def test_load_tenant_slugs_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STOCKPILOT_LOAD_TENANT_COUNT", "3")
    assert seed_load.load_tenant_slugs() == ("load-01", "load-02", "load-03")
    monkeypatch.setenv("STOCKPILOT_LOAD_TENANT_COUNT", "11")
    with pytest.raises(SystemExit, match="1..10"):
        seed_load.load_tenant_slugs()
