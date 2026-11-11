# ADR-003 — Tenant isolation

- **Status:** Accepted
- **Date:** 2026-11-11

## Question

How do membership checks, repository filters, Row-Level Security (RLS), and composite foreign keys that include `tenant_id` work together?

## Decision

Layered defence:

1. Valid local session (opaque cookie; see ADR-004).
2. Membership lookup builds an immutable `ActorContext` (never from a free-form body).
3. Path `tenant_id` must match membership; otherwise **404**.
4. Commercial repositories always filter by `tenant_id`.
5. RLS is enabled with `FORCE` on tenant-scoped tables. Runtime role `stockpilot_app` is not owner, not superuser, not `BYPASSRLS`.
6. Tenant/user/role context is applied with `SET LOCAL` / `set_config(..., true)` **inside the current transaction** via `UnitOfWork`.
7. Ops bootstrap uses `stockpilot_migrator` with explicit migrator RLS policies (FORCE still applies to owners).

Cross-tenant resources return **404**. Same-tenant missing permission returns **403**.

## Consequences

- Isolation tests must run as the runtime role.
- Listing “my organizations” sets `app.user_id` before a tenant is selected.
- Later modules must keep composite FKs including `tenant_id`.
