# Roles and permissions

Roles are defined **inside one organization**. The same person may be `admin` in Aftab and `viewer` in Baran. No role, by itself, grants access to another organization.

In v1, each membership has **exactly one role** in that organization. The organization admin has full authority in that organization only.

## Enforcement

- The backend checks identity **and** membership and permission on every request.
- Hiding a button in the frontend is not a security policy.
- For a resource that belongs to another organization, return **`404`**, so that the resource's existence is not disclosed.

## Matrix

| Role | Allowed | Not allowed |
|---|---|---|
| `admin` (organization admin) | All operations in that organization, including changing roles of existing members, viewing the audit log, and setting a product's stock warning threshold. | The last active admin of an organization cannot remove their own admin role. |
| `sales` (sales user) | Manage customers and draft orders; reserve, confirm, or cancel an order before shipment. | Adjust inventory; change member roles. |
| `warehouse` (warehouse user) | Record receipts; adjust stock with a required reason; ship a **confirmed** order. | Change prices; commercially confirm an order. |
| `viewer` (read-only) | See catalog, inventory, orders, and the dashboard; personal actions such as logout and marking their own notifications as read. | Change any commercial data. |

## Bootstrap note

Initial organization setup and linking Keycloak users is **not** a self-service admin UI in v1. It is the containerized ops bootstrap tool, audited, operator-only in production-like environments.
