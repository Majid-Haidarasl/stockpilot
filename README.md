# StockPilot

Web app for small/medium distribution companies to manage orders and stock.

Basic flow:

1. sales creates a customer order
2. system reserves available stock
3. sales confirms the order
4. warehouse ships it (full shipment only)

If the reservation expires or the order gets cancelled, reserved stock goes back.

## Status

Phase 2 (identity, orgs, catalog/customers) is implemented locally. Evidence: `docs/evidence/phase-2-report.md`.

## Requirements (Windows 11 host)

- Docker Desktop (WSL2 engine, give the engine **≥ 8 GB** RAM if you can)
- Git for Windows
- Cursor (optional but recommended)
- **Do not** install project Python or Node on Windows for this repo

Preferred path shape: `C:\dev\stockpilot` (avoid spaces / non-ASCII in the path when possible).

On many Windows hosts Hyper-V reserves `8000` and `8080`. Defaults use **API `8200`** and **Keycloak `8180`**.

## Quickstart (PowerShell)

```powershell
copy .env.example .env
docker compose -f compose.yaml -f compose.dev.yaml up -d --wait postgres
docker compose -f compose.yaml -f compose.dev.yaml build migrate ops api
docker compose -f compose.yaml -f compose.dev.yaml run --rm migrate
docker compose -f compose.yaml -f compose.dev.yaml run --rm ops
docker compose -f compose.yaml -f compose.dev.yaml up -d --build --wait keycloak api frontend-dev
```

Then open:

- API live: http://localhost:8200/health/live
- API ready (after migrate): http://localhost:8200/health/ready
- UI: http://localhost:5173
- Keycloak (dev): http://localhost:8180

Demo users (password `Passw0rd!`): `admin@aftab.test`, `sales@aftab.test`, `warehouse@aftab.test`, `admin@baran.test`, `viewer@baran.test`.

Login entry: http://localhost:5173/login → Keycloak → org picker → products/customers.

## Quality checks (PowerShell)

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm backend-checks
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm frontend-checks
```

## Docs

- Product language / roles / order lifecycle: `docs/product/`
- ADRs: `docs/architecture/decisions/`
- Agent brief: `AGENTS.md`
- Task specs: `docs/tasks/`

## Stack (v1 direction)

| Area | Choice |
|---|---|
| Backend | Python / FastAPI (modular monolith) |
| DB | PostgreSQL 17 |
| Auth | Keycloak (OIDC + PKCE, opaque server session) |
| Frontend | React + TypeScript + Vite + MUI RTL |
| Queue | RabbitMQ + Celery (later phase) |
| Edge | Caddy (production-like routing later) |

## License

Private/public project settings are managed on GitHub. No separate license file yet.
