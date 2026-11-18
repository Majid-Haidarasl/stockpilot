# Phase 6 Run 6.2 — Production deployment

Date: 2026-11-18  
Scope: T15 partial — reverse proxy + TLS (Caddy), secrets templates, GHCR release workflow, hardened `compose.prod.yaml`, Keycloak production hostname v2, deploy runbook, local prod-like proof. No Outbox/Inbox purge, no `down -v`, no GHCR push from the developer machine, no 6.3 backup / 6.4 load test.

## Result

**Pass.** Backend **217**, Vitest **85**, Playwright e2e **8**. Local prod-like (`-p stockpilot-prodlike`): login + image upload OK; `/metrics` and `/metrics/*` return **404** through edge; published ports only edge **80/443** (+ Grafana loopback **127.0.0.1:18300** in prodlike overlay; VPS overlay uses **127.0.0.1:8300**). Gitleaks (`zricethezav/gitleaks:v8.21.2 --no-git`) on the working tree: **no leaks found**.

## What landed

| Area | Paths |
|---|---|
| Edge / TLS | [infra/caddy/Caddyfile](../../infra/caddy/Caddyfile), [infra/caddy/Caddyfile.local](../../infra/caddy/Caddyfile.local), [infra/edge/Dockerfile](../../infra/edge/Dockerfile) |
| Prod compose | [compose.prod.yaml](../../compose.prod.yaml) (approved §2 + fixes) |
| Local prod-like | [compose.prodlike.yaml](../../compose.prodlike.yaml), [env.prodlike.example](../../env.prodlike.example) → copy to gitignored `env.prodlike`, [infra/prodlike/smoke.py](../../infra/prodlike/smoke.py) |
| Secrets / realm | [.env.prod.example](../../.env.prod.example), [infra/keycloak/realm/stockpilot-realm.prod.example.json](../../infra/keycloak/realm/stockpilot-realm.prod.example.json), [infra/keycloak/realm/stockpilot-realm.prodlike.example.json](../../infra/keycloak/realm/stockpilot-realm.prodlike.example.json) (filled `*.prodlike.json` / `env.prodlike` gitignored) |
| CI release | [.github/workflows/release.yml](../../.github/workflows/release.yml) (checks → build/push lowercase GHCR → scans) |
| Gitleaks | [.gitleaks.toml](../../.gitleaks.toml) allowlists known realm/env **examples** + vendor trees |
| Runbook | [docs/runbooks/deploy.md](../runbooks/deploy.md) |
| Guards | `test_caddy_prod_routing_guards.py`, `test_compose_prod_hardening.py`, `test_oidc_endpoint_rewrite.py` |
| Media | Backend image `chown`/`chmod` on `/var/lib/stockpilot/media`; runbook alpine one-off for **existing** volumes only |

## Locked production behaviours

- **Caddy** automatic HTTPS (ACME email via `ACME_EMAIL`); local uses `tls internal`.
- Public hosts (placeholders): `example.com` + `auth.example.com` (Keycloak subdomain avoids API `/auth` clash).
- Public host **`/metrics` and `/metrics/*` → explicit `respond 404`** (no SPA fallthrough). Never proxy `api:8001`. Never publish Prometheus, Alertmanager, RabbitMQ mgmt/metrics, Postgres, or Keycloak ports publicly.
- Grafana: `127.0.0.1:8300:3000` on VPS; tunnel `ssh -N -L 8300:127.0.0.1:8300 user@vps`.
- `STOCKPILOT_ENVIRONMENT=production` on api, relay, worker, scheduler, migrate, ops, ops-exporter.
- GHCR images: `ghcr.io/majid-haidarasl/stockpilot-backend:<sha>`, `…/stockpilot-edge:<sha>` (lowercase owner).
- Keycloak 26 hostname v2: `KC_HOSTNAME=https://…`, `KC_HOSTNAME_BACKCHANNEL_DYNAMIC=true`, `KC_PROXY_HEADERS=xforwarded`, `KC_HTTP_ENABLED=true`; clear `KC_HOSTNAME_PORT`; bootstrap admin via `KC_BOOTSTRAP_ADMIN_*`.
- OIDC backchannel: API metadata at `http://keycloak:8080/...`; `_rewrite_server_endpoints` rewrites token/JWKS to the internal host.

## Media volume ownership (fresh vs existing)

Probe (named volume `stockpilot_media_fresh_probe`, **not deleted**): first mount of `/var/lib/stockpilot/media` from `stockpilot-backend:localprod` showed `drwxrwxr-x … 1000 1000`, and `touch` as the image user succeeded.

**Conclusion:** the Dockerfile `chown`/`chmod` is enough for a **fresh** volume. The alpine `chown` helper in the runbook is for **existing** volumes that need repair. During the first prodlike bring-up, alpine was used after `compose run api chown` failed because the API service is `read_only` — that was not evidence that the new prodlike media volume was unwritable.

## Compose note (`!reset` vs `!override`)

`ports: !reset []` correctly clears published ports. A tagged `volumes: !reset` followed by a list was observed to wipe mounts without applying replacements — Keycloak realm import uses **`volumes: !override`**. Same for Grafana port override in `compose.prodlike.yaml`.

## Local prod-like evidence

Project: `stockpilot-prodlike` (never `down -v`). Images tagged locally `…:localprod` (not pushed).

```powershell
Copy-Item env.prodlike.example env.prodlike
Copy-Item infra\keycloak\realm\stockpilot-realm.prodlike.example.json infra\keycloak\realm\stockpilot-realm.prodlike.json
# Fill REPLACE_* in both files (keep OIDC client secret + user password aligned).

docker compose -p stockpilot-prodlike -f compose.yaml -f compose.prod.yaml -f compose.prodlike.yaml --env-file env.prodlike up -d --wait postgres rabbitmq
docker compose -p stockpilot-prodlike -f compose.yaml -f compose.prod.yaml -f compose.prodlike.yaml --env-file env.prodlike run --rm ops python -m stockpilot.bootstrap.ops ensure-db-roles
docker compose -p stockpilot-prodlike -f compose.yaml -f compose.prod.yaml -f compose.prodlike.yaml --env-file env.prodlike run --rm migrate
docker compose -p stockpilot-prodlike -f compose.yaml -f compose.prod.yaml -f compose.prodlike.yaml --env-file env.prodlike up -d --wait keycloak api relay worker scheduler edge
docker compose -p stockpilot-prodlike -f compose.yaml -f compose.prod.yaml -f compose.prodlike.yaml --env-file env.prodlike run --rm ops python -m stockpilot.bootstrap.ops bootstrap --environment production
docker compose -p stockpilot-prodlike -f compose.yaml -f compose.prod.yaml -f compose.prodlike.yaml --env-file env.prodlike run --rm --no-deps -e STOCKPILOT_SMOKE_BASE=https://stockpilot.local -e STOCKPILOT_SMOKE_AUTH_HOST=auth.stockpilot.local -v "${PWD}/infra/prodlike:/smoke:ro" --entrypoint python api /smoke/smoke.py
```

Smoke output (after `/metrics` 404 change):

```text
OK health/live
OK /metrics and /metrics/* return 404
OK login redirect to Keycloak
OK login + /api/v1/me
OK create product
OK image upload
```

## Gitleaks

```powershell
docker run --rm -v "${PWD}:/repo" -w /repo zricethezav/gitleaks:v8.21.2 detect --source . --no-git --config .gitleaks.toml
```

Result: `no leaks found` (exit 0). Allowlist covers documented examples and the long-lived e2e/dev realm fixture `infra/keycloak/realm/stockpilot-realm.json` (known test passwords/secrets, not production). Filled local prodlike files are gitignored and also listed in the allowlist so a dirty tree scan stays clean.

## Test counts

| Suite | Count |
|---|---|
| backend-checks | **217 passed** |
| Vitest | **85 passed** |
| Playwright e2e | **8 passed** |

## Commands used (quality gates)

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm backend-checks
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm frontend-checks
docker compose -f compose.yaml -f compose.e2e.yaml -p stockpilot-e2e --profile test build e2e-ensure-db migrate api relay worker
docker compose -f compose.yaml -f compose.e2e.yaml -p stockpilot-e2e --profile test run --rm e2e
```

## Carry-overs / not done

- Run **6.3** off-host backup + restore drill
- Run **6.4** load test
- Outbox/Inbox auto-purge (OPEN DECISION)
- Real alert notification channel (OPEN DECISION)
- prometheus-client **multiprocess** — still N/A (single uvicorn); documented in deploy runbook
- Did **not** push images to GHCR from this machine (`release.yml` only)
- Did **not** commit or push

## Deviations

1. Local Grafana host port **18300** in `compose.prodlike.yaml` to avoid clashing with compose.dev Grafana on 8300; production overlay remains `127.0.0.1:8300:3000`.
2. Keycloak realm mount uses `!override` (not `!reset` + list).
3. Prodlike env/realm are **templates only** in git; operators copy to gitignored filled files before smoke.
