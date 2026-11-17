"""Fail fast when DB alembic_version does not match code head (schema drift).

Used by backend-checks and e2e migrate so a stale migrate image / lagging DB
(e.g. stuck at 0009 while code is at 0012) surfaces with a clear message
instead of obscure runtime SQL errors.
"""

from __future__ import annotations

import os
import sys

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text


def code_alembic_head(*, alembic_ini: str = "alembic.ini") -> str:
    cfg = Config(alembic_ini)
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    if len(heads) != 1:
        raise SystemExit(f"SCHEMA DRIFT: expected a single Alembic head, got {heads!r}")
    return heads[0]


def fetch_db_revision(database_url: str) -> str | None:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version")).first()
            if row is None:
                return None
            return str(row[0])
    finally:
        engine.dispose()


def assert_schema_at_head(
    *,
    database_url: str,
    expected_revision: str | None = None,
    alembic_ini: str = "alembic.ini",
) -> str:
    """Raise SystemExit with a clear message if DB revision != code head (and expected)."""
    head = code_alembic_head(alembic_ini=alembic_ini)
    actual = fetch_db_revision(database_url)
    expected = expected_revision or os.environ.get("STOCKPILOT_EXPECTED_SCHEMA_REVISION")

    if actual != head:
        raise SystemExit(
            "SCHEMA DRIFT: database alembic_version="
            f"{actual!r} != code head={head!r}. "
            "Rebuild the migrate (and api/relay/worker) images, then run "
            "`alembic upgrade head` against this database. "
            f"(STOCKPILOT_EXPECTED_SCHEMA_REVISION={expected!r})"
        )
    if expected and actual != expected:
        raise SystemExit(
            "SCHEMA DRIFT: database/code at "
            f"{actual!r} but STOCKPILOT_EXPECTED_SCHEMA_REVISION={expected!r}. "
            "Bump the env/default to match Alembic head, or finish migrations."
        )
    return head


def main() -> None:
    database_url = os.environ.get("STOCKPILOT_MIGRATION_DATABASE_URL") or os.environ.get(
        "STOCKPILOT_DATABASE_URL"
    )
    if not database_url:
        raise SystemExit(
            "SCHEMA DRIFT: STOCKPILOT_MIGRATION_DATABASE_URL (or STOCKPILOT_DATABASE_URL) "
            "is required for assert_schema_revision"
        )
    head = assert_schema_at_head(database_url=database_url)
    print(f"schema ok: {head}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — fail checks visibly
        print(f"assert_schema_revision failed: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1) from exc
