import os
import sys

import httpx

from auth import oidc_login

BASE = "https://stockpilot.local"


def main() -> int:
    with httpx.Client(verify=False, follow_redirects=False, timeout=60.0) as client:
        info = oidc_login(
            client,
            base=BASE,
            auth_host="auth.stockpilot.local",
            username="admin@load-01.test",
            password=os.environ["STOCKPILOT_LOAD_PASSWORD"],
        )
        tid = info["tenant_id"]
        r = client.get(f"{BASE}/api/v1/tenants/{tid}/dashboard")
        print(r.status_code)
        print(r.text[:800])
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
