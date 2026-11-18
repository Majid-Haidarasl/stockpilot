"""Prod-like smoke: health, /metrics blocked, OIDC login, image upload.

Run inside the compose network (see docs/reports/phase6-run6_2.md).
Uses STOCKPILOT_SMOKE_* env vars. TLS verify off for Caddy internal CA.
"""

from __future__ import annotations

import io
import os
import sys
import uuid
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx
from PIL import Image

BASE = os.environ.get("STOCKPILOT_SMOKE_BASE", "https://edge").rstrip("/")
AUTH_HOST = os.environ.get("STOCKPILOT_SMOKE_AUTH_HOST", "auth.stockpilot.local")
USER = os.environ.get("STOCKPILOT_SMOKE_USER", "admin@aftab.test")
PASSWORD = os.environ.get("STOCKPILOT_SMOKE_PASSWORD", "Passw0rd!")


class _FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.action: str | None = None
        self.inputs: dict[str, str] = {}
        self._in_form = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = {k: (v or "") for k, v in attrs}
        if tag == "form":
            self._in_form = True
            self.action = ad.get("action") or self.action
        if self._in_form and tag == "input":
            name = ad.get("name")
            if name:
                self.inputs[name] = ad.get("value", "")


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (20, 40, 60)).save(buf, format="PNG")
    return buf.getvalue()


def main() -> int:
    client = httpx.Client(verify=False, follow_redirects=False, timeout=30.0)
    try:
        live = client.get(f"{BASE}/health/live")
        assert live.status_code == 200, live.text
        print("OK health/live")

        metrics = client.get(f"{BASE}/metrics")
        assert metrics.status_code == 404, (
            f"/metrics must be 404 from edge, got {metrics.status_code}: {metrics.text[:200]}"
        )
        metrics_sub = client.get(f"{BASE}/metrics/prometheus")
        assert metrics_sub.status_code == 404, metrics_sub.status_code
        print("OK /metrics and /metrics/* return 404")

        login = client.get(f"{BASE}/auth/login", follow_redirects=False)
        assert login.status_code in (302, 303), login.status_code
        loc = login.headers["location"]
        assert AUTH_HOST in loc or "openid-connect/auth" in loc, loc
        print("OK login redirect to Keycloak")

        # Follow authorize URL (may be absolute).
        page = client.get(loc, follow_redirects=True)
        assert page.status_code == 200, page.status_code
        parser = _FormParser()
        parser.feed(page.text)
        assert parser.action, "login form action missing"
        action = urljoin(str(page.url), parser.action)
        form = dict(parser.inputs)
        form["username"] = USER
        form["password"] = PASSWORD
        # Keycloak 26 often uses name=login
        if "credentialId" not in form:
            form.setdefault("credentialId", "")

        posted = client.post(action, data=form, follow_redirects=False)
        # May redirect through several hops to /auth/callback
        hops = 0
        resp = posted
        while resp.status_code in (302, 303, 307, 308) and hops < 10:
            nxt = resp.headers.get("location")
            assert nxt, resp.status_code
            if nxt.startswith("/"):
                # Relative to current IdP or app host
                nxt = urljoin(str(resp.url), nxt)
            resp = client.get(nxt, follow_redirects=False)
            hops += 1
            if "/auth/callback" in str(resp.url) or "/auth/callback" in nxt:
                # Consume callback if we only got the Location
                if resp.status_code in (302, 303) and "stockpilot" in (
                    urlparse(resp.headers.get("location", "")).hostname or ""
                ):
                    resp = client.get(
                        urljoin(str(resp.url), resp.headers["location"]),
                        follow_redirects=False,
                    )
                break

        assert client.cookies.get("stockpilot_session"), dict(client.cookies)
        me = client.get(f"{BASE}/api/v1/me", follow_redirects=True)
        assert me.status_code == 200, me.text
        print("OK login + /api/v1/me")

        me_json = me.json()
        orgs = me_json.get("organizations") or []
        assert orgs, me_json
        tenant_id = orgs[0]["tenant_id"]

        csrf = client.cookies.get("stockpilot_csrf")
        assert csrf, dict(client.cookies)
        sku = f"PRODLIKE-{uuid.uuid4().hex[:8]}"
        create = client.post(
            f"{BASE}/api/v1/tenants/{tenant_id}/products",
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": f"prodlike-smoke-create-{sku}",
            },
            json={
                "sku": sku,
                "title": "Prodlike Smoke",
                "unit_price_rial": "1000",
                "is_active": True,
            },
        )
        assert create.status_code in (200, 201), create.text
        product_id = create.json()["id"]
        print("OK create product")

        upload = client.post(
            f"{BASE}/api/v1/tenants/{tenant_id}/products/{product_id}/images",
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": f"prodlike-smoke-upload-{sku}",
            },
            files={"file": ("smoke.png", _png(), "image/png")},
        )
        assert upload.status_code in (200, 201), upload.text
        print("OK image upload")
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
