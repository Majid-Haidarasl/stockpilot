"""Local filesystem object storage behind ObjectStorage port."""

from __future__ import annotations

import os
import re
from pathlib import Path
from uuid import uuid4

from stockpilot.modules.catalog.application.ports import PutResult

_KEY_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/"
    r"[0-9a-f]{64}(?:\.thumb)?\.webp$"
)


class LocalMediaStorage:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, data: bytes, *, content_type: str) -> PutResult:
        del content_type  # stored separately in DB; filesystem is opaque bytes
        path = self._resolved(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic publish: write temp → fsync → link into place (fails if exists).
        temp = path.parent / f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp"
        try:
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
            except Exception:
                temp.unlink(missing_ok=True)
                raise
            try:
                os.link(temp, path)
            except FileExistsError:
                temp.unlink(missing_ok=True)
                return PutResult(created=False)
            temp.unlink(missing_ok=True)
            return PutResult(created=True)
        except Exception:
            temp.unlink(missing_ok=True)
            raise

    def get(self, key: str) -> bytes:
        path = self._resolved(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return self._resolved(key).is_file()

    def delete(self, key: str) -> None:
        path = self._resolved(key)
        path.unlink(missing_ok=True)

    def _resolved(self, key: str) -> Path:
        if not _KEY_RE.match(key):
            raise ValueError(f"Invalid storage key: {key}")
        if ".." in key or key.startswith("/") or "\\" in key:
            raise ValueError(f"Invalid storage key: {key}")
        candidate = (self._root / key).resolve()
        try:
            candidate.relative_to(self._root)
        except ValueError as exc:
            raise ValueError(f"Path escapes media root: {key}") from exc
        return candidate
