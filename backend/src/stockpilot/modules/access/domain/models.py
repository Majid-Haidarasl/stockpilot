"""Access domain types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class Role(StrEnum):
    ADMIN = "admin"
    SALES = "sales"
    WAREHOUSE = "warehouse"
    VIEWER = "viewer"


@dataclass(frozen=True, slots=True)
class ActorContext:
    user_id: UUID
    tenant_id: UUID
    role: Role
    issuer: str
    subject: str
    email: str | None = None
    display_name: str | None = None

    def has_role(self, *roles: Role) -> bool:
        return self.role in roles

    def can_manage_catalog_writes(self) -> bool:
        return self.role in {Role.ADMIN, Role.SALES}

    def can_change_product_price(self) -> bool:
        return self.role == Role.ADMIN or self.role == Role.SALES

    def can_set_stock_warning_threshold(self) -> bool:
        return self.role == Role.ADMIN

    def can_manage_customers(self) -> bool:
        return self.role in {Role.ADMIN, Role.SALES}

    def can_manage_members(self) -> bool:
        return self.role == Role.ADMIN

    def can_manage_inventory(self) -> bool:
        return self.role in {Role.ADMIN, Role.WAREHOUSE}

    def can_edit_draft_orders(self) -> bool:
        return self.role in {Role.ADMIN, Role.SALES}

    def can_view_orders(self) -> bool:
        return self.role in {Role.ADMIN, Role.SALES, Role.WAREHOUSE, Role.VIEWER}

    def can_reserve_orders(self) -> bool:
        return self.role in {Role.ADMIN, Role.SALES}

    def can_confirm_orders(self) -> bool:
        return self.role in {Role.ADMIN, Role.SALES}

    def can_cancel_orders(self) -> bool:
        return self.role in {Role.ADMIN, Role.SALES}

    def can_ship_orders(self) -> bool:
        return self.role in {Role.ADMIN, Role.WAREHOUSE}


class AccessError(Exception):
    """Base access/domain error."""


class PermissionDenied(AccessError):
    pass


class NotFound(AccessError):
    pass


class Conflict(AccessError):
    pass
