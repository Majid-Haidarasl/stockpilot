"""Cancel leftover RESERVED orders for load-* tenants via the normal API.

No direct DB updates. Run after Locust (same compose network / env as load-test).
"""

from __future__ import annotations

import os
import sys
import uuid

import httpx

from auth import oidc_login

BASE = os.environ.get("STOCKPILOT_LOAD_BASE", "https://stockpilot.local").rstrip("/")
AUTH_HOST = os.environ.get("STOCKPILOT_LOAD_AUTH_HOST", "auth.stockpilot.local")
PASSWORD = os.environ.get("STOCKPILOT_LOAD_PASSWORD", "")
TENANT_COUNT = int(os.environ.get("STOCKPILOT_LOAD_TENANT_COUNT", "10"))


def _cancel_reserved(client: httpx.Client, tenant_id: str, csrf: str) -> int:
    cancelled = 0
    cursor_created_at: str | None = None
    cursor_id: str | None = None
    for _ in range(40):  # safety cap
        params: dict[str, str | int] = {"status": "RESERVED", "limit": 50}
        if cursor_created_at and cursor_id:
            params["cursor_created_at"] = cursor_created_at
            params["cursor_id"] = cursor_id
        resp = client.get(
            f"{BASE}/api/v1/tenants/{tenant_id}/orders",
            params=params,
        )
        if resp.status_code != 200:
            print(f"list RESERVED failed: {resp.status_code} {resp.text[:200]}", file=sys.stderr)
            break
        rows = resp.json()
        if not rows:
            break
        for order in rows:
            oid = order["id"]
            version = int(order["version"])
            cancel = client.post(
                f"{BASE}/api/v1/tenants/{tenant_id}/orders/{oid}/cancel",
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": f"load-cleanup-cancel-{oid}-{uuid.uuid4().hex[:8]}",
                },
                json={"expected_version": version},
            )
            if cancel.status_code == 200:
                cancelled += 1
            else:
                print(
                    f"cancel {oid} -> {cancel.status_code} {cancel.text[:160]}",
                    file=sys.stderr,
                )
        if len(rows) < 50:
            break
        last = rows[-1]
        if not last.get("created_at"):
            break
        cursor_created_at = str(last["created_at"])
        cursor_id = str(last["id"])
    return cancelled


def main() -> int:
    if not PASSWORD:
        print("STOCKPILOT_LOAD_PASSWORD is required", file=sys.stderr)
        return 1
    total = 0
    with httpx.Client(verify=False, follow_redirects=False, timeout=60.0) as client:
        for i in range(1, TENANT_COUNT + 1):
            user = f"admin@load-{i:02d}.test"
            try:
                info = oidc_login(
                    client,
                    base=BASE,
                    auth_host=AUTH_HOST,
                    username=user,
                    password=PASSWORD,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"login failed for {user}: {exc}", file=sys.stderr)
                continue
            n = _cancel_reserved(client, str(info["tenant_id"]), str(info["csrf"]))
            print(f"{user}: cancelled_reserved={n}", flush=True)
            total += n
            # Fresh client cookies per tenant to avoid session mix-ups.
            client.cookies.clear()
    print(f"cleanup_reserved complete total_cancelled={total}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
