# Phase 4.5 Run 3.5 — Serious UX Polish + Fixes

**Date:** 2026-11-13  
**Repo:** `D:\Me\Last Term\WEB\stockpilot`  
**Host:** Windows 11, Docker Desktop (WSL2), PowerShell  

---

## Verdict

Rejected screens rebuilt as a modern SaaS surface (landing, login, Keycloak theme, org picker, dashboard Jalali + layout, sidebar, customer edit, zero-stock visibility, Soft Slate Sky dark). Behavior and e2e selectors preserved.

| Check | Result |
|---|---|
| Backend-checks | **89 passed**, 1 skipped |
| Vitest | **69 passed** (34 files) |
| Playwright e2e | **7 passed** |
| OpenAPI / generate:api | Clean (additive `has_position`) |
| New npm deps | `@mui/x-date-pickers@7.28.3`, `date-fns-jalali@2.30.0-0` |
| Migrations | **None** |
| Phase 5+ (T13–T16) | **Untouched** |
| Selector / e2e changes | **None** |

---

## Zero-stock root cause

Inventory list SQL used `FROM inventory.stock_positions INNER JOIN catalog.products`. Positions are created only on first receipt, so **never-received active products did not appear on Inventory**. Products catalog already listed them; draft picker showed products without stock cues.

**Fix:** `list_positions` now starts from **active** `catalog.products` with `LEFT JOIN` positions, `COALESCE` zeros, `has_position=false` and `version=0` when no row (version not usable for writes). Negative adjustment without a position returns Persian `STOCK_INVARIANT` (“ابتدا رسید ثبت کنید”). Receipt still creates the position.

### Inventory 403 → hide chip (never break page)

Products page and draft-order picker use shared `useInventoryStockMap` → `queryKeys.inventory(tenantId)`. On inventory failure/403, chips are hidden; pages still render.

**Vitest:** `DraftOrderPage stock chips > keeps picker usable when inventory returns 403 (no ناموجود chip)` in [`frontend/src/features/orders/DraftOrderStockChip.test.tsx`](../../frontend/src/features/orders/DraftOrderStockChip.test.tsx).

### Backend no-position / zero-stock tests

In [`backend/tests/integration/test_inventory_list_zeros.py`](../../backend/tests/integration/test_inventory_list_zeros.py):

| Case | Test |
|---|---|
| Never-received appears with zeros | `test_list_includes_never_received_and_zeroed_excludes_inactive` |
| Received then reduced to 0 still appears | same test (`zeroed` product) |
| Adjustment without position → clear error | `test_adjustment_decrease_without_position_returns_clear_error` |
| Receipt creates position | `test_receipt_creates_position_for_never_received` |
| Tenant isolation | `test_inventory_list_tenant_isolation` |

### Dashboard recent orders

- Endpoint: `GET /api/v1/tenants/{tenant_id}/orders?limit=5` — `limit` is supported (`Query(ge=1, le=100)`, default 50).
- Query key: `queryKeys.recentOrders(tenantId, 5)` → `["tenant", tenantId, "orders", "recent", 5]` (separate from the full orders-list cache).

---

## Dark palette (Option A Soft Slate Sky)

| Token | Value |
|---|---|
| `background.default` | `#0B1220` |
| `background.paper` | `#1E293B` |
| Chrome (sidebar/app bar) | `#111827` |
| Text | `#E2E8F0` / `#94A3B8` |
| Primary (dark) | `#38BDF8` / contrast `#0F172A` |
| Borders | `rgba(148,163,184,0.15)` |
| Nav active tint | `rgba(56,189,248,0.12)` |

---

## Jalali packages (pinned)

| Package | Version | Why |
|---|---|---|
| `@mui/x-date-pickers` | **7.28.3** | MIT community DatePicker + LocalizationProvider; matches MUI 6 |
| `date-fns-jalali` | **2.30.0-0** | Compatible with `AdapterDateFnsJalali` in X Date Pickers 7.28 (v3/v4 hit `longFormatters` export issues) |

Presets (**امروز**, **۷ روز اخیر**, **۳۰ روز اخیر**, **این ماه**) use **Asia/Tehran** via existing `todayTehranYmd` / Jalali month walk — not browser-local midnight. API still gets Tehran-day → UTC ISO `from`/`to`.

Accessible names kept: `از تاریخ به وقت تهران` / `تا تاریخ به وقت تهران`.

---

## Customer edit

Backend `PATCH` already existed (`expected_version`, CSRF, roles, audit). Added HTTP integration tests + frontend dialog (409 → Persian message + refetch; focus restore; keyboard dialog).

---

## Keycloak theme (no data loss)

- Theme: `infra/keycloak/themes/stockpilot/login/` (CSS + `messages_fa` + self-hosted Vazirmatn woff2).
- Compose mount: **only** `./infra/keycloak/themes/stockpilot:/opt/keycloak/themes/stockpilot` (not whole themes dir).
- Realm JSON: `loginTheme=stockpilot`, `defaultLocale=fa` for **fresh** imports.
- **Safe apply on existing realm (no `-v`):**

```powershell
powershell -File .\infra\keycloak\apply-login-theme.ps1
```

Equivalent:

```powershell
docker compose -p stockpilot -f compose.yaml -f compose.dev.yaml exec -T keycloak /opt/keycloak/bin/kcadm.sh config credentials --server http://localhost:8080 --realm master --user admin --password admin
docker compose -p stockpilot -f compose.yaml -f compose.dev.yaml exec -T keycloak /opt/keycloak/bin/kcadm.sh update realms/stockpilot -s loginTheme=stockpilot
docker compose -p stockpilot -f compose.yaml -f compose.dev.yaml exec -T keycloak /opt/keycloak/bin/kcadm.sh update realms/stockpilot -s internationalizationEnabled=true
docker compose -p stockpilot -f compose.yaml -f compose.dev.yaml exec -T keycloak /opt/keycloak/bin/kcadm.sh update realms/stockpilot -s supportedLocales+=fa
docker compose -p stockpilot -f compose.yaml -f compose.dev.yaml exec -T keycloak /opt/keycloak/bin/kcadm.sh update realms/stockpilot -s supportedLocales+=en
docker compose -p stockpilot -f compose.yaml -f compose.dev.yaml exec -T keycloak /opt/keycloak/bin/kcadm.sh update realms/stockpilot -s defaultLocale=fa
```


Form ids preserved: `#username`, `#password`, `#kc-login` (e2e green).

---

## OpenAPI diff summary

Additive field on `InventoryItemOut`:

- `has_position: boolean` (default `true`)

No removals; no path/method changes. Customer PATCH already in schema.

---

## Selector changes

**None.** E2e still uses button **ورود**, org `/Aftab/`, Keycloak `#username` / `#password` / `#kc-login`.

Sidebar aria: **جمع کردن منو** / **باز کردن منو** (not previously asserted).

---

## Screenshots

Gallery: [`docs/reports/phase45-run3_5-screenshots/`](phase45-run3_5-screenshots/) — landing, app login, Keycloak login, orgs, dashboard (+ Jalali open), customers edit, products/inventory zero-stock, sidebar expanded/collapsed; light-desktop, dark-desktop, mobile-390 (sidebar desktop-only). Dark after shots also cover orders/products/inventory.

---

## Commands to run afterwards

```powershell
# Rebuild / restart long-running services only (--wait must not include one-shot migrate/ops)
docker compose -f compose.yaml -f compose.dev.yaml up -d --build --wait keycloak api frontend-dev

# No Alembic migrate required for this run

# Apply Keycloak login theme on an EXISTING realm (safe, no volume wipe; no JSON-in-PowerShell)
$env:COMPOSE_PROJECT = "stockpilot"
$env:COMPOSE_FILES = "compose.yaml compose.dev.yaml"
powershell -File .\infra\keycloak\apply-login-theme.ps1

# Hard-refresh Keycloak login in the browser (Ctrl+F5)

# Optional re-verify
docker compose --profile test run --rm backend-checks
docker compose --profile test run --rm frontend-checks
docker compose -p stockpilot-e2e -f compose.yaml -f compose.e2e.yaml --profile test build
docker compose -p stockpilot-e2e -f compose.yaml -f compose.e2e.yaml --profile test run --rm e2e
docker compose -p stockpilot-e2e -f compose.yaml -f compose.e2e.yaml --profile test down
```

---

## Phase 5+ confirmation

No changes to Relay/Worker/Inbox, scheduler, Grafana, GHCR, Locust, `compose.prod.yaml`, or T13–T16 task docs beyond this report.
