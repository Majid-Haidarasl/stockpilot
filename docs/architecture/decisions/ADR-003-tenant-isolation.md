# ADR-003 — Tenant isolation

- **Status:** Accepted-in-principle, to be confirmed at implementation
- **Date:** 2026-11-11

## Question

How do membership checks, repository filters, Row-Level Security (RLS), and composite foreign keys that include `tenant_id` work together?

## Plan direction (not yet coded)

Layered defence: valid session → membership → immutable `ActorContext` → tenant-scoped repositories → RLS with `SET LOCAL` in the transaction → worker/scheduler/relay role limits. Cross-tenant resources return `404`. Runtime DB role is not table owner, not superuser, not `BYPASSRLS`.

## Consequences (expected)

- Multiple independent controls; RLS does not replace membership checks.
- Isolation tests must run as the real runtime role.
