# Backup and restore runbook

Encrypted logical backup of PostgreSQL (`stockpilot` + `keycloak`) and the `stockpilot_media` volume via **restic**. `rabbitmq_data` is **not** backed up (fresh broker + controlled Outbox replay on restore).

**Hard rules:** never `docker compose down -v`; never delete volumes; never restore onto the live project; never put real restic passwords, bucket names, or hosts in git.

---

## What is backed up

| Asset | Method |
|-------|--------|
| Roles (reference) | `pg_dumpall --globals-only --no-role-passwords` (kept in snapshot; **not** replayed on restore by default) |
| `stockpilot` DB | `pg_dump -Fc` as `stockpilot_backup` |
| `keycloak` DB | `pg_dump -Fc` as `stockpilot_backup` |
| Media | `stockpilot_media` volume (`/var/lib/stockpilot/media`) in the same restic snapshot |

Dump role: `stockpilot_backup` — `LOGIN`, `NOSUPERUSER`, `BYPASSRLS`, member of `pg_read_all_data`. Heartbeat via `platform.record_backup_heartbeat` only (migration `0015`).

---

## Setup

1. Create role (existing volumes):  
   `docker compose … run --rm ops python -m stockpilot.bootstrap.ops ensure-db-roles`
2. Set `STOCKPILOT_BACKUP_PASSWORD`, `RESTIC_REPOSITORY`, `RESTIC_PASSWORD` in host env (see `.env.prod.example`, `infra/backup/restic.env.example`).
3. **Restic password custody:** store a copy **off the app server** and **outside** the restic repository that it unlocks. Named ops owner holds the copy.
4. Production destination placeholders: S3-compatible (`s3:https://s3.example.com/REPLACE_BUCKET`) or SFTP (`sftp:backup@backup-host.example:/restic`).
5. Local practice: `RESTIC_REPOSITORY=/var/lib/stockpilot/restic-practice` on volume `restic_practice` — **PRACTICE ONLY**, not a host-loss test.

Enable profile:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --profile backup build backup
```

---

## Manual backup

Pause Keycloak / membership **admin** changes during the two DB dumps. Ordinary orders may continue.

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --profile backup run --rm backup
```

Success requires a restic snapshot **and** a `platform.heartbeats` row `service_name=backup` (ops-exporter / Grafana). Dump-only without restic must not heartbeat.

Retention each run: `restic forget --keep-daily 14 --keep-monthly 3`.  
`restic prune` + `restic check` every `STOCKPILOT_BACKUP_CHECK_EVERY_N` runs (default 14 ≈ weekly at 12h).

Unencrypted scratch under `backup_scratch` is deleted on success **and** failure (trap).

---

## Scheduled backup (VPS)

```bash
docker compose -f compose.yaml -f compose.prod.yaml --env-file /etc/stockpilot/.env --profile backup up -d backup-scheduler
```

Interval: `STOCKPILOT_BACKUP_INTERVAL_SECONDS` (default `43200` = 12h). Compose loop — no host cron, no Docker socket.

---

## Alert

`StockpilotBackupStale`: no backup heartbeat or age **> 14 hours** (`for: 15m`). Investigate logs; do not treat a local dump without restic transfer as success.

---

## Restore drill (`-p stockpilot-restore`)

Uses **new** volumes only. Shares practice restic repo via external volume `stockpilot_restic_practice`.

### One-shot script (preferred)

```powershell
Copy-Item env.restore.example env.restore   # once; align RESTIC_PASSWORD with the source backup
.\infra\backup\restore-drill.ps1
# optional: .\infra\backup\restore-drill.ps1 -Snapshot <id>
# optional: .\infra\backup\restore-drill.ps1 -SkipRepublish
```

The script uses **only** `docker compose -p stockpilot-restore` (compose.yaml + compose.restore.yaml + env.restore). It:

1. `up -d --wait postgres`
2. `ops ensure-db-roles`
3. `--profile backup` build + `run --rm restore` (latest restic snapshot by default)
4. `run --rm migrate`
5. `up -d --wait rabbitmq keycloak api relay worker scheduler`
6. Verifies: alembic head, DEFINER owners, FORCE RLS, product count, one media file, backup EXECUTE grant, RLS smoke (`stockpilot_app` + fake tenant → 0 rows), `/health/live`, `/auth/login` → 302 to Keycloak
7. Counts published-without-Inbox rows and, unless `-SkipRepublish`, clears `published_at` for those rows inside this project only (no purge, no general replay tool)
8. Prints per-step seconds and approximate RTO (restore + migrate + app plane)

Stop when finished (keep volumes):

```powershell
docker compose -p stockpilot-restore stop
```

**Never** `down -v`. **Never** delete volumes.

### Behaviour notes

- **Do not** replay `globals.sql` by default (roles already from init + `ensure-db-roles`). The restore container verifies expected role names from the snapshot file only.
- `pg_restore` without `--no-owner` / `--no-privileges` (restore container uses Postgres superuser **only** for restore).
- Fresh `rabbitmq_data`. Unpublished Outbox drains via Relay.

Companion secrets not in restic: `/etc/stockpilot/.env`, Keycloak realm file, Fernet key, restic password copy.

---

## If backup fails

1. Check `backup` / `backup-scheduler` logs.
2. Confirm Postgres reachable as `stockpilot_backup`, restic repo credentials, disk space.
3. Confirm no leftover unencrypted dumps in `backup_scratch` (script traps cleanup).
4. Do not proceed with a release until a successful backup heartbeat exists (see deploy runbook).
5. Never delete volumes to “make space” as the first fix.

---

## Consistency window

Order: globals → `stockpilot` dump → `keycloak` dump → restic (dumps + media).  
Uploads during the window may leave **orphan** media files (safe). Broken image URLs (DB row without file) are minimized by dumping DB before media.
