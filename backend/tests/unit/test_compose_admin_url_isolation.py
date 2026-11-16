"""Assert STOCKPILOT_ADMIN_DATABASE_URL is not wired into api/relay services."""

from __future__ import annotations

import os
import re
from pathlib import Path

COMPOSE_CANDIDATES = (
    Path(os.environ["STOCKPILOT_COMPOSE_PATH"])
    if os.environ.get("STOCKPILOT_COMPOSE_PATH")
    else None,
    Path("/compose.yaml"),
    Path(__file__).resolve().parents[3] / "compose.yaml",
)


def _compose_text() -> str:
    for path in COMPOSE_CANDIDATES:
        if path is not None and path.is_file():
            return path.read_text(encoding="utf-8")
    raise AssertionError("compose.yaml not found for admin-URL isolation check")


def _service_block(name: str, text: str) -> str:
    pattern = rf"(?ms)^  {re.escape(name)}:\n(.*?)(?=^  [a-z0-9-]+:|\Z)"
    match = re.search(pattern, text)
    assert match is not None, f"service {name} not found in compose.yaml"
    return match.group(1)


def test_admin_url_absent_from_checks_process_env() -> None:
    assert "STOCKPILOT_ADMIN_DATABASE_URL" not in os.environ


def test_admin_database_url_only_on_ops() -> None:
    text = _compose_text()
    ops = _service_block("ops", text)
    assert "STOCKPILOT_ADMIN_DATABASE_URL" in ops
    for name in ("api", "relay", "worker", "migrate", "backend-checks"):
        block = _service_block(name, text)
        assert "STOCKPILOT_ADMIN_DATABASE_URL" not in block, (
            f"{name} must not receive STOCKPILOT_ADMIN_DATABASE_URL"
        )


def test_worker_service_uses_app_role_and_low_concurrency() -> None:
    text = _compose_text()
    worker = _service_block("worker", text)
    assert "stockpilot_app" in worker
    assert "STOCKPILOT_ADMIN_DATABASE_URL" not in worker
    assert "--concurrency=2" in worker
    assert "celery" in worker
    deps = re.search(r"(?ms)depends_on:\n(.*?)(?=\n    [a-z]|\Z)", worker)
    assert deps is not None
    dep_block = deps.group(1)
    assert "postgres" in dep_block
    assert "migrate" in dep_block
    assert "rabbitmq" in dep_block


def test_api_ready_does_not_depend_on_rabbitmq() -> None:
    text = _compose_text()
    api = _service_block("api", text)
    deps = re.search(r"(?ms)depends_on:\n(.*?)(?=\n    [a-z]|\Z)", api)
    assert deps is not None
    assert "rabbitmq" not in deps.group(1)
