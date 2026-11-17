"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from stockpilot.bootstrap.health import router as health_router
from stockpilot.modules.access.adapters.inbound.auth_routes import router as auth_router
from stockpilot.modules.access.adapters.inbound.member_routes import router as member_router
from stockpilot.modules.catalog.adapters.inbound.image_routes import router as catalog_images_router
from stockpilot.modules.catalog.adapters.inbound.routes import router as catalog_router
from stockpilot.modules.inventory.adapters.inbound.routes import router as inventory_router
from stockpilot.modules.notifications.adapters.inbound.routes import (
    router as notifications_router,
)
from stockpilot.modules.sales.adapters.inbound.customer_routes import router as customer_router
from stockpilot.modules.sales.adapters.inbound.dashboard_routes import router as dashboard_router
from stockpilot.modules.sales.adapters.inbound.order_routes import router as order_router
from stockpilot.platform.observability.http_metrics import setup_http_metrics
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
    # Middleware always; internal :8001 bind only when STOCKPILOT_API_METRICS_ENABLED.
    setup_http_metrics(
        app,
        enabled=settings.api_metrics_enabled,
        port=settings.api_metrics_port,
    )
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(member_router)
    app.include_router(catalog_router)
    app.include_router(catalog_images_router)
    app.include_router(customer_router)
    app.include_router(order_router)
    app.include_router(dashboard_router)
    app.include_router(inventory_router)
    app.include_router(notifications_router)
    return app


app = create_app()
