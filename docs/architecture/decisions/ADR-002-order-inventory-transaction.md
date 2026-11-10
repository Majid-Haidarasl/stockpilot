# ADR-002 — Order and inventory transaction

- **Status:** Accepted-in-principle, to be confirmed at implementation
- **Date:** 2026-11-11

## Question

Why may several aggregates (`Order`, `Reservation`, stock positions) change in one PostgreSQL transaction across `sales` and `inventory`, and what will extraction cost later?

## Plan direction (not yet coded)

Reserve, confirm, cancel, expire, and ship record the order change and the related inventory change in **one PostgreSQL transaction**, together with audit, Outbox, and idempotency response. `sales` calls `InventoryCommands` (public port); inventory adapters stage work and must **not** `commit`. Final commit stays with the outer use case / `UnitOfWork`.

## Consequences (expected)

- Strong consistency on the main path in v1.
- `sales` and `inventory` are not independently deployable until a future redesign.
