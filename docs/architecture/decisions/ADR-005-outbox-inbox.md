# ADR-005 — Outbox and Inbox

- **Status:** Accepted
- **Date:** 2026-11-16

## Question

What is the delivery contract for background notifications, how are duplicates handled, and what is explicitly not exactly-once?

## Decision

- **Transactional Outbox:** Integration events are written to `platform.outbox` in the same PostgreSQL transaction as the business change (`platform.outbox.writer.enqueue`).
- **Relay:** Claims unpublished rows with a short lease (`FOR UPDATE SKIP LOCKED`), publishes named Celery tasks with publisher confirms (`confirm_publish`, `mandatory`), then marks `published_at` only after a successful confirm. Network I/O happens outside the claim transaction. Publish failures set `last_error` and back off the lease (no hot-loop).
- **At-least-once:** Duplicate publishes are possible (crash after publish, before mark). The project does **not** claim globally exactly-once processing.
- **Inbox:** Worker uniqueness is `(consumer_name, event_id)`. Inbox + in-app notifications commit in one transaction; then the Celery task returns and acks (`acks_late`). Duplicates ack without a second notification set.
- **Retry:** Transient consume errors use exponential backoff + jitter, max **five** attempts. Poison / unknown type → durable `platform.failed_jobs` with an allow-listed `sanitized_envelope` (original `event_id` preserved). Do not ack if failure cannot be recorded. `task_reject_on_worker_lost` is enabled and covered by a killed-worker test.
- **Ops replay:** `python -m stockpilot.bootstrap.ops replay-failed-jobs` (ops service only). Dry-run by default; `--confirm` republishes the **original** envelope with the **same** `event_id` under `FOR UPDATE SKIP LOCKED`, then UPDATE `replayed_*` + audit in the same transaction held across publish. Unscoped jobs (`tenant_id` NULL) are skipped. Rows are never deleted. Re-replay is safe because Inbox dedups.
- **Scheduler independence:** Reservation expiry does not depend on the queue (T14).
- **Inbox auto-purge:** Not enabled in v1 (**OPEN DECISION**).
- **Outbox retention:** Published event bodies are kept at least **30 days** for controlled republish. **No auto-purge in this run** (document only).
- **TODO Run 5.4:** Scheduled purge of Outbox/Inbox rows older than 30 days (dry-run first); resolve OPEN DECISION before enabling Inbox deletes.

## Consequences

- Queue outage must not block order recording (API ready stays independent of RabbitMQ).
- Duplicate publishes / redeliveries must not duplicate notifications.
- Ops must diagnose `failed_jobs` before `--confirm` replay; see `docs/runbooks/queue-outage.md`.
