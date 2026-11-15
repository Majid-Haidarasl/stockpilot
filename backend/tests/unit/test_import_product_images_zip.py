"""Unit tests for zip safety + import actor rules (no DB for zip-slip)."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from stockpilot.bootstrap.import_product_images import (
    _normalize_zip_path,
    load_manifest_entries,
    read_manifest_image,
)


def _png_bytes(color: tuple[int, int, int] = (20, 40, 60)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(buf, format="PNG")
    return buf.getvalue()


def _write_zip(path: Path, *, entries: dict[str, bytes], manifest: list[dict]) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
        for name, data in entries.items():
            zf.writestr(name, data)


def test_normalize_rejects_zip_slip() -> None:
    with pytest.raises(SystemExit, match="Unsafe"):
        _normalize_zip_path("../etc/passwd")
    with pytest.raises(SystemExit, match="Unsafe"):
        _normalize_zip_path("images/../../secret.png")
    with pytest.raises(SystemExit, match="Unsafe"):
        _normalize_zip_path("/abs/file.png")


def test_normalize_accepts_relative_image_path() -> None:
    assert _normalize_zip_path("images/SKU-1.jpg") == "images/SKU-1.jpg"


def test_zip_slip_entry_rejected(tmp_path: Path) -> None:
    zip_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(
            "manifest.json",
            json.dumps(
                [{"sku": "SKU-1", "image_file": "../evil.png"}],
                ensure_ascii=False,
            ),
        )
        # Craft a slip member
        info = zipfile.ZipInfo("../evil.png")
        zf.writestr(info, b"not-an-image")

    with zipfile.ZipFile(zip_path, "r") as zf:
        entries = load_manifest_entries(zf)
        assert entries[0]["image_file"] == "../evil.png"
        with pytest.raises(SystemExit, match="Unsafe|Zip-slip|Absolute"):
            read_manifest_image(
                zf,
                image_file="../evil.png",
                names=set(zf.namelist()),
            )


def test_manifest_reads_listed_file_only(tmp_path: Path) -> None:
    zip_path = tmp_path / "ok.zip"
    png = _png_bytes()
    _write_zip(
        zip_path,
        entries={
            "images/SKU-1.png": png,
            "images/EXTRA.png": _png_bytes((1, 2, 3)),
        },
        manifest=[{"sku": "SKU-1", "image_file": "images/SKU-1.png"}],
    )
    with zipfile.ZipFile(zip_path, "r") as zf:
        data = read_manifest_image(
            zf,
            image_file="images/SKU-1.png",
            names={n for n in zf.namelist() if not n.endswith("/")},
        )
    assert data == png
