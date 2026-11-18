# Deploy runbook (single VPS, Docker Compose)

Placeholders only in this guide (`example.com`, `auth.example.com`, `user@vps`). Never commit real secrets, domains, or IPs.

**Hard rules:** never `docker compose down -v`; never delete volumes; no Outbox/Inbox purge; never publish `8001`, `15692`, `5432`, `5672`, `15672`, `9090`, `9093`, or `9108`. Grafana is loopback-only (`127.0.0.1:8300`).

Require Docker Compose **≥ 2.24** (`!reset` support).

Images (lowercase GHCR owner):

- `ghcr.io/majid-haidarasl/stockpilot-backend:<git-sha>`
- `ghcr.io/majid-haidarasl/stockpilot-edge:<git-sha>`

Compose files: `compose.yaml` + `compose.prod.yaml` with `--env-file /etc/stockpilot/.env`.

---

## First-time server setup

1. Install Docker Engine + Compose plugin on the Linux VPS.
2. Create `/etc/stockpilot` (mode `700`). Copy `.env.prod.example` → `/etc/stockpilot/.env` and fill secrets (`chmod 600`).
3. Copy `infra/keycloak/realm/stockpilot-realm.prod.example.json` → path in `STOCKPILOT_KEYCLOAK_REALM_FILE` (e.g. `/etc/stockpilot/keycloak-realm.json`). Set client secret, redirect URIs, and `sslRequired` for your domain. Align `STOCKPILOT_OIDC_CLIENT_SECRET` with the realm client secret.
4. DNS: `A`/`AAAA` for `example.com` and `auth.example.com` → VPS.
5. Place compose files on the host (git clone or rsync of the release tree). Do **not** build images on the VPS; pull from GHCR.
6. `docker login ghcr.io` with a read token for private packages.
7. Set `STOCKPILOT_IMAGE_TAG=<full-git-sha>` and pull:

```bash
docker compose -f compose.yaml -f compose.prod.yaml --env-file /etc/stockpilot/.env pull
```

8. Start data plane, roles, migrate, then app:

```bash
docker compose -f compose.yaml -f compose.prod.yaml --env-file /etc/stockpilot/.env up -d --wait postgres rabbitmq
docker compose -f compose.yaml -f compose.prod.yaml --env-file /etc/stockpilot/.env run --rm ops python -m stockpilot.bootstrap.ops ensure-db-roles
docker compose -f compose.yaml -f compose.prod.yaml --env-file /etc/stockpilot/.env run --rm migrate
docker compose -f compose.yaml -f compose.prod.yaml --env-file /etc/stockpilot/.env up -d --wait keycloak api relay worker scheduler edge
```

9. **Media volume ownership (uid 1000):** Fresh volumes inherit ownership from the backend image (`/var/lib/stockpilot/media` owned by `app` uid 1000). The API runs `read_only` + `user: 1000:1000`, so do **not** use `compose run api chown` (rootfs is read-only). If uploads fail on an **existing** volume, chown via a one-off helper:

```bash
docker run --rm -u 0 -v <project>_stockpilot_media:/media alpine:3.20 chown -R 1000:1000 /media
```

Replace `<project>` with the Compose project name (default directory name, or `-p` value).

10. Bootstrap memberships (idempotent; not `seed-demo`):

```bash
docker compose -f compose.yaml -f compose.prod.yaml --env-file /etc/stockpilot/.env run --rm ops python -m stockpilot.bootstrap.ops bootstrap --environment production
```

Link real Keycloak users as documented for your environment (subjects/emails must match IdP users you create in Keycloak admin).

11. Smoke: open `https://example.com/health/live`, login via `/auth/login`, confirm session. Confirm `https://example.com/metrics` returns **404**.

12. Optional observability (private):

```bash
docker compose -f compose.yaml -f compose.prod.yaml --env-file /etc/stockpilot/.env --profile observability up -d
```

---

## Grafana access (SSH tunnel)

Grafana publishes **only** on the VPS loopback: `127.0.0.1:8300:3000`.

From your laptop:

```bash
ssh -N -L 8300:127.0.0.1:8300 user@vps
```

Browse `http://127.0.0.1:8300`. Do not publish Grafana on `0.0.0.0`.

---

## Normal release

1. **Backup first.** Until Run 6.3 automates off-host backup, take a manual `pg_dump` of `stockpilot` and `keycloak` and copy it off-box. Record that you did so before migrating.
2. Note current and target `STOCKPILOT_IMAGE_TAG` (git SHA) and digests from the release workflow.
3. Update `/etc/stockpilot/.env` with the new SHA; `docker compose … pull`.
4. Drain processors: stop `relay`, `worker`, `scheduler`; allow in-flight work a short finish window. If the migration is incompatible with the running API, stop `api` too (maintenance window).
5. `run --rm migrate`. If migrate fails, **do not** start the new app containers (see below).
6. Start `api`, `relay`, `worker`, `scheduler`, `edge` on the new SHA; check health, login, a short commercial path (including an image upload if catalog images matter for the release).
7. Watch errors, latency, Outbox lag, and scheduler (Grafana tunnel). Record the result.

Migrations are **forward-only** (Expand/Contract). Rollback means the previous image plus a **compatible** schema — not a migrate-down.

---

## Rollback to previous SHA

1. Confirm schema and in-flight messages are compatible with the previous image (Expand/Contract). If a destructive migration already ran, fix-forward or use a planned restore (6.3) — do not casually restore over newer data.
2. Set `STOCKPILOT_IMAGE_TAG` to the previous SHA; `pull`; restart app services (`api`, `relay`, `worker`, `scheduler`, `edge`). Do **not** run migrate-down.
3. Never `down -v`. Never delete volumes.

---

## Migration failure

1. Leave the previous app version running if it is still up.
2. Do not start containers on the new SHA.
3. Capture `migrate` logs; fix forward with a new migration/release.
4. Database restore only as a planned drill (Run 6.3), not as the default reaction.

---

## Metrics multiprocess checklist (from Run 6.1)

API metrics use in-process `prometheus-client` on internal `:8001` with a **single** uvicorn worker. If the API ever runs multiple workers, switch to prometheus-client **multiprocess** mode (`PROMETHEUS_MULTIPROC_DIR`) before trusting scraped HTTP metrics. Do not reverse-proxy `/metrics`.

---

## Local prod-like (developer host)

Windows PowerShell, project `-p stockpilot-prodlike`, Caddy `tls internal` via `compose.prodlike.yaml`.

1. Copy templates (filled files are gitignored):

```powershell
Copy-Item env.prodlike.example env.prodlike
Copy-Item infra\keycloak\realm\stockpilot-realm.prodlike.example.json infra\keycloak\realm\stockpilot-realm.prodlike.json
```

2. Replace every `REPLACE_*` / `REPLACE_ME` in both files with local dummy values (keep client secret and user password aligned).
3. Map `stockpilot.local` and `auth.stockpilot.local` to `127.0.0.1` if you browse from the host.
4. See `docs/reports/phase6-run6_2.md` for compose/smoke commands. Never `down -v`.

Confirm `https://…/metrics` returns **404** (not the SPA).
