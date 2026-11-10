# ADR-006 — Synchronous SQLAlchemy data model

- **Status:** Accepted
- **Date:** 2026-11-11

## Context

Commercial use cases need explicit locks, a shared `UnitOfWork`, and clear retry boundaries. Mixing async SQLAlchemy sessions with FastAPI’s event loop invites accidental cross-thread session sharing.

## Options considered

1. Fully async SQLAlchemy everywhere.
2. Sync SQLAlchemy for commercial paths; isolate async OIDC routes.
3. Dual repository models (sync + async) for the same aggregates.

## Decision

Commercial use cases and SQLAlchemy are **synchronous**. Related FastAPI routes use `def` so FastAPI runs them in the thread pool. OIDC routes that need an async HTTP client may be `async def`; persistence work uses a complete job with its own unit of work on a worker thread. Sessions are never shared across threads. Direct sync SQL on the async event loop is forbidden.

## Consequences

- One commercial repository model.
- Adapter layer absorbs sync/async differences.
- Operational baseline: one Uvicorn process per API container until load measurement (**OPEN DECISION** on process count).
