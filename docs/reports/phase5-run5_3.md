# Phase 5 Run 5.3 — Reliability tests, ops replay, notifications UI, docs

Date: 2026-11-16  
Scope: T13 completion — cut-point + killed-worker tests, `0012_failed_jobs_replay`, ops `replay-failed-jobs`, RTL notifications UI, ADR-005 + queue-outage runbook. No scheduler (5.4), no Grafana/email, no commit.

## Result

**Pass.** Backend **179**, Vitest **85**, Playwright e2e **8** (post-commit review).

## Privilege summary (`0012`)

| Change | `stockpilot_app` | `stockpilot_migrator` |
|---|---|---|
| `failed_jobs.sanitized_envelope`, `replayed_at`, `replayed_by`, `replay_count` | **No new rights** (INSERT-only from 0011 still covers new INSERT columns) | SELECT/INSERT/UPDATE/DELETE re-asserted |

## What landed

- Migration `0012_failed_jobs_replay` + schema revision bump on api/relay/worker/backend-checks.
- Allow-list `sanitize_envelope` (consumer-derived payload keys); stored on final failure.
- Ops `replay-failed-jobs`: dry-run default; `--confirm` locks with `FOR UPDATE SKIP LOCKED`, publishes **original** envelope / **same `event_id`**, then UPDATE `replayed_*` + audit in the same TX; skips unscoped (`tenant_id` NULL); never deletes rows. Broker URL on **ops only**.
- Cut-points (a)/(b)/(c) + killed-worker tests; hang hook gated to `STOCKPILOT_ENVIRONMENT=test` only (never in compose).
- Celery: `worker_enable_remote_control=False` + compose worker `--without-gossip/mingle/heartbeat` (RabbitMQ 4.4 rejects Celery pidbox transient queues).
- Notifications UI: list, unread filter, cursor load-more, mark-read (CSRF), empty/error, badge with MUI `max={99}` (`99+`), refetchInterval 20s + refetchOnWindowFocus.
- E2E: rabbitmq/relay/worker wired in `compose.e2e.yaml`; notifications spec; `seed-e2e` tops up sellable stock.
- Docs: ADR-005 Accepted; `docs/runbooks/queue-outage.md`; Outbox retention ≥30 days, no auto-purge.

## Test counts

| Suite | Count |
|---|---|
| backend-checks | **179 passed** (was 176 pre-review) |
| Vitest | **85 passed** |
| Playwright e2e (`-p stockpilot-e2e`) | **8 passed** |

## Commands used

```powershell
docker compose -f compose.yaml -f compose.dev.yaml build api relay worker ops migrate backend-checks frontend-checks
docker compose -f compose.yaml -f compose.dev.yaml up -d --wait postgres rabbitmq
docker compose -f compose.yaml -f compose.dev.yaml run --rm migrate
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm backend-checks
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm frontend-checks
docker compose -f compose.yaml -f compose.e2e.yaml -p stockpilot-e2e --profile test run --rm e2e
```

Never used `down -v` or volume deletion. Did not touch `compose.prod.yaml`. Did not commit.

## Deviations / notes

1. **Keycloak host port:** Dev bring-up may need `KEYCLOAK_HOST_PORT=8280` when Windows excludes 8180 (same as 5.2).
2. **RabbitMQ 4.4 + Celery pidbox:** Workers crash-looped on `transient_nonexcl_queues`. Fixed by disabling remote control and adding `--without-gossip/mingle/heartbeat` on the compose worker.
3. **E2E migrate image lag:** Isolated e2e DB was stuck at `0009` until migrate image rebuilt and upgraded through `0012`; relay could not claim without lease columns.
4. **E2E stock top-up:** Repeated runs left aftab available=0; `seed-e2e` now tops sellable stock to ≥50.
5. **E2E relay role:** Existing e2e Postgres volumes may lack `stockpilot_relay`; run `ops ensure-db-roles` (or `e2e-ensure-db`) before messaging.

## Explicitly not done (later runs)

- Scheduler Compose + lag signals (5.4)
- Grafana/Prometheus, email
- **TODO Run 5.4:** scheduled purge of Outbox/Inbox rows older than 30 days (dry-run first); no purge implemented in 5.3
- `compose.prod.yaml`, Phase 6–7
