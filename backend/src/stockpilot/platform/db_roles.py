"""Idempotent database role helpers (superuser only; never log passwords)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

RELAY_ROLE = "stockpilot_relay"
METRICS_ROLE = "stockpilot_metrics"


def _ensure_login_role(
    conn: Connection,
    *,
    role_name: str,
    password: str | None,
    password_env: str,
) -> None:
    """Create or update a LOGIN NOBYPASSRLS NOINHERIT role; GRANT CONNECT."""
    exists = conn.execute(
        text("SELECT 1 FROM pg_roles WHERE rolname = :name"),
        {"name": role_name},
    ).first()
    if exists is None:
        if not password:
            raise RuntimeError(
                f"Role {role_name} does not exist and no password was provided via {password_env}"
            )
        quoted = conn.execute(
            text("SELECT quote_literal(:pw)"),
            {"pw": password},
        ).scalar_one()
        conn.execute(
            text(
                f"CREATE ROLE {role_name} LOGIN NOSUPERUSER NOCREATEDB "
                f"NOCREATEROLE NOBYPASSRLS NOINHERIT PASSWORD {quoted}"
            )
        )
    else:
        conn.execute(
            text(
                f"ALTER ROLE {role_name} WITH LOGIN NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOBYPASSRLS NOINHERIT"
            )
        )
        if password:
            quoted = conn.execute(
                text("SELECT quote_literal(:pw)"),
                {"pw": password},
            ).scalar_one()
            conn.execute(text(f"ALTER ROLE {role_name} PASSWORD {quoted}"))

    for db_name in ("stockpilot", "stockpilot_test"):
        db_exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": db_name},
        ).first()
        if db_exists is not None:
            conn.execute(text(f'GRANT CONNECT ON DATABASE "{db_name}" TO {role_name}'))


def ensure_stockpilot_relay(conn: Connection, *, password: str | None) -> None:
    """Create or update stockpilot_relay: LOGIN NOBYPASSRLS NOINHERIT.

    Safe to re-run. Does not grant table privileges (Alembic owns grants).
    Password is applied only when provided; never echoed.
    """
    _ensure_login_role(
        conn,
        role_name=RELAY_ROLE,
        password=password,
        password_env="STOCKPILOT_RELAY_PASSWORD",
    )


def ensure_stockpilot_metrics(conn: Connection, *, password: str | None) -> None:
    """Create or update stockpilot_metrics: LOGIN NOBYPASSRLS NOINHERIT.

    Safe to re-run. Table/function grants come from Alembic only.
    """
    _ensure_login_role(
        conn,
        role_name=METRICS_ROLE,
        password=password,
        password_env="STOCKPILOT_METRICS_PASSWORD",
    )


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


def require_metrics_role(conn: Connection) -> None:
    """Fail migration with a clear message if stockpilot_metrics is missing."""
    exists = conn.execute(
        text("SELECT 1 FROM pg_roles WHERE rolname = :name"),
        {"name": METRICS_ROLE},
    ).first()
    if exists is None:
        raise RuntimeError(
            "Database role stockpilot_metrics does not exist. "
            "Run `docker compose ... run --rm ops ensure-db-roles` "
            "(or recreate Postgres from init) before migrate. "
            "Migrations never CREATE ROLE or store passwords."
        )
