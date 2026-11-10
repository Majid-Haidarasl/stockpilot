# ADR-001 — Modular monolith

- **Status:** Accepted
- **Date:** 2026-11-11

## Context

StockPilot needs clear module boundaries (access, catalog, sales, inventory, notifications) and a complete order path in eight weeks. Microservices would add distributed transactions, independent deploys, and version coordination before the domain model is proven.

## Options considered

1. Microservices per bounded context from day one.
2. Classic single-package monolith with weak internal boundaries.
3. **Modular monolith**: one releasable backend, modules with contracts, same image for API/worker/relay/scheduler as separate processes.

## Decision

Use a **modular monolith**. One backend image; process separation is not a microservice architecture. Modules expose contracts via `public.py`. Import Linter enforces dependency direction.

## Consequences

- Immediate consistency for order + inventory in one PostgreSQL transaction is feasible (see ADR-002).
- Extracting a service later starts from existing module boundaries, but needs a redesigned workflow and eventual consistency.
- Team must keep boundaries honest; folder names alone are not enough.
