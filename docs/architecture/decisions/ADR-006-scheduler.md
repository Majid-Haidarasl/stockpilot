# ADR-006 — Reservation-expiry scheduler

- **Status:** Accepted
- **Date:** 2026-11-17

## Question

How does the reservation-expiry scheduler run safely as one Compose instance under RLS, without depending on RabbitMQ, and how are heartbeats / Outbox lag exposed for later monitoring?

## Decision

- **One instance:** Compose `scheduler` uses the same backend image as api/relay/worker. V1 runs exactly one replica (no scale-out).
- **Reuse expire use case:** `ReservationExpiryScheduler` calls `OrderCycleService.expire` only. No duplicated business rules. `OrderExpired` is written to `platform.outbox` in the same tenant transaction; the Relay publishes later. The scheduler never talks to RabbitMQ.
- **DB role:** Runtime login is `stockpilot_app` only (no admin URL). Session role `app.role=scheduler` (`SESSION_ROLE_SCHEDULER`) is not a human membership role and is never accepted from HTTP.
- **Tenant loop without BYPASSRLS:** List orgs via `tenants_select_scheduler`, then one `UnitOfWork` per tenant with `SET LOCAL app.tenant_id`.
- **Concurrency guard:** Session-scoped `pg_try_advisory_lock(hashtext('stockpilot.reservation_expiry'))` on a **dedicated connection** held for the whole tick; per-tenant work uses other connections. Unlock on that same connection in `finally`. If the lock connection drops mid-tick, abort. Accidental second copy gets `lock_not_acquired` and skips the tick. Per-order races with confirm remain covered by order `FOR UPDATE` (ADR-002).
- **Per-tenant isolation:** A failed tenant is logged (structured `tenant_id` + error), rolled back alone, and other tenants continue. Heartbeat details include `expired_count`, `failed_tenant_count`, `tenant_count`.
- **Graceful shutdown:** SIGTERM/SIGINT sets a stop flag; finish the current tenant; release the advisory lock; exit 0.
- **Signals:** `platform.heartbeats` stores last success per `service_name` (`scheduler`, `relay`, `worker`). Writers may only upsert their own row (RLS). Outbox lag is `platform.outbox_lag()` (SECURITY DEFINER, migrator-owned, fixed `search_path`) returning only `(unpublished_count, oldest_unpublished_age_seconds)` — no cross-tenant Outbox SELECT for the scheduler. Compose healthcheck reads scheduler heartbeat freshness. Ops: `queue-signals`. Grafana/Prometheus are Phase 6.

## Consequences

- Queue outage does not block stock release.
- Two accidental scheduler copies cannot double-expire via competing ticks.
- Phase 6 exporters can scrape heartbeats + `outbox_lag()` without new product APIs.
