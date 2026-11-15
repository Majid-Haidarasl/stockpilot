"""Unit tests for magic-byte detection, letterbox encode, and path safety."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from stockpilot.modules.catalog.adapters.outbound.local_media import LocalMediaStorage
from stockpilot.modules.catalog.adapters.outbound.pillow_images import (
    ImageValidationError,
    PillowImageProcessor,
    detect_image_type,
)


def _png_bytes(width: int = 100, height: int = 50) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_with_exif() -> bytes:
    buf = io.BytesIO()
    image = Image.new("RGB", (120, 80), (200, 100, 50))
    # Pillow may omit EXIF on some builds; still assert output has no exif.
    image.save(buf, format="JPEG", quality=90, exif=b"Exif\x00\x00" + b"\x00" * 20)
    return buf.getvalue()


def test_detect_rejects_text_named_jpg() -> None:
    with pytest.raises(ImageValidationError) as exc:
        detect_image_type(b"not an image at all")
    assert exc.value.code == "IMAGE_TYPE_NOT_ALLOWED"


def test_normalize_png_to_exact_webp_sizes(tmp_path: Path) -> None:
    del tmp_path
    processor = PillowImageProcessor(max_bytes=5_000_000, max_pixels=24_000_000)
    result = processor.normalize(_png_bytes(300, 100))
    main = Image.open(io.BytesIO(result.main_bytes))
    thumb = Image.open(io.BytesIO(result.thumb_bytes))
    assert main.format == "WEBP"
    assert thumb.format == "WEBP"
    assert main.size == (800, 800)
    assert thumb.size == (200, 200)
    assert main.getexif() is None or len(main.getexif()) == 0


def test_normalize_strips_jpeg_exif() -> None:
    processor = PillowImageProcessor(max_bytes=5_000_000, max_pixels=24_000_000)
    result = processor.normalize(_jpeg_with_exif())
    out = Image.open(io.BytesIO(result.main_bytes))
    assert out.format == "WEBP"
    assert out.getexif() is None or len(out.getexif()) == 0


def test_too_large_bytes() -> None:
    processor = PillowImageProcessor(max_bytes=10, max_pixels=24_000_000)
    with pytest.raises(ImageValidationError) as exc:
        processor.normalize(_png_bytes())
    assert exc.value.code == "IMAGE_TOO_LARGE"


def test_too_many_pixels() -> None:
    processor = PillowImageProcessor(max_bytes=5_000_000, max_pixels=100)
    with pytest.raises(ImageValidationError) as exc:
        processor.normalize(_png_bytes(50, 50))
    assert exc.value.code == "IMAGE_DIMENSIONS_TOO_LARGE"


def test_local_storage_rejects_traversal(tmp_path: Path) -> None:
    storage = LocalMediaStorage(tmp_path)
    with pytest.raises(ValueError):
        storage.put("../escape.webp", b"x", content_type="image/webp")


def test_local_storage_put_created_flag(tmp_path: Path) -> None:
    storage = LocalMediaStorage(tmp_path)
    tenant = "11111111-1111-1111-1111-111111111111"
    digest = "a" * 64
    key = f"{tenant}/{digest}.webp"
    first = storage.put(key, b"hello", content_type="image/webp")
    second = storage.put(key, b"other", content_type="image/webp")
    assert first.created is True
    assert second.created is False
    assert storage.get(key) == b"hello"
    leftovers = list(tmp_path.joinpath(tenant).glob(".*.tmp"))
    assert leftovers == []
