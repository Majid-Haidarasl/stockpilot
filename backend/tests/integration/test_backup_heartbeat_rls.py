"""Migration 0015: stockpilot_backup heartbeat DEFINER; no direct table writes."""

from __future__ import annotations

import json
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, ProgrammingError

pytestmark = pytest.mark.skipif(
    not os.environ.get("STOCKPILOT_DATABASE_URL")
    or not os.environ.get("STOCKPILOT_MIGRATION_DATABASE_URL"),
    reason="Database URLs not configured",
)


def _backup():
    url = os.environ.get("STOCKPILOT_BACKUP_DATABASE_URL")
    if not url:
        password = os.environ.get("STOCKPILOT_BACKUP_PASSWORD", "backup_dev_change_me")
        app_url = os.environ["STOCKPILOT_DATABASE_URL"]
        after_at = app_url.split("@", 1)[1]
        url = f"postgresql+psycopg://stockpilot_backup:{password}@{after_at}"
    return create_engine(url, pool_pre_ping=True)


def _migrator():
    return create_engine(os.environ["STOCKPILOT_MIGRATION_DATABASE_URL"], pool_pre_ping=True)


def test_backup_role_can_record_backup_heartbeat() -> None:
    details = {"snapshot_id": "testsnap", "schema": "0015_backup_heartbeat"}
    with _backup().begin() as conn:
        conn.execute(
            text("SELECT platform.record_backup_heartbeat(CAST(:d AS jsonb))"),
            {"d": json.dumps(details)},
        )
    with _migrator().connect() as conn:
        row = (
            conn.execute(
                text(
                    """
                    SELECT service_name, details->>'snapshot_id' AS snap
                    FROM platform.heartbeats
                    WHERE service_name = 'backup'
                    """
                )
            )
            .mappings()
            .one()
        )
        assert row["service_name"] == "backup"
        assert row["snap"] == "testsnap"


def test_backup_role_cannot_write_other_heartbeat_rows() -> None:
    with _backup().connect() as conn:
        with pytest.raises((ProgrammingError, DBAPIError)):
            conn.execute(
                text(
                    """
                    INSERT INTO platform.heartbeats (
                      service_name, last_success_at, details, updated_at
                    ) VALUES (
                      'scheduler', now(), '{}'::jsonb, now()
                    )
                    """
                )
            )
        conn.rollback()


def test_backup_role_cannot_write_tables_directly() -> None:
    statements = (
        "INSERT INTO platform.heartbeats (service_name, last_success_at) VALUES ('backup', now())",
        "UPDATE platform.heartbeats SET details = '{}'::jsonb WHERE service_name = 'backup'",
        "INSERT INTO sales.orders (id, tenant_id, customer_id, status, version) "
        "VALUES ("
        "'00000000-0000-0000-0000-000000000099',"
        "'00000000-0000-0000-0000-000000000001',"
        "'00000000-0000-0000-0000-000000000002',"
        "'DRAFT', 1)",
    )
    with _backup().connect() as conn:
        for sql in statements:
            with pytest.raises((ProgrammingError, DBAPIError)):
                conn.execute(text(sql))
            conn.rollback()
