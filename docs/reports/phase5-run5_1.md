# Phase 5 Run 5.1 — RabbitMQ + Celery app + Outbox Relay

Date: 2026-11-15  
Scope: T13 partial — durable RabbitMQ, Celery app, Relay (lease/claim, publisher confirms, unroutable detection, versioned envelope, event→task mapping). No worker Inbox, notifications APIs, or scheduler Compose service.

## Result

**Pass.** Backend **132**, Vitest **80**, Playwright e2e **7**. API readiness stays green with RabbitMQ stopped; an Outbox row written during the outage is published after RabbitMQ + Relay recover.

## Pins (verified in Docker)

| Component | Pin | Digest / note |
|---|---|---|
| RabbitMQ image | `rabbitmq:4.4.0-management-alpine` | `sha256:4841f6384ef8313c3594cd3f2e9f40c10805f8a61c45f08a9a5d9ddea8199267` |
| celery | `5.5.3` | from `uv.lock` |
| kombu | `5.5.4` | |
| amqp | `5.4.2` | |
| billiard | `4.3.2` | |
| vine | `5.1.0` | |

Recorded in `docs/architecture/versions.md`.

## What landed

- Compose: `rabbitmq` (named volume `rabbitmq_data`, healthcheck, management UI `127.0.0.1` only in `compose.dev.yaml`), `relay` (same backend image).
- Role `stockpilot_relay` (`NOBYPASSRLS NOINHERIT LOGIN`): created by postgres init (fresh) or `ops ensure-db-roles` (existing volumes). **No** `CREATE ROLE` / passwords in Alembic.
- Migration `0010_outbox_lease`: `lease_owner`, `lease_expires_at`, `last_error`; claim index; `SELECT` + column-level `UPDATE` on relay columns only; RLS policy for relay.
- Relay: short claim tx → kombu publish (`confirm_publish`, `mandatory=True`, `on_return`) → idempotent `UPDATE … WHERE published_at IS NULL`.
- Publish failure / unroutable: `last_error` set; `lease_expires_at = now() + exponential backoff` (cap 5 minutes + jitter) — no hot-loop.
- Celery stub task `stockpilot.notifications.deliver_order_lifecycle_event` for all five T11 order event types.
- Broker URL built in Compose from `RABBITMQ_DEFAULT_USER` / `RABBITMQ_DEFAULT_PASS` only.
- `STOCKPILOT_ADMIN_DATABASE_URL` on **ops only** (asserted in tests + live `exec`).

## Test counts

| Suite | Count |
|---|---|
| backend-checks | **132 passed** (was 116) |
| Vitest | **80 passed** |
| Playwright e2e (`-p stockpilot-e2e`) | **7 passed** |

New backend coverage includes: backoff unit tests, mapping/envelope, compose admin-URL isolation, relay privilege, dual-claim after lease expiry, unroutable → unpublished + `last_error`, mapping publish, outage recovery.

## Outage checks

1. `docker compose … stop rabbitmq`
2. `GET /health/ready` → **200** (API does not depend on RabbitMQ)
3. Inserted unpublished Outbox row while broker down (`5045ff51-be6e-47a4-aa0d-ed69d0c71ad1`)
4. `up -d --wait rabbitmq relay` → row `published_at IS NOT NULL`, `last_error` null

## Commands used (existing `postgres_data`)

```powershell
docker compose -f compose.yaml -f compose.dev.yaml build api relay ops migrate backend-checks frontend-checks
docker compose -f compose.yaml -f compose.dev.yaml up -d --wait postgres rabbitmq
docker compose -f compose.yaml -f compose.dev.yaml run --rm ops python -m stockpilot.bootstrap.ops ensure-db-roles
docker compose -f compose.yaml -f compose.dev.yaml run --rm migrate
docker compose -f compose.yaml -f compose.dev.yaml up -d --wait api relay
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm backend-checks
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm frontend-checks
docker compose -f compose.yaml -f compose.e2e.yaml -p stockpilot-e2e --profile test run --rm e2e
```

Never used `down -v` or volume deletion. Did not touch `compose.prod.yaml`.

## Deviations from the revised plan

1. **`ops ensure-db-roles` invocation:** Compose service default command is `python -m stockpilot.bootstrap.ops bootstrap …`, so the runnable form is  
   `run --rm ops python -m stockpilot.bootstrap.ops ensure-db-roles`  
   (not bare `run --rm ops ensure-db-roles`).
2. **Celery extra:** PyPI `celery` has no `[amqp]` extra; dependency is `celery==5.5.3` (amqp/kombu come as transitive deps).
3. **RabbitMQ definitions file:** Durable Celery exchange/queue are declared by the Relay publisher on connect; no `management.load_definitions` import (avoids wiping the default user).
4. **kombu `content_type`/`content_encoding`:** Must not be passed alongside `serializer="json"` — that combination caused `struct.error: argument for 's' must be a bytes object` on py-amqp. Documented in publisher code.
5. **Additions (approved at implement time):** failure backoff with jitter; admin URL isolation for ops-only.

## Explicitly not done (later runs)

- Worker Inbox, `failed_jobs`, notifications HTTP/UI (5.2)
- Cut-point / killed-worker tests, ops replay, ADR-005 completion, queue-outage runbook (5.3)
- Scheduler Compose service + lag signals (5.4)
- Prometheus/Grafana, GHCR, email, `compose.prod.yaml`
