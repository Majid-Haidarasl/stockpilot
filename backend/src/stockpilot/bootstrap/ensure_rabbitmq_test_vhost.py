"""Idempotent create RabbitMQ vhost for backend-checks (no volume wipe).

Uses the management HTTP API so it works against an already-running broker
on an existing named volume. Does not load definitions (avoids wiping users).
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import quote, urlparse

DEFAULT_VHOST = "stockpilot_test"


def _management_base(broker_url: str) -> tuple[str, str, str]:
    """Return (management_root, username, password) from an AMQP broker URL."""
    parsed = urlparse(broker_url)
    user = parsed.username or "guest"
    password = parsed.password or "guest"
    host = parsed.hostname or "rabbitmq"
    # Management plugin listens on 15672 inside the Compose network.
    return f"http://{host}:15672", user, password


def _request(
    *,
    method: str,
    url: str,
    user: str,
    password: str,
    body: dict[str, Any] | None = None,
) -> tuple[int, str]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    token = base64.b64encode(f"{user}:{password}".encode()).decode("ascii")
    req.add_header("Authorization", f"Basic {token}")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return int(resp.status), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8", errors="replace")


def ensure_vhost(
    *,
    broker_url: str,
    vhost: str = DEFAULT_VHOST,
) -> None:
    """Create vhost and grant the broker user full permissions (idempotent)."""
    root, user, password = _management_base(broker_url)
    encoded = quote(vhost, safe="")

    status, detail = _request(
        method="PUT",
        url=f"{root}/api/vhosts/{encoded}",
        user=user,
        password=password,
        body={},
    )
    if status not in (201, 204):
        raise SystemExit(f"ensure_rabbitmq_test_vhost: PUT vhost failed HTTP {status}: {detail}")

    status, detail = _request(
        method="PUT",
        url=f"{root}/api/permissions/{encoded}/{quote(user, safe='')}",
        user=user,
        password=password,
        body={"configure": ".*", "write": ".*", "read": ".*"},
    )
    if status not in (201, 204):
        raise SystemExit(
            f"ensure_rabbitmq_test_vhost: PUT permissions failed HTTP {status}: {detail}"
        )


def broker_url_vhost(broker_url: str) -> str:
    """Return the AMQP vhost path segment ('' or name without leading slash)."""
    parsed = urlparse(broker_url)
    path = parsed.path or "/"
    if path == "/" or path == "":
        return "/"
    return path.lstrip("/") or "/"


def main() -> None:
    broker_url = os.environ.get("STOCKPILOT_CELERY_BROKER_URL")
    if not broker_url:
        print("STOCKPILOT_CELERY_BROKER_URL not set; skipping rabbitmq test vhost", flush=True)
        return
    vhost = os.environ.get("STOCKPILOT_TEST_RABBITMQ_VHOST", DEFAULT_VHOST)
    ensure_vhost(broker_url=broker_url, vhost=vhost)
    print(f"ensure_rabbitmq_test_vhost: vhost {vhost!r} ready", flush=True)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"ensure_rabbitmq_test_vhost failed: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1) from exc
