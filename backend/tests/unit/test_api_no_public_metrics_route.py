"""Public API must not expose /metrics (internal :8001 only when enabled)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from stockpilot.bootstrap.app import create_app


def test_public_app_has_no_metrics_route(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STOCKPILOT_API_METRICS_ENABLED", "false")
    app = create_app()
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 404
