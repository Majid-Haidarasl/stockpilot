"""Database helpers for health checks (runtime role)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from stockpilot.platform.settings import Settings, get_settings

_engine: Engine | None = None


def get_engine(settings: Settings | None = None) -> Engine:
    global _engine
    if _engine is None:
        cfg = settings or get_settings()
        _engine = create_engine(cfg.database_url, pool_pre_ping=True)
    return _engine


def reset_engine() -> None:
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None


@contextmanager
def connect(settings: Settings | None = None) -> Iterator[Connection]:
    engine = get_engine(settings)
    with engine.connect() as conn:
        yield conn


def fetch_schema_revision(settings: Settings | None = None) -> str | None:
    cfg = settings or get_settings()
    with connect(cfg) as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version")).first()
        if row is None:
            return None
        return str(row[0])
