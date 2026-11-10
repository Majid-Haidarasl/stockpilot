# Ready-to-paste Cursor prompts (StockPilot)

Use these in Cursor **Agent** mode after the files in this pack have been copied to the repository root (`stockpilot/`, typically `C:\dev\stockpilot` on Windows 11). The Cursor terminal should be **PowerShell**. Work **one task at a time**, in order. After each task: review the diff, run or inspect the reported Compose checks (PowerShell, one command per line), then commit before pasting the next prompt.

Replace nothing in the `@` references if those files sit at the repo root. If you opened a subfolder, adjust the references so they resolve.

General review prompt (optional, after a task):

```text
Review the current uncommitted changes only for defects that could actually happen.
Focus on cross-tenant data leaks, illegal order-status transitions, double stock consumption,
broken transaction boundaries, and lost or duplicated messages.
For each issue, explain the path and impact, and point to the file.
If a check is required, run it via docker compose as defined in @AGENTS.md.
Do not treat “no issue found” as proof of total correctness.
Do not invent requirements. Flag OPEN DECISIONS instead.
```

---

## T01 — Product language and ADRs

```text
Read @AGENTS.md and @docs/tasks/T01.md carefully before changing anything.

Task: T01 only. Freeze StockPilot ubiquitous language, roles, order state machine and inventory-effect table, business invariants, v1 scope and non-goals in docs/product/, and write ADRs as specified in T01 (ADR-001 plus first versions of ADR-006, ADR-007, ADR-008, and stubs for ADR-002–005).

Plan first: list the files you will create and how you will keep identifiers identical to AGENTS.md. Then implement the documentation only.

Do not invent requirements or patch versions. Mark every OPEN DECISION from AGENTS.md section 27 in the product docs. Do not write application runtime code.

Do not run project toolchains on the host (Windows 11). Keep `.gitattributes`. Docs must not assume an Ubuntu development machine; containers remain Linux. There are no Docker checks required for T01. Stop when the docs are ready and summarize what you wrote and any OPEN DECISIONS. Wait for review.
```

---

## T02 — Monorepo, images, API health, React shell

```text
Read @AGENTS.md and @docs/tasks/T02.md carefully before changing anything.

Task: T02 only. Scaffold the monorepo tree, backend (Python 3.13, FastAPI, uv, /health/live and the /health/ready route shape), frontend React + TypeScript strict + Vite + MUI RTL Persian shell, Dockerfiles (official Python base + uv; Node 24 LTS for the frontend; no deprecated FastAPI image), compose.yaml, compose.dev.yaml, a minimal compose.prod.yaml, .env.example, keep `.gitattributes`, enable Vite `server.watch.usePolling` for Windows bind mounts, and a quickstart README in PowerShell (one command per line, no bash `&&`, no sudo/chmod/apt) that never installs Python or Node on the Windows 11 host. Images stay Linux. Default example path is C:\dev\stockpilot (no spaces, no Persian characters).

Plan first, then implement. Pin patch versions and image digests only after they actually install and run in Docker; record them in docs/architecture/versions.md. If a pin cannot be tested, label it OPEN DECISION — do not invent patch numbers.

Phase 1 services: postgres (skeleton), migrate (skeleton), api, frontend-dev. Do not require Keycloak, RabbitMQ, worker, relay, scheduler, observability, or backup to start.

All tool usage (uv, npm, builds) must run via docker compose or a one-shot official Linux container — never on the host toolchain, and never via a host Makefile. After implementation, start api and the frontend shell via compose using PowerShell-safe commands, report the exact commands you ran and their results, then stop for review.
```

---

## T03 — PostgreSQL 17, roles, first Alembic migration

```text
Read @AGENTS.md and @docs/tasks/T03.md carefully before changing anything.

Task: T03 only. PostgreSQL 17 with databases stockpilot and keycloak, separate users, a migration/schema-owner role used only by the migrate job, and a limited runtime role for the API. First Alembic revision: schemas access, catalog, sales, inventory, notifications, platform (no full business table sprawl). /health/ready succeeds only when Postgres is up and the expected schema revision is present. /health/live stays independent of the database. Ready must not require RabbitMQ.

Plan first, then implement. Secrets belong in untracked env/secret files; commit only .env.example placeholders. Run migrate and the API ready check via docker compose on this machine. Report PowerShell-safe commands and results. If host port 5432 is already in use on Windows, publish a different host port and keep container port 5432. Do not invent image patch tags; pin after a successful pull and record them. Stop for review.
```

---

## T04 — Ruff, mypy, ESLint, Import Linter, sample domain test, CI

```text
Read @AGENTS.md and @docs/tasks/T04.md carefully before changing anything.

Task: T04 only. Add Ruff (format+lint), mypy, Import Linter (domain must not import SQLAlchemy/FastAPI/Celery/HTTP models; application must not import DB adapters; modules may import only public contracts), ESLint and TypeScript checks, a meaningful sample domain unit test (e.g. Money in IRR), Compose services backend-checks and frontend-checks under profile test, and a GitHub Actions workflow that runs those same containerized checks. Default GITHUB permissions read-only. Pin third-party actions by version or digest only if you can record a real pin; otherwise mark OPEN DECISION, do not invent SHAs.

Plan first, then implement. Run:

docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm backend-checks
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm frontend-checks

Report what actually ran. Do not add pip-audit/Trivy/Gitleaks as a Phase 1 blocker (release-line scans are later; see OPEN DECISION 11). Stop for review.
```

---

## T05 — Keycloak, OIDC, server-side session

```text
Read @AGENTS.md and @docs/tasks/T05.md carefully before changing anything.

Task: T05 only. Add Keycloak to Compose (separate DB, stable issuer hostname — never disable issuer checks to hide localhost vs keycloak:8080), Authorization Code + PKCE with Authlib, routes GET /auth/login and GET /auth/callback, server-side hashed sessions, cookie flags, CSRF on logout, GET /api/v1/me, POST /api/v1/auth/logout, and a frontend login entry. Session: 30 minutes idle, 8 hours max. Tokens are not stored in localStorage or JS-readable cookies. Complete ADR-004. Do not claim back-channel global logout unless you implement it (OPEN DECISION).

Plan first, then implement. Run checks via docker compose (backend-checks and login/logout integration tests). Do not run toolchains on the Windows host. Stop for review and report PowerShell-safe commands, results, and remaining limitations.
```

---

## T06 — Organizations, membership, roles, RLS

```text
Read @AGENTS.md and @docs/tasks/T06.md carefully before changing anything.

Task: T06 only. Implement tenants, memberships, one role per membership (admin, sales, warehouse, viewer), ActorContext, repository tenant filters, RLS with SET LOCAL in the current transaction only, runtime role without BYPASSRLS, 404 for cross-tenant resources, last-admin protection (including the concurrent critical test), org picker UI, and an idempotent audited ops bootstrap to create orgs and link existing Keycloak users (needed for week-2 exit; see OPEN DECISION 11). Isolation tests must run as the runtime role, not the table owner. Complete ADR-003.

Plan first, then implement. Run tests via docker compose. Stop for review. Do not invent extra roles or a public invite flow.
```

---

## T07 — Products and customers

```text
Read @AGENTS.md and @docs/tasks/T07.md carefully before changing anything.

Task: T07 only. Tenant-scoped catalog and customers, APIs and a minimal Persian UI, integer IRR money as JSON strings, per-tenant SKU uniqueness (Aftab and Baran may both have SKU-100), versioned product PATCH with audit, permission matrix (viewer cannot write; warehouse cannot change price). Composite FKs include tenant_id. Deletion of a product used on an order is forbidden; provide deactivation.

Plan first, then implement. Run checks via docker compose. Week-2 exit also requires create-and-view of a same-org product from the UI. Stop for review.
```

---

## T08 — Inventory receipts, adjustments, ledger

```text
Read @AGENTS.md and @docs/tasks/T08.md carefully before changing anything.

Task: T08 only. StockPosition (0 <= reserved <= on_hand), create position on first receipt, movements ledger, GET inventory, POST receipts and adjustments (reason required; decreasing adjustment cannot take on_hand below reserved), warehouse/admin write permissions, viewer denied even via direct API, and a visible ledger in the UI. available is computed. No auto stock repair. Use PostgreSQL 17, not SQLite.

Plan first, then implement. Add the domain and integration tests listed in T08. Run them via docker compose. Stop for review.
```

---

## T09 — reserve_all and competitive stock tests

```text
Read @AGENTS.md and @docs/tasks/T09.md carefully before changing anything.

Task: T09 only. Implement InventoryCommands.reserve_all (and allocate/release/consume ports as specified) with all-or-nothing multi-line behaviour, no commit inside the adapter, fixed lock ordering, HELD reservations, and non-removable critical tests: concurrent last-stock reserve on two real PostgreSQL connections, and multi-line reserve with one short line reserving nothing. Add Hypothesis balance/non-negativity tests. Missing position equals zero stock; do not create positions on reserve.

Plan first, then implement. Run checks via docker compose. Stop for review. Do not build the HTTP order cycle (that is T11).
```

---

## T10 — Draft orders and status cycle domain

```text
Read @AGENTS.md and @docs/tasks/T10.md carefully before changing anything.

Task: T10 only. Order/OrderLine aggregate, named status methods only, draft CRUD APIs (PATCH only in DRAFT, no stock effect), frozen-price snapshot fields ready for reserve, numeric and uniqueness limits, testable clock, and a scheduler skeleton so expiry logic is not rewritten in week 6. Domain tests for legal and illegal transitions. Cursor pagination as specified. No public expire endpoint.

Plan first, then implement. Run checks via docker compose. Stop for review. Full inventory transaction, idempotency, and Outbox writer are T11.
```

---

## T11 — Shared unit of work and full order API cycle

```text
Read @AGENTS.md and @docs/tasks/T11.md carefully before changing anything.

Task: T11 only. Wire reserve, confirm, cancel, expire, and ship so order, inventory, audit, Outbox row, and idempotency response commit in one PostgreSQL transaction. Follow the lock order and reserve path in AGENTS.md. Implement Idempotency-Key and expected_version. Confirm after expiry must persist the expiry and return 409 RESERVATION_EXPIRED. Inventory effects must match the official table. Add every non-removable critical test listed in T11 (including rollback and confirm-after-expiry). Design the Outbox table now; do not build Relay yet. Complete ADR-002.

Plan first, then implement. Run all relevant tests via docker compose against PostgreSQL 17. If reserve/cancel are not correct, do not start unrelated features. Stop for review and report commands, results, and any remaining gaps.
```

---

## T12 — Persian UI main path and Playwright

```text
Read @AGENTS.md and @docs/tasks/T12.md carefully before changing anything.

Task: T12 only. Complete the Persian RTL order list, draft form, order detail (allowed actions, frozen lines, deadline, timeline), limited dashboard, and admin members page. Error states as specified (stock, version conflict, forbidden). Tenant-keyed React Query cache cleared on org switch and logout. No optimistic updates for reserve/ship/inventory. Money stays a string. Add Playwright e2e in the Compose e2e service (image version must match the project Playwright package): login, draft, reserve, confirm, ship, two-org isolation. Viewer denial of inventory writes must be clear in the UI.

Plan first, then implement. Run frontend-checks and e2e via docker compose. Stop for review.
```

---

## T13 — Relay, Worker, Inbox, replay

```text
Read @AGENTS.md and @docs/tasks/T13.md carefully before changing anything.

Task: T13 only. Transactional Outbox already written in T11: add Relay (lease, publisher confirms, named Celery tasks, mapping test), Worker, Inbox uniqueness, in-app notifications, durable failed_jobs, audited ops replay, and the three cut-point tests plus duplicate-message test. Delivery is at-least-once, not exactly-once. Do not enable automatic Inbox purge (OPEN DECISION). API ready must still not depend on RabbitMQ. Complete ADR-005. Configure acks_late and task_reject_on_worker_lost and test a killed worker.

Plan first, then implement. Run checks via docker compose, including a queue-down scenario where reserve still succeeds. Stop for review.
```

---

## T14 — Scheduler and observability

```text
Read @AGENTS.md and @docs/tasks/T14.md carefully before changing anything.

This task has two parts. If week-6 messaging just finished, implement the week-6 part only (scheduler + lag signals + “expires without RabbitMQ” test) and stop. If that part already exists, implement the week-7 part (Prometheus, Grafana, ops-exporter, starting alert thresholds, a test alert on the owner-chosen or local receiver — alert channel is OPEN DECISION).

Do not rebuild expiry domain logic; reuse the T11 use case and T10 clock/skeleton. One scheduler instance. No high-cardinality Prometheus labels. Run checks via docker compose. Plan first, then implement, then stop for review.
```

---

## T15 — Versioned release, off-host backup, restore drill, initial load

```text
Read @AGENTS.md and @docs/tasks/T15.md carefully before changing anything.

Task: T15 only. Build release images once, tag with digest, promote the same digest to staging (document GHCR/CI as specified). Harden compose.prod.yaml. Implement pg_dump + restic backup every 12 hours to an independent destination, backup and backup-scheduler services, and a restore drill on a separate Compose project (login, membership, stock-balance; invalidate sessions; do not attach an old queue). Record elapsed time; RPO/RTO remain design goals until measured (OPEN DECISION). Run an initial Locust test and write a report with hardware, image, data volume, and scenario. Add pip-audit, Gitleaks, and Trivy on the release line (week placement was not pinned in the original plan; they belong on this pipeline).

Never make docker compose down -v a normal step. Do not invent vendor prices or untested performance claims. Plan first, then implement what can be done on this machine, run checks via docker compose, write evidence under docs/evidence/, and stop for review.
```

---

## T16 — Acceptance, evidence, docs, demo

```text
Read @AGENTS.md and @docs/tasks/T16.md carefully before changing anything.

Task: T16 only. Walk the section-29 / AGENTS.md §26 checklist on a fresh environment, fix remaining defects, and produce the delivery docs, evidence reports (final load, failure, restore, release downtime, known limits), synthetic seed-demo, a ~10-minute demo script, and recorded image digests. Do not declare unmeasured p95/RPO/RTO goals as achieved. Do not add postponed features. No open critical defects in authorization, isolation, stock balance, or restore are allowed.

Plan first: list checklist items and evidence gaps. Then implement only what is needed to close them. Run final checks via docker compose. Stop for review with a report mapping each checklist item to evidence.
```
