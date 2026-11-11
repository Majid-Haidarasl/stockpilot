"""Auth session HTTP checks that do not require a live Keycloak round-trip."""

from __future__ import annotations

from fastapi.testclient import TestClient

from stockpilot.bootstrap.app import create_app


def test_me_requires_session() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/me")
    assert response.status_code == 401


def test_logout_requires_session() -> None:
    client = TestClient(create_app())
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 401


def test_callback_rejects_missing_code_state() -> None:
    client = TestClient(create_app(), follow_redirects=False)
    response = client.get("/auth/callback")
    assert response.status_code == 400


def test_callback_rejects_unknown_state() -> None:
    client = TestClient(create_app(), follow_redirects=False)
    response = client.get("/auth/callback", params={"code": "x", "state": "unknown"})
    assert response.status_code == 400
