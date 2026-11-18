"""Prod / local Caddyfiles must never expose metrics or admin backends."""

from __future__ import annotations

import os
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]

CADDY_PROD = Path(
    os.environ.get("STOCKPILOT_CADDY_PROD_PATH", str(_REPO / "infra" / "caddy" / "Caddyfile"))
)
CADDY_LOCAL = Path(
    os.environ.get(
        "STOCKPILOT_CADDY_LOCAL_PATH",
        str(_REPO / "infra" / "caddy" / "Caddyfile.local"),
    )
)

_FORBIDDEN_UPSTREAMS = (
    "api:8001",
    ":8001",
    "prometheus",
    "grafana",
    "alertmanager",
    "rabbitmq",
    "postgres",
    "15672",
    "15692",
    "9090",
    "9093",
    "9108",
    "5432",
)


def _read(path: Path) -> str:
    assert path.is_file(), f"missing Caddyfile: {path}"
    return path.read_text(encoding="utf-8")


def _assert_common_guards(text: str, *, label: str) -> None:
    assert "handle /metrics" in text, f"{label}: must explicitly handle /metrics"
    assert "handle /metrics/*" in text, f"{label}: must explicitly handle /metrics/*"
    assert re.search(r"(?ms)handle /metrics(?:/\*)?\s*\{[^}]*respond 404", text), (
        f"{label}: /metrics handlers must respond 404"
    )
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "/metrics" in stripped:
            assert (
                stripped.startswith("handle /metrics")
                or stripped == "respond 404"
                or "never route /metrics" in stripped.lower()
            ), f"{label}: unexpected /metrics line ({stripped!r})"
            continue
        for needle in _FORBIDDEN_UPSTREAMS:
            assert needle not in stripped, (
                f"{label}: forbidden upstream token {needle!r} in {stripped!r}"
            )
    assert "reverse_proxy api:8000" in text
    assert "reverse_proxy keycloak:8080" in text
    assert "handle /api/*" in text
    assert "handle /auth/*" in text
    assert "handle /health/*" in text


def test_prod_caddyfile_routing_guards() -> None:
    text = _read(CADDY_PROD)
    _assert_common_guards(text, label="Caddyfile")
    assert "Strict-Transport-Security" in text
    assert "Content-Security-Policy" in text
    assert "frame-ancestors 'none'" in text
    assert "X-Content-Type-Options" in text


def test_local_caddyfile_routing_guards() -> None:
    text = _read(CADDY_LOCAL)
    _assert_common_guards(text, label="Caddyfile.local")
    assert "tls internal" in text
    assert "stockpilot.local" in text
    assert "auth.stockpilot.local" in text
