"""Quick login + list products smoke for load users."""

from __future__ import annotations

import os
import sys

import httpx

from auth import oidc_login

BASE = os.environ.get("STOCKPILOT_LOAD_BASE", "https://stockpilot.local").rstrip("/")
AUTH_HOST = os.environ.get("STOCKPILOT_LOAD_AUTH_HOST", "auth.stockpilot.local")
PASSWORD = os.environ.get("STOCKPILOT_LOAD_PASSWORD", "")


def main() -> int:
    if not PASSWORD:
        print("STOCKPILOT_LOAD_PASSWORD required", file=sys.stderr)
        return 1
    with httpx.Client(verify=False, follow_redirects=False, timeout=60.0) as client:
        info = oidc_login(
            client,
            base=BASE,
            auth_host=AUTH_HOST,
            username="admin@load-01.test",
            password=PASSWORD,
        )
        print("OK", info["slug"], info["role"], info["tenant_id"], flush=True)
        resp = client.get(f"{BASE}/api/v1/tenants/{info['tenant_id']}/products")
        print("products", resp.status_code, len(resp.json()), flush=True)
        return 0 if resp.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
