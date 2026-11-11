# ADR-002 — Order and inventory transaction

- **Status:** Accepted
- **Date:** 2026-11-11
- **Confirmed at:** T11 (order cycle HTTP + shared UoW)

## Question

Why may several aggregates (`Order`, `Reservation`, stock positions) change in one PostgreSQL transaction across `sales` and `inventory`, and what will extraction cost later?

## Decision

Reserve, confirm, cancel, expire, and ship record the order change and the related inventory change in **one PostgreSQL transaction**, together with audit, Outbox, and idempotency response. `sales` calls `InventoryCommands` (public port); inventory adapters stage work and must **not** `commit`. Final commit stays with the outer use case / `UnitOfWork`.

### Lock order (all cycle commands)

Relative order must never be reversed:

1. Idempotency record
2. Order row (`FOR UPDATE`)
3. Products by id (reserve only — price/active freeze)
4. Stock positions by product id
5. Reservation row

**Never lock the reservation before positions** (confirm, cancel, expire, and ship included). This is required to prevent deadlocks with reserve.

### Confirm after expiry

If confirm finds `now >= expires_at`, the use case expires the order, releases stock, writes Outbox/audit/idempotency for `409 RESERVATION_EXPIRED`, and **commits** that expiry — it does not roll back.

## Consequences

- Strong consistency on the main path in v1.
- `sales` and `inventory` are not independently deployable until a future redesign.
