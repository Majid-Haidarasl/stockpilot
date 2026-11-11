# Phase 3 step 3 report — Draft orders domain (T10)

**Date:** 2026-11-11  
**Repo:** `D:\Me\Last Term\WEB\stockpilot`  
**Host:** Windows 11, Docker Desktop (WSL2), PowerShell  
**Commit/push:** not done by the agent (developer-owned)

---

## Verdict

T10 local exit criteria are **met**. Inventory is **not** wired (T11).

| Criterion | Result |
|---|---|
| `sales.orders` / `order_lines` (`0006_orders`) | Pass |
| Named domain transitions (reserve/confirm/cancel/expire/ship) | Pass |
| Draft create/edit APIs; no stock/reservation side effects | Pass |
| FixedClock: confirm after `expires_at` rejected; exactly before succeeds | Pass |
| Clock + scheduler skeleton (no public expire HTTP) | Pass |
| Illegal transitions / duplicate / >20 lines / totals | Pass |
| Tests on `stockpilot_test` | Pass |
| `backend-checks` | Pass (**58** tests) |
| `frontend-checks` | Pass (**1** test, regression) |

---

## What was delivered

- Migration `0006_orders` + RLS; expected schema revision bumped
- `Order` / `OrderLine` aggregate; draft mutators; money `total()`
- Draft routes: `GET/POST .../orders`, `GET/PATCH .../orders/{id}` (PATCH draft only); `Idempotency-Key` / `expected_version` hooks only
- `FixedClock` / `SystemClock`; `ReservationExpiryScheduler` skeleton
- Permissions: `can_edit_draft_orders` (admin/sales); warehouse read-only for drafts

**Explicitly not done:** HTTP or use-case calls to `InventoryCommands` for reserve/confirm/cancel/ship.

---

## Verification (PowerShell)

```powershell
Set-Location "D:\Me\Last Term\WEB\stockpilot"
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm backend-checks
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm frontend-checks
```

Observed: backend-checks **58 passed**; frontend-checks eslint/tsc/vitest OK.

---

## Suggested commit message

```
Complete T10: draft orders domain and APIs without inventory wiring

Add sales orders schema, named status transitions, FixedClock expiry
confirm rules, draft CRUD APIs, and a scheduler skeleton. Reserve path
inventory coordination remains T11.
```

Remind: commit and push are yours when ready.
