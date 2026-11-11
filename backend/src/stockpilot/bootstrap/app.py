"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from stockpilot.bootstrap.health import router as health_router
from stockpilot.modules.access.adapters.inbound.auth_routes import router as auth_router
from stockpilot.modules.access.adapters.inbound.member_routes import router as member_router
from stockpilot.modules.catalog.adapters.inbound.routes import router as catalog_router
from stockpilot.modules.inventory.adapters.inbound.routes import router as inventory_router
from stockpilot.modules.sales.adapters.inbound.customer_routes import router as customer_router
from stockpilot.modules.sales.adapters.inbound.order_routes import router as order_router
from stockpilot.platform.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="StockPilot API", version="0.3.0")
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(member_router)
    app.include_router(catalog_router)
    app.include_router(customer_router)
    app.include_router(order_router)
    app.include_router(inventory_router)
    return app


app = create_app()
