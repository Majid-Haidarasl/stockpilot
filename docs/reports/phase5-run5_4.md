# Phase 5 Run 5.4 — Scheduler, heartbeat, lag signals

Date: 2026-11-17  
Scope: T14 week-6 — Compose `scheduler` (one instance), advisory-lock tick, `0013_scheduler_heartbeats`, heartbeats + `platform.outbox_lag()`, ops `queue-signals`, ADR-006 + queue-outage scheduler section. No Grafana/Prometheus, no Outbox/Inbox purge, no commit.

## Result

**Pass.** Backend **192**, Vitest **85**, Playwright e2e **8** (after RabbitMQ test-vhost isolation review fix).

## Privilege summary (`0013`)

| Object | `stockpilot_app` | `stockpilot_relay` | `stockpilot_migrator` |
|---|---|---|---|
| `platform.heartbeats` | SELECT; INSERT/UPDATE only when `service_name = app.role` and role ∈ {`scheduler`,`worker`} | SELECT; INSERT/UPDATE only `service_name='relay'` | full DML |
| `access.tenants` | existing + `tenants_select_scheduler` (SELECT when `app.role=scheduler`) | — | existing |
| `platform.outbox` | **no** new SELECT policy (no cross-tenant Outbox reads) | existing relay policy | existing |
| `platform.outbox_lag()` | EXECUTE | EXECUTE | owner + EXECUTE |

HTTP / normal tenant sessions (`app.role` = human role) cannot write heartbeats (covered by test).

## What landed

- Compose `scheduler`: same backend image, DB as `stockpilot_app`, no RabbitMQ/admin URL, healthcheck via `scheduler_health` (heartbeat stale threshold 180s).
- Dedicated-connection `pg_try_advisory_lock(hashtext('stockpilot.reservation_expiry'))` for the tick; unlock in `finally`; abort if lock connection drops.
- Reuses `OrderCycleService.expire` / Outbox `OrderExpired` in tenant UoW; per-tenant error isolation; SIGTERM/SIGINT stop flag.
- Migration `0013_scheduler_heartbeats`: heartbeats table, row-scoped RLS, `tenants_select_scheduler`, SECURITY DEFINER `outbox_lag()`.
- Relay + worker cheap last-activity upserts; ops `queue-signals`.
- Docs: ADR-006, ADR-005 pointer, queue-outage scheduler section.
- **Review fix:** `backend-checks` uses RabbitMQ vhost `stockpilot_test` (idempotent `ensure_rabbitmq_test_vhost` via management API). Dev `api`/`relay`/`worker`/`ops`/`scheduler` stay on default `/`. E2E project has its **own** RabbitMQ container (`-p stockpilot-e2e`) and keeps `/`.

## Test counts

| Suite | Count |
|---|---|
| backend-checks | **192 passed** (was 179 at 5.3; 191 before vhost isolation test) |
| Vitest | **85 passed** |
| Playwright e2e (`-p stockpilot-e2e`) | **8 passed** |

New coverage includes: parallel advisory-lock ticks, lock release after tick/exception, expire without broker then relay publish, heartbeat details, stale healthcheck, `outbox_lag()`, no cross-tenant Outbox SELECT, heartbeat write denied for admin session, per-tenant failure isolation, stop-flag unit tests, compose broker vhost isolation.

## Commands used

```powershell
docker compose -f compose.yaml -f compose.dev.yaml build api relay worker scheduler ops migrate backend-checks frontend-checks
docker compose -f compose.yaml -f compose.dev.yaml up -d --wait postgres rabbitmq
docker compose -f compose.yaml -f compose.dev.yaml run --rm migrate
docker compose -f compose.yaml -f compose.dev.yaml up -d --wait api relay worker scheduler
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm backend-checks
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm frontend-checks
docker compose -f compose.yaml -f compose.e2e.yaml -p stockpilot-e2e --profile test build migrate api relay worker
docker compose -f compose.yaml -f compose.e2e.yaml -p stockpilot-e2e --profile test run --rm e2e
```

Never used `down -v` or volume deletion. Did not touch `compose.prod.yaml`. Did not commit.

## Deviations / notes

1. **RabbitMQ test vhost (review fix):** `backend-checks` broker URL ends with `/stockpilot_test`. `ensure_rabbitmq_test_vhost` creates that vhost + permissions via management HTTP API (no `load_definitions`, no volume wipe). Dev worker may stay **running** during backend-checks without stealing messages. E2E uses an isolated Compose project RabbitMQ on `/` — unchanged.
2. **E2E project images:** Project `-p stockpilot-e2e` builds `stockpilot-e2e-*` images separately from the main stack; rebuild migrate/api/relay/worker after schema bumps or migrate assert fails at an older revision.
3. **Keycloak host port:** Dev bring-up may still need `KEYCLOAK_HOST_PORT=8280` when Windows excludes 8180 (same as 5.2/5.3).

## Explicitly not done (later)

- Outbox/Inbox auto-purge (OPEN DECISION)
- Grafana / Prometheus / ops-exporter (Phase 6)
- Email, `compose.prod.yaml`, Phase 6–7
