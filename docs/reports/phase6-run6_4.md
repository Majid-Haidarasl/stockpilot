# Phase 6 Run 6.4 — Initial Locust load test (T15)

Date: 2026-11-18  
Scope: T15 initial Locust load test on local prod-like (`-p stockpilot-prodlike`) with observability. Documented down-scale of AGENTS §27.4. No `down -v`, no volume deletion, no Outbox/Inbox purge, no `compose.prod.yaml` edits, no commit.

## Result

**Pass (steady window vs design goals).** Backend **233**, Vitest **85**, Playwright e2e **8**. Gitleaks (`zricethezav/gitleaks:v8.21.2 --no-git`): **no leaks found**.

Steady-state Locust (2–18 min): read p95 **~39 ms**, command p95 **~54 ms**, failure ratio **0%**. Prometheus HTTP histogram p95 over ~16m: **~36 ms**. Stock `balance-check`: **0 mismatches**. `failed_jobs` unreplayed stayed at baseline **0**. Reserved leftovers cancelled via normal API (`cleanup_reserved.py`).

## Images / hardware / data / scenario

| Field | Value |
|---|---|
| Backend image | `ghcr.io/majid-haidarasl/stockpilot-backend:localprod` (`sha256:f7b2c37879b8…`) |
| Edge image | `ghcr.io/majid-haidarasl/stockpilot-edge:localprod` (`sha256:d53a72a8bda4…`) |
| Hardware | Windows 11 + Docker Desktop; 12th Gen Intel i5-12400F (**12** logical CPUs); **15.8 GiB** RAM; SSD. Locust **on the same Docker network** (not a separate host) |
| Dataset (down-scale) | **10** tenants `load-01`…`load-10`; **1 000** products; **2 000** seed DRAFT orders (~10k lines) + Locust-created orders during the run. Not the §27.4 10k/100k/500k reference volume |
| Scenario | `StockPilotLoadShape`: warm-up 0–2m → steady 15 VUs 2–18m → spike 30 VUs 18–20m; ~70% reads / ~30% commands; base `https://stockpilot.local` |
| Auth | OIDC form login → session + CSRF cookies (no password grant). Keycloak users created via Admin API (`infra/prodlike/ensure_load_users.py`), passwords only in gitignored `env.prodlike` |

**Design goals (unchanged):** p95 reads &lt;300 ms; p95 order commands &lt;800 ms; infrastructural 5xx &lt;1%; zero stock-rule violations.

## What landed

| Area | Paths |
|---|---|
| Locust harness | [`tests/load/`](../../tests/load/) (`locustfile.py`, `auth.py`, `cleanup_reserved.py`, `analyze_phases.py`, Dockerfile, pinned `locust==2.32.4`) |
| Compose (prod-like only) | [`compose.loadtest.yaml`](../../compose.loadtest.yaml) — **not** in base `compose.yaml`; no host ports; results → `tests/load/results/` |
| Seed | [`seed_load.py`](../../backend/src/stockpilot/bootstrap/seed_load.py) + `ops seed-load`; requires `STOCKPILOT_ENVIRONMENT=production` **and** `STOCKPILOT_ALLOW_LOAD_SEED=true` |
| Keycloak users | [`infra/prodlike/ensure_load_users.py`](../../infra/prodlike/ensure_load_users.py) (Admin API; no realm re-import) |
| Env template | [`env.prodlike.example`](../../env.prodlike.example) — `STOCKPILOT_ALLOW_LOAD_SEED`, `STOCKPILOT_LOAD_PASSWORD=REPLACE_…`, practice RESTIC placeholders for compose interpolation |
| Tests | `test_ops_seed_load_guards.py`, `test_seed_load_idempotent.py` |
| Evidence | [`docs/evidence/initial-load-report.md`](../evidence/initial-load-report.md) |

## Commands (PowerShell, one line at a time)

```powershell
# Users (Admin API) + seed-load (flag required)
docker compose -p stockpilot-prodlike -f compose.yaml -f compose.prod.yaml -f compose.prodlike.yaml -f compose.loadtest.yaml --env-file env.prodlike run --rm --no-deps -e KEYCLOAK_ADMIN -e KEYCLOAK_ADMIN_PASSWORD -e STOCKPILOT_LOAD_PASSWORD -v "${PWD}/infra/prodlike:/scripts:ro" -v "${PWD}/tests/load/results:/results" -e STOCKPILOT_LOAD_SUBJECTS_FILE=/results/load-subjects.json --entrypoint python api /scripts/ensure_load_users.py
docker compose -p stockpilot-prodlike -f compose.yaml -f compose.prod.yaml -f compose.prodlike.yaml -f compose.loadtest.yaml --env-file env.prodlike run --rm -e STOCKPILOT_ALLOW_LOAD_SEED=true -e STOCKPILOT_LOAD_SUBJECTS_FILE=/results/load-subjects.json -v "${PWD}/tests/load/results:/results:ro" ops python -m stockpilot.bootstrap.ops seed-load --environment production

# Locust (shape owns users/duration)
docker compose -p stockpilot-prodlike -f compose.yaml -f compose.prod.yaml -f compose.prodlike.yaml -f compose.loadtest.yaml --env-file env.prodlike --profile test build load-test
docker compose -p stockpilot-prodlike -f compose.yaml -f compose.prod.yaml -f compose.prodlike.yaml -f compose.loadtest.yaml --env-file env.prodlike run --rm --no-deps -e STOCKPILOT_LOAD_PASSWORD load-test --headless --csv=/results/locust --csv-full-history --html=/results/locust.html --only-summary

# Cleanup reserved via API + phase split
docker compose … run --rm --no-deps -e STOCKPILOT_LOAD_PASSWORD --entrypoint python load-test cleanup_reserved.py
docker compose … run --rm --no-deps --entrypoint python load-test analyze_phases.py
```

## Baseline → post-run

| Check | Baseline (before official run) | After run |
|---|---|---|
| `failed_jobs` unreplayed | **0** (historic “13 Unknown tenant_id” rows **not** on this prod-like volume) | **0** (unchanged) |
| Outbox unpublished | **2404** (still draining rehearsal backlog) | **7718** immediately after run (load-generated); **relay+worker actively draining** (no purge). Later snapshot **7623** and falling |
| `balance-check` | 1000 positions, **0** mismatches | **0** mismatches |
| Load `RESERVED` orders | 0 | 0 after `cleanup_reserved` (2 cancelled via API) |

## Pass/fail table (steady window only)

| Metric | Target | Measured (steady 2–18m) | Verdict |
|---|---|---|---|
| Read p95 | &lt; 300 ms | **~39 ms** (Locust); Prom HTTP p95 ~**36 ms** | Met |
| Order-command p95 | &lt; 800 ms | **~54 ms** | Met |
| Failure / 5xx ratio | &lt; 1% infrastructural | **0.0%** Locust failures; no `StockpilotHttp5xxHigh` expected | Met |
| Stock invariants | zero mismatches | **0** | Met |

Warm-up / spike (informational, not pass/fail):

| Phase | Approx Aggregated p95 | Fail ratio |
|---|---|---|
| Warm-up (0–2m) | ~42 ms | 0 |
| Spike (18–20m, 30 VUs) | ~160 ms | 0 |

Full-run Locust summary: **18 920** requests, **0** failures, ~**15.7** req/s average (above the ~10 req/s reference; still under targets).

## Grafana / alerts (http://127.0.0.1:18300)

Watched: HTTP RPS + p95, 5xx ratio, outbox age/count, celery ready, failed_jobs, heartbeats.

| Alert | Expected? | Observed |
|---|---|---|
| `StockpilotHttp5xxHigh` | No | Not indicated by Locust (0 failures) |
| `StockpilotOutboxLagHigh` | Possible while backlog drains | Lag age elevated during/after run while relay catches up — **expected under this drain**, not a load failure |
| `StockpilotQueueDepthHigh` | No | Celery ready ~0 when sampled |
| `StockpilotFailedJobsGrowing` | No | Unreplayed stayed 0 |
| Heartbeat stale | No | Relay/worker/scheduler heartbeats advancing |
| `StockpilotBackupStale` | Ignore | Backup profile not part of this run |

## Checks re-run after code changes

```text
backend-checks: 233 passed
Vitest:         85 passed
Playwright e2e: 8 passed
Gitleaks:       no leaks found
```

## Notes / deviations

1. **Down-scale** of §27.4 dataset and co-located Locust (not separate load host) — called out explicitly; targets unchanged.
2. First rehearsal run mis-called `GET /dashboard` without required `from`/`to` (422s). Fixed before the official run; rehearsal artifacts under `tests/load/results/run1_dashboard422/`.
3. Prod-like postgres container was recreated once during ops bring-up (volumes kept). `0015_backup_heartbeat` was applied after `ensure-db-roles`; aftab/baran + load tenants retained.
4. Outbox drain is slower than publish bursts under this load volume; **no purge** — relay continues to publish and worker consumes. Post-run “drained” means *draining with healthy processors*, not an immediate zero at T+0.
5. `STOCKPILOT_ALLOW_LOAD_SEED` is set only in local `env.prodlike` / example; real production must omit it.

## Explicitly not done

- Claiming §27.4 full reference dataset or separate-host topology.
- Caches / extra Uvicorn workers.
- Commit / push.
- `compose.prod.yaml` changes.
- `docker compose down -v` or volume deletes (`stockpilot_media_fresh_probe`, `stockpilot-restore_*` kept).
