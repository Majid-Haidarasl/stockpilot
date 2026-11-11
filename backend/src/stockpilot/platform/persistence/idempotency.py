"""Idempotency record claim/store for commercial commands."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError, OperationalError


class IdempotencyKeyReused(Exception):
    pass


class IdempotencyInProgress(Exception):
    """Another request holds the same key; caller should return Retry-After."""

    def __init__(self, retry_after: int = 1) -> None:
        self.retry_after = retry_after
        super().__init__("Idempotency key in progress")


@dataclass(slots=True)
class StoredResponse:
    status: int
    body: dict[str, Any]
    headers: dict[str, str]


def fingerprint(
    *,
    method: str,
    path: str,
    contract_version: str,
    body: dict[str, Any] | None,
) -> str:
    canonical = json.dumps(body or {}, sort_keys=True, separators=(",", ":"), default=str)
    raw = f"{method.upper()}\n{path}\n{contract_version}\n{canonical}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class IdempotencyStore:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def begin(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        operation: str,
        key: str,
        fp: str,
        wait_seconds: float = 0.4,
    ) -> StoredResponse | None:
        """Claim the key or return a completed stored response.

        Concurrent starters wait briefly (lock_timeout); if still in progress,
        raise IdempotencyInProgress so the HTTP layer can send Retry-After.
        """
        # Cap how long we block on a peer holding the same key (unique index or row).
        timeout_ms = max(50, int(wait_seconds * 1000))
        self._conn.execute(
            text("SELECT set_config('lock_timeout', :ms, true)"),
            {"ms": str(timeout_ms)},
        )
        try:
            row = self._insert_or_lock(
                tenant_id=tenant_id, user_id=user_id, operation=operation, key=key, fp=fp
            )
        except (OperationalError, DBAPIError) as exc:
            if _is_lock_error(exc):
                raise IdempotencyInProgress(retry_after=1) from exc
            raise
        if row is None:
            # Lost race on insert; wait and re-lock.
            deadline = time.monotonic() + wait_seconds
            while time.monotonic() < deadline:
                time.sleep(0.05)
                try:
                    locked = self._lock_existing(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        operation=operation,
                        key=key,
                    )
                except IdempotencyInProgress:
                    raise
                except (OperationalError, DBAPIError) as exc:
                    if _is_lock_error(exc):
                        raise IdempotencyInProgress(retry_after=1) from exc
                    raise
                if locked is None:
                    continue
                return self._handle_locked(locked, fp)
            raise IdempotencyInProgress(retry_after=1)

        return self._handle_locked(row, fp)

    def complete(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        operation: str,
        key: str,
        response: StoredResponse,
    ) -> None:
        self._conn.execute(
            text(
                """
                UPDATE platform.idempotency_records
                SET status = 'completed',
                    response_status = :status,
                    response_body = CAST(:body AS jsonb),
                    response_headers = CAST(:headers AS jsonb),
                    completed_at = now()
                WHERE tenant_id = :tenant_id
                  AND user_id = :user_id
                  AND operation = :operation
                  AND key = :key
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "user_id": str(user_id),
                "operation": operation,
                "key": key,
                "status": response.status,
                "body": json.dumps(response.body),
                "headers": json.dumps(response.headers),
            },
        )

    def _handle_locked(self, row: dict[str, Any], fp: str) -> StoredResponse | None:
        if str(row["fingerprint"]) != fp:
            raise IdempotencyKeyReused("Idempotency-Key reused with a different body")
        if str(row["status"]) == "completed":
            body = row["response_body"] or {}
            headers = row["response_headers"] or {}
            if isinstance(body, str):
                body = json.loads(body)
            if isinstance(headers, str):
                headers = json.loads(headers)
            return StoredResponse(
                status=int(row["response_status"]),
                body=dict(body),
                headers={str(k): str(v) for k, v in dict(headers).items()},
            )
        # We own the started row (or re-locked our own). Proceed with new work.
        return None

    def _insert_or_lock(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        operation: str,
        key: str,
        fp: str,
    ) -> dict[str, Any] | None:
        inserted = (
            self._conn.execute(
                text(
                    """
                INSERT INTO platform.idempotency_records (
                  id, tenant_id, user_id, operation, key, fingerprint, status
                ) VALUES (
                  :id, :tenant_id, :user_id, :operation, :key, :fingerprint, 'started'
                )
                ON CONFLICT (tenant_id, user_id, operation, key) DO NOTHING
                RETURNING id, fingerprint, status, response_status, response_body, response_headers
                """
                ),
                {
                    "id": str(uuid4()),
                    "tenant_id": str(tenant_id),
                    "user_id": str(user_id),
                    "operation": operation,
                    "key": key,
                    "fingerprint": fp,
                },
            )
            .mappings()
            .first()
        )
        if inserted is not None:
            return dict(inserted)
        return self._lock_existing(
            tenant_id=tenant_id, user_id=user_id, operation=operation, key=key
        )

    def _lock_existing(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        operation: str,
        key: str,
    ) -> dict[str, Any] | None:
        try:
            row = (
                self._conn.execute(
                    text(
                        """
                    SELECT id, fingerprint, status, response_status, response_body, response_headers
                    FROM platform.idempotency_records
                    WHERE tenant_id = :tenant_id
                      AND user_id = :user_id
                      AND operation = :operation
                      AND key = :key
                    FOR UPDATE NOWAIT
                    """
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "user_id": str(user_id),
                        "operation": operation,
                        "key": key,
                    },
                )
                .mappings()
                .first()
            )
        except (OperationalError, DBAPIError) as exc:
            if _is_lock_error(exc):
                raise IdempotencyInProgress(retry_after=1) from exc
            raise
        return dict(row) if row else None


def _is_lock_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return (
        "lock" in msg
        or "could not obtain" in msg
        or "55p03" in msg
        or "canceling statement due to lock timeout" in msg
    )
