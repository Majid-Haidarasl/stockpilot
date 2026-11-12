# T12 week-5 report — Persian UI main path + Playwright e2e

**Date:** 2026-11-12  
**Repo:** `D:\Me\Last Term\WEB\stockpilot`  
**Host:** Windows 11, Docker Desktop (WSL2), PowerShell  
**Commit/push:** not done by the agent (developer-owned)

---

## Verdict

T12 local exit criteria are **met**. Week-5 browser path (sales + warehouse), cancel/expire, two-org isolation, org-switch, and viewer inventory denial are covered by Playwright in an isolated Compose project.

| Criterion | Result |
|---|---|
| Order list / draft / detail (actions, frozen lines, countdown, timeline) | Pass |
| Dashboard (Tehran range) + admin members + empty notifications | Pass (runs 2–3) |
| Viewer inventory write denial (UI) | Pass (e2e + Vitest) |
| Playwright: draft → reserve → confirm → ship | Pass |
| Playwright: cancel reserved + confirmed (stock release) | Pass |
| Playwright: expire via backdate + confirm → `RESERVATION_EXPIRED` | Pass |
| Playwright: two-org isolation (UI + API 404) | Pass |
| Playwright: dual-org switch (no cross-org data) | Pass |
| E2E isolation: `-p stockpilot-e2e`, no host ports, no `compose.dev.yaml` | Pass |
| `seed-e2e` / `e2e-backdate-reservation` refuse non-dev/test | Pass (unit guards) |
| Keycloak extra redirect/webOrigins only in dev/test realm file | Pass |
| Traces/screenshots on failure under `tests/e2e/test-results/` (gitignored) | Pass |
| `backend-checks` | Pass (**81** tests) |
| `frontend-checks` | Pass (**24** Vitest) |
| Playwright e2e | Pass (**7** tests) |

---

## What was delivered (run 4)

- `compose.e2e.yaml`: isolated project, `stockpilot_test`, `e2e-ensure-db` / `e2e-seed` / `e2e`, in-network **`edge-e2e`** Caddy (single origin for session cookies); no published host ports
- Ops: idempotent `seed-e2e` (aftab/baran product+customer+stock; sales dual membership), `e2e-backdate-reservation`, `_assert_dev_or_test` + unit tests
- Playwright 1.50.1 specs under `tests/e2e/` (main, cancel×2, expire, isolation+API 404, org-switch, viewer)
- Realm: `http://edge-e2e` redirect/webOrigin only in `infra/keycloak/realm/stockpilot-realm.json` (dev/test realm; no production realm file)
- Fix: org-picker cache clear no longer cancels/`clear()`s `me` (tenant-scoped only) — unblocks org list after login

**Explicitly not done:** Relay/Worker/Inbox (T13), Locust, production hardening, GHCR release.

---

## Verification (PowerShell)

```powershell
Set-Location "D:\Me\Last Term\WEB\stockpilot"
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm backend-checks
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm frontend-checks
docker compose -p stockpilot-e2e -f compose.yaml -f compose.e2e.yaml --profile test build
docker compose -p stockpilot-e2e -f compose.yaml -f compose.e2e.yaml --profile test run --rm e2e
```

Observed: backend-checks **81 passed**; frontend-checks **24** Vitest passed; e2e **7 passed** (~44s).

---

## Suggested commit message

```
Complete T12: Persian order UI path and isolated Playwright e2e
```
