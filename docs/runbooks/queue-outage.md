# Runbook — Queue outage (RabbitMQ / Relay / Worker)

## Symptoms

- Orders succeed but in-app notifications lag or never appear.
- `platform.outbox` rows remain with `published_at IS NULL` and rising age.
- RabbitMQ queue depth grows, or relay/worker containers unhealthy / restarting.
- New rows in `platform.failed_jobs` (poison / exhausted retries).
- API `GET /health/ready` stays **200** (ready must not depend on RabbitMQ).

## Celery remote control disabled

RabbitMQ 4.x rejects Celery pidbox transient non-exclusive queues, so workers run with:

- `worker_enable_remote_control=False` (app config)
- Compose flags: `--without-gossip --without-mingle --without-heartbeat`

**What no longer works:** `celery -A … inspect …`, `celery -A … control …`, and Flower-style remote control. Do not rely on them for diagnosis.

**What to use instead:**

1. **Container logs** — `docker compose … logs relay worker` (publish failures, consume retries, permanent failures).
2. **RabbitMQ management UI** — localhost-only in dev; queue depth, consumers, connections.
3. **Ops / SQL** — unpublished Outbox lag and `platform.failed_jobs` queries below; `ops replay-failed-jobs` for controlled republish.

**Heartbeat note:** `--without-heartbeat` disables Celery *worker event* heartbeats only (events/pidbox). The **AMQP broker connection heartbeat** remains active (`broker_heartbeat=30` in `celery_app`). Do not confuse the two.

## Checks

1. Compose: `docker compose … ps` — `postgres`, `rabbitmq`, `relay`, `worker`, `scheduler` healthy/started.
2. `GET /health/ready` on the API — expect 200 even if the broker is down; **503 `schema_mismatch`** if DB alembic revision ≠ expected (rebuild migrate / upgrade head).
3. RabbitMQ: container health; management UI is localhost-only in dev.
4. Unpublished Outbox lag (migrator / ops SQL):

```sql
SELECT event_id, event_type, created_at, last_error, lease_expires_at
FROM platform.outbox
WHERE published_at IS NULL
ORDER BY created_at
LIMIT 50;
```

5. Relay / worker logs: publish failures, consume retries, permanent failures.
6. Final failures:

```sql
SELECT id, tenant_id, event_id, task_name, error_message, attempts,
       replayed_at, replay_count, last_failed_at
FROM platform.failed_jobs
ORDER BY last_failed_at DESC
LIMIT 50;
```

## Recovery

1. Restore broker: `docker compose … up -d --wait rabbitmq`
2. Start publishers/consumers: `up -d --wait relay worker` (after migrate).
3. Wait for Relay to claim and publish unpublished Outbox rows; workers drain the queue.
4. Confirm notifications for a known order; Outbox `published_at` fills in; queue depth falls.
5. Do **not** `down -v` or delete volumes. Do **not** casually delete Inbox or `failed_jobs` rows.

## Controlled replay (`failed_jobs`)

Dry-run first (default):

```powershell
docker compose -f compose.yaml -f compose.dev.yaml run --rm ops python -m stockpilot.bootstrap.ops replay-failed-jobs --id <uuid>
```

Confirm (republishes **same** `event_id`; lock held across publish):

```powershell
docker compose -f compose.yaml -f compose.dev.yaml run --rm ops python -m stockpilot.bootstrap.ops replay-failed-jobs --id <uuid> --confirm --replayed-by ops@example
```

Notes:

- Default skips rows with `replayed_at IS NOT NULL`; use `--include-replayed` only intentionally (Inbox still dedups).
- Unscoped jobs (`tenant_id` NULL) are printed as `skipped: unscoped` and are not audited/replayed.
- If publish succeeds but the DB UPDATE/audit fails, the CLI reports it clearly; **re-replay is safe** because Inbox keys on `event_id`.
- Never deletes `failed_jobs` rows.

## Scheduler

The reservation-expiry `scheduler` service does **not** use RabbitMQ. It expires due RESERVED orders via the same use case as confirm-after-expiry, writing `OrderExpired` to the Outbox in the same tenant transaction; Relay publishes later.

### Symptoms

- Compose `scheduler` unhealthy (heartbeat stale > ~180s).
- Reservations still held more than ~2 minutes after `expires_at`.
- Accidental `docker compose … up --scale scheduler=2` (second copy should idle on advisory lock).

### Checks

1. `docker compose … ps` — `scheduler` health; `ops queue-signals` for heartbeats + Outbox lag.
2. Confirm one scheduler replica only (V1). Session advisory lock: only one tick runs; the other logs `lock_not_acquired`.
3. If RabbitMQ is down: orders should still expire and Outbox rows appear with `published_at IS NULL`; after broker+relay recovery, rows publish (same as queue outage recovery above).
4. Logs: `scheduler_tenant_failed` with `tenant_id` means one org failed; others should still proceed.

### Recovery

1. Fix DB connectivity / schema drift; rebuild migrate and upgrade if needed.
2. Restart a single scheduler: `up -d --wait scheduler` (do not scale to 2).
3. Prove: backdated RESERVED order becomes EXPIRED; `queue-signals` shows fresh `scheduler` heartbeat; lag falls once Relay runs.

## Outbox / Inbox retention

Keep published Outbox bodies at least **30 days** for controlled republish. No automatic Outbox or Inbox purge in the current release.

> **OPEN DECISION:** Scheduled purge of `platform.outbox` / `platform.inbox` older than 30 days (dry-run first). Not implemented in Phase 5.

## What not to do

- Attach an old queue to a restored database without a controlled Outbox replay plan.
- Delete Inbox rows to “force” a re-notify without a reviewed repair.
- Put `STOCKPILOT_TEST_HANG_EVENT_ID` or admin DB URLs on api/worker/relay/scheduler.
- Scale the scheduler above one replica in v1.
