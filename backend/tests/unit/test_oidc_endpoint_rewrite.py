"""Server-side OIDC endpoints must stay on the Docker-internal Keycloak host."""

from __future__ import annotations

from stockpilot.platform.security.oidc import _rewrite_server_endpoints
from stockpilot.platform.settings import Settings


def test_rewrite_keeps_public_issuer_and_rewrites_token_jwks() -> None:
    settings = Settings.model_construct(
        oidc_issuer="https://auth.example.com/realms/stockpilot",
        oidc_metadata_url=(
            "http://keycloak:8080/realms/stockpilot/.well-known/openid-configuration"
        ),
    )
    payload = {
        "issuer": "https://auth.example.com/realms/stockpilot",
        "authorization_endpoint": (
            "https://auth.example.com/realms/stockpilot/protocol/openid-connect/auth"
        ),
        "token_endpoint": (
            "https://auth.example.com/realms/stockpilot/protocol/openid-connect/token"
        ),
        "jwks_uri": ("https://auth.example.com/realms/stockpilot/protocol/openid-connect/certs"),
        "end_session_endpoint": (
            "https://auth.example.com/realms/stockpilot/protocol/openid-connect/logout"
        ),
    }
    out = _rewrite_server_endpoints(settings, payload)
    assert out["issuer"] == "https://auth.example.com/realms/stockpilot"
    assert out["authorization_endpoint"].startswith("https://auth.example.com/")
    assert out["token_endpoint"].startswith("http://keycloak:8080/")
    assert out["jwks_uri"].startswith("http://keycloak:8080/")
    # Browser logout stays on public host (not rewritten).
    assert out["end_session_endpoint"].startswith("https://auth.example.com/")
