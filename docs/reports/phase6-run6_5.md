# Phase 6 Run 6.5 — Outbox drain diagnosis and fix

Date: 2026-11-18  
Scope: Diagnose slow Outbox drain after Run 6.4; fix the cause on **prod-like only**. No purge, no `down -v`, no `compose.prod.yaml` edits, no commit.

## Result

**Pass.** Root cause **(c) relay throughput** — not stuck, not missing index, not a worker backlog. After a batch-publish fix, the existing backlog drained to **0** in under **1 minute** (~**2422** events/min vs ~**74**/min before). Locust 6.4 shape re-run: failures **0%**, steady p95 still under targets, outbox **0** immediately after the run (baseline restored within 10 min), `balance-check` **0** mismatches, `failed_jobs` unchanged at **0**.

Checks: backend **237**, Vitest **85**, e2e **8**, Gitleaks **clean**.

## Step 1 — Measure (before change)

### No-load drain sample (15 × 60s)

Artifacts: `tests/load/results/outbox_drain_samples.json`

| Sample | Unpublished | Oldest age (s) | last_error | attempt≥5 |
|---|---:|---:|---:|---:|
| t=0 | 6856 | 3240 | 0 | 0 |
| t=14 min | 5819 | 3801 | 0 | 0 |

- **Drain rate:** **~74.1 events/min** (~1.23/s)
- **Projected time to zero:** **~78.6 min**

### Relay settings in effect

| Setting | Value | Source |
|---|---|---|
| `STOCKPILOT_OUTBOX_BATCH_SIZE` | **50** | settings / compose default |
| `STOCKPILOT_OUTBOX_LEASE_SECONDS` | **30** | settings |
| `STOCKPILOT_RELAY_POLL_SECONDS` | **1.0** | settings |
| Claim lock | `FOR UPDATE SKIP LOCKED` + lease columns | `claim_batch` |
| Publish path (before) | **one Kombu connection per event** + `drain_events(timeout=0.75)` after each | `publisher.py` |

### Worker / RabbitMQ

| Item | Value |
|---|---|
| Worker command | Celery `--concurrency=2` |
| Prefetch | Celery default (queue empty when sampled) |
| `celery` queue | **messages=0**, **ready=0**, **consumers=1** |

Worker logs: tasks succeed in ~5–8 ms; arrivals ~0.8–1.0s apart (waiting on relay).

### Logs

- Relay: only `relay_published count=50` — no errors, no poison loop.
- Worker: successful `deliver_order_lifecycle_event` — no retries/poison.
- Outbox rows: `last_error` all null; `attempt_count` max **1**.

### EXPLAIN ANALYZE (claim select pattern)

Partial index present and used:

```text
Index Scan using ix_outbox_claimable on outbox
  Filter: ((lease_expires_at IS NULL) OR (lease_expires_at < now()))
Execution Time: 0.237 ms
```

`ix_outbox_claimable` = `btree (created_at) WHERE published_at IS NULL`.

## Step 2 — Diagnosis

| Hypothesis | Verdict | Evidence |
|---|---|---|
| (a) stuck (poison / lock / error loop) | **No** | No `last_error`; attempts ≤1; SKIP LOCKED; steady progress |
| (b) slow query / missing index | **No** | Index used; claim plan **0.24 ms** |
| (c) relay throughput | **Yes** | ~74/min despite batch=50; ~0.8s per message matches per-event connect + **`drain_events(0.75)`**; queue empty → not waiting on consumer |
| (d) consumer bottleneck | **No** | RabbitMQ depth **0**; worker finishes each task in ms |

**Root cause:** Relay published **serially with a new AMQP connection and a 0.75s return-poll per message**, plus a new DB engine/txn pattern that capped effective throughput near **1 event/s** even while logging batches of 50.

## Step 3 — Fix (minimal)

No migration (index already correct). Code-only:

1. **`publish_celery_tasks`** — one AMQP connection/channel per batch; non-blocking per-message return poll; short end-of-batch drain.
2. **`mark_published_many`** — single UPDATE for successful ids.
3. **`relay.run_once` / `main`** — reuse process-level SQLAlchemy engine; skip poll sleep when a full batch was published (keep pulling the backlog).

Files: [`publisher.py`](../../backend/src/stockpilot/platform/outbox/publisher.py), [`claim.py`](../../backend/src/stockpilot/platform/outbox/claim.py), [`relay.py`](../../backend/src/stockpilot/bootstrap/relay.py).

Tests: `test_outbox_batch_publish.py` (one connection for N publishes), `test_relay_publishes_batch_of_five_in_one_cycle` (integration).

Deployed by rebuilding `ghcr.io/majid-haidarasl/stockpilot-backend:localprod` and `up -d --no-deps --force-recreate relay worker` on `-p stockpilot-prodlike`.

## Step 4 — Verify

### After-fix idle drain

`tests/load/results/outbox_drain_samples_after.json`

| t | Unpublished |
|---|---:|
| 0s | 4845 |
| 30s | 95 |
| 60s | **0** |

- **After rate:** ~**2422 events/min** (~32× before)
- Backlog reached **0** in **&lt; 1 min** (under 30 min requirement)

### Locust 6.4 shape re-run

| Check | Target | Result |
|---|---|---|
| Steady read p95 | &lt; 300 ms | **~42 ms** |
| Steady command p95 | &lt; 800 ms | **~58 ms** |
| Failures | 0% | **0%** (18844 req) |
| Outbox vs baseline within 10 min | back to baseline | **unpublished=0 at t=0 min** after run |
| `balance-check` | 0 mismatches | **0** |
| `failed_jobs` unreplayed | unchanged | **0 → 0** |

Reserved leftovers: `cleanup_reserved` cancelled **0** (none left).

### Checks

```text
backend-checks: 237 passed
Vitest:         85 passed
Playwright e2e: 8 passed
Gitleaks:       no leaks found
```

Backend image after fix: `sha256:6bd9cd4d56ad…`

## Commands used (PowerShell, one line at a time)

```powershell
# Before sample (15 min)
docker compose -p stockpilot-prodlike -f compose.yaml -f compose.prod.yaml -f compose.prodlike.yaml -f compose.loadtest.yaml --env-file env.prodlike run --rm --no-deps -v "${PWD}/tests/load/results:/results" -e STOCKPILOT_DRAIN_SAMPLES=15 -e STOCKPILOT_DRAIN_INTERVAL_SECONDS=60 -e STOCKPILOT_DRAIN_SAMPLE_FILE=/results/outbox_drain_samples.json --entrypoint python ops /results/outbox_drain_sample.py

# Deploy fix
docker build -t ghcr.io/majid-haidarasl/stockpilot-backend:localprod --target runtime ./backend
docker compose -p stockpilot-prodlike -f compose.yaml -f compose.prod.yaml -f compose.prodlike.yaml --env-file env.prodlike up -d --no-deps --force-recreate relay worker

# After sample + Locust (same load-test overlay as 6.4)
docker compose … run --rm --no-deps -e STOCKPILOT_LOAD_PASSWORD load-test --headless --csv=/results/locust --csv-full-history --html=/results/locust.html --only-summary
```

## Explicitly not done

- Outbox/Inbox purge or row deletes
- `compose.prod.yaml` changes / capacity scaling / full-scale load
- Changing `event_id` or inbox dedupe semantics
- Commit / push / `down -v`

---

## 6.5b — Batch publish delivery safety

Date: 2026-11-18  
Scope: Confirm-mode batch publish; mark only broker-confirmed, non-returned ids; mid-batch disconnect must not mark later rows. Prod-like only. No purge, no `down -v`, no `compose.prod.yaml` edits, no `event_id`/inbox weakening, no commit.

### When is an outbox row marked published?

In the batch path:

1. Relay claims rows and calls `publish_celery_tasks` on **one** channel opened with `transport_options={"confirm_publish": True}` (hard-required; open fails if not set).
2. For each message, `producer.publish(..., mandatory=True, correlation_id=task_id)` **blocks until the broker ack/nack** for that publish. A nack/connection error yields `PublishResult(ok=False)`.
3. After publish returns, a non-blocking return poll (plus a short end-of-batch drain) attributes any `basic.return` by `correlation_id` / task id → that result is flipped to `ok=False`.
4. Relay builds `ok_ids` **only** from `result.ok is True`, then `mark_published_many(conn, event_ids=ok_ids)`.

So a row is marked published **only after the broker confirmed that specific message** and **no** `basic.return` was observed for it. Returned, nacked, unconfirmed, or never-attempted rows stay unpublished (`attempt_count+1`, `last_error` set) for the next cycle.

If the connection drops mid-batch: already-confirmed results keep `ok=True`; the failing message and all later never-attempted messages get `ok=False` (`batch_aborted_after_connection_error`). Nothing after the last confirmed message can be marked published.

### Code / tests

- [`publisher.py`](../../backend/src/stockpilot/platform/outbox/publisher.py): `confirm_publish=True`; per-message confirm + return attribution; mid-batch abort.
- [`relay.py`](../../backend/src/stockpilot/bootstrap/relay.py): marks only `result.ok` ids.
- Unit: `test_returned_message_in_middle_of_batch_not_ok`, `test_connection_error_after_k_of_n_leaves_rest_unpublished`, `test_open_producer_requires_confirm_publish`, `test_relay_marks_only_ok_results`.
- Integration: `test_retried_message_keeps_event_id_inbox_dedupes` (same `event_id` republish → inbox dedupe no-op).

### Idle drain remasure (after confirm-safe path)

Seeded **3000** unpublished probe rows (`payload.probe=drain_6_5b`) with relay stopped, then restarted relay on image `sha256:0500a6dc7acc…`. Artifact: `tests/load/results/outbox_drain_samples_6_5b.json` (7 × 10s).

| Sample | Unpublished | with_last_error | attempt≥5 |
|---|---:|---:|---:|
| t=0s | 3000 | 0 | 0 |
| t=10s | 1650 | 0 | 0 |
| t=20s | 50 | 0 | 0 |
| t=30s | **0** | 0 | 0 |

- Active window (t0→t2): **~8850 events/min** (2950 in 20s) — still ≫ ~74/min and above the 6.5 ~2422/min sample.
- Backlog to **0** in **&lt; 30s**; all 3000 probe rows published; no `last_error` / high-attempt pile-up.

### Checks

```text
backend-checks: 242 passed
Vitest:         85 passed
Playwright e2e: 8 passed
Gitleaks:       no leaks found
```

Deploy: rebuild `ghcr.io/majid-haidarasl/stockpilot-backend:localprod`, `up -d --no-deps --force-recreate relay worker` on `-p stockpilot-prodlike`.
