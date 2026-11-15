"""Pillow-backed image normalization for product uploads."""

from __future__ import annotations

import hashlib
import io
from typing import Any

from PIL import Image, ImageOps

from stockpilot.modules.catalog.application.ports import NormalizedImages

JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class ImageValidationError(Exception):
    def __init__(self, code: str, title: str) -> None:
        self.code = code
        self.title = title
        super().__init__(title)


def detect_image_type(raw: bytes) -> str:
    if len(raw) >= 3 and raw[:3] == JPEG_MAGIC:
        return "jpeg"
    if len(raw) >= 8 and raw[:8] == PNG_MAGIC:
        return "png"
    if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp"
    raise ImageValidationError(
        "IMAGE_TYPE_NOT_ALLOWED",
        "Only JPEG, PNG, or WebP images are accepted",
    )


def _letterbox(image: Image.Image, size: int) -> Image.Image:
    contained = ImageOps.contain(image, (size, size), method=Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (size, size), (255, 255, 255))
    offset = ((size - contained.width) // 2, (size - contained.height) // 2)
    canvas.paste(contained, offset)
    return canvas


def _to_rgb(image: Image.Image) -> Image.Image:
    if image.mode in ("RGB", "L"):
        return image.convert("RGB")
    if image.mode == "RGBA":
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        return background
    if image.mode == "P":
        return _to_rgb(image.convert("RGBA"))
    return image.convert("RGB")


class PillowImageProcessor:
    def __init__(self, *, max_bytes: int, max_pixels: int) -> None:
        self._max_bytes = max_bytes
        self._max_pixels = max_pixels

    def normalize(self, raw: bytes) -> NormalizedImages:
        if len(raw) > self._max_bytes:
            raise ImageValidationError(
                "IMAGE_TOO_LARGE",
                "Image exceeds the maximum allowed size",
            )
        detect_image_type(raw)

        previous: Any = Image.MAX_IMAGE_PIXELS
        Image.MAX_IMAGE_PIXELS = self._max_pixels
        try:
            try:
                with Image.open(io.BytesIO(raw)) as opened:
                    opened.load()
                    oriented = ImageOps.exif_transpose(opened)
                    assert oriented is not None
                    rgb = _to_rgb(oriented)
                    main = _letterbox(rgb, 800)
                    thumb = _letterbox(rgb, 200)
            except Image.DecompressionBombError as exc:
                raise ImageValidationError(
                    "IMAGE_DIMENSIONS_TOO_LARGE",
                    "Image dimensions exceed the maximum allowed",
                ) from exc
            except Exception as exc:
                if isinstance(exc, ImageValidationError):
                    raise
                raise ImageValidationError(
                    "IMAGE_DECODE_FAILED",
                    "Image file could not be decoded",
                ) from exc
        finally:
            Image.MAX_IMAGE_PIXELS = previous

        main_buf = io.BytesIO()
        thumb_buf = io.BytesIO()
        main.save(main_buf, format="WEBP", quality=85, method=4)
        thumb.save(thumb_buf, format="WEBP", quality=80, method=4)
        main_bytes = main_buf.getvalue()
        thumb_bytes = thumb_buf.getvalue()
        digest = hashlib.sha256(main_bytes).hexdigest()
        return NormalizedImages(
            main_bytes=main_bytes,
            thumb_bytes=thumb_bytes,
            width=800,
            height=800,
            sha256=digest,
        )
