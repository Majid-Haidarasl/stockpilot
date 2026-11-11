"""OIDC login/callback/logout and /api/v1/me."""

from __future__ import annotations

import base64
import hashlib
import logging
from datetime import timedelta
from typing import Annotated, Any
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse, RedirectResponse

from stockpilot.modules.access.adapters.inbound.deps import (
    SessionPrincipal,
    require_csrf,
    require_session,
)
from stockpilot.modules.access.adapters.outbound.repo import AccessRepository, utcnow
from stockpilot.platform.persistence.uow import UnitOfWork
from stockpilot.platform.security.crypto import encrypt_secret, hash_token, new_token
from stockpilot.platform.security.oidc import (
    OIDCError,
    build_authorize_url,
    exchange_code,
    fetch_metadata,
    validate_id_token,
)
from stockpilot.platform.settings import Settings, get_settings

router = APIRouter(tags=["auth"])
logger = logging.getLogger(__name__)


def _pkce_pair() -> tuple[str, str]:
    verifier = new_token(48)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def _safe_return_to(settings: Settings, return_to: str | None) -> str:
    candidate = return_to or settings.frontend_default_url
    parsed = urlparse(candidate)
    allowed = {urlparse(origin) for origin in settings.cors_origin_list}
    allowed.add(urlparse(settings.frontend_default_url))
    if parsed.scheme and parsed.netloc:
        if any(parsed.scheme == a.scheme and parsed.netloc == a.netloc for a in allowed):
            return candidate
    return settings.frontend_default_url


def _set_session_cookies(
    response: Response,
    settings: Settings,
    *,
    session_raw: str,
    csrf_raw: str,
) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_raw,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
        max_age=settings.session_max_hours * 3600,
        path="/",
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_raw,
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
        max_age=settings.session_max_hours * 3600,
        path="/",
    )


def _clear_session_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")


@router.get("/auth/login")
async def login_start(
    settings: Annotated[Settings, Depends(get_settings)],
    return_to: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    if settings.oidc_redirect_uri not in settings.allowed_redirect_uri_list:
        raise HTTPException(status_code=500, detail="Redirect URI is not allow-listed")

    # Fail fast if the IdP is unreachable before creating a login attempt.
    await fetch_metadata(settings)
    state = new_token(24)
    nonce = new_token(24)
    verifier, challenge = _pkce_pair()
    expires = utcnow() + timedelta(minutes=10)
    safe_return = _safe_return_to(settings, return_to)

    with UnitOfWork() as uow:
        AccessRepository(uow.connection).create_login_attempt(
            state=state,
            nonce=nonce,
            code_verifier=verifier,
            redirect_uri=settings.oidc_redirect_uri,
            return_to=safe_return,
            expires_at=expires,
        )

    url = build_authorize_url(
        issuer=settings.oidc_issuer,
        client_id=settings.oidc_client_id,
        redirect_uri=settings.oidc_redirect_uri,
        state=state,
        nonce=nonce,
        code_challenge=challenge,
    )
    return RedirectResponse(url=url, status_code=302)


@router.get("/auth/callback")
async def login_callback(
    settings: Annotated[Settings, Depends(get_settings)],
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    if error:
        raise HTTPException(status_code=400, detail="Identity provider returned an error")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing authorization code or state")

    with UnitOfWork() as uow:
        repo = AccessRepository(uow.connection)
        attempt = repo.consume_login_attempt(state)
        if attempt is None:
            raise HTTPException(status_code=400, detail="Invalid or expired login state")
        uow.commit()

    try:
        metadata = await fetch_metadata(settings)
        token = await exchange_code(
            settings=settings,
            metadata=metadata,
            code=code,
            code_verifier=str(attempt["code_verifier"]),
            redirect_uri=str(attempt["redirect_uri"]),
        )
        id_token = token.get("id_token")
        if not id_token:
            raise OIDCError("Missing id_token")
        claims = await validate_id_token(
            settings=settings,
            metadata=metadata,
            id_token=str(id_token),
            nonce=str(attempt["nonce"]),
            access_token=token.get("access_token"),
        )
    except Exception as exc:
        logger.exception("OIDC validation failed: %s", type(exc).__name__)
        raise HTTPException(status_code=400, detail="OIDC validation failed") from exc

    subject = str(claims["sub"])
    email = claims.get("email")
    display_name = claims.get("name") or claims.get("preferred_username")
    session_raw = new_token(32)
    csrf_raw = new_token(32)
    now = utcnow()
    idle = now + timedelta(minutes=settings.session_idle_minutes)
    absolute = now + timedelta(hours=settings.session_max_hours)

    with UnitOfWork() as uow:
        repo = AccessRepository(uow.connection)
        user_id = repo.upsert_user(
            issuer=settings.oidc_issuer,
            subject=subject,
            email=str(email) if email else None,
            display_name=str(display_name) if display_name else None,
        )
        refresh = token.get("refresh_token")
        repo.create_session(
            user_id=user_id,
            session_token_hash=hash_token(session_raw),
            csrf_token_hash=hash_token(csrf_raw),
            encrypted_refresh_token=(
                encrypt_secret(settings.token_encryption_key, str(refresh)) if refresh else None
            ),
            encrypted_id_token=encrypt_secret(settings.token_encryption_key, str(id_token)),
            expires_at=absolute,
            idle_expires_at=idle,
        )

    response = RedirectResponse(url=str(attempt["return_to"]), status_code=302)
    _set_session_cookies(response, settings, session_raw=session_raw, csrf_raw=csrf_raw)
    return response


@router.post("/api/v1/auth/logout")
def logout(
    principal: Annotated[SessionPrincipal, Depends(require_csrf)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> JSONResponse:
    with UnitOfWork() as uow:
        AccessRepository(uow.connection).revoke_session(principal.session_id)

    # Standard Keycloak logout path (browser can follow). Local session is already invalid.
    end_session = f"{settings.oidc_issuer}/protocol/openid-connect/logout?" + urlencode(
        {
            "client_id": settings.oidc_client_id,
            "post_logout_redirect_uri": settings.frontend_default_url,
        }
    )
    response = JSONResponse({"status": "logged_out", "keycloak_logout_url": end_session})
    _clear_session_cookies(response, settings)
    return response


@router.get("/api/v1/me")
def me(principal: Annotated[SessionPrincipal, Depends(require_session)]) -> dict[str, Any]:
    with UnitOfWork(user_id=principal.user_id) as uow:
        repo = AccessRepository(uow.connection)
        memberships = repo.list_memberships_for_user(principal.user_id)
    return {
        "user": {
            "id": str(principal.user_id),
            "email": principal.email,
            "display_name": principal.display_name,
            "issuer": principal.issuer,
            "subject": principal.subject,
        },
        "organizations": [
            {
                "tenant_id": str(m["tenant_id"]),
                "slug": m["slug"],
                "name": m["name"],
                "role": m["role"],
                "membership_id": str(m["id"]),
            }
            for m in memberships
        ],
    }
