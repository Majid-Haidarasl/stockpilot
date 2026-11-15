"""Idempotent database role helpers (superuser only; never log passwords)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

RELAY_ROLE = "stockpilot_relay"


def ensure_stockpilot_relay(conn: Connection, *, password: str | None) -> None:
    """Create or update stockpilot_relay: LOGIN NOBYPASSRLS NOINHERIT.

    Safe to re-run. Does not grant table privileges (Alembic owns grants).
    Password is applied only when provided; never echoed.
    """
    exists = conn.execute(
        text("SELECT 1 FROM pg_roles WHERE rolname = :name"),
        {"name": RELAY_ROLE},
    ).first()
    if exists is None:
        if not password:
            raise RuntimeError(
                f"Role {RELAY_ROLE} does not exist and no password was provided "
                "via STOCKPILOT_RELAY_PASSWORD"
            )
        quoted = conn.execute(
            text("SELECT quote_literal(:pw)"),
            {"pw": password},
        ).scalar_one()
        conn.execute(
            text(
                f"CREATE ROLE {RELAY_ROLE} LOGIN NOSUPERUSER NOCREATEDB "
                f"NOCREATEROLE NOBYPASSRLS NOINHERIT PASSWORD {quoted}"
            )
        )
    else:
        conn.execute(
            text(
                f"ALTER ROLE {RELAY_ROLE} WITH LOGIN NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOBYPASSRLS NOINHERIT"
            )
        )
        if password:
            quoted = conn.execute(
                text("SELECT quote_literal(:pw)"),
                {"pw": password},
            ).scalar_one()
            conn.execute(text(f"ALTER ROLE {RELAY_ROLE} PASSWORD {quoted}"))

    for db_name in ("stockpilot", "stockpilot_test"):
        db_exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": db_name},
        ).first()
        if db_exists is not None:
            conn.execute(text(f'GRANT CONNECT ON DATABASE "{db_name}" TO {RELAY_ROLE}'))


def require_relay_role(conn: Connection) -> None:
    """Fail migration with a clear message if stockpilot_relay is missing."""
    exists = conn.execute(
        text("SELECT 1 FROM pg_roles WHERE rolname = :name"),
        {"name": RELAY_ROLE},
    ).first()
    if exists is None:
        raise RuntimeError(
            "Database role stockpilot_relay does not exist. "
            "Run `docker compose ... run --rm ops ensure-db-roles` "
            "(or recreate Postgres from init) before migrate. "
            "Migrations never CREATE ROLE or store passwords."
        )
