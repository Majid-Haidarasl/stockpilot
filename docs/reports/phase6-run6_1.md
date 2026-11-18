# Phase 6 Run 6.1 — Metrics, dashboards, alerts

Date: 2026-11-18  
Scope: T14 week-7 — Compose profile `observability` (Prometheus, Grafana, Alertmanager, alert-sink, ops-exporter), migration `0014_ops_metrics`, API RED metrics on internal `:8001`, RabbitMQ `rabbitmq_prometheus` detailed queue scrape, idle worker heartbeat. No Outbox/Inbox purge, no `compose.prod.yaml` edits, no commit.

## Result

**Pass.** Backend **206**, Vitest **85**, Playwright e2e **8**. Alert proof: `StockpilotOutboxLagHigh` received by alert-sink; relay restarted and Outbox lag returned to normal.

## Privilege summary (`0014`)

| Object | `stockpilot_metrics` | Notes |
|---|---|---|
| `platform.heartbeats` | SELECT (+ `heartbeats_select_metrics`) | No tenant columns |
| `platform.outbox_lag()` | EXECUTE | Existing DEFINER; migrator owner |
| `platform.failed_jobs_metrics()` | EXECUTE | DEFINER; count of `replayed_at IS NULL` only |
| `platform.stale_reserved_orders_metrics()` | EXECUTE | DEFINER; count of stale RESERVED only |
| `platform.outbox` / `failed_jobs` / `sales.orders` | **no** table grants | Direct SELECT denied |

FORCE RLS is enabled on `failed_jobs` and `sales.orders`; `migrator_all USING (true)` lets DEFINER aggregates see all tenants. Integration tests seed two tenants and assert counts sum across both.

Role `stockpilot_metrics` is created by init (fresh volumes) or `ops ensure-db-roles` / `ensure_test_db` (existing volumes). Migrations never CREATE ROLE.

## Adjustments vs first plan draft

1. **Idle worker heartbeat:** Celery `worker_ready` starts a daemon thread (`STOCKPILOT_WORKER_IDLE_HEARTBEAT_SECONDS`, default 60) that upserts `platform.heartbeats` with `app.role=worker` so idle workers do not false-trigger `StockpilotHeartbeatStaleWorker`. Covered by `test_worker_idle_heartbeat.py`.
2. **Internal metrics `:8001`:** Bound only when `STOCKPILOT_API_METRICS_ENABLED=true` (api compose service). Idempotent start flag. Off for backend-checks / TestClient. Exposition tested via `render_metrics()`, not a real bind. Public app has no `/metrics` route. **Run 6.2 must never reverse-proxy `/metrics`.**

## What landed

- Migration `0014_ops_metrics` + role helpers + `.env.example` placeholders.
- `ops-exporter` (metrics DB role) gauges: outbox lag, heartbeats (scheduler/relay/worker), failed_jobs increase signal, stale reserved orders.
- API HTTP RED metrics (`prometheus-client`); single uvicorn process (no multiprocess mode).
- Compose profile `observability`: prometheus, grafana, alertmanager, alert-sink, ops-exporter. Host ports 9090 / 8300 / 8301 only (not 8001, not 15692; not 8084–8183).
- RabbitMQ `enabled_plugins`: `[rabbitmq_management,rabbitmq_prometheus]`.
- Prometheus scrape of `http://rabbitmq:15692/metrics/detailed?family=queue_coarse_metrics`.
- Grafana provisioned datasource + **StockPilot Ops** dashboard.
- Alert rules per plan (`FailedJobsGrowing` = `increase(...[15m]) > 0` only).

## Live RabbitMQ metric names used

From `/metrics/detailed?family=queue_coarse_metrics`:

- `rabbitmq_detailed_queue_messages_ready{vhost="/",queue="celery"}`
- `rabbitmq_detailed_queue_messages_unacked{...}`
- `rabbitmq_detailed_queue_messages{...}` (total depth)

Alert `StockpilotQueueDepthHigh` keys off ready/total for `queue="celery"`, `vhost="/"`.

## Alert proof + relay recovery

1. Stopped relay; inserted unpublished Outbox rows with aged `created_at`.
2. Prometheus fired `StockpilotOutboxLagHigh` (age > 60 for 2m).
3. alert-sink excerpt:

```text
ALERT_SINK_RECEIVED {"receiver": "alert-sink", "status": "firing", "alerts": [{"status": "firing", "labels": {"alertname": "StockpilotOutboxLagHigh", "instance": "ops-exporter:9108", "job": "stockpilot-ops-exporter", "severity": "warning"}, "annotations": {"description": "Oldest unpublished Outbox age exceeds 60s.", "summary": "Outbox lag high"}, ...}]}
```

4. Recovery:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml up -d --wait relay
docker compose -f compose.yaml -f compose.dev.yaml run --rm ops python -m stockpilot.bootstrap.ops queue-signals
```

Post-recovery: `unpublished_count=0`, `oldest_unpublished_age_seconds=None`.

**Side-effect note (this run):** The fake `OrderCancelled` Outbox rows were published into the **dev** DB and the worker created Inbox + (for some tenants) notifications. Targeted cleanup removed **only** the 6 resulting `OrderCancelled` notifications; Inbox/Outbox/`failed_jobs` were left alone.

**Future alert proofs:** Do **not** insert consumable lifecycle events into the shared development database. Prefer either (a) inducing lag on **`stockpilot_test`** (or another isolated Compose project DB), or (b) using an event type / path with **no worker side effects** (so publish alone moves lag without Inbox/notifications). If a temporary row is required in a product DB, plan a reviewed, ID-scoped cleanup beforehand.

## Test counts

| Suite | Count |
|---|---|
| backend-checks | **206 passed** (was 192 at Phase 5.4) |
| Vitest | **85 passed** |
| Playwright e2e (`-p stockpilot-e2e`) | **8 passed** |

New coverage includes: metrics role RLS denials, two-tenant DEFINER counts, idle worker heartbeat, HTTP label guards, metrics server idempotency flag, no public `/metrics` route.

## Commands used

```powershell
docker compose -f compose.yaml -f compose.dev.yaml run --rm ops python -m stockpilot.bootstrap.ops ensure-db-roles
docker compose -f compose.yaml -f compose.dev.yaml build api relay worker scheduler ops migrate ops-exporter backend-checks frontend-checks openapi-export
docker compose -f compose.yaml -f compose.dev.yaml up -d --wait postgres rabbitmq
docker compose -f compose.yaml -f compose.dev.yaml run --rm migrate
docker compose -f compose.yaml -f compose.dev.yaml up -d --wait api relay worker scheduler
docker compose -f compose.yaml -f compose.dev.yaml up -d --wait alert-sink alertmanager ops-exporter prometheus grafana
docker compose -f compose.yaml -f compose.dev.yaml run --rm ops python -m stockpilot.bootstrap.ops queue-signals
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm backend-checks
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm frontend-checks
docker compose -f compose.yaml -f compose.e2e.yaml -p stockpilot-e2e --profile test build e2e-ensure-db migrate api relay worker
docker compose -f compose.yaml -f compose.e2e.yaml -p stockpilot-e2e --profile test run --rm e2e
```

Never used `down -v` or volume deletion. Did not touch `compose.prod.yaml`. Did not commit.

## Deviations / notes

1. Ops CLI must be invoked as `python -m stockpilot.bootstrap.ops <cmd>` (bare `run ops queue-signals` replaces CMD incorrectly).
2. Fresh `uv.lock` includes `prometheus-client==0.26.0` (lock updated via `uv lock` as root with backend bind-mount).
3. E2E project must rebuild `e2e-ensure-db` so `stockpilot_metrics` exists before `0014`.
4. Single-process uvicorn: no `PROMETHEUS_MULTIPROC_DIR`. If 6.2 adds workers, enable multiprocess mode then.
5. Alert-proof fakes on the shared `stockpilot` DB created Inbox/notification side effects; notifications cleaned up (count 6). Prefer test DB / no-side-effect events next time (see Alert proof section).

## Explicitly not done (later)

- Run 6.2 production deploy / reverse proxy / `compose.prod.yaml` hardening (proxy must not route `/metrics`)
- Run 6.3 off-host backup + restore drill
- Run 6.4 load test
- Outbox/Inbox auto-purge (OPEN DECISION)
- Real alert notification channel (OPEN DECISION; local webhook sink used)
- `postgres_exporter` / `node_exporter` / backup freshness alerts
