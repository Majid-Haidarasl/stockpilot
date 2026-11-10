# StockPilot

Web app for small/medium distribution companies to manage orders and stock.

Basic flow:
1. sales creates a customer order
2. system reserves available stock
3. sales confirms the order
4. warehouse ships it (full shipment only)

If the reservation expires or the order gets cancelled, reserved stock goes back.

## What I'm aiming for (v1)

- multi-tenant (each company only sees its own data)
- Keycloak login + server-side sessions
- product catalog, customers, inventory receipts/adjustments
- order lifecycle: draft → reserved → confirmed → shipped
- in-app notifications for important order changes
- audit log + a small dashboard
- everything runnable with Docker Compose

## Stack

| Area | Choice |
|---|---|
| Backend | Python / FastAPI |
| DB | PostgreSQL |
| Auth | Keycloak |
| Frontend | React + TypeScript + Vite + MUI (RTL, Persian UI) |
| Queue | RabbitMQ + Celery |
| Edge | Caddy |
| Ops | Docker Compose, Prometheus/Grafana later |

Architecture is a modular monolith — one backend image, separate processes for API / worker / relay / scheduler. Not microservices for v1.

## Repo status

Empty for now. Planning docs are ready; implementation starts from phase 1 (repo scaffold + compose + domain foundation).

## Local notes

- Dev host: Windows 11 + Docker Desktop (WSL2)
- Don't install project Python/Node on the host — use containers
- Preferred project path without spaces / non-ASCII chars if possible

## License

Private project for now.
