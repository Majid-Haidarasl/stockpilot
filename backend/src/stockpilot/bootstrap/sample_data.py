"""Parse docs/stockpilot-sample-data.md into structured seed rows."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CompanyRow:
    code: str
    name_fa: str
    slug: str
    admin_email: str


@dataclass(frozen=True, slots=True)
class InventorySeedRow:
    company_code: str
    slug: str
    sku: str
    title: str
    unit_price_rial: int
    on_hand: int
    stock_warning_threshold: int


_COMPANY_HEADER = re.compile(r"^##\s*۱\.\s*شرکت")
_INVENTORY_HEADER = re.compile(r"^##\s*۵\.\s*جدول یکپارچه")
_NEXT_SECTION = re.compile(r"^##\s+")


def _split_row(line: str) -> list[str]:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells


def _parse_int(raw: str) -> int:
    cleaned = raw.replace(",", "").replace("٬", "").replace(" ", "").strip()
    return int(cleaned)


def parse_companies(markdown: str) -> list[CompanyRow]:
    lines = markdown.splitlines()
    in_section = False
    rows: list[CompanyRow] = []
    for line in lines:
        if _COMPANY_HEADER.search(line):
            in_section = True
            continue
        if in_section and _NEXT_SECTION.match(line) and not _COMPANY_HEADER.search(line):
            break
        if not in_section or not line.strip().startswith("|"):
            continue
        cells = _split_row(line)
        if len(cells) < 6:
            continue
        if cells[0] in {"کد شرکت", "---"} or cells[0].startswith("---"):
            continue
        if not cells[0].startswith("T"):
            continue
        rows.append(
            CompanyRow(
                code=cells[0],
                name_fa=cells[1],
                slug=cells[2],
                admin_email=cells[5],
            )
        )
    return rows


def parse_inventory_rows(markdown: str) -> list[InventorySeedRow]:
    lines = markdown.splitlines()
    in_section = False
    rows: list[InventorySeedRow] = []
    for line in lines:
        if _INVENTORY_HEADER.search(line):
            in_section = True
            continue
        if in_section and _NEXT_SECTION.match(line) and not _INVENTORY_HEADER.search(line):
            break
        if not in_section or not line.strip().startswith("|"):
            continue
        cells = _split_row(line)
        if len(cells) < 7:
            continue
        if cells[0] in {"کد شرکت", "---"} or cells[0].startswith("---"):
            continue
        if not cells[0].startswith("T"):
            continue
        rows.append(
            InventorySeedRow(
                company_code=cells[0],
                slug=cells[1],
                sku=cells[2],
                title=cells[3],
                unit_price_rial=_parse_int(cells[4]),
                on_hand=_parse_int(cells[5]),
                stock_warning_threshold=_parse_int(cells[6]),
            )
        )
    return rows


def load_sample_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8")
