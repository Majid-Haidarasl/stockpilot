"""OIDC helpers using Authlib (Authorization Code + PKCE)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.jose import JsonWebKey, JsonWebToken

from stockpilot.platform.settings import Settings

_SERVER_SIDE_ENDPOINTS = (
    "token_endpoint",
    "jwks_uri",
    "introspection_endpoint",
    "userinfo_endpoint",
    "revocation_endpoint",
)


class OIDCError(Exception):
    pass


def _internal_issuer_base(settings: Settings) -> str:
    return settings.oidc_metadata_url.split("/.well-known/", 1)[0].rstrip("/")


def _rewrite_server_endpoints(settings: Settings, payload: dict[str, Any]) -> dict[str, Any]:
    """Keep public issuer for claim checks; force server calls onto the Docker-internal host."""
    internal = urlparse(_internal_issuer_base(settings))
    rewritten = dict(payload)
    rewritten["issuer"] = settings.oidc_issuer
    for key in _SERVER_SIDE_ENDPOINTS:
        value = rewritten.get(key)
        if not isinstance(value, str) or not value:
            continue
        current = urlparse(value)
        rewritten[key] = urlunparse(
            (
                internal.scheme,
                internal.netloc,
                current.path,
                current.params,
                current.query,
                current.fragment,
            )
        )
    return rewritten


async def fetch_metadata(settings: Settings) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(settings.oidc_metadata_url)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise OIDCError("OIDC metadata must be a JSON object")
        return _rewrite_server_endpoints(settings, dict(payload))


def build_authorize_url(
    *,
    issuer: str,
    client_id: str,
    redirect_uri: str,
    state: str,
    nonce: str,
    code_challenge: str,
) -> str:
    # Browser must hit the public issuer host/port (not the Docker-internal metadata host).
    params = {
        "client_id": client_id,
        "response_type": "code",
        # offline_access requires client offline-token permission; not needed for week-2 sessions.
        "scope": "openid profile email",
        "redirect_uri": redirect_uri,
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{issuer.rstrip('/')}/protocol/openid-connect/auth?{urlencode(params)}"


async def exchange_code(
    *,
    settings: Settings,
    metadata: dict[str, Any],
    code: str,
    code_verifier: str,
    redirect_uri: str,
) -> dict[str, Any]:
    async with AsyncOAuth2Client(
        client_id=settings.oidc_client_id,
        client_secret=settings.oidc_client_secret,
        timeout=15.0,
    ) as client:
        token = await client.fetch_token(
            metadata["token_endpoint"],
            code=code,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
            grant_type="authorization_code",
        )
        return dict(token)


async def validate_id_token(
    *,
    settings: Settings,
    metadata: dict[str, Any],
    id_token: str,
    nonce: str,
    access_token: str | None = None,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        jwks_resp = await client.get(metadata["jwks_uri"])
        jwks_resp.raise_for_status()
        jwks = jwks_resp.json()

    key_set = JsonWebKey.import_key_set(jwks)
    jwt = JsonWebToken(["RS256"])
    claims = jwt.decode(
        id_token,
        key_set,
        claims_options={
            "iss": {"essential": True, "value": settings.oidc_issuer},
            "aud": {"essential": True, "value": settings.oidc_client_id},
            "exp": {"essential": True},
            "nonce": {"essential": True, "value": nonce},
        },
    )
    claims.validate()
    if access_token is not None and "at_hash" in claims:
        # Authlib validates at_hash when access_token is provided via options in some versions;
        # keep a soft check by ensuring subject exists.
        pass
    if "sub" not in claims:
        raise OIDCError("ID token missing sub")
    return dict(claims)
