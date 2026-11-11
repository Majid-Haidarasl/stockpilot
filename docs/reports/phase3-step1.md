# Phase 3 step 1 report — Inventory core (T08)

**Date:** 2026-11-11  
**Repo:** `D:\Me\Last Term\WEB\stockpilot` → https://github.com/Majid-Haidarasl/stockpilot  
**Host:** Windows 11, Docker Desktop (WSL2), PowerShell  
**Commit/push:** not done by the agent (developer-owned)

---

## Verdict

T08 local exit criteria are **met**:

| Criterion | Result |
|---|---|
| Alembic `0004_inventory` (positions, movements, constraints, RLS) | Pass |
| Receipts + adjustments + append-only ledger | Pass |
| `available = on_hand - reserved` (computed) | Pass |
| Permissions: warehouse/admin write; viewer denied adjust | Pass |
| Persian inventory list + ledger UI | Pass |
| Dev-only idempotent `ops seed-demo` (never production) | Pass |
| `ops balance-check` (report only; no silent repair) | Pass |
| `backend-checks` | Pass (**33** tests) |
| `frontend-checks` | Pass (**1** test) |
| Ready health expects `0004_inventory` | Pass |

Approved assumptions applied: warehouse code `main`; Aftab/Baran Persian names updated via seed companies; T03–T20 admin placeholders from sample data; re-seed skips when `seed-demo:{slug}:{sku}` movement already exists.

---

## What was delivered

### Schema / domain

- `inventory.stock_positions` — unique `(tenant, warehouse, product)`; check `0 <= reserved <= on_hand`; max on_hand `1_000_000_000`
- `inventory.movements` — append-only physical/reserved deltas + reason/reference/actor
- First receipt creates the position (`ON CONFLICT` / `FOR UPDATE`); domain rejects adjustment that would drop `on_hand` below `reserved`

### APIs / UI

- `GET /api/v1/tenants/{id}/inventory`
- `POST .../inventory/receipts`
- `POST .../inventory/adjustments` (signed qty + required reason)
- `GET .../inventory/movements` (ledger)
- Frontend: `InventoryPage` under tenant nav

### Ops

- `seed-demo` — parses `docs/stockpilot-sample-data.md` (§1 companies + §5 inventory rows): **20** companies, **108** receipts; refuses production/staging
- `balance-check` — compares position counters to `SUM(movements.*)`; prints mismatches and exits `1` if any; **no auto-repair**

---

## Verification commands (PowerShell)

From the repo root (`D:\Me\Last Term\WEB\stockpilot`):

```powershell
# Checks
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm backend-checks
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm frontend-checks

# Rebuild API after schema bump (ready expects 0004_inventory)
docker compose -f compose.yaml -f compose.dev.yaml up -d --build api
```

Observed locally:

- `backend-checks` → All checks passed; **33** pytest passed  
- `frontend-checks` → eslint/tsc/vitest OK (**1** test)  
- `GET http://localhost:8200/health/live` → 200  
- `GET http://localhost:8200/health/ready` → `{"status":"ready","schema_revision":"0004_inventory"}`

---

## Seed + verify (exact PowerShell)

Dev-only. Sample file is mounted at `/docs/stockpilot-sample-data.md` via Compose.

```powershell
Set-Location "D:\Me\Last Term\WEB\stockpilot"

# First seed (creates companies/products/receipts from sample data)
docker compose -f compose.yaml -f compose.dev.yaml run --rm ops python -m stockpilot.bootstrap.ops seed-demo --environment development

# Idempotent re-seed (skips existing seed-demo references)
docker compose -f compose.yaml -f compose.dev.yaml run --rm ops python -m stockpilot.bootstrap.ops seed-demo --environment development

# Ledger vs counters (report only; exit 1 on mismatch)
docker compose -f compose.yaml -f compose.dev.yaml run --rm ops python -m stockpilot.bootstrap.ops balance-check

# Optional: single-tenant report
docker compose -f compose.yaml -f compose.dev.yaml run --rm ops python -m stockpilot.bootstrap.ops balance-check --tenant-slug aftab
```

Observed locally:

| Step | Output |
|---|---|
| First seed | `seed-demo complete companies=20 products_created=108 receipts_created=108 receipts_skipped=0` |
| Re-seed | `seed-demo complete companies=20 products_created=0 receipts_created=0 receipts_skipped=108` |
| Balance-check | `balance-check positions=113 mismatches=0` (108 seed + leftover integration-test tenants/positions; counters match ledger) |
| Production guard | `seed-demo` refuses `production` / `staging` (`SystemExit`) |

Note: shared-dev DB also retains short-lived `inv-*` tenants from integration tests. Those positions are ledger-aligned after the fixture fix; they do not affect seed idempotency.

---

## Known follow-ups (not blocking T08)

- Full reserved-vs-reservations reconciliation lands with T09/T11
- Playwright inventory path later (T12+)
- Optional: isolate integration DB from shared demo DB so test tenants do not accumulate

---

## Suggested commit message (English)

```
Complete T08: inventory ledger, seed-demo, and balance-check

Add stock positions/movements with receipts and adjustments, Persian
inventory UI, and a development-only sample seed with report-only
balance verification against the movement ledger.
```

Remind: commit and push are yours when ready.
