# Phase 6 Run 6.3 — Off-host encrypted backup + restore drill

Date: 2026-11-18  
Scope: T15 backup/restore — `stockpilot_backup` role, migration `0015_backup_heartbeat`, restic backup image, compose profile `backup`, practice restic volume, freshness alert (14h), restore drill under `-p stockpilot-restore`. No Outbox/Inbox purge, no `down -v`, no real off-host bucket, no load test (6.4), no commit.

## Result

**Pass.** Backend **227**, Vitest **85**, Playwright e2e **8**. Practice restic snapshot **`edd2b3ab`**. Repeatable drill via `infra/backup/restore-drill.ps1` (compose-only, `-p stockpilot-restore`). Latest scripted RTO (restore + migrate + app plane) **8.7s** on warm restore volumes; first scripted cold-ish run was **~24s**.

## rabbitmq_data

**Confirmed: not backed up.** Restore uses a fresh broker. Unpublished Outbox drains via Relay. Inbox dedupes. One published-without-Inbox row was counted on restore and cleared with a **restore-project-only** `UPDATE … SET published_at = NULL` (no general replay tool, no purge).

## What landed

| Area | Paths |
|------|--------|
| Role | `stockpilot_backup` (`LOGIN`, `NOSUPERUSER`, `BYPASSRLS`, `INHERIT`, `pg_read_all_data WITH INHERIT TRUE`, CONNECT on stockpilot/test/keycloak/postgres) via init + `ensure-db-roles` |
| Migration | `0015_backup_heartbeat` — `platform.record_backup_heartbeat(jsonb)` SECURITY DEFINER, EXECUTE only for backup (+ migrator) |
| Backup image | `infra/backup/` Dockerfile (postgres:17 + restic 0.17.3), `backup.sh` / `restore.sh` / `scheduler.sh` |
| Restore drill | `infra/backup/restore-drill.ps1` + runbook section — **only** `docker compose -p stockpilot-restore` |
| Compose | profile `backup` on `backup`, `backup-scheduler`, `restore`; volumes `backup_scratch`, `restic_practice` (PRACTICE ONLY); `compose.restore.yaml`; `compose.prod.yaml` approved overlay |
| Observability | `KNOWN_SERVICES` includes `backup`; `StockpilotBackupStale` (>50400s / 14h); Grafana heartbeat panel title updated |
| Docs | `docs/runbooks/backup-restore.md`; deploy.md backup-first points here |
| CI | `release.yml` builds/pushes `stockpilot-backup` + Trivy |
| Env | `.env.example` / `.env.prod.example` / `env.restore.example`; `env.restore` gitignored |

## Dump privilege proof

`pg_dumpall --globals-only --no-role-passwords` and `pg_dump -Fc` for `stockpilot` and `keycloak` succeed as **`stockpilot_backup` without superuser** after `GRANT pg_read_all_data … WITH INHERIT TRUE`. Restore uses Postgres superuser **only** for `pg_restore` (preserve owners/privileges; no `--no-owner` / `--no-privileges`).

## Practice backup

- Repository: volume `stockpilot_restic_practice` (`RESTIC_REPOSITORY=/var/lib/stockpilot/restic-practice`) — **not** a host-loss test.
- Snapshot id: **`edd2b3ab`**
- Heartbeat recorded via `platform.record_backup_heartbeat`
- Scratch staging deleted after success (trap on failure too)
- `forget --keep-daily 14 --keep-monthly 3` each run; prune/check every 14 runs

## Restore drill (`-p stockpilot-restore`)

Command:

```powershell
.\infra\backup\restore-drill.ps1
```

| Step | Result |
|------|--------|
| New volumes only | `stockpilot-restore_postgres_data`, `_stockpilot_media`, `_rabbitmq_data`, `_backup_scratch` |
| External restic | `stockpilot_restic_practice` |
| globals.sql | Verified role names present; **not** replayed |
| `pg_restore` | Owners kept (`record_backup_heartbeat` / DEFINER fns → `stockpilot_migrator`) |
| migrate | No-op at `0015_backup_heartbeat` |
| Fresh rabbitmq | New volume; processors healthy |
| Product count | **123** |
| Image | `IMAGE_OK` for sampled `storage_key` |
| FORCE RLS | Enabled on tenant tables (products, orders, …) |
| RLS smoke | `stockpilot_app` + fake `app.tenant_id` → **0** visible products |
| Login path | `/auth/login` → **302** to Keycloak OIDC authorize URL |
| API health | `/health/live` → `{"status":"ok"}` |
| Published-without-Inbox | Count **1** → controlled republish in restore only → **0** |

### Timing (scripted re-run)

| Phase | Seconds |
|-------|---------|
| postgres up | **0.8** |
| ensure-db-roles | **1.8** |
| restic restore + pg_restore + media | **4.7** |
| migrate | **1.9** |
| app plane up --wait | **2.1** (already healthy from prior drill) |
| **RTO (restore + migrate + app)** | **8.7** |

Earlier same-day scripted run (app plane from stopped/starting): restore **5.2s**, migrate **1.8s**, app **17s**, RTO **~24s**. Design goals remain RPO ≤ 24h / RTO ≤ 2h (OPEN DECISION until production-like host).

### Script output (paste)

Docker build layer noise omitted; compose-only path, no ad-hoc `docker run`.

```text
StockPilot restore drill (project=stockpilot-restore)
Repo: D:\Me\Last Term\WEB\stockpilot

=== postgres up --wait ===
 Container stockpilot-restore-postgres-1 Running
 Container stockpilot-restore-postgres-1 Waiting
 Container stockpilot-restore-postgres-1 Healthy
=== postgres up --wait done in 0.8s ===

=== ensure-db-roles ===
ensure-db-roles: stockpilot_relay ready
ensure-db-roles: stockpilot_metrics ready
ensure-db-roles: stockpilot_backup ready
=== ensure-db-roles done in 1.8s ===

=== restic restore + pg_restore + media ===
 Image stockpilot-restore-restore Built
restore start snapshot=latest as PGUSER=postgres
restoring snapshot edd2b3ab of [/var/lib/stockpilot/backup-scratch/20261118T002140Z-1 /var/lib/stockpilot/media] at 2026-11-18 00:21:43.581071919 +0000 UTC by @82f0890e704a to /var/lib/stockpilot/backup-scratch/restore-1
Summary: Restored 93 files/dirs (1.220 MiB) in 0:00
verifying expected roles from globals.sql (reference only; not replaying)
  globals lists role: stockpilot_migrator
  globals lists role: stockpilot_app
  globals lists role: stockpilot_relay
  globals lists role: stockpilot_metrics
  globals lists role: stockpilot_backup
  globals lists role: keycloak
pg_restore stockpilot (keep owners and privileges)
pg_restore keycloak (keep owners and privileges)
restoring media into /var/lib/stockpilot/media
scratch cleaned: /var/lib/stockpilot/backup-scratch/restore-1
restore complete
=== restic restore + pg_restore + media done in 4.7s ===

=== migrate ===
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
=== migrate done in 1.9s ===

=== app plane up --wait ===
 Container stockpilot-restore-api-1 Healthy
 Container stockpilot-restore-keycloak-1 Healthy
 Container stockpilot-restore-relay-1 Healthy
 Container stockpilot-restore-rabbitmq-1 Healthy
 Container stockpilot-restore-postgres-1 Healthy
 Container stockpilot-restore-worker-1 Healthy
 Container stockpilot-restore-scheduler-1 Healthy
=== app plane up --wait done in 2.1s ===

=== verifications ===
-- alembic + function owners --
      version_num
-----------------------
 0015_backup_heartbeat
(1 row)

         proname         |        owner
-------------------------+---------------------
 failed_jobs_metrics     | stockpilot_migrator
 outbox_lag              | stockpilot_migrator
 record_backup_heartbeat | stockpilot_migrator
(3 rows)

-- FORCE RLS on tenant tables --
    relname     | relforcerowsecurity
----------------+---------------------
 customers      | t
 memberships    | t
 order_lines    | t
 orders         | t
 product_images | t
 products       | t
 tenants        | t
(7 rows)

-- product count --
product_count=123
-- sample image file --
storage_key=6bf37346-04bb-460d-833e-3c50714586c0/e2e4b264affabb04f4ab19c42ba09fed899b104152235d9717bdefc831bf4066.webp -> IMAGE_OK
-- grants (backup EXECUTE + heartbeats) --
 backup_exec
-------------
 t
(1 row)

       grantee       | privilege_type
---------------------+----------------
 stockpilot_app      | INSERT
 stockpilot_app      | SELECT
 stockpilot_app      | UPDATE
 stockpilot_metrics  | SELECT
 stockpilot_migrator | DELETE
 stockpilot_migrator | INSERT
 stockpilot_migrator | REFERENCES
 stockpilot_migrator | SELECT
 stockpilot_migrator | TRIGGER
 stockpilot_migrator | TRUNCATE
 stockpilot_migrator | UPDATE
 stockpilot_relay    | INSERT
 stockpilot_relay    | SELECT
 stockpilot_relay    | UPDATE
(14 rows)

-- RLS smoke (stockpilot_app + fake tenant) --
visible_products_fake_tenant=0
-- API health + /auth/login 302 --
{"status":"ok"}
auth/login status=302 location=http://keycloak:8080/realms/stockpilot/protocol/openid-connect/auth?client_id=stockpilot-api&response_type=code&scope=openid+profile+email&redirect_uri=http%3A%2F%2Flocalhost%3A8200%2Fauth%2Fcallback&state=…&nonce=…&code_challenge=…&code_challenge_method=S256
-- published-without-Inbox count --
published_without_inbox_before=1
-- controlled republish (restore project only; clear published_at) --
UPDATE 1
published_without_inbox_after=0

======== RESTORE DRILL SUMMARY ========
restic_snapshot_id=edd2b3ab
postgres_up_s=0.8
ensure_db_roles_s=1.8
restore_s=4.7
migrate_s=1.9
app_plane_s=2.1
rto_post_postgres_s=8.7
product_count=123
image=IMAGE_OK
rls_visible_fake_tenant=0
auth_login_status=302
published_without_inbox_before=1
published_without_inbox_after=0
Teardown when done: docker compose -p stockpilot-restore stop   # NEVER down -v
======== PASS ========
```

(OIDC `state` / `nonce` / `code_challenge` redacted in the paste above with `…`; live run printed full values.)

After the drill: `docker compose -p stockpilot-restore stop` (volumes kept).

## Test counts

| Suite | Count |
|-------|--------|
| backend-checks | **227 passed** (4 warnings) |
| Vitest | **85 passed** (35 files) |
| Playwright e2e | **8 passed** |

## Gitleaks

```powershell
docker run --rm -v "${PWD}:/repo" -w /repo zricethezav/gitleaks:v8.21.2 detect --source . --no-git --config .gitleaks.toml
```

Result: **no leaks found** (exit 0, ~55s).

## Commands used (PowerShell)

```powershell
$env:Path = "C:\Users\majid\AppData\Local\Programs\DockerDesktop\resources\bin;" + $env:Path
cd "d:\Me\Last Term\WEB\stockpilot"
docker compose -f compose.yaml -f compose.dev.yaml run --rm ops python -m stockpilot.bootstrap.ops ensure-db-roles
docker compose -f compose.yaml -f compose.dev.yaml run --rm migrate
docker compose -f compose.yaml -f compose.dev.yaml --profile backup build backup
docker compose -f compose.yaml -f compose.dev.yaml --profile backup run --rm backup
Copy-Item env.restore.example env.restore
.\infra\backup\restore-drill.ps1
docker compose -p stockpilot-restore stop
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm backend-checks
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm frontend-checks
docker compose -f compose.yaml -f compose.e2e.yaml -p stockpilot-e2e --profile test run --rm e2e
```

Never used `down -v` or volume deletion on existing stockpilot / stockpilot-prodlike / stockpilot-restore volumes.

## Deviations / notes

1. Backup role must use **`INHERIT` + `GRANT … WITH INHERIT TRUE`** or `pg_dump` fails with schema permission denied despite `pg_read_all_data`.
2. Postgres image already has a user named `backup`; image runs as numeric `1000:1000`.
3. `RESTIC_CACHE_DIR` under scratch avoids `/.cache` permission warnings.
4. Practice restic volume is same-host only (AGENTS §22).
5. Compose may warn that `stockpilot-restore_backup_scratch` already exists; drill does not recreate or delete it.

## Explicitly not done

- Real VPS / real S3 or SFTP off-host destination
- Run 6.4 load test
- Outbox/Inbox auto-purge (OPEN DECISION)
- Dedicated `stockpilot_backup` table DML (intentionally denied; DEFINER heartbeat only)
- Commit
