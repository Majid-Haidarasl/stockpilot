# Task status

| Task | Status | Notes |
|---|---|---|
| T01 | Done (local) | Product docs + ADR-001..008 |
| T02 | Done (local) | Monorepo, Compose, API health, RTL shell |
| T03 | Done (local) | Postgres 17, roles, Alembic `0001_schemas`, ready check |
| T04 | Done (local) | Ruff/mypy/Import Linter/pytest, ESLint/tsc/Vitest, CI workflow |
| T05 | Done (local) | Keycloak, OIDC+PKCE, opaque sessions, `/api/v1/me`, logout CSRF |
| T06 | Done (local) | Tenants/memberships, ActorContext, RLS `SET LOCAL`, ops bootstrap, last-admin lock |
| T07 | Done (local) | Products/customers APIs + Persian UI, integer IRR strings, per-tenant SKU |
| T08 | Done (local) | Stock positions/movements, receipts/adjustments, ledger UI, seed-demo |
| T09 | Done (local) | `InventoryCommands.reserve_all`, reservations schema, concurrency + shortfall tests, `stockpilot_test` |
| T10 | Done (local) | Order domain + draft APIs, clock/scheduler skeleton; inventory wiring deferred to T11 |
| T11 | Done (local) | Shared UoW cycle, idempotency+Outbox writer, lock order in ADR-002, tenant-scoped expire scheduler; critical tests ×20 last-stock + Retry-After |
| T12 | In progress (run 1/4) | Frontend foundations: OpenAPI codegen+drift, tenant Query keys, cancel-then-clear, shared RTL states, error mapper, idempotent helper, money |

Phase 1 verification evidence: `docs/evidence/phase-1-report.md`  
Phase 2 verification evidence: `docs/evidence/phase-2-report.md`  
Phase 3 step 1 report: `docs/reports/phase3-step1.md`  
Phase 3 step 2 report: `docs/reports/phase3-step2.md`  
Phase 3 step 3 report: `docs/reports/phase3-step3.md`  
Phase 3 step 4 report: `docs/reports/phase3-step4.md`

Commits/pushes are owned by the developer.
