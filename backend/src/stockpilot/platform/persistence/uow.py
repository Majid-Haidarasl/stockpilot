"""Unit of work with optional tenant/user SET LOCAL context for RLS."""

from __future__ import annotations

from types import TracebackType
from typing import Self
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, Transaction

from stockpilot.platform.persistence.db import get_engine


class UnitOfWork:
    def __init__(
        self,
        *,
        engine: Engine | None = None,
        user_id: UUID | None = None,
        tenant_id: UUID | None = None,
        role: str | None = None,
    ) -> None:
        self._engine = engine or get_engine()
        self._user_id = user_id
        self._tenant_id = tenant_id
        self._role = role
        self._conn: Connection | None = None
        self._tx: Transaction | None = None

    @property
    def connection(self) -> Connection:
        if self._conn is None:
            raise RuntimeError("UnitOfWork is not active")
        return self._conn

    def __enter__(self) -> Self:
        self._conn = self._engine.connect()
        self._tx = self._conn.begin()
        self._conn.execute(text("SELECT set_config('app.user_id', '', true)"))
        self._conn.execute(text("SELECT set_config('app.tenant_id', '', true)"))
        self._conn.execute(text("SELECT set_config('app.role', '', true)"))
        if self._user_id is not None:
            self._conn.execute(
                text("SELECT set_config('app.user_id', :v, true)"),
                {"v": str(self._user_id)},
            )
        if self._tenant_id is not None:
            self._conn.execute(
                text("SELECT set_config('app.tenant_id', :v, true)"),
                {"v": str(self._tenant_id)},
            )
        if self._role is not None:
            self._conn.execute(
                text("SELECT set_config('app.role', :v, true)"),
                {"v": self._role},
            )
        return self

    def commit(self) -> None:
        assert self._conn is not None
        assert self._tx is not None
        self._tx.commit()
        self._tx = self._conn.begin()
        # Re-apply local settings for the new transaction.
        if self._user_id is not None:
            self._conn.execute(
                text("SELECT set_config('app.user_id', :v, true)"),
                {"v": str(self._user_id)},
            )
        if self._tenant_id is not None:
            self._conn.execute(
                text("SELECT set_config('app.tenant_id', :v, true)"),
                {"v": str(self._tenant_id)},
            )
        if self._role is not None:
            self._conn.execute(
                text("SELECT set_config('app.role', :v, true)"),
                {"v": self._role},
            )

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        assert self._conn is not None
        assert self._tx is not None
        try:
            if exc_type is None:
                self._tx.commit()
            else:
                self._tx.rollback()
        finally:
            self._conn.close()
            self._conn = None
            self._tx = None
