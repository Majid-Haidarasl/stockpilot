# Phase 2 report — Identity, orgs, master data (T05–T07)

**Date:** 2026-11-11  
**Repo:** `D:\Me\Last Term\WEB\stockpilot` → https://github.com/Majid-Haidarasl/stockpilot  
**Host:** Windows 11, Docker Desktop (WSL2), PowerShell  
**Commit/push:** not done by the agent (developer-owned)

---

## Verdict

Phase 2 local exit criteria are **met**:

| Criterion | Result |
|---|---|
| Real Keycloak login → opaque server session | Pass |
| Unauthorized `/api/v1/me` → 401 | Pass |
| Two orgs (Aftab / Baran) via audited `ops bootstrap` | Pass |
| Membership + `ActorContext` + RLS as runtime role | Pass |
| Same-org product create/view (API + UI path) | Pass |
| ADR-003 / ADR-004 Accepted | Pass |
| `backend-checks` (ruff/mypy/import-linter/migrate/pytest) | Pass (**23** tests) |
| `frontend-checks` (eslint/tsc/vitest) | Pass (**1** test) |

Windows Hyper-V reserved ports blocked naive `8000`/`8080` binds. Defaults are **API `8200`** and **Keycloak `8180`**.

---

## What was done by task

### T05 — Keycloak, OIDC, opaque session

- Compose `keycloak` (realm import), Authlib Authorization Code + PKCE
- Routes: `GET /auth/login`, `GET /auth/callback`, `GET /api/v1/me`, `POST /api/v1/auth/logout` (CSRF)
- Hashed session cookie + readable CSRF cookie; idle 30m / max 8h
- Public issuer for browser + `iss` checks; Docker-internal rewrite for token/JWKS
- Scope is `openid profile email` (no `offline_access` until client offline tokens are enabled)
- Frontend login entry; post-login lands on `/orgs`

### T06 — Tenants, membership, RLS

- Migrations `0002_access_identity` (+ grants/RLS prep) and tenant-scoped tables in `0003`
- `ActorContext`, membership APIs, last-admin lock (`SELECT … FOR UPDATE` on tenant)
- Idempotent `python -m stockpilot.bootstrap.ops bootstrap` seeds Aftab/Baran + demo memberships
- First login links bootstrap users by email → real Keycloak `sub`
- Isolation / last-admin / permission tests as **runtime** role

### T07 — Catalog & customers

- `catalog.products` (per-tenant SKU, integer IRR, versioned PATCH, audit)
- `sales.customers` CRUD + audit
- Persian product/customer pages under `/t/:tenantId/...`
- Money JSON as digit strings + `IRR`

---

## Verification commands (PowerShell)

```powershell
copy .env.example .env
docker compose -f compose.yaml -f compose.dev.yaml up -d --wait postgres
docker compose -f compose.yaml -f compose.dev.yaml build migrate ops api
docker compose -f compose.yaml -f compose.dev.yaml run --rm migrate
docker compose -f compose.yaml -f compose.dev.yaml run --rm ops
docker compose -f compose.yaml -f compose.dev.yaml up -d --build --wait keycloak api frontend-dev

docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm backend-checks
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm frontend-checks
```

Smoke observed locally:

- `GET http://localhost:8200/health/live` → 200  
- `GET http://localhost:8200/health/ready` → 200 (`0003_catalog_customers_rls`)  
- `GET /api/v1/me` without cookie → 401  
- Browser: login `admin@aftab.test` / `Passw0rd!` → session → org picker (Aftab) → product create `SKU-100` → **201**

---

## Demo accounts

Password for all: `Passw0rd!`

| Email | Org | Role |
|---|---|---|
| `admin@aftab.test` | Aftab | admin |
| `sales@aftab.test` | Aftab | sales |
| `warehouse@aftab.test` | Aftab | warehouse |
| `admin@baran.test` | Baran | admin |
| `viewer@baran.test` | Baran | viewer |

---

## Known follow-ups (not blocking week-2 exit)

- Stronger Keycloak management-port healthcheck
- Full Keycloak login integration job in CI (currently session/callback unit + DB isolation tests)
- Optional offline/refresh tokens if product needs them later
- Playwright main-path later (T12+)

---

## Suggested commit message (English)

```
Complete Phase 2: Keycloak sessions, tenants/RLS, catalog UI

Add OIDC PKCE login with opaque hashed sessions, org memberships with
runtime RLS, products/customers APIs and Persian UI, plus Compose ports
that avoid Windows Hyper-V exclusions.
```

Remind: commit and push are yours when ready.
