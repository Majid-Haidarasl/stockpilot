# Phase 3 step 2 report — Reservation contract (T09)

**Date:** 2026-11-11  
**Repo:** `D:\Me\Last Term\WEB\stockpilot`  
**Host:** Windows 11, Docker Desktop (WSL2), PowerShell  
**Commit/push:** not done by the agent (developer-owned)

---

## Verdict

T09 local exit criteria are **met**:

| Criterion | Result |
|---|---|
| `inventory.reservations` + `reservation_lines` (`0005_reservations`) | Pass |
| `InventoryCommands.reserve_all` / allocate / release / consume (no commit) | Pass |
| All-or-nothing multi-line shortfall (critical, executed) | Pass |
| Concurrent last-stock reserve × **20** iterations (critical, executed) | Pass |
| Inactive product reserve rejected with no writes | Pass |
| HELD/ALLOCATED qty vs `reserved` in balance-check | Pass |
| Integration tests isolated on `stockpilot_test` | Pass |
| Dev-only `cleanup-test-tenants` (`inv-*` / `rsv-*`) | Pass |
| ADR-002 Accepted (shared UoW staging) | Pass |
| `backend-checks` | Pass (**44** tests) |
| Demo `balance-check` | Pass (`positions=108 mismatches=0`) |

---

## What was delivered

- Public port: `ReserveStock` / `AllocateStock` / `ReleaseStock` / `ConsumeStock` + `SqlInventoryCommands` staging adapter
- Domain: reserve / release / consume on `StockPosition`; reservation status transitions
- Lock order documented in `inventory/public.py` and ADR-002
- `backend-checks` uses logical DB **`stockpilot_test`**; demo/seed stay on `stockpilot`
- Concurrent last-stock race asserted **20 times** in one test (not a single lucky pass)
- Inactive-product reserve returns `InactiveProduct` with zero reservation/movement writes
- Ops: `cleanup-test-tenants` (dev-only; refuses production/staging) removes leftover `inv-*` / `rsv-*` tenants
- Hypothesis property tests for non-negativity of stock ops

---

## Verification (PowerShell)

```powershell
Set-Location "D:\Me\Last Term\WEB\stockpilot"

docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm backend-checks

docker compose -f compose.yaml -f compose.dev.yaml build ops
docker compose -f compose.yaml -f compose.dev.yaml run --rm ops python -m stockpilot.bootstrap.ops cleanup-test-tenants --environment development
docker compose -f compose.yaml -f compose.dev.yaml run --rm ops python -m stockpilot.bootstrap.ops balance-check
```

Observed:

- `backend-checks` → **44 passed** (concurrent last-stock loop ×20 + multi-line shortfall + inactive product; not skipped)
- `cleanup-test-tenants` → `removed=0 slugs=(none)` (demo DB already clean after test isolation)
- Demo `balance-check` → `balance-check positions=108 mismatches=0`

---

## Suggested commit message

```
Complete T09: reserve_all, concurrency stress, test-tenant cleanup

Add reservations and InventoryCommands staging, stress the last-stock
race over 20 iterations, reject inactive-product reserves, isolate
integration tests on stockpilot_test, and add a dev-only cleanup for
leftover inv-*/rsv-* tenants on the demo database.
```

Remind: commit and push are yours when ready.
