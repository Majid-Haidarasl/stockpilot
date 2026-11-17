"""HTTP RED metrics for the API (internal exposition only)."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
    start_http_server,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger("stockpilot.http_metrics")

_REGISTRY = CollectorRegistry()
_STARTED = False
_START_LOCK = threading.Lock()

REQUESTS = Counter(
    "stockpilot_http_requests_total",
    "Total HTTP requests",
    labelnames=("method", "handler", "status_code"),
    registry=_REGISTRY,
)
DURATION = Histogram(
    "stockpilot_http_request_duration_seconds",
    "HTTP request duration in seconds",
    labelnames=("method", "handler"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=_REGISTRY,
)
FORBIDDEN_LABEL_KEYS = frozenset(
    {
        "tenant_id",
        "organization_id",
        "org_id",
        "user_id",
        "order_id",
        "customer_id",
        "event_id",
    }
)


def assert_no_tenant_labels(label_names: tuple[str, ...] | list[str]) -> None:
    bad = FORBIDDEN_LABEL_KEYS.intersection(label_names)
    if bad:
        raise ValueError(f"forbidden high-cardinality labels: {sorted(bad)}")


def handler_label(request: Request) -> str:
    """Low-cardinality route template; never the raw path with ids."""
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        return path
    return "unmatched"


def record_request(
    *,
    method: str,
    handler: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    assert_no_tenant_labels(("method", "handler", "status_code"))
    REQUESTS.labels(method=method, handler=handler, status_code=str(status_code)).inc()
    DURATION.labels(method=method, handler=handler).observe(duration_seconds)


def render_metrics() -> bytes:
    """Return Prometheus text exposition (for tests and the internal server)."""
    return generate_latest(_REGISTRY)


def metrics_content_type() -> str:
    return CONTENT_TYPE_LATEST


class HttpMetricsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        method = request.method
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            handler = handler_label(request)
            duration = time.perf_counter() - started
            record_request(
                method=method,
                handler=handler,
                status_code=status_code,
                duration_seconds=duration,
            )


def start_internal_metrics_server(*, host: str = "0.0.0.0", port: int = 8001) -> bool:
    """Start prometheus_client HTTP server once. Idempotent; returns True if started."""
    global _STARTED
    with _START_LOCK:
        if _STARTED:
            return False
        start_http_server(port, addr=host, registry=_REGISTRY)
        _STARTED = True
        logger.info("api_metrics_server_started host=%s port=%s", host, port)
        return True


def reset_metrics_server_state_for_tests() -> None:
    """Allow unit tests to clear the started flag (does not unbind a live socket)."""
    global _STARTED
    with _START_LOCK:
        _STARTED = False


def metrics_server_started() -> bool:
    return _STARTED


def setup_http_metrics(app: FastAPI, *, enabled: bool, port: int = 8001) -> None:
    """Attach middleware always; bind :port only when enabled (compose api)."""
    app.add_middleware(HttpMetricsMiddleware)

    @asynccontextmanager
    async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if enabled:
            try:
                start_internal_metrics_server(port=port)
            except OSError:
                logger.exception("api_metrics_server_bind_failed port=%s", port)
        yield

    app.router.lifespan_context = _lifespan
