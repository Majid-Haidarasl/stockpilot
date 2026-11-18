"""Contract tests for backup compose services, alerts, and scripts."""

from __future__ import annotations

import os
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
COMPOSE = Path(os.environ.get("STOCKPILOT_COMPOSE_PATH", str(_REPO / "compose.yaml")))
COMPOSE_PROD = Path(
    os.environ.get("STOCKPILOT_COMPOSE_PROD_PATH", str(_REPO / "compose.prod.yaml"))
)
ALERTS = Path(
    os.environ.get(
        "STOCKPILOT_ALERTS_PATH",
        str(_REPO / "infra" / "prometheus" / "alerts.yml"),
    )
)
BACKUP_DIR = Path(os.environ.get("STOCKPILOT_BACKUP_DIR", str(_REPO / "infra" / "backup")))


def _service_block(name: str, text: str) -> str:
    pattern = rf"(?ms)^  {re.escape(name)}:\n(.*?)(?=^  [a-z0-9-]+:|^networks:|^volumes:|\Z)"
    match = re.search(pattern, text)
    assert match is not None, f"service {name} not found"
    return match.group(1)


def test_compose_defines_backup_services_with_profile() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    for name in ("backup", "backup-scheduler", "restore"):
        block = _service_block(name, text)
        assert 'profiles: ["backup"]' in block
        assert "docker.sock" not in block
        assert "PGUSER: stockpilot_backup" in block or name == "restore"
        # No host port publishes in 8084-8183
        for m in re.finditer(r"(\d{4}):(\d+)", block):
            host_port = int(m.group(1))
            assert not (8084 <= host_port <= 8183)


def test_compose_prod_backup_uses_ghcr_and_no_ports() -> None:
    text = COMPOSE_PROD.read_text(encoding="utf-8")
    assert "ghcr.io/majid-haidarasl/stockpilot-backup" in text
    for name in ("backup", "backup-scheduler", "restore"):
        block = _service_block(name, text)
        assert "profiles:" in block and "backup" in block
        assert "ports:" not in block or "ports: !reset" in block


def test_backup_stale_alert_is_14_hours() -> None:
    text = ALERTS.read_text(encoding="utf-8")
    assert "StockpilotBackupStale" in text
    assert 'service_name="backup"' in text
    assert "50400" in text  # 14 hours


def test_backup_scripts_refuse_missing_confirm_and_clean_scratch() -> None:
    backup_sh = (BACKUP_DIR / "backup.sh").read_text(encoding="utf-8")
    restore_sh = (BACKUP_DIR / "restore.sh").read_text(encoding="utf-8")
    assert "trap" in backup_sh
    assert "cleanup_scratch" in backup_sh
    assert "pg_dumpall --globals-only --no-role-passwords" in backup_sh
    assert "PGUSER" in backup_sh or "stockpilot_backup" in COMPOSE.read_text(encoding="utf-8")
    assert "STOCKPILOT_RESTORE_CONFIRM" in restore_sh
    assert "stockpilot-restore" in restore_sh
    restore_cmds = [
        line for line in restore_sh.splitlines() if line.strip().startswith("pg_restore")
    ]
    assert restore_cmds, "expected pg_restore invocations"
    for line in restore_cmds:
        assert "--no-owner" not in line
        assert "--no-privileges" not in line
    assert "forget --keep-daily 14 --keep-monthly 3" in backup_sh
    assert "restic prune" in backup_sh
    assert "restic check" in backup_sh


def test_restic_env_example_has_placeholders_only() -> None:
    example = (BACKUP_DIR / "restic.env.example").read_text(encoding="utf-8")
    assert "REPLACE_BUCKET" in example or "example.com" in example
    assert "replace_me" in example.lower() or "practice" in example.lower()
    # No obvious AWS key pattern
    assert not re.search(r"AKIA[0-9A-Z]{16}", example)
