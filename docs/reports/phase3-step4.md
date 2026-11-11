# Phase 3 step 4 report — Order cycle, UoW, idempotency (T11)

**Date:** 2026-11-11  
**Repo:** `D:\Me\Last Term\WEB\stockpilot`  
**Host:** Windows 11, Docker Desktop (WSL2), PowerShell  
**Commit/push:** not done by the agent (developer-owned)

---

## Verdict

T11 local exit criteria are **met**. Relay/Worker/Inbox remain T13; polished browser path remains T12.

| Criterion | Result |
|---|---|
| Migration `0007_idempotency_outbox` (idempotency + outbox + expiry index) | Pass |
| Shared UoW: reserve/confirm/cancel/expire/ship + inventory + audit + Outbox | Pass |
| Lock order: idempotency → order → products → positions → reservation (ADR-002) | Pass |
| HTTP `POST .../reserve\|confirm\|cancel\|ship` with Idempotency-Key | Pass |
| Confirm-after-expiry commits expiry, returns `409 RESERVATION_EXPIRED` | Pass |
| Scheduler expire: one tenant at a time, `SET LOCAL`, no BYPASSRLS/owner | Pass |
| Concurrent last-stock at **order-cycle** level ×20 | Pass |
| Concurrent same Idempotency-Key → Retry-After, no double-apply | Pass |
| Critical races (expire vs confirm, cancel vs ship, price freeze, cross-tenant, rollback) | Pass |
| `backend-checks` | Pass (**70** tests) |
| `frontend-checks` | Pass (**1** test, regression) |
| Demo `balance-check` | Pass (`positions=108 mismatches=0`) |

---

## What was delivered

- Alembic `0007_idempotency_outbox`; expected schema revision bumped
- `IdempotencyStore` (fingerprint, replay, lock_timeout → `IdempotencyInProgress` / Retry-After)
- Outbox writer (`platform.outbox`); Relay deferred to T13
- `OrderCycleService` + cycle HTTP routes; inventory staging only (no inner commit)
- `ReservationExpiryScheduler` tenant-scoped via runtime role + `UnitOfWork` SET LOCAL
- ADR-002 completed (lock order); ADR-005 accepted-in-principle (Outbox writer landed)

**Explicitly not done:** Relay/Worker/Inbox, email, Grafana, load tests, T12 UI polish.

---

## Verification (PowerShell)

```powershell
Set-Location "D:\Me\Last Term\WEB\stockpilot"
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm backend-checks
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm frontend-checks
docker compose -f compose.yaml -f compose.dev.yaml run --rm ops python -m stockpilot.bootstrap.ops balance-check
```

Observed: backend-checks **70 passed**; frontend-checks eslint/tsc/vitest OK; balance-check `positions=108 mismatches=0`.

---

## Suggested commit message

```
Complete T11: order cycle with shared UoW, idempotency, and Outbox writer

Wire reserve/confirm/cancel/expire/ship through one transaction, document
lock order in ADR-002, tenant-scoped expiry scheduler, and critical
concurrency/idempotency tests on stockpilot_test.
```

Remind: commit and push are yours when ready.
