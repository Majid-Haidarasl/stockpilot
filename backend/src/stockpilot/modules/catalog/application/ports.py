"""Catalog application ports (storage and image processing)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class PutResult:
    """Result of writing bytes under a storage key."""

    created: bool


@dataclass(frozen=True, slots=True)
class NormalizedImages:
    """Re-encoded main and thumbnail WebP payloads."""

    main_bytes: bytes
    thumb_bytes: bytes
    width: int
    height: int
    sha256: str


class ObjectStorage(Protocol):
    def put(self, key: str, data: bytes, *, content_type: str) -> PutResult:
        """Write bytes. created=True only when this call created the file."""

    def get(self, key: str) -> bytes:
        """Read bytes for an existing key; raise FileNotFoundError if missing."""

    def exists(self, key: str) -> bool:
        """Return True if the key exists under the media root."""

    def delete(self, key: str) -> None:
        """Delete the key if present; no-op if missing."""


class ImageProcessor(Protocol):
    def normalize(self, raw: bytes) -> NormalizedImages:
        """Validate magic bytes, decode, strip EXIF, emit 800 and 200 WebP."""
