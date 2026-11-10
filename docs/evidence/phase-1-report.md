# Phase 1 report — Foundation (T01–T04)

**Date:** 2026-11-11  
**Repo:** `D:\Me\Last Term\WEB\stockpilot` → https://github.com/Majid-Haidarasl/stockpilot  
**Host:** Windows 11, Docker Desktop (WSL2), PowerShell  
**Commit/push:** not done by the agent (developer-owned)

---

## Verdict

Phase 1 local exit criteria are **met**:

| Criterion | Result |
|---|---|
| Product language / roles / order lifecycle / ADRs frozen in-repo | Pass |
| Fresh Compose path: Postgres → migrate → API + Persian RTL UI | Pass |
| `/health/live` → 200 | Pass |
| `/health/ready` → 200 after migrate (`0001_schemas`) | Pass |
| `backend-checks` (Ruff, mypy, Import Linter, pytest, migrate) | Pass (8 tests) |
| `frontend-checks` (ESLint, `tsc`, Vitest) | Pass (1 test) |
| CI workflow checked in (`.github/workflows/ci.yml`) | Present |
| Patch pins recorded from real Docker runs | `docs/architecture/versions.md` |

---

## What was done by task

### T01 — Product docs & ADRs

Created:

- `docs/product/README.md`
- `docs/product/ubiquitous-language.md`
- `docs/product/roles-and-permissions.md`
- `docs/product/order-lifecycle.md` (state machine, inventory table, 30‑min TTL, numeric example 10→reserve 3→ship 7)
- `docs/product/invariants-and-v1-scope.md` (10 invariants, caps, non-goals, OPEN DECISIONS)
- `docs/architecture/decisions/README.md`
- `ADR-001` Modular monolith — **Accepted**
- `ADR-002`…`ADR-005` — stubs (**accepted-in-principle**)
- `ADR-006` sync SQLAlchemy — **Accepted**
- `ADR-007` integer IRR / freeze-at-reserve — **Accepted**
- `ADR-008` single-server deploy — **Accepted**

Identifiers match `AGENTS.md`. No invented features or patch versions.

### T02 — Monorepo, Docker, API shell, React RTL shell

- Monorepo tree per plan (`backend/`, `frontend/`, `infra/`, `tests/`, module packages with `public.py`)
- Backend FastAPI app: `GET /health/live`, `GET /health/ready`
- Frontend Vite + React + TS strict + MUI RTL + Vazirmatn + Persian subtitle
- `compose.yaml` / `compose.dev.yaml` / `compose.prod.yaml`
- `.env.example`, Dockerfiles, `uv.lock`, `package-lock.json`
- Vite `server.watch.usePolling = true` for Windows bind mounts
- README quickstart in PowerShell (no host Python/Node)

### T03 — PostgreSQL 17, roles, Alembic

- Init script creates DBs `stockpilot` + `keycloak` and roles `stockpilot_migrator`, `stockpilot_app`, `keycloak`
- Alembic revision `0001_schemas`: schemas `access`, `catalog`, `sales`, `inventory`, `notifications`, `platform` + grants
- Runtime role granted `SELECT` on `alembic_version` (needed for readiness)
- API uses runtime URL only; migrate uses migrator URL
- Docs: `docs/architecture/database-roles.md`

### T04 — Quality gate

- Ruff + mypy + Import Linter + pytest (`Money` domain tests + architecture smoke)
- ESLint + TypeScript + Vitest shell test
- Compose profile `test`: `backend-checks`, `frontend-checks`
- GitHub Actions workflow running the same Compose checks
- Coverage 85% target documented, **not** enforced yet (domain mostly empty)

---

## Commands actually run (and results)

```powershell
docker compose -f compose.yaml -f compose.dev.yaml up -d --wait postgres
docker compose -f compose.yaml -f compose.dev.yaml run --rm migrate
docker compose -f compose.yaml -f compose.dev.yaml up -d --build --wait api frontend-dev
```

Probes:

- `GET http://localhost:8000/health/live` → `{"status":"ok"}` **200**
- `GET http://localhost:8000/health/ready` → `{"status":"ready","schema_revision":"0001_schemas"}` **200**
- `GET http://localhost:5173/` → **200**

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm backend-checks
```

→ Ruff OK, mypy OK, Import Linter **3 kept / 0 broken**, **8 passed**, Alembic upgrade OK.

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm --no-deps frontend-checks
```

→ ESLint OK, `tsc` OK, Vitest **1 passed**.

---

## Notable fixes during verification

1. Runtime role lacked `SELECT` on `alembic_version` → readiness returned 503 `database_unavailable`; fixed in migration grant.
2. Import Linter failed on unmatched `ignore_imports` for future public cross-imports → removed unused ignores for Phase 1.
3. Vitest 2 + Vite 6 type clash → Vitest 3.2.7.
4. Login-shell `bash -lc` dropped venv PATH → switched checks CMD to `bash -c`.

---

## Explicitly not in Phase 1

Keycloak container, RabbitMQ/worker/relay/scheduler, RLS policies, business tables, order aggregate, e2e/Playwright, Locust, Trivy/Gitleaks/pip-audit as release blockers, production Caddy edge serving built UI.

---

## Reminder for you

Local work is ready. **Commit and push when you want** (agent will not push). Suggested review before commit:

- Confirm `.env` is not staged
- Confirm `.cursor/skills/` stays ignored (rules under `.cursor/rules/` are fine to commit)
- After push, GitHub Actions should run `ci.yml` on `main`

---

## Suggested next step

Phase 2 / **T05** (Keycloak + session) when you say go.
