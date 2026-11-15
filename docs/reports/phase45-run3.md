# Phase 4.5 Run 3 — Remaining Pages + Final Audit (Part A complete)

**Date:** 2026-11-13  
**Repo:** `D:\Me\Last Term\WEB\stockpilot`  
**Host:** Windows 11, Docker Desktop (WSL2), PowerShell  

---

## Verdict

Run 3 completes Part A of Phase 4.5: remaining pages redesigned, timeline flake fixed with `audit_log.seq`, 404 + error boundary shipped, Vitest/e2e green, full screenshot gallery captured.

| Check | Result |
|---|---|
| Backend-checks | **81 passed** |
| Timeline flake proof | **20/20** consecutive passes |
| Vitest | **60 passed** (was 48) |
| Playwright e2e | **7 passed** |
| OpenAPI / generate:api | Clean |
| New npm dependencies | **None** |
| Phase 5+ (T13–T16) | **Untouched** |
| Selector / e2e changes | **None** |

---

## Timeline flake fix

**Cause:** Equal `created_at` (`DEFAULT now()` in one transaction) + UUID `id` tie-break → non-deterministic order.

**Fix (as approved):**

- Alembic `0008_audit_log_seq`: `seq BIGINT GENERATED ALWAYS AS IDENTITY` on `platform.audit_log` (backfills existing rows), index `(tenant_id, entity_type, entity_id, seq)`, `GRANT USAGE, SELECT` on `platform.audit_log_seq_seq` to `stockpilot_app` / migrator.
- Timeline query only: `ORDER BY a.seq ASC` in `order_repo.list_order_timeline`.
- **No** `write_audit` INSERT changes in the five repos.
- `seq` not exposed in API / OpenAPI.
- `STOCKPILOT_EXPECTED_SCHEMA_REVISION` → `0008_audit_log_seq` (`compose.yaml` + settings default).
- RLS policies unchanged; inserts verified via full backend suite + 20× timeline test (`FAILS=0`).

---

## Per-page before → after (summary)

| Page | Before | After |
|---|---|---|
| `/` | Brand + text link | Brand + contained **link** CTA (`Button` + `RouterLink`, role=link) |
| `/login` | Hardcoded light hex | Theme-token card; PKCE via `loginUrl()` unchanged |
| `/orgs` | Plain list + role text | SectionCard list + `RoleChip`; cache-clear-on-switch + `me` kept |
| `/members` | Card stack | DataTable + RoleChip + role save; LAST_ADMIN unchanged; no invite/remove (none exist) |
| `/customers` | Form + boxes | SectionCard form + client search + DataTable mobile rows |
| `/notifications` | Plain EmptyState | Illustrated empty inbox placeholder (no Phase 5 logic) |
| 404 | Missing | Standalone `*`; tenant ` /t/:tenantId/*` inside TenantShell |
| Error | Missing | Boundary + `/error` fallback; generic Persian only; reset on route change |

---

## Files touched

**Backend**

- `backend/alembic/versions/0008_audit_log_seq.py`
- `backend/src/stockpilot/modules/sales/adapters/outbound/order_repo.py` (ORDER BY only)
- `backend/src/stockpilot/platform/settings.py`
- `compose.yaml` (expected schema revision)

**Frontend — shared**

- `EmptyState`, `ErrorState`, `ForbiddenState`, `RoleChip`, `roleLabels`, `StateIllustration`, `index.ts`
- `TenantShell` consumers unchanged structurally

**Frontend — pages / routing**

- `app/App.tsx`, `main.tsx`
- `features/home/HomePage.tsx`
- `features/auth/LoginPage.tsx`
- `features/orgs/OrgPickerPage.tsx`
- `features/members/MembersPage.tsx`
- `features/customers/CustomersPage.tsx`, `customersFilter.ts`
- `features/notifications/NotificationsPage.tsx`
- `features/errors/NotFoundPage.tsx`, `AppErrorBoundary.tsx`, `ErrorFallbackPage.tsx`

**Tests**

- Vitest: NotFound, AppErrorBoundary, OrgPicker, customersFilter, MembersPage, NotificationsPage
- `tests/e2e/scripts/capture-phase45-run3.mjs` (gallery helper)

**Docs**

- `docs/reports/phase45-run3.md`
- `docs/reports/phase45-run3-screenshots/` (45 PNGs)

---

## Accessibility / mobile / contrast audit

| Issue found | Fix |
|---|---|
| Login page hardcoded light gradient (broken/contrast-poor in dark) | Theme `palette` tokens + mode-aware background |
| No catch-all / blank unknown paths | Standalone + tenant-scoped NotFound with landmarks / single h1 |
| Error details could leak if a naive boundary dumped `error.message` | Generic Persian only; `console.error` in DEV only; reset on route change |
| Members/customers used ad-hoc cards (weak mobile density) | DataTable + exclusive `renderMobileRow` |
| Roles shown as plain text (color/status cue missing) | `RoleChip` = label + icon + theme tones |
| Empty/forbidden/error were Alert-only | Shared illustrations (MUI icons) + consistent layout |
| Landing CTA must stay `role=link` for tests | `Button component={RouterLink}` keeping «ورود به سامانه» |

**Verified patterns retained:** TenantShell skip link «پرش به محتوا», visible focus via MUI theme, ConfirmDialog focus trap on order cancel, status never color-alone (`StatusChip` / `RoleChip`), Persian display digits only (inputs/API Latin).

**Not changed:** Auth/PKCE, query keys, cache clear policy, Idempotency-Key, `expected_version`, `mapApiError` LAST_ADMIN string, roles/viewer denial.

---

## Selector changes

**None.** E2E still uses `ورود`, org button `/Aftab/`, cancel confirm `لغو سفارش`, etc.

---

## Screenshots

[`docs/reports/phase45-run3-screenshots/`](./phase45-run3-screenshots/) — **45 PNGs**  
15 surfaces × (`light-desktop`, `dark-desktop`, `mobile-390`):

landing, login, orgs, dashboard, orders, orders-new, orders-detail, products, inventory, customers, members, notifications, 404, tenant-404, error

---

## Exact commands used

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm backend-checks
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm frontend-checks

docker compose -p stockpilot-e2e -f compose.yaml -f compose.e2e.yaml --profile test build
docker compose -p stockpilot-e2e -f compose.yaml -f compose.e2e.yaml --profile test run --rm e2e
docker compose -p stockpilot-e2e -f compose.yaml -f compose.e2e.yaml --profile test down
```

Timeline proof (inside backend-checks image):

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm backend-checks bash -c 'fails=0; for i in $(seq 1 20); do echo RUN $i; pytest -q tests/integration/test_order_timeline.py::test_timeline_returns_events_in_order || fails=$((fails+1)); done; echo FAILS=$fails; test $fails -eq 0'
```

E2E frontend rebuild when source changes:

```powershell
docker compose -p stockpilot-e2e -f compose.yaml -f compose.e2e.yaml --profile test build frontend-dev
docker compose -p stockpilot-e2e -f compose.yaml -f compose.e2e.yaml --profile test up -d --force-recreate frontend-dev
```

---

## Part A complete

Runs 1–3 are done: theme/shell/shared blocks → main commercial pages → remaining auth/org/admin pages + 404/error + a11y audit + timeline determinism. Product thumbnails remain placeholder until later Phase 4.5 runs. Phase 5+ (T13–T16) not started.
