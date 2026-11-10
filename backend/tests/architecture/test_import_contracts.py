"""Architecture smoke checks complementing Import Linter.

Import Linter contracts in pyproject.toml fail CI if domain imports sqlalchemy/fastapi
or application imports outbound adapters. This test documents that expectation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

DOMAIN_ROOT = (
    Path(__file__).resolve().parents[2] / "src" / "stockpilot" / "modules" / "sales" / "domain"
)


def test_money_domain_file_has_no_sqlalchemy_import() -> None:
    source = (DOMAIN_ROOT / "money.py").read_text(encoding="utf-8")
    assert "sqlalchemy" not in source
    assert "fastapi" not in source


@pytest.mark.parametrize(
    "forbidden",
    ["from sqlalchemy", "import sqlalchemy", "from fastapi", "import fastapi"],
)
def test_domain_tree_avoids_forbidden_imports(forbidden: str) -> None:
    for path in DOMAIN_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert forbidden not in text, f"{path} contains forbidden import pattern: {forbidden}"
