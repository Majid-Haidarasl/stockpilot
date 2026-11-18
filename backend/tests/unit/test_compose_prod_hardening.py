"""Lint compose.prod.yaml hardening rules for Run 6.2."""

from __future__ import annotations

import os
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
COMPOSE_PROD = Path(
    os.environ.get("STOCKPILOT_COMPOSE_PROD_PATH", str(_REPO / "compose.prod.yaml"))
)

_BACKEND_SERVICES = (
    "api",
    "relay",
    "worker",
    "scheduler",
    "migrate",
    "ops",
    "ops-exporter",
)


def _prod_text() -> str:
    assert COMPOSE_PROD.is_file(), f"missing {COMPOSE_PROD}"
    return COMPOSE_PROD.read_text(encoding="utf-8")


def _service_block(name: str, text: str) -> str:
    pattern = rf"(?ms)^  {re.escape(name)}:\n(.*?)(?=^  [a-z0-9-]+:|^volumes:|\Z)"
    match = re.search(pattern, text)
    assert match is not None, f"service {name} not found in compose.prod.yaml"
    return match.group(1)


def _published_port_specs(block: str) -> list[str]:
    ports_match = re.search(r"(?ms)^\s{4}ports:\s*\n((?:\s{6}-.+\n)+)", block)
    if ports_match is None:
        # !reset [] or absent
        return []
    specs: list[str] = []
    for line in ports_match.group(1).splitlines():
        m = re.search(r'-\s*"([^"]+)"', line) or re.search(r"-\s*'([^']+)'", line)
        if m:
            specs.append(m.group(1))
        elif "!reset" in line:
            continue
    return specs


def test_edge_publishes_only_80_and_443() -> None:
    block = _service_block("edge", _prod_text())
    specs = _published_port_specs(block)
    assert set(specs) == {"80:80", "443:443"}


def test_grafana_loopback_only_extra_publish() -> None:
    text = _prod_text()
    grafana = _service_block("grafana", text)
    specs = _published_port_specs(grafana)
    assert specs == ["127.0.0.1:8300:3000"]
    # No other service may publish host ports except edge 80/443 and this loopback.
    for name in (
        "api",
        "postgres",
        "rabbitmq",
        "keycloak",
        "prometheus",
        "alertmanager",
        "ops-exporter",
        "relay",
        "worker",
        "scheduler",
    ):
        block = _service_block(name, text)
        assert _published_port_specs(block) == [], f"{name} must not publish host ports"
        assert "ports: !reset []" in block or "ports: !reset" in block


def test_no_forbidden_host_port_range_or_metrics_ports() -> None:
    text = _prod_text()
    forbidden = (
        ":8001",
        ":15692",
        ":5432",
        ":5672",
        ":15672",
        ":9090",
        ":9093",
        ":9108",
    )
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "127.0.0.1:8300:3000" in stripped:
            continue
        if '"80:80"' in stripped or '"443:443"' in stripped:
            continue
        for needle in forbidden:
            assert needle not in stripped, f"forbidden publish token {needle} in {stripped!r}"
        # Host ports 8084-8183
        for m in re.finditer(r"(\d{4}):(\d+)", stripped):
            host_port = int(m.group(1))
            assert not (8084 <= host_port <= 8183), f"forbidden host port range: {stripped}"


def test_production_environment_on_all_backend_services() -> None:
    text = _prod_text()
    for name in _BACKEND_SERVICES:
        block = _service_block(name, text)
        assert "STOCKPILOT_ENVIRONMENT: production" in block, (
            f"{name} must set STOCKPILOT_ENVIRONMENT=production"
        )


def test_keycloak_hostname_v2_options() -> None:
    block = _service_block("keycloak", _prod_text())
    env_lines = [
        line.strip()
        for line in block.splitlines()
        if line.strip().startswith("KC_") or "KC_" in line
    ]
    env_blob = "\n".join(env_lines)
    assert "KC_HOSTNAME_STRICT_HTTPS" not in env_blob
    assert 'KC_HOSTNAME_PORT: ""' in block
    assert "KC_HOSTNAME: https://${STOCKPILOT_AUTH_HOST" in block
    assert "KC_HOSTNAME_BACKCHANNEL_DYNAMIC" in block
    assert "KC_PROXY_HEADERS: xforwarded" in block
    assert "KC_HTTP_ENABLED" in block
    assert "KC_BOOTSTRAP_ADMIN_USERNAME" in block
    assert "start-dev" not in block
    assert "- start" in block or '"start"' in block


def test_images_use_lowercase_ghcr_owner() -> None:
    text = _prod_text()
    assert "ghcr.io/majid-haidarasl/stockpilot-backend" in text
    assert "ghcr.io/majid-haidarasl/stockpilot-edge" in text
    assert re.search(r"ghcr\.io/[A-Z]", text) is None


def test_keycloak_volumes_override_uses_host_realm_file() -> None:
    block = _service_block("keycloak", _prod_text())
    assert "volumes: !override" in block
    assert "STOCKPILOT_KEYCLOAK_REALM_FILE" in block
    assert "/opt/keycloak/data/import/stockpilot-realm.json" in block


def test_api_cookie_secure_and_single_metrics_expose_only_via_base() -> None:
    block = _service_block("api", _prod_text())
    assert 'STOCKPILOT_COOKIE_SECURE: "true"' in block
    assert 'STOCKPILOT_API_METRICS_PORT: "8001"' in block or "8001" in block
