# Phase 4.5 Run 2 — Redesign Main Pages

**Date:** 2026-11-13  
**Repo:** `D:\Me\Last Term\WEB\stockpilot`  
**Host:** Windows 11, Docker Desktop (WSL2), PowerShell  

---

## Verdict

Run 2 main-page redesign is **complete** for frontend UX. Shared blocks from Run 1 are wired into Dashboard, Orders (list / new / detail), Products, and Inventory. Playwright **7/7** passed. Vitest **48** passed. Backend checks: **80 passed + 1 pre-existing flake** (timeline order tie-break; not introduced by this run; no backend code changed).

| Check | Result |
|---|---|
| Chart | **Skipped** — dashboard API has no time series |
| New npm dependencies | **None** |
| Playwright e2e | **7 passed** |
| Vitest | **48 passed** (was 32) |
| Backend-checks | **80 passed**, 1 flake `test_timeline_returns_events_in_order` |
| OpenAPI / generate:api | Clean (frontend-checks drift check passed) |
| Phase 5+ (T13–T16) | Untouched |
| Backend / contracts | Untouched |

---

## Persian digits — test assertion audit

Grep of e2e + Vitest before converting display quantities/counts:

| Location | What asserts numbers? | Action |
|---|---|---|
| e2e `createDraftOrder` | `fill(quantity)` Latin in **input** | Unchanged (inputs stay Latin) |
| e2e `cancel.spec` | DB stock via SQL helper | Unchanged (not UI text) |
| e2e `main-path` | `/ریال/` only | Safe |
| e2e isolation/org-switch | `orderId.slice(0, 8)` (hex UUID) | Safe |
| Vitest `mapApiError` | Already expects Persian `۲` | Safe |
| Vitest money/persianDigits | Unit tests for conversion | Safe |

**Finding:** No e2e/Vitest assertion required Latin digits in **displayed** quantities/counts. Display conversion to Persian digits was applied.

---

## Behavior change (explicit)

**Inventory low-stock highlight** now uses `available <= stock_warning_threshold` (was `on_hand <= …`), matching dashboard/API low-stock semantics.

---

## Chart

**Not possible** with current `GET .../dashboard` payload (flat `order_counts_by_status`, `shipped_total`, `low_stock[]`). No chart library added.

---

## Selector / e2e changes

| Change | Reason |
|---|---|
| [`tests/e2e/helpers/orders.ts`](../../tests/e2e/helpers/orders.ts) `clickAction(..., "لغو")` now clicks ConfirmDialog **لغو سفارش** after `action-cancel` | Cancel is confirm-gated; Idempotency-Key/request only on confirm. Assertions unchanged. |

No other Playwright selector weakening.

---

## Files touched (frontend + e2e helper + report)

**Shared / theme consumers**

- `frontend/src/shared/ui/DataTable.tsx` — exclusive mobile/desktop via `useMediaQuery` + `renderMobileRow`
- `frontend/src/shared/ui/ConfirmDialog.tsx` — `confirmColor`
- `frontend/src/shared/ui/LowStockMark.tsx`, `lowStock.ts`, tests
- `frontend/src/shared/tehranDisplay.ts` (+ test) — Asia/Tehran display formatting
- `frontend/src/shared/ui/index.ts`
- `frontend/src/test/setup.ts` — default `matchMedia` → desktop (`matches: false`)

**Pages / features**

- `frontend/src/features/dashboard/DashboardPage.tsx`
- `frontend/src/features/orders/OrderListPage.tsx` (+ test)
- `frontend/src/features/orders/DraftOrderPage.tsx`
- `frontend/src/features/orders/OrderDetailPage.tsx`
- `frontend/src/features/orders/OrderTimeline.tsx`, `eventLabels.ts`, tests
- `frontend/src/features/orders/OrderDetailCancel.test.tsx`
- `frontend/src/features/catalog/ProductsPage.tsx`, `productsFilter.ts`, test
- `frontend/src/features/inventory/InventoryPage.tsx`

**E2E / docs**

- `tests/e2e/helpers/orders.ts`
- `docs/reports/phase45-run2.md`
- `docs/reports/phase45-run2-screenshots/*` (18 PNGs)

---

## Screenshots

All under [`docs/reports/phase45-run2-screenshots/`](./phase45-run2-screenshots/):

- 6 pages × light desktop, dark desktop, mobile 390px

---

## frontend-dev rebuild

**Dev stack** (`compose.dev.yaml` bind-mounts `./frontend`): restart is enough for HMR:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml up -d frontend-dev
```

**E2E stack** (no bind mount): image must include `@mui/icons-material` + new source. Rebuild when Docker Hub DNS works:

```powershell
docker compose -p stockpilot-e2e -f compose.yaml -f compose.e2e.yaml --profile test build frontend-dev
docker compose -p stockpilot-e2e -f compose.yaml -f compose.e2e.yaml --profile test up -d --force-recreate frontend-dev
```

This run also verified e2e by syncing `src` + `npm install` icons into the running e2e frontend container when bake failed on DNS.

Exact e2e command used:

```powershell
docker compose -p stockpilot-e2e -f compose.yaml -f compose.e2e.yaml --profile test run --rm e2e
```

---

## Cancel ConfirmDialog contract

- Opening cancel only sets dialog open; **no** Idempotency-Key / HTTP until **لغو سفارش**.
- **انصراف** / dialog close → no request (Vitest covered).
- `expected_version` path unchanged inside `useOrderCycleAction`.

---

## Gaps left for Run 3

Login/landing, org picker, members, customers, notifications, residual error/404 polish, full a11y/contrast/mobile audit on remaining routes. Product thumbnails remain placeholder until Run 5/6.

---

## Backend flake note (out of Run 2 scope)

`tests/integration/test_order_timeline.py::test_timeline_returns_events_in_order` fails when two audits share `created_at` and UUID `id` order differs from insert order (`ORDER BY created_at ASC, id ASC`). Not caused by frontend changes; left untouched per Phase 4.5 constraints.
