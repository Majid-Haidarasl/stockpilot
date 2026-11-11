# ADR-002 — Order and inventory transaction

- **Status:** Accepted
- **Date:** 2026-11-11

## Question

Why may several aggregates (`Order`, `Reservation`, stock positions) change in one PostgreSQL transaction across `sales` and `inventory`, and what will extraction cost later?

## Decision

Reserve, confirm, cancel, expire, and ship record the order change and the related inventory change in **one PostgreSQL transaction**, together with audit, Outbox, and idempotency response. `sales` calls `InventoryCommands` (public port); inventory adapters stage work and must **not** `commit`. Final commit stays with the outer use case / `UnitOfWork`.

Confirmed at T09: `SqlInventoryCommands.reserve_all` / `allocate` / `release` / `consume` stage reservation rows, counter updates, and movements on the caller’s connection. Order HTTP wiring remains T11, but the shared-UoW contract is in place.

Inventory-side lock order (after outer idempotency + order locks): products by id (caller; active/SKU on command in T09) → stock positions by product id → reservation.

## Consequences

- Strong consistency on the main path in v1.
- `sales` and `inventory` are not independently deployable until a future redesign.
