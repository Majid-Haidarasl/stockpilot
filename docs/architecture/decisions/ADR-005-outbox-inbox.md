# ADR-005 — Outbox and Inbox

- **Status:** Accepted-in-principle, to be confirmed at implementation
- **Date:** 2026-11-11

## Question

What is the delivery contract for background notifications, how are duplicates handled, and what is explicitly not exactly-once?

## Plan direction (not yet coded)

Transactional Outbox in the same DB transaction as the business change. Relay publishes to RabbitMQ (at-least-once). Worker uses Inbox uniqueness `(consumer_name, event_id)` and creates notifications in the same transaction as Inbox. Reservation expiry scheduler does **not** depend on the queue. Automatic Inbox purge is not enabled in v1 (**OPEN DECISION** for any future policy).

## Consequences (expected)

- Queue outage must not block order recording.
- Duplicate publishes must not duplicate notifications.
- The project does **not** claim globally exactly-once processing.
