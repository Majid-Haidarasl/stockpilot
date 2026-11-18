"""StockPilot Run 6.4 Locust scenarios (prod-like edge only).

Phases (LoadTestShape): warm-up 0–2m, steady 2–18m, spike 18–20m.
Pass/fail uses the steady window only (see analyze_phases.py).
"""

from __future__ import annotations

import os
import random
import time
import uuid
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

from locust import HttpUser, LoadTestShape, TaskSet, between, events, task
from locust.exception import StopUser

BASE = os.environ.get("STOCKPILOT_LOAD_BASE", "https://stockpilot.local").rstrip("/")
AUTH_HOST = os.environ.get("STOCKPILOT_LOAD_AUTH_HOST", "auth.stockpilot.local")
PASSWORD = os.environ.get("STOCKPILOT_LOAD_PASSWORD", "")
RESULTS_DIR = Path(os.environ.get("STOCKPILOT_LOAD_RESULTS_DIR", "/results"))
TENANT_COUNT = int(os.environ.get("STOCKPILOT_LOAD_TENANT_COUNT", "10"))

# Absolute phase boundaries (seconds from Locust start).
WARMUP_END = 120
STEADY_END = 1080
SPIKE_END = 1200

PHASE_FILE = RESULTS_DIR / "phase_boundaries.json"


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


def _phase_name(run_time: float) -> str:
    if run_time < WARMUP_END:
        return "warmup"
    if run_time < STEADY_END:
        return "steady"
    return "spike"


@events.test_start.add_listener
def _on_test_start(environment, **_kwargs) -> None:  # noqa: ANN001
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    started = time.time()
    PHASE_FILE.write_text(
        __import__("json").dumps(
            {
                "wall_start_unix": started,
                "warmup_end_s": WARMUP_END,
                "steady_end_s": STEADY_END,
                "spike_end_s": SPIKE_END,
                "note": "Locust run_time windows; CSV full-history rows use relative time",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _login(session, username: str, password: str) -> dict:  # noqa: ANN001
    """OIDC form login using Locust/requests session; cookies stick on session."""
    with session.get(
        f"{BASE}/auth/login",
        name="/auth/login",
        allow_redirects=False,
        catch_response=True,
    ) as login:
        if login.status_code not in (302, 303):
            login.failure(f"expected redirect, got {login.status_code}")
            raise StopUser()
        loc = login.headers.get("location") or ""
        login.success()

    page = session.get(loc, name="/auth/keycloak-form", allow_redirects=True)
    parser = _FormParser()
    parser.feed(page.text)
    if not parser.action:
        raise StopUser()
    action = urljoin(page.url, parser.action)
    form = dict(parser.inputs)
    form["username"] = username
    form["password"] = password
    form.setdefault("credentialId", "")

    resp = session.post(action, data=form, name="/auth/keycloak-post", allow_redirects=False)
    hops = 0
    while resp.status_code in (302, 303, 307, 308) and hops < 12:
        nxt = resp.headers.get("location")
        if not nxt:
            break
        if nxt.startswith("/"):
            nxt = urljoin(resp.url, nxt)
        resp = session.get(nxt, name="/auth/callback-hop", allow_redirects=False)
        hops += 1
        if "/auth/callback" in resp.url or (nxt and "/auth/callback" in nxt):
            if resp.status_code in (302, 303):
                host = urlparse(resp.headers.get("location", "")).hostname or ""
                if "stockpilot" in host:
                    resp = session.get(
                        urljoin(resp.url, resp.headers["location"]),
                        name="/auth/callback",
                        allow_redirects=False,
                    )
            break

    me = session.get(f"{BASE}/api/v1/me", name="GET /api/v1/me")
    if me.status_code != 200:
        raise StopUser()
    body = me.json()
    orgs = body.get("organizations") or []
    if not orgs:
        raise StopUser()
    csrf = session.cookies.get("stockpilot_csrf")
    if not csrf:
        raise StopUser()
    return {
        "tenant_id": orgs[0]["tenant_id"],
        "slug": orgs[0].get("slug"),
        "role": orgs[0].get("role"),
        "csrf": csrf,
    }


class CommercialTasks(TaskSet):
    tenant_id: str = ""
    csrf: str = ""
    role: str = ""
    product_ids: list[str]
    customer_id: str | None = None
    reserved: list[tuple[str, int]]  # (order_id, version)

    def on_start(self) -> None:
        if not PASSWORD:
            raise StopUser()
        # Spread VUs across load-01..load-N; every 5th VU is admin (members).
        uid = getattr(self.user, "_stockpilot_vu_index", None)
        if uid is None:
            uid = random.randint(1, max(TENANT_COUNT * 5, 15))
            self.user._stockpilot_vu_index = uid  # type: ignore[attr-defined]
        idx = ((int(uid) - 1) % TENANT_COUNT) + 1
        if int(uid) % 5 == 0:
            username = f"admin@load-{idx:02d}.test"
        else:
            username = f"sales@load-{idx:02d}.test"

        info = _login(self.client, username, PASSWORD)
        self.tenant_id = str(info["tenant_id"])
        self.csrf = str(info["csrf"])
        self.role = str(info.get("role") or "")
        self.product_ids = []
        self.customer_id = None
        self.reserved = []
        self._refresh_catalog()

    def _headers(self, *, idem: str | None = None) -> dict[str, str]:
        h = {"X-CSRF-Token": self.csrf}
        if idem:
            h["Idempotency-Key"] = idem
        return h

    def _t(self, path: str) -> str:
        return f"{BASE}/api/v1/tenants/{self.tenant_id}{path}"

    def _refresh_catalog(self) -> None:
        with self.client.get(
            self._t("/products"),
            name="GET /products",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"products {resp.status_code}")
                return
            rows = resp.json()
            self.product_ids = [str(r["id"]) for r in rows if r.get("is_active", True)]
            resp.success()
        with self.client.get(
            self._t("/customers"),
            name="GET /customers",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200 and resp.json():
                self.customer_id = str(resp.json()[0]["id"])
                resp.success()
            else:
                resp.failure(f"customers {resp.status_code}")

    @task(25)
    def browse_products(self) -> None:
        self.client.get(self._t("/products"), name="GET /products")

    @task(15)
    def view_product_stock(self) -> None:
        # No single-product GET in v1; inventory list is the product-stock view.
        self.client.get(self._t("/inventory"), name="GET /inventory")

    @task(15)
    def list_orders(self) -> None:
        self.client.get(self._t("/orders"), name="GET /orders")

    @task(10)
    def dashboard(self) -> None:
        # Dashboard requires an inclusive shipped-total window (`from` / `to`).
        self.client.get(
            self._t("/dashboard"),
            params={"from": "2020-01-01T00:00:00Z", "to": "2030-01-01T00:00:00Z"},
            name="GET /dashboard",
        )

    @task(5)
    def admin_members(self) -> None:
        if self.role != "admin":
            self.client.get(self._t("/orders"), name="GET /orders")
            return
        self.client.get(self._t("/members"), name="GET /members")

    @task(5)
    def inventory_movements(self) -> None:
        self.client.get(self._t("/inventory/movements"), name="GET /inventory/movements")

    @task(15)
    def create_and_reserve(self) -> None:
        if not self.customer_id or not self.product_ids:
            self._refresh_catalog()
            if not self.customer_id or not self.product_ids:
                return
        product_id = random.choice(self.product_ids)
        idem = f"load-create-{uuid.uuid4()}"
        body = {
            "customer_id": self.customer_id,
            "lines": [{"product_id": product_id, "quantity": 1}],
        }
        with self.client.post(
            self._t("/orders"),
            json=body,
            headers=self._headers(idem=idem),
            name="POST /orders",
            catch_response=True,
        ) as create:
            if create.status_code not in (200, 201):
                create.failure(f"create {create.status_code}")
                return
            order = create.json()
            create.success()
        order_id = str(order["id"])
        version = int(order["version"])
        with self.client.post(
            self._t(f"/orders/{order_id}/reserve"),
            json={"expected_version": version},
            headers=self._headers(idem=f"load-reserve-{order_id}"),
            name="POST /orders/{id}/reserve",
            catch_response=True,
        ) as reserve:
            if reserve.status_code == 200:
                reserved = reserve.json()
                self.reserved.append((order_id, int(reserved["version"])))
                # Cap in-flight reserved per VU to limit oversell pressure.
                if len(self.reserved) > 3:
                    self._cancel_one()
                reserve.success()
            elif reserve.status_code in (409, 422):
                reserve.success()  # business conflict under contention
            else:
                reserve.failure(f"reserve {reserve.status_code}")

    @task(5)
    def confirm_order(self) -> None:
        if not self.reserved:
            return
        order_id, version = self.reserved.pop(0)
        with self.client.post(
            self._t(f"/orders/{order_id}/confirm"),
            json={"expected_version": version},
            headers=self._headers(idem=f"load-confirm-{order_id}"),
            name="POST /orders/{id}/confirm",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code in (409, 422):
                resp.success()
            else:
                resp.failure(f"confirm {resp.status_code}")

    @task(5)
    def cancel_order(self) -> None:
        self._cancel_one()

    def _cancel_one(self) -> None:
        if not self.reserved:
            return
        order_id, version = self.reserved.pop()
        with self.client.post(
            self._t(f"/orders/{order_id}/cancel"),
            json={"expected_version": version},
            headers=self._headers(idem=f"load-cancel-{order_id}"),
            name="POST /orders/{id}/cancel",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code in (409, 422):
                resp.success()
            else:
                resp.failure(f"cancel {resp.status_code}")

    def on_stop(self) -> None:
        # Best-effort cancel of VU-local reserved orders via normal API.
        while self.reserved:
            self._cancel_one()


class StockPilotUser(HttpUser):
    tasks = [CommercialTasks]
    wait_time = between(0.8, 1.6)
    host = BASE
    # Locust verifies TLS; prod-like uses internal CA.
    def on_start(self) -> None:
        self.client.verify = False  # noqa: S501 — Caddy tls internal


class StockPilotLoadShape(LoadTestShape):
    """Warm-up → steady → short spike (20 minutes total)."""

    def tick(self):  # noqa: ANN201
        t = self.get_run_time()
        if t < WARMUP_END:
            users = max(1, min(15, int(15 * (t / WARMUP_END) + 1)))
            return (users, 2.0)
        if t < STEADY_END:
            return (15, 2.0)
        if t < SPIKE_END:
            return (30, 5.0)
        return None
