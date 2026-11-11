# ADR-005 — Outbox and Inbox

- **Status:** Accepted-in-principle (Outbox table + writer landed in T11; Relay/Inbox remain T13)
- **Date:** 2026-11-11

## Question

What is the delivery contract for background notifications, how are duplicates handled, and what is explicitly not exactly-once?

## Decision so far

- Transactional Outbox rows are written in the same DB transaction as the business change (`platform.outbox` via `platform.outbox.writer.enqueue`).
- Relay publishes to RabbitMQ (at-least-once) — **T13**.
- Worker uses Inbox uniqueness `(consumer_name, event_id)` — **T13**.
- Reservation expiry scheduler does **not** depend on the queue; it uses the expire use case with runtime role + `SET LOCAL` per tenant (never BYPASSRLS/owner).
- Automatic Inbox purge is not enabled in v1 (**OPEN DECISION**).

## Consequences

- Queue outage must not block order recording.
- Duplicate publishes must not duplicate notifications.
- The project does **not** claim globally exactly-once processing.
