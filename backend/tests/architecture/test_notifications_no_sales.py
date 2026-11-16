"""Notifications module must not depend on sales (orders)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "src" / "stockpilot" / "modules" / "notifications"


def test_notifications_tree_does_not_import_sales() -> None:
    forbidden = (
        "stockpilot.modules.sales",
        "from stockpilot.modules.sales",
        "import stockpilot.modules.sales",
    )
    for path in ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in forbidden:
            assert pattern not in text, f"{path} imports sales via {pattern}"
