# ADR-007 — Integer IRR and freeze-at-reserve

- **Status:** Accepted
- **Date:** 2026-11-11

## Context

Order totals can exceed JavaScript’s safe integer range. Floating-point money causes rounding bugs. Draft prices are estimates; commercial truth must freeze at a clear moment.

## Options considered

1. Store money as `float` / decimal floating types in JSON numbers.
2. Integer minor units with currency code; JSON as digit strings.
3. Freeze prices at draft creation vs at reserve.

## Decision

- Money is a **64-bit integer** amount in Iranian rial (`IRR`). Never use `float` for money.
- JSON money is a **string of decimal digits** plus currency `"IRR"`. Frontend must not coerce to `number`; use `BigInt` or a decimal tool if computing. Server totals are authoritative.
- At **reserve** time, prices are read from the catalog and **frozen** on the order. Draft amounts remain estimates only.
- Summing different currencies is forbidden.

## Consequences

- OpenAPI must document string money types and limits.
- Catalog price changes do not rewrite already reserved orders.
