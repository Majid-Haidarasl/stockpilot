"""FastAPI dependencies for session and actor context."""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request

from stockpilot.modules.access.adapters.outbound.repo import AccessRepository, utcnow
from stockpilot.modules.access.domain.models import ActorContext, Role
from stockpilot.platform.persistence.uow import UnitOfWork
from stockpilot.platform.security.crypto import hash_token
from stockpilot.platform.settings import Settings, get_settings


class SessionPrincipal:
    def __init__(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        issuer: str,
        subject: str,
        email: str | None,
        display_name: str | None,
        csrf_token_hash: str,
    ) -> None:
        self.session_id = session_id
        self.user_id = user_id
        self.issuer = issuer
        self.subject = subject
        self.email = email
        self.display_name = display_name
        self.csrf_token_hash = csrf_token_hash


def get_settings_dep() -> Settings:
    return get_settings()


def require_session(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> SessionPrincipal:
    raw = request.cookies.get(settings.session_cookie_name)
    if not raw:
        raise HTTPException(status_code=401, detail="Authentication required")

    with UnitOfWork() as uow:
        repo = AccessRepository(uow.connection)
        row = repo.get_session_by_token_hash(hash_token(raw))
        if row is None:
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        idle = utcnow() + timedelta(minutes=settings.session_idle_minutes)
        max_exp = row["expires_at"]
        if idle > max_exp:
            idle = max_exp
        repo.touch_session(UUID(str(row["id"])), idle)
        uow.commit()
        return SessionPrincipal(
            session_id=UUID(str(row["id"])),
            user_id=UUID(str(row["user_id"])),
            issuer=str(row["issuer"]),
            subject=str(row["subject"]),
            email=row.get("email"),
            display_name=row.get("display_name"),
            csrf_token_hash=str(row["csrf_token_hash"]),
        )


def require_csrf(
    request: Request,
    principal: Annotated[SessionPrincipal, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    x_csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> SessionPrincipal:
    origin = request.headers.get("origin")
    if origin and origin not in settings.cors_origin_list and origin != settings.app_public_origin:
        raise HTTPException(status_code=403, detail="Invalid origin")
    if not x_csrf_token or hash_token(x_csrf_token) != principal.csrf_token_hash:
        raise HTTPException(status_code=403, detail="CSRF validation failed")
    return principal


def require_actor(
    tenant_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(require_session)],
) -> ActorContext:
    with UnitOfWork(user_id=principal.user_id) as uow:
        repo = AccessRepository(uow.connection)
        membership = repo.get_membership(principal.user_id, tenant_id)
        if membership is None:
            raise HTTPException(status_code=404, detail="Not found")
        return ActorContext(
            user_id=principal.user_id,
            tenant_id=tenant_id,
            role=Role(str(membership["role"])),
            issuer=principal.issuer,
            subject=principal.subject,
            email=principal.email,
            display_name=principal.display_name,
        )
