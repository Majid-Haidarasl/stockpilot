"""Liveness and readiness HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from stockpilot.platform.persistence.db import connect, fetch_schema_revision
from stockpilot.platform.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def ready() -> JSONResponse:
    settings = get_settings()
    try:
        with connect(settings) as conn:
            conn.execute(text("SELECT 1"))
        revision = fetch_schema_revision(settings)
    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "reason": "database_unavailable",
            },
        )

    if revision != settings.expected_schema_revision:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "reason": "schema_mismatch",
                "expected": settings.expected_schema_revision,
                "actual": revision,
            },
        )

    return JSONResponse(
        status_code=200,
        content={"status": "ready", "schema_revision": revision},
    )
