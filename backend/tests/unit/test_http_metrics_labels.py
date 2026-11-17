"""HTTP metrics label cardinality and exposition helpers."""

from __future__ import annotations

import pytest
from starlette.requests import Request

from stockpilot.platform.observability.http_metrics import (
    assert_no_tenant_labels,
    handler_label,
    metrics_server_started,
    record_request,
    render_metrics,
    reset_metrics_server_state_for_tests,
    start_internal_metrics_server,
)


def test_forbidden_tenant_labels_rejected() -> None:
    with pytest.raises(ValueError, match="forbidden"):
        assert_no_tenant_labels(("method", "tenant_id"))


def test_handler_label_uses_route_template() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/orders/abc",
        "headers": [],
        "query_string": b"",
        "route": type("R", (), {"path": "/orders/{order_id}"})(),
    }
    request = Request(scope)
    assert handler_label(request) == "/orders/{order_id}"


def test_render_metrics_has_no_tenant_label_keys() -> None:
    record_request(
        method="GET",
        handler="/health/live",
        status_code=200,
        duration_seconds=0.01,
    )
    body = render_metrics().decode()
    assert "stockpilot_http_requests_total" in body
    assert 'handler="/health/live"' in body
    # Forbid tenant-identifying *label keys*, not path-template placeholders.
    assert 'tenant_id="' not in body
    assert 'order_id="' not in body
    assert 'user_id="' not in body
    assert 'organization_id="' not in body


def test_metrics_server_start_idempotent_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_metrics_server_state_for_tests()
    calls: list[tuple[int, str]] = []

    def fake_start(port: int, addr: str = "", registry: object = None) -> None:
        calls.append((port, addr))

    monkeypatch.setattr(
        "stockpilot.platform.observability.http_metrics.start_http_server",
        fake_start,
    )
    assert start_internal_metrics_server(port=8001) is True
    assert metrics_server_started() is True
    assert start_internal_metrics_server(port=8001) is False
    assert len(calls) == 1
    reset_metrics_server_state_for_tests()
