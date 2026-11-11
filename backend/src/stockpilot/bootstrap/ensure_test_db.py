"""Ensure the isolated stockpilot_test database exists (for backend-checks)."""

from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, text


def main() -> None:
    admin_url = os.environ.get("STOCKPILOT_TEST_ADMIN_DATABASE_URL")
    if not admin_url:
        print("STOCKPILOT_TEST_ADMIN_DATABASE_URL not set; skipping ensure_test_db", flush=True)
        return

    db_name = os.environ.get("STOCKPILOT_TEST_DATABASE_NAME", "stockpilot_test")
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    with engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": db_name},
        ).first()
        if exists is None:
            # Identifier cannot be parameterized; db_name is controlled by env, not user input.
            conn.execute(text(f'CREATE DATABASE "{db_name}" OWNER stockpilot_migrator'))
            print(f"created database {db_name}", flush=True)
        else:
            print(f"database {db_name} already exists", flush=True)
        conn.execute(text(f'GRANT CONNECT ON DATABASE "{db_name}" TO stockpilot_app'))

    # Match init script privileges on public schema for existing volumes.
    db_engine = create_engine(
        admin_url.rsplit("/", 1)[0] + f"/{db_name}",
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )
    with db_engine.connect() as conn:
        conn.execute(text("REVOKE ALL ON SCHEMA public FROM PUBLIC"))
        conn.execute(text("REVOKE ALL ON SCHEMA public FROM stockpilot_app"))
        conn.execute(text("GRANT USAGE ON SCHEMA public TO stockpilot_app"))
        conn.execute(text("GRANT CREATE ON SCHEMA public TO stockpilot_migrator"))
    print("ensure_test_db complete", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 — fail checks visibly
        print(f"ensure_test_db failed: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1) from exc
