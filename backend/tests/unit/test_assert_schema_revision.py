"""Unit tests for schema drift guard messaging."""

from __future__ import annotations

import pytest

from stockpilot.bootstrap.assert_schema_revision import (
    assert_schema_at_head,
    code_alembic_head,
)


def test_code_alembic_head_is_single_revision() -> None:
    head = code_alembic_head()
    assert head == "0013_scheduler_heartbeats"


def test_assert_schema_at_head_rejects_lag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "stockpilot.bootstrap.assert_schema_revision.code_alembic_head",
        lambda **_: "0013_scheduler_heartbeats",
    )
    monkeypatch.setattr(
        "stockpilot.bootstrap.assert_schema_revision.fetch_db_revision",
        lambda _url: "0009_product_images",
    )
    with pytest.raises(SystemExit, match="SCHEMA DRIFT") as exc:
        assert_schema_at_head(
            database_url="postgresql+psycopg://unused",
            expected_revision="0013_scheduler_heartbeats",
        )
    msg = str(exc.value)
    assert "0009_product_images" in msg
    assert "0013_scheduler_heartbeats" in msg


def test_assert_schema_at_head_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "stockpilot.bootstrap.assert_schema_revision.code_alembic_head",
        lambda **_: "0013_scheduler_heartbeats",
    )
    monkeypatch.setattr(
        "stockpilot.bootstrap.assert_schema_revision.fetch_db_revision",
        lambda _url: "0013_scheduler_heartbeats",
    )
    assert (
        assert_schema_at_head(
            database_url="postgresql+psycopg://unused",
            expected_revision="0013_scheduler_heartbeats",
        )
        == "0013_scheduler_heartbeats"
    )
