"""Parser smoke tests for the sample-data markdown."""

from __future__ import annotations

from pathlib import Path

import pytest

from stockpilot.bootstrap.sample_data import parse_companies, parse_inventory_rows


def test_parse_sample_markdown_counts() -> None:
    candidates = [
        Path("/docs/stockpilot-sample-data.md"),
        Path(__file__).resolve().parents[3] / "docs" / "stockpilot-sample-data.md",
    ]
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        pytest.skip("stockpilot-sample-data.md not mounted")
    markdown = path.read_text(encoding="utf-8")
    companies = parse_companies(markdown)
    rows = parse_inventory_rows(markdown)
    assert len(companies) == 20
    assert len(rows) == 108
    assert companies[0].slug == "aftab"
    assert any(row.sku == "LAP-ASUS-FA507NV-16-1T" for row in rows)
