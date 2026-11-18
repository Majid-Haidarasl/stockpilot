"""One-shot Keycloak Admin API: create load-01..load-10 users (no realm re-import).

Passwords from STOCKPILOT_LOAD_PASSWORD. Admin creds from KEYCLOAK_ADMIN*.
Writes email→id map to STOCKPILOT_LOAD_SUBJECTS_FILE (default /results/load-subjects.json).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

KC = os.environ.get("STOCKPILOT_KEYCLOAK_ADMIN_URL", "http://keycloak:8080").rstrip("/")
REALM = os.environ.get("STOCKPILOT_KEYCLOAK_REALM", "stockpilot")
ADMIN_USER = os.environ.get("KEYCLOAK_ADMIN", "admin")
ADMIN_PASSWORD = os.environ.get("KEYCLOAK_ADMIN_PASSWORD", "")
LOAD_PASSWORD = os.environ.get("STOCKPILOT_LOAD_PASSWORD", "")
TENANT_COUNT = int(os.environ.get("STOCKPILOT_LOAD_TENANT_COUNT", "10"))
OUT = Path(
    os.environ.get(
        "STOCKPILOT_LOAD_SUBJECTS_FILE",
        "/results/load-subjects.json",
    )
)


def _token(client: httpx.Client) -> str:
    resp = client.post(
        f"{KC}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": ADMIN_USER,
            "password": ADMIN_PASSWORD,
        },
    )
    resp.raise_for_status()
    return str(resp.json()["access_token"])


def _find_user(client: httpx.Client, token: str, username: str) -> dict | None:
    resp = client.get(
        f"{KC}/admin/realms/{REALM}/users",
        params={"username": username, "exact": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None


def _ensure_user(
    client: httpx.Client,
    token: str,
    *,
    email: str,
    first_name: str,
) -> str:
    existing = _find_user(client, token, email)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if existing is None:
        create = client.post(
            f"{KC}/admin/realms/{REALM}/users",
            headers=headers,
            json={
                "username": email,
                "email": email,
                "enabled": True,
                "emailVerified": True,
                "firstName": first_name,
                "lastName": "Load",
            },
        )
        if create.status_code not in (201, 204):
            raise RuntimeError(f"create {email}: {create.status_code} {create.text[:200]}")
        existing = _find_user(client, token, email)
        if existing is None:
            raise RuntimeError(f"created but not found: {email}")
    user_id = str(existing["id"])
    reset = client.put(
        f"{KC}/admin/realms/{REALM}/users/{user_id}/reset-password",
        headers=headers,
        json={"type": "password", "value": LOAD_PASSWORD, "temporary": False},
    )
    if reset.status_code not in (204, 200):
        raise RuntimeError(f"password {email}: {reset.status_code} {reset.text[:200]}")
    return user_id


def main() -> int:
    if not ADMIN_PASSWORD:
        print("KEYCLOAK_ADMIN_PASSWORD is required", file=sys.stderr)
        return 1
    if not LOAD_PASSWORD or LOAD_PASSWORD.startswith("REPLACE"):
        print("STOCKPILOT_LOAD_PASSWORD must be set (non-placeholder)", file=sys.stderr)
        return 1
    subjects: dict[str, str] = {}
    with httpx.Client(timeout=60.0) as client:
        token = _token(client)
        for i in range(1, TENANT_COUNT + 1):
            for role, prefix in (("admin", "admin"), ("sales", "sales")):
                email = f"{prefix}@load-{i:02d}.test"
                uid = _ensure_user(
                    client,
                    token,
                    email=email,
                    first_name=f"Load{i:02d}{role}",
                )
                subjects[email] = uid
                print(f"OK {email} id={uid}", flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(subjects, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {OUT} users={len(subjects)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
