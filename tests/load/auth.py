"""OIDC form login for Locust / cleanup (mirrors infra/prodlike/smoke.py)."""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx


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


def oidc_login(
    client: httpx.Client,
    *,
    base: str,
    auth_host: str,
    username: str,
    password: str,
) -> dict[str, Any]:
    """Complete Keycloak form login; leave session + CSRF cookies on client."""
    base = base.rstrip("/")
    login = client.get(f"{base}/auth/login", follow_redirects=False)
    if login.status_code not in (302, 303):
        raise RuntimeError(f"login redirect expected, got {login.status_code}")
    loc = login.headers["location"]
    if auth_host not in loc and "openid-connect/auth" not in loc:
        raise RuntimeError(f"unexpected authorize location: {loc}")

    page = client.get(loc, follow_redirects=True)
    if page.status_code != 200:
        raise RuntimeError(f"Keycloak login page status {page.status_code}")
    parser = _FormParser()
    parser.feed(page.text)
    if not parser.action:
        raise RuntimeError("login form action missing")
    action = urljoin(str(page.url), parser.action)
    form = dict(parser.inputs)
    form["username"] = username
    form["password"] = password
    form.setdefault("credentialId", "")

    resp = client.post(action, data=form, follow_redirects=False)
    hops = 0
    while resp.status_code in (302, 303, 307, 308) and hops < 12:
        nxt = resp.headers.get("location")
        if not nxt:
            break
        if nxt.startswith("/"):
            nxt = urljoin(str(resp.url), nxt)
        resp = client.get(nxt, follow_redirects=False)
        hops += 1
        if "/auth/callback" in str(resp.url) or "/auth/callback" in nxt:
            if resp.status_code in (302, 303) and "stockpilot" in (
                urlparse(resp.headers.get("location", "")).hostname or ""
            ):
                resp = client.get(
                    urljoin(str(resp.url), resp.headers["location"]),
                    follow_redirects=False,
                )
            break

    if not client.cookies.get("stockpilot_session"):
        raise RuntimeError(f"session cookie missing after login for {username}")

    me = client.get(f"{base}/api/v1/me", follow_redirects=True)
    if me.status_code != 200:
        raise RuntimeError(f"/api/v1/me failed: {me.status_code} {me.text[:200]}")
    body = me.json()
    orgs = body.get("organizations") or []
    if not orgs:
        raise RuntimeError(f"no organizations for {username}: {body}")
    csrf = client.cookies.get("stockpilot_csrf")
    if not csrf:
        raise RuntimeError("csrf cookie missing")
    return {
        "tenant_id": orgs[0]["tenant_id"],
        "slug": orgs[0].get("slug"),
        "role": orgs[0].get("role"),
        "csrf": csrf,
        "me": body,
    }
