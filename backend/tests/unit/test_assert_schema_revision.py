"""Unit tests for schema drift guard messaging."""

from __future__ import annotations

import pytest

from stockpilot.bootstrap.assert_schema_revision import (
    assert_schema_at_head,
    code_alembic_head,
)


def test_code_alembic_head_is_single_revision() -> None:
    head = code_alembic_head()
    assert head == "0015_backup_heartbeat"


def test_assert_schema_at_head_rejects_lag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "stockpilot.bootstrap.assert_schema_revision.code_alembic_head",
        lambda **_: "0014_ops_metrics",
    )
    monkeypatch.setattr(
        "stockpilot.bootstrap.assert_schema_revision.fetch_db_revision",
        lambda _url: "0009_product_images",
    )
    with pytest.raises(SystemExit, match="SCHEMA DRIFT") as exc:
        assert_schema_at_head(
            database_url="postgresql+psycopg://unused",
            expected_revision="0014_ops_metrics",
        )
    msg = str(exc.value)
    assert "0009_product_images" in msg
    assert "0014_ops_metrics" in msg


def test_assert_schema_at_head_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "stockpilot.bootstrap.assert_schema_revision.code_alembic_head",
        lambda **_: "0014_ops_metrics",
    )
    monkeypatch.setattr(
        "stockpilot.bootstrap.assert_schema_revision.fetch_db_revision",
        lambda _url: "0014_ops_metrics",
    )
    assert (
        assert_schema_at_head(
            database_url="postgresql+psycopg://unused",
            expected_revision="0014_ops_metrics",
        )
        == "0014_ops_metrics"
    )
