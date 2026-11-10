"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from stockpilot.bootstrap.health import router as health_router
from stockpilot.platform.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="StockPilot API", version="0.1.0")
    app.state.settings = settings
    app.include_router(health_router)
    return app


app = create_app()
