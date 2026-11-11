"""Unit tests for role matrix helpers."""

from __future__ import annotations

from uuid import uuid4

from stockpilot.modules.access.domain.models import ActorContext, Role


def _actor(role: Role) -> ActorContext:
    return ActorContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        role=role,
        issuer="http://localhost:8180/realms/stockpilot",
        subject="sub",
    )


def test_viewer_cannot_write_catalog_or_customers() -> None:
    actor = _actor(Role.VIEWER)
    assert not actor.can_manage_catalog_writes()
    assert not actor.can_manage_customers()
    assert not actor.can_manage_members()


def test_warehouse_cannot_change_price_or_confirm_commercial_admin() -> None:
    actor = _actor(Role.WAREHOUSE)
    assert not actor.can_change_product_price()
    assert not actor.can_manage_customers()
    assert not actor.can_manage_members()


def test_sales_can_manage_catalog_and_customers() -> None:
    actor = _actor(Role.SALES)
    assert actor.can_manage_catalog_writes()
    assert actor.can_manage_customers()
    assert not actor.can_set_stock_warning_threshold()


def test_admin_can_set_threshold_and_members() -> None:
    actor = _actor(Role.ADMIN)
    assert actor.can_set_stock_warning_threshold()
    assert actor.can_manage_members()
