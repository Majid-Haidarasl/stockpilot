"""Dump the FastAPI OpenAPI document as canonical JSON (no live server required)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    return value


def export_openapi_dict() -> dict[str, Any]:
    from stockpilot.bootstrap.app import create_app

    document: dict[str, Any] = create_app().openapi()
    canonical = _canonicalize(document)
    if not isinstance(canonical, dict):
        raise TypeError("OpenAPI document must be an object")
    return canonical


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export StockPilot OpenAPI JSON")
    parser.add_argument(
        "output",
        nargs="?",
        default="-",
        help="Output path, or '-' for stdout",
    )
    args = parser.parse_args(argv)
    document = export_openapi_dict()
    text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    if args.output == "-":
        sys.stdout.write(text)
    else:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
