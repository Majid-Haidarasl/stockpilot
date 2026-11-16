# Phase 5 Run 5.2 — Worker, Inbox, failed_jobs, notifications API

Date: 2026-11-16  
Scope: T13 partial — Compose `worker`, migration `0011_inbox_notifications`, Inbox-idempotent Celery consumer, durable `failed_jobs`, notifications HTTP list/read + OpenAPI regen. No UI, no ADR-005 completion, no cut-point/killed-worker/replay (5.3).

## Result

**Pass.** Backend **158**, Vitest **80**, Playwright e2e **7** (after worker-session RLS review fix).

## Privilege summary (`stockpilot_app`)

| Table | SELECT | INSERT | UPDATE | DELETE | RLS notes |
|---|---|---|---|---|---|
| `platform.inbox` | yes | yes | no | no | Tenant `FOR ALL` policy; grants limit DML |
| `platform.failed_jobs` | **no** | yes | no | no | `FOR INSERT` only: tenant match, or null tenant when `app.tenant_id` unset |
| `notifications.notifications` | yes | yes | **`read_at` column only** | no | Tenant policy; column-level UPDATE |

Migrator retains full DML + `migrator_all` policies. Ops/cross-tenant reads of `failed_jobs` deferred.

Default privileges from `0001_schemas` grant full DML to `stockpilot_app` on new tables; migration **REVOKEs ALL** then re-grants the least-privilege set above.

## What landed

- Compose `worker`: same backend image, `celery … --concurrency=2`, DB as `stockpilot_app`, broker URL, depends on postgres/migrate/rabbitmq. **No** `STOCKPILOT_ADMIN_DATABASE_URL`.
- Migration `0011_inbox_notifications`: `platform.inbox`, `platform.failed_jobs`, `notifications.notifications` + ENABLE/FORCE RLS; SELECT-only `memberships_select_worker` on `access.memberships`.
- Worker session role: `SESSION_ROLE_WORKER` (`app.role=worker`) — not a human `access.Role`; HTTP never sets it.
- Consumer: one transaction Inbox + notifications; duplicate `event_id` → ack, no second notifications; empty recipients → Inbox + 0 rows + structured warning + ack.
- Recipients: admin+sales for all five order events; **warehouse only on `OrderConfirmed`**.
- Retry: exponential backoff + jitter, max 5 attempts; poison/unknown → `failed_jobs` then ack; failed_jobs insert failure → no ack.
- Celery: `acks_late`, `task_reject_on_worker_lost`, prefetch 1, `confirm_publish=True`; concrete retry-confirm test.
- HTTP: `GET …/notifications`, `POST …/notifications/{id}/read` (CSRF); OpenAPI + generated FE types updated.
- Import Linter: notifications must not import sales.

## Test counts

| Suite | Count |
|---|---|
| backend-checks | **158 passed** (was 132 at 5.1; 155 before worker-role review fix) |
| Vitest | **80 passed** |
| Playwright e2e (`-p stockpilot-e2e`) | **7 passed** |

## Commands used

```powershell
docker compose -f compose.yaml -f compose.dev.yaml build api relay worker ops migrate backend-checks frontend-checks
```

```powershell
docker compose -f compose.yaml -f compose.dev.yaml up -d --wait postgres rabbitmq
```

```powershell
docker compose -f compose.yaml -f compose.dev.yaml run --rm migrate
```

```powershell
docker compose -f compose.yaml -f compose.dev.yaml up -d --wait api relay worker
```

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm backend-checks
```

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm frontend-checks
```

```powershell
docker compose -f compose.yaml -f compose.e2e.yaml -p stockpilot-e2e --profile test run --rm e2e
```

OpenAPI regen (after export):

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm openapi-export
docker compose -f compose.yaml -f compose.dev.yaml run --rm --no-deps --entrypoint sh frontend-dev -c "npm run generate:api"
```

Never used `down -v` or volume deletion. Did not touch `compose.prod.yaml`. Did not commit.

## Deviations

1. **Keycloak host port:** Windows excluded TCP range includes `8084–8183`, so default `8180` could not bind. Dev bring-up used `KEYCLOAK_HOST_PORT=8280` (and matching OIDC issuer env) for `api`/`keycloak` only. E2E project uses its own compose and passed independently.
2. **Re-apply of 0011:** After privilege REVOKEs and again after the worker-role RLS fix, images were rebuilt and `alembic downgrade -1` / `upgrade` was run on `stockpilot` and `stockpilot_test` (migrate image must include the latest `0011`; host bind-mount alone is not used by the migrate service).
3. **Memberships RLS for recipient resolution:** Worker UoW sets non-human `SESSION_ROLE_WORKER` (`app.role=worker`). Migration `0011` adds SELECT-only policy `memberships_select_worker` (tenant match + role=worker). Not a valid `access.Role`; HTTP `ActorContext` never accepts it. No admin impersonation.
4. **failed_jobs id:** Generated in Python; no `RETURNING` (app has no SELECT on `failed_jobs`).

## Explicitly not done (later runs)

- Cut-point / killed-worker tests, ops replay, ADR-005 completion, queue-outage runbook, notification UI (5.3)
- Scheduler Compose + lag signals (5.4)
- Automatic Inbox purge (OPEN DECISION)
- Email, `compose.prod.yaml`, Phase 6/7
