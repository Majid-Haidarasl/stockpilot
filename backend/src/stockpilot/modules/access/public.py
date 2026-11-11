"""Public contract for the access module."""

from stockpilot.modules.access.adapters.inbound.deps import (
    SessionPrincipal,
    require_actor,
    require_csrf,
    require_session,
)
from stockpilot.modules.access.domain.models import (
    AccessError,
    ActorContext,
    Conflict,
    NotFound,
    PermissionDenied,
    Role,
)

__all__ = [
    "AccessError",
    "ActorContext",
    "Conflict",
    "NotFound",
    "PermissionDenied",
    "Role",
    "SessionPrincipal",
    "require_actor",
    "require_csrf",
    "require_session",
]
