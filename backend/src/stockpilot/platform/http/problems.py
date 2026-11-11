"""RFC 9457-ish problem responses."""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse


def problem(
    *,
    status: int,
    code: str,
    title: str,
    detail: str | None = None,
    errors: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"urn:stockpilot:problem:{code.lower().replace('_', '-')}",
        "title": title,
        "status": status,
        "code": code,
    }
    if detail:
        body["detail"] = detail
    if errors:
        body["errors"] = errors
    return JSONResponse(status_code=status, content=body, media_type="application/problem+json")
