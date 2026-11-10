# ADR-008 — Single-server deploy limits

- **Status:** Accepted
- **Date:** 2026-11-11

## Context

V1 targets an eight-week first version suitable for professional review and a limited pilot. Multi-region HA and Kubernetes are out of scope.

## Options considered

1. Kubernetes / multi-node from week 1.
2. Single-server Docker Compose deploy with documented backup/restore.
3. Managed multi-service PaaS with independent scaling per process.

## Decision

V1 is a **single-server** Docker Compose deploy. Images are Linux containers. The **developer host** is Windows 11 + Docker Desktop (WSL2); that does not change the deploy architecture or imply Windows containers.

Availability limits of one host apply. Backup/restore (logical dump + restic to an independent store) is the recovery method. Design goals (not yet measured — **OPEN DECISION**): RPO ≤ 24 h, RTO ≤ 2 h.

## Consequences

- Short maintenance windows are acceptable; measure and report downtime.
- Compose on one server does not recover from total host loss by itself.
- Off-host backup and restore drills are mandatory for operational delivery.
- Zero-downtime release and high SLA are not v1 deliverables.
