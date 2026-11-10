# StockPilot — Agent Brief

This file is the standing instruction set for any AI coding agent working in this repository (Cursor, Codex, or similar). Read it before changing code. For task-level scope, also read the matching file in `docs/tasks/`. Product language and rules in this file are taken from the StockPilot execution plan (source review date: 10 November 2026). Do not invent requirements. If a detail is missing, mark it **OPEN DECISION** and stop for the developer rather than filling the gap silently.

## 1. How to work in this repo

1. One reviewable change at a time. Prefer work that a developer can finish and review in about two to four hours. Do not mix domain model, login, UI chrome, database, and deployment in a single change.
2. Start from behaviour and a failing example, then implement a limited change, then run the repository's Docker Compose check commands, then report what actually ran.
3. Always add or update tests for the behaviour you change. Inventory, reservation, tenancy, and messaging changes require transactional, concurrency, and balance tests as specified below. Do not claim a test passed if it was not executed.
4. Never install or run Python, Node.js, pytest, npm, Alembic, or other project toolchains on the host. The **developer host is Windows 11** with Docker Desktop (WSL2 backend), Git for Windows, Cursor, and **PowerShell** as the default terminal. All build, test, migrate, and ops commands run through `docker compose`. Containers use **Linux images**; the architecture does not change because the host OS is Windows. Do not invent hidden host steps (no "first `pip install` on the laptop", no `sudo`, no host `chmod`, no `apt`, no Ubuntu/bash-only instructions). Host commands must be PowerShell-compatible: write one command per line and do not chain with bash `&&`. Do not add a Makefile that requires `make` on the host; prefer commands inside containers, and add a `.ps1` helper only if a host script is truly needed.
5. Never commit secrets, real customer data, live tokens, or private keys. Do not put them in Git, Dockerfiles, images, logs, or prompts to the AI tool. Demo data must be synthetic. Use `.env.example` as the committed template; generated env files and secret files stay untracked.
6. Keep generated API types in `frontend/src/generated/api/` in sync with the backend OpenAPI contract. Do not hand-edit generated files.
7. Update the relevant docs and the task file when behaviour or decisions change. Record architecture decisions as ADRs under `docs/architecture/decisions/`.
8. Review any generated migration before it is applied. Never assume a migration may be auto-applied to operational data.
9. At the end of a change, report: behaviour changed, checks actually executed, and remaining limitations. An unrun test is not a success.

Canonical Compose commands (from the project plan; implement these as the repo contract):

```powershell
docker compose -f compose.yaml -f compose.dev.yaml up -d --wait postgres keycloak
docker compose -f compose.yaml -f compose.dev.yaml run --rm migrate
docker compose -f compose.yaml -f compose.dev.yaml run --rm ops bootstrap --environment development
docker compose -f compose.yaml -f compose.dev.yaml run --rm ops seed-demo
docker compose -f compose.yaml -f compose.dev.yaml --profile observability up -d --build --wait
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm backend-checks
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm frontend-checks
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm e2e
```

Phase 1 will not yet have Keycloak, `ops`, observability, or e2e. Use the subset that exists in that week (`postgres`, `migrate`, `api`, frontend shell, `backend-checks`, `frontend-checks`). Do not pretend later services already run.


### 1.1 Developer host (Windows 11) and pitfalls

Commit `.gitattributes` (included in this pack) so the repo stays consistent:

```text
* text=auto eol=lf
*.sh text eol=lf
*.ps1 text eol=crlf
```

Developers should also set:

```powershell
git config --global core.autocrlf false
git config --global core.longpaths true
```

(`core.longpaths` may also be set in this repository only with `git config core.longpaths true`.)

Additional host rules:

- Shell scripts that run **inside Linux containers** (`*.sh`, entrypoints, init scripts) must be checked out as **LF**. CRLF scripts fail in containers with obscure errors (`$'\r'`, `bad interpreter`). PowerShell helpers on the host, if any, use CRLF.
- Default project location is a Windows folder such as `C:\dev\stockpilot`. Avoid spaces and Persian or other non-ASCII characters in the path. Cloning into the WSL filesystem (for example `\\wsl$\...`) can improve bind-mount performance but is **optional and advanced**; do not require it.
- On Windows bind mounts, Vite hot reload must use polling: set `server.watch.usePolling` to `true` in the Vite config used by `frontend-dev`.
- If Docker cannot bind `5432`, look for a Postgres (or other service) already installed on Windows and using that port. Change the **host** published port in Compose if needed; keep the container port `5432`.
- In Docker Desktop, give the WSL/VM engine at least **8 GB** of memory (Settings → Resources). The original plan's "about 16 GB RAM on the development machine" is still a more comfortable host total.
- Do not use `sudo`, `chmod`, `usermod`, or `apt` on the Windows host. File permissions inside images are set in Dockerfiles and Linux container steps, not with host `chmod`.
- If image pulls from Docker Hub fail (for example because of network sanctions), stop and ask the developer to configure a registry mirror in Docker Desktop (Docker Engine JSON `registry-mirrors`). **Do not invent a mirror URL.**


## 2. Product summary

StockPilot is a web application for small and medium distribution companies. A sales user records a customer order; the system sets the ordered quantities aside from sellable stock (a **reservation**); a sales user confirms the order; a warehouse user records full goods issue and the order becomes **shipped**. If the order expires before confirmation or is cancelled, reserved stock is released.

Several companies may share one installation, but each company sees only its own data (**multi-tenancy**). Example: company Aftab and company Baran may both have a product with SKU `SKU-100` without mixing orders or stock.

The project must behave like industrial work, not a toolbox demo: access control, concurrency control, audit history, background processing, repeatable release, monitoring, and backup restore must work on the main order path. Adding tool names to the repo is not the quality bar.

**Architecture decision: Modular Monolith.** There is one releasable backend. Code is split into modules with clear contracts. The API and background processors use the same backend code and the same backend image, run as separate processes in containers. Process separation is not a microservice architecture. This is a conscious choice for an eight-week first version: get business rules and module boundaries right, and do not take on distributed transactions, independently deployed services, or version coordination. If a later need is real, these boundaries are the starting point for extracting a service.

The plan is written for one full-time developer, eight weeks, about 35 useful hours per week (28 planned + 7 buffer). Buffer is not permission to add features. "Done" at the end of week 8 means: first version with demo data, usable frontend, complete order path, critical tests, Docker deployment, operations guides, and one successful restore drill. That is suitable for a professional review, trial use, and a limited pilot. It is not an operational commitment to real customers without further load, security, legal, and support assessment.

## 3. Version-1 scope and non-goals

### 3.1 Required v1 capabilities

| Area | Expected v1 behaviour |
|---|---|
| Login and session | User signs in through Keycloak. The application creates a secure server-side session. Passwords are not stored in the product backend. |
| Organization and membership | At least two independent organizations. An organization admin can change roles of existing members of that organization. |
| Product catalog | An authorized user can manage product, SKU, title, price, and active flag. Deleting a product used on an order is not allowed. |
| Customer | A sales user can register and edit customer name and minimal contact details in their own organization. |
| Inventory | A warehouse user can record receipts and adjustments with a reason. Sellable quantity and reserved quantity are visible in the UI. |
| Orders | Draft creation, line edits, reserve, confirm, cancel, expire, and ship must follow the rules in this brief. |
| In-app notification | Important order changes create an in-app notification. Notification creation runs in the background. |
| Audit history | Sensitive operations are recorded with user, organization, time, action type, and entity id. |
| Limited dashboard | Order counts by status, sum of shipped order amounts in a selected range, and products below their stock threshold. |
| Software operations | Build, test, deploy, monitor, back up, and restore with documented commands in Docker environments. |

### 3.2 Conscious v1 constraints

- Each organization has **one warehouse** only.
- Quantities are **integers**. Weighted or metered goods are out of scope.
- An order has at most **20 lines**, with **no duplicate product** on the same order (quantity lives on the single line).
- Shipment is **complete**; partial shipment does not exist.
- Currency for all organizations is Iranian rial, code `IRR`. The UI must display amounts explicitly as rial so rial and toman are not confused.
- No discount, tax, shipping fee, or FX in v1 totals. The order total is the sum of (line quantity × frozen unit price).
- No public self-registration, email invitation, subscription billing, or real payment gateway.
- Initial organization creation and linking of existing Keycloak users is done by an **in-container administrative tool**. In operational environments this tool is only for the deployment operator, and all of its changes are audited.
- Browser session is the v1 auth model. There is **no public third-party API or API key**.

### 3.3 Explicitly postponed after v1

Multi-warehouse, returns, accounting, legal invoices, real payments, public webhooks, file attachments, heavy exports, specialized search, a mobile app, and advanced analytics are **out of the eight-week plan**. Email is optional; in-app notifications cover v1 communication. If time remains after all required work, at most **one** of these extensions may be chosen with a separate estimate.

Intentionally not added in v1: Redis (sessions live in PostgreSQL; stock must not depend on a cache), Kafka, Elasticsearch, Kubernetes, a service mesh, Event Sourcing, a standalone feature-flag system, S3/MinIO (no attachments). Zero-downtime release and a high SLA are **not** v1 deliverables.

## 4. Ubiquitous language

These words have the same meaning in conversation, API names, tests, and code. Do not invent synonyms that change the meaning (for example, do not treat "reservation" as a completed sale).

| Persian term | English identifier | Meaning in this project |
|---|---|---|
| سازمان | `Tenant` | An independent company with its own data and members. |
| کالا | `Product` | Commercial identity of an item: SKU, title, price, active flag. |
| موقعیت موجودی | `StockPosition` | On-hand and reserved quantities of one product in the organization's warehouse. |
| پیش‌نویس | `Draft` / order status `DRAFT` | An editable order that has not yet set any stock aside. |
| رزرو | `Reservation` | A definite warehouse commitment to hold a quantity for one order. |
| تأیید | `Confirmation` | A commercial decision to continue the order. It is **not** payment and **not** a legal invoice. |
| ارسال | `Shipment` | Recording complete goods issue for the order. No carrier integration in v1. |
| موجودی فیزیکی | `on_hand` | Physical quantity in the warehouse. |
| موجودی رزروشده | `reserved` | Quantity currently held for reservations. |
| موجودی قابل فروش | `available` | Always `on_hand - reserved`. Not an independently editable column. |
| رویداد دامنه | Domain event | A fact about a business change (for example, the order was confirmed). |
| رویداد یکپارچه‌سازی | Integration event | A versioned, transferable form of that fact for processors outside the core. The internal domain model is **not** serialized directly onto the queue. |
| زبان مشترک / زمینه محدود | Ubiquitous language / Bounded Context | In v1, each bounded context is one module. That mapping is a project choice, not a universal DDD law. |
| مورد کاربرد | Use case | A specific user or system goal, e.g. "cancel order and release reservation". Not a raw table write. |
| درگاه و مبدل | Port and Adapter | A port is a core contract; an adapter binds it to a concrete tool (PostgreSQL, HTTP, queue). |
| مخزن دامنه | Repository | A contract to load and save a domain model. Not the Git repository. |
| واحد کار | `UnitOfWork` | The boundary of one PostgreSQL transaction for a use case. |
| جلوگیری از تکرار | Idempotency | Repeating the same request must not create a new business effect. |
| نقش زمان اجرا | Runtime role | The limited database account used by the API and processors; not the migration schema-owner account. |

Identifiers to keep stable: `Order`, `OrderLine`, `StockPosition`, `Reservation`, `Product`, `Money`, `Quantity`, `ActorContext`, `InventoryCommands`, `ReserveStock`, `RequestedStock`.

## 5. Roles and permission matrix

Roles are defined **inside one organization**. The same person may be `admin` in Aftab and `viewer` in Baran. No role, by itself, grants access to another organization. In v1, each membership has **exactly one role** in that organization. The organization admin has full authority in that organization only.

The backend checks identity **and** membership and permission on every request. Hiding a button in the frontend is not a security policy. For a resource that belongs to another organization, return **`404`**, so that the resource's existence is not disclosed.

| Role | Allowed | Not allowed |
|---|---|---|
| `admin` (organization admin) | All operations in that organization, including changing roles of existing members, viewing the audit log, and setting a product's stock warning threshold. | The last active admin of an organization cannot remove their own admin role. |
| `sales` (sales user) | Manage customers and draft orders; reserve, confirm, or cancel an order before shipment. | Adjust inventory; change member roles. |
| `warehouse` (warehouse user) | Record receipts; adjust stock with a required reason; ship a **confirmed** order. | Change prices; commercially confirm an order. |
| `viewer` (read-only) | See catalog, inventory, orders, and the dashboard; personal actions such as logout and marking their own notifications as read. | Change any commercial data. |

Initial organization setup and linking Keycloak users is **not** a self-service admin UI in v1; it is the containerized ops bootstrap tool, audited, operator-only in production-like environments.

## 6. Order state machine and inventory effects

### 6.1 States and allowed transitions

```text
[*] → DRAFT
DRAFT      --reserve--> RESERVED
DRAFT      --cancel---> CANCELLED
RESERVED   --confirm before expiry--> CONFIRMED
RESERVED   --cancel---> CANCELLED
RESERVED   --expire---> EXPIRED
CONFIRMED  --ship-----> SHIPPED
CONFIRMED  --cancel---> CANCELLED
SHIPPED, CANCELLED, EXPIRED are terminal. A terminal order is not reopened.
```

Returns, if ever added, must be a separate process. Do not implement returns by manually writing the order status backwards.

Every status transition must go through a **named domain method**. Direct assignment to `status` from a controller or repository is forbidden.

### 6.2 Inventory effect table

If a product appears on the order with quantity `q`:

| Transition | Change to `on_hand` | Change to `reserved` | Reservation status |
|---|---|---|---|
| Create draft | no change | no change | no reservation is created |
| Draft → reserved | no change | increases by `q` | reservation becomes `HELD` and has an expiry |
| Reserved → confirmed | no change | no change | reservation becomes `ALLOCATED`; no automatic expiry |
| Reserved → cancelled | no change | decreases by `q` | reservation becomes `RELEASED` |
| Reserved → expired | no change | decreases by `q` | reservation becomes `EXPIRED` |
| Confirmed → cancelled | no change | decreases by `q` | reservation becomes `RELEASED` |
| Confirmed → shipped | decreases by `q` | decreases by `q` | reservation becomes `CONSUMED` |

Example from the plan: `on_hand = 10`, `reserved = 0`. Reserving 3 yields `10` and `3` (`available = 7`). Confirmation does not change the numbers. After shipment, `on_hand = 7` and `reserved = 0`.

In v1 an order has **at most one reservation**. `Reservation` is its own aggregate root, with at most 20 lines.

### 6.3 Reservation expiry

V1 reservation lifetime is **30 minutes**, stored in `expires_at`. Database times use `timestamptz`. The API contract uses **UTC**. The UI displays time in the user's selected time zone. The clock that authorizes a transition is the trusted **server** clock, taken after the order row is locked; in operational implementation this comes from the database. The browser clock is not authoritative.

The scheduler inspects expired reservations about **every minute**, in limited batches. Confirmation **also** re-checks expiry. If the deadline has passed, the same use case expires the order, releases stock, records that change, and then returns **`409`** with code `RESERVATION_EXPIRED`. This is a recordable business outcome. Do **not** throw an error that rolls back the expiry transaction.

Confirm, cancel, and expire all lock the **same order row first**, so a concurrent scheduler and user produce only one valid transition. A confirmed order does not expire with the passage of time; its stock stays held until ship or cancel.

Expiry is a scheduler and administrative operation. There is **no public browser endpoint** to expire an order.

## 7. Business invariants

These must never be violated:

1. `on_hand` and `reserved` never go negative, and `reserved` never exceeds `on_hand` (`0 <= reserved <= on_hand`).
2. A product appears at most once on an order; changing quantity edits that line.
3. Reservation is **all-or-nothing** for the order's lines. If any line lacks stock, no line is reserved, the order stays in its previous status, and the response lists the short products.
4. After reservation, lines, customer, and prices on the order do not change. To change them, cancel and create a new order.
5. At reserve time, prices are read from the catalog and **frozen** on the order. Draft amounts are estimates only.
6. Status changes only through named domain methods.
7. Shipment is allowed only for a confirmed order, and stock consumption happens only once.
8. A decreasing adjustment must not take `on_hand` below `reserved`. Adjustment reason and acting user are required.
9. Deactivating a product blocks **new** reservations, but does not block confirm or ship of a valid existing reservation.
10. Commercial data of one organization is never attached to another, even if the application is mistakenly given a foreign id.

Numeric limits (enforced in input, domain, and database constraints):

- Maximum quantity per line: **100,000**.
- Maximum unit price: **10^12 IRR** (one trillion rial).
- With the 20-line cap, an order total cannot exceed `2 × 10^18` IRR and fits in a signed 64-bit integer.
- Maximum `on_hand` per product: **1,000,000,000**. Receipts or adjustments that would exceed this are rejected.
- Money is stored as a **64-bit integer**. Never use `float` for money.

`Money` holds an integer rial amount and a currency code; summing different currencies is forbidden. `Quantity` is a positive integer for order lines (zero stock is allowed; a line quantity cannot be zero).

A product title or price change must not rewrite an already reserved order. Historical reservations are not loaded inside `StockPosition`; the position holds counters, and reservations and the movement ledger are stored as independent models. A balance check command verifies consistency of those representations.

## 8. Architecture

### 8.1 Runtime view

Browser → Caddy (`edge`) → React static files, FastAPI session/API, and Keycloak public login paths. FastAPI → PostgreSQL and Keycloak. Outbox relay → PostgreSQL and RabbitMQ. RabbitMQ → Celery worker → PostgreSQL. Scheduler → PostgreSQL. Prometheus scrapes the API, `ops-exporter`, and RabbitMQ. Grafana reads Prometheus.

React is built to static files and does not need a permanent Node.js server in production. Caddy serves those files and routes API and login traffic. **PostgreSQL is the system of record** for business truth. RabbitMQ only transports background work; it is not the source of stock truth.

### 8.2 Modules (bounded contexts)

| Module | Owns | Public contract to others |
|---|---|---|
| `access` | Organization, membership, organizational role. Keycloak owns identity and passwords. | A validated `ActorContext` and permission checks in the selected organization. |
| `catalog` | Product, current price, active flag. | Valid product data and the price suitable for freezing on an order. |
| `sales` | Customer, order, lines, and the order status cycle. | Order use cases and an order-read contract. |
| `inventory` | Stock position, reservation, and the stock movement ledger. | Receipt, complete reserve, allocate, release, and consume. |
| `notifications` | In-app notifications and read state. | Consumes known events and provides the user's notification list. |

The distinctive core is coordination of orders and stock. Give `sales` and `inventory` the most modelling and test care. Customer and catalog are simpler; do not inflate them with patterns just to make folders look uniform.

`sales` talks to the **public contracts** of `inventory` and `catalog`. `inventory` must not access the orders table or the `Order` class; it stores only an order reference id. `notifications` uses events and must not mutate orders. `access` has no knowledge of order logic.

Cross-module code sharing is allowed only when meaning and change cycle are truly shared. Do not put price, order, or stock logic in `platform`. `platform` is for shared technical capabilities (persistence utilities, outbox, observability, security).

Each module exposes its contract through `public.py`. Other modules import that contract, never another module's internal repository or tables. Example shape of the inventory command port (design sketch from the plan, not a complete implementation):

```python
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

@dataclass(frozen=True)
class RequestedStock:
    product_id: UUID
    quantity: int

@dataclass(frozen=True)
class ReserveStock:
    tenant_id: UUID
    order_id: UUID
    items: tuple[RequestedStock, ...]

class InventoryCommands(Protocol):
    def reserve_all(self, command: ReserveStock) -> UUID:
        """Stage a complete reservation in the caller's unit of work."""
        ...
```

`reserve_all` returns a reservation id and does **not** `commit`. Contract errors and allowed outcomes must be typed and documented in the real implementation.

### 8.3 Layers inside a module

| Layer | Responsibility and limit |
|---|---|
| `domain` | Entities, value objects, status transitions, business errors. **No** dependency on FastAPI, SQLAlchemy, Celery, or HTTP request models. |
| `application` | Coordinates a use case (e.g. reserve order). Uses storage ports and other modules' public contracts. Defines the use-case transaction boundary. |
| `ports` (often `application/ports.py`) | Small contracts for repositories, clock, inventory gateway, etc. These contracts are part of the application core. |
| `adapters/inbound` | Turns HTTP, a queue message, or an admin command into a use-case input. Does not implement reserve rules or stock arithmetic. |
| `adapters/outbound` | Implements core contracts with SQLAlchemy, PostgreSQL, RabbitMQ, or the identity service. |
| `bootstrap` | Wires implementations to contracts and builds the runnable app. Only here may core and infrastructure be known at the same time. |

Dependency direction: adapters depend on application and its ports; application depends on domain; domain depends on no external tools. At runtime a use case may call a repository, but it knows only the repository **port**.

These rules are enforced by [Import Linter](https://import-linter.readthedocs.io/en/stable/). Tests must reject: importing `sqlalchemy` in domain; importing a database adapter in application; one module reaching into another module's internal repository.

ORM models and domain models are **separate**. Pydantic HTTP models stay at the HTTP boundary and do not enter the domain.

### 8.4 Transaction decision (ADR-002 territory)

Reserve, confirm, cancel, expire, and ship record the order change and the related inventory change in **one PostgreSQL transaction**. The same transaction also stores the audit record, the Outbox event, and the idempotency response. If any required part fails, everything rolls back.

This is a conscious crossing of multiple aggregates and two modules in one transaction. The design does **not** claim independent deployment of `sales` and `inventory`. The benefit is immediate consistency in v1; the cost is that extracting either module later needs a redesigned workflow and eventual consistency.

The use case opens a `UnitOfWork`. Order and inventory repository adapters share that transactional connection. The public inventory port accepts typed commercial commands and must **not** expose a SQLAlchemy `Session` in its signature. Wiring adapters to the shared unit of work is `bootstrap`'s job.

`sales` must not import inventory's internal repository. It calls something like `InventoryCommands.reserve_all(...)`. The implementation runs in-process and only stages changes. An independent `commit` inside that implementation is forbidden. Final commit authority stays in the outer use case.

For list pages and the dashboard, a simpler read path with direct SQL and flat output is allowed. Do not hydrate a hundred full aggregates to show a hundred orders. This is not a separate read database, Event Sourcing, or a full CQRS platform.

## 9. Transaction, lock ordering, retries

For order commands, lock in this **fixed order**:

1. The idempotency record
2. The order
3. Needed products, in a stable id order
4. Stock positions, in a stable id order
5. The related reservation

Ship, cancel, and expire paths must follow the same order. Paths that do not need every row still follow the same relative order and must not lock a later resource and then go back to an earlier one.

At reserve time, product price and active flag are read under an appropriate **product-row lock** so a concurrent price change cannot produce an ambiguous result. Inventory adjustment locks only the relevant stock position and must not then try to lock an order. Multi-line operations always sort items by id to reduce deadlock risk.

Use `SELECT ... FOR UPDATE` on rows that will change. After the lock is taken, re-check stock. Database constraints are the last line of defence. On deadlock or a retryable transaction error, retry the **whole use case** with the same request identity, at most **three** times, with a short random backoff. No external I/O runs inside this transaction.

Default isolation is `READ COMMITTED`. Explicit locks control stock races. Do not turn on global `SERIALIZABLE` without a transaction-retry design. Each request and each job execution has its own unit of work. A SQLAlchemy `Session` is never shared across concurrent work.

Commercial use cases and SQLAlchemy are written **synchronously**. Related FastAPI routes use `def` so FastAPI runs them in its thread pool and does not block the event loop. OIDC routes that use an async client are `async def`. If those routes need the sync session repository, a complete persistence job with its own unit of work is handed to a worker thread; sessions are not passed or shared across threads. Direct sync SQL on the async event loop is forbidden. This difference stays in the adapter; do not create two commercial repository models.

Operational baseline: one Uvicorn process per API container. Increasing process count happens only after load measurement (**OPEN DECISION** until measured), and requires a PostgreSQL connection-budget and metrics review. The worker uses the same backend image, a different command, and limited concurrency.

## 10. Idempotency and optimistic concurrency

### 10.1 Idempotency

All business-mutating commands carry an `Idempotency-Key` header. The frontend generates a random value for each **new** action and reuses that same value when retrying the same action. A second click or a retry after a dropped response must not automatically mint a new key.

The key is unique in the scope `(organization, user, operation name)`. A request fingerprint is built from method, path including the resource id, contract version, and a canonicalized body. If the same key is reused with a different body, return **`409`** with code `IDEMPOTENCY_KEY_REUSED`.

The stored response includes HTTP status, body, and essential headers, written in the **same transaction** as the business change. Deterministic business outcomes such as insufficient stock may be stored. Transient infrastructure errors and `500` responses are **not** stored as final results. Structurally invalid or unauthenticated requests are rejected before this mechanism.

Records are kept at least **72 hours**. That is the commitment for the same key. After deletion there is no unlimited guarantee. Status rules and reservation uniqueness still prevent double consumption of stock, but creating a draft again after this window may create a separate order. This limit must be explicit in the API contract.

Concurrent requests with the same key are coordinated with a uniqueness constraint and a bounded wait on that record. If the wait exceeds the limit, return a retryable response with `Retry-After`. An in-memory cache is not a substitute for this guarantee.

### 10.2 Optimistic concurrency

Editable entities such as `Order` have a `version` field. The frontend sends `expected_version` on mutating commands against an existing entity. After locking, if the version has changed, the backend returns **`409`** with code `VERSION_CONFLICT`, and the UI asks the user to reload. This complements transactional locking; preventing oversell remains the inventory path's job.

## 11. Transactional Outbox, Relay, Worker, Inbox, and scheduler

Writing the order in PostgreSQL and publishing to RabbitMQ are two independent acts. Doing them in sequence can lose a message or publish for a rolled-back transaction. V1 uses the **Transactional Outbox**: the event is stored in a table in the same database, in the order's transaction, and a separate process publishes it.

Each Outbox row includes `event_id`, `tenant_id`, event type and version, aggregate id and version, occurred-at, needed payload, tracing context, and publish-attempt metadata. Payload must be minimal: no passwords, session tokens, or unnecessary contact details.

**Relay** claims ready rows in limited batches with a lock and an ownership **lease**. Claiming happens in a short transaction. Network I/O to the queue must not be held inside a long locked transaction. If the process dies, lease expiry frees the row for another attempt.

A publish is marked successful only after RabbitMQ **accepts** the message (persistent queue, persistent message, known routing). An unroutable message must be detected. Publisher confirm is not consumer completion.

For each supported event, Relay publishes a **named Celery task** with the standard Celery envelope. Raw domain JSON must not be pushed straight into Celery's internal queue. Event-type-to-task mapping lives in one place and is checked by an integration test.

Delivery is **at-least-once**. The project does **not** claim globally exactly-once processing. A message may reach the queue and Relay may die before marking success, so the message can be published again.

**Worker** records an Inbox row with uniqueness on `(consumer_name, event_id)`. Creating the notification and writing Inbox happen in **one transaction**. A duplicate message is recognized and does not create another notification. The message is acknowledged only after that transaction commits.

V1 does **not** enable automatic Inbox cleanup (**OPEN DECISION** for any future purge: the retention must be longer than the full redelivery and replay window, or an old notification could be created again).

Transient errors retry with exponential backoff plus jitter, at most **five** consume attempts in v1. Invalid structure or unknown type must not retry forever; they are recorded in a replayable failed-job list with id, reason, and sanitized data. Final failure recording must be durable. After it is recorded, the task may be acked. If the database is unavailable for that recording, the message must not be silently dropped. `acks_late` and worker-lost behaviour, including `task_reject_on_worker_lost`, must be configured deliberately and tested by forcibly stopping a worker.

Replay is an **ops-only** command and every replay is audited. Do not delete an Inbox row without review if a message was wrongly marked success or consumer logic changed. Corrective work needs a data migration or a repair process with its own identity.

The **reservation-expiry scheduler** does not depend on the notification queue. It uses the same expire use case, directly, in small batches. A RabbitMQ outage must not stop stock release. V1 runs **one** scheduler instance; locks also neutralize accidental concurrent runs.

Notification arrival order is **not** a business guarantee. Notifications are ordered by occurred-at time. Current order status is read from the order itself. No consumer changes order status based only on message arrival order.

V1 RabbitMQ is a **single node**. A complete queue-disk failure can lose accepted messages. Published event bodies are kept in the Outbox for at least **30 days** and can be republished in a controlled way. Inbox prevents duplicate notifications. This is not equivalent to a multi-node cluster.

If email is added later (optional, **OPEN DECISION**), it must be a separate output. Inbox recording and SMTP send do not share a transaction, so a failure between send and success recording can duplicate email. V1 completion criteria require in-app notifications only.

Outbox table design is written beside the order transaction in week 4 (task T11). The full Relay/Worker path is completed in week 6 (T13). A testable clock and a scheduler skeleton exist when expiry is implemented in week 4; week 6 must not rebuild expiry logic from scratch.

## 12. Data model and multi-tenancy

### 12.1 Databases, schemas, identifiers

One PostgreSQL 17 instance, two logical databases: `stockpilot` (product) and `keycloak` (identity). Usernames and privileges are separate. The application does **not** connect to Keycloak's internal tables; it receives identity through the OIDC contract.

In the product database, each module has its own schema. A schema is a logical namespace, not a complete security boundary by itself. **One** Alembic branch runs migrations in a single order (no competing heads).

| Schema and main tables | Important data and constraints |
|---|---|
| `access.tenants`, `access.memberships` | Organization and membership. `(user, organization)` is unique. External identity is the pair `(issuer, subject)`. |
| `access.sessions`, `access.login_attempts` | Session and short-lived login-flow state. Used for authentication before an organization is selected. |
| `catalog.products` | `(tenant_id, sku)` unique. Price, status, version, and a non-negative stock warning threshold (set by the org admin). |
| `sales.customers` | Customer and minimal contact details. |
| `sales.orders`, `sales.order_lines` | Status, version, customer, lines, times, and the frozen snapshot of product title, SKU, and price. |
| `inventory.stock_positions` | One row per `(organization, warehouse, product)`. A check constraint enforces non-negativity and `reserved <= on_hand`. |
| `inventory.reservations`, `inventory.reservation_lines` | `(organization, order)` unique on a reservation. Status and expiry are stored. |
| `inventory.movements` | Append-only stock ledger: physical delta, reserved delta, reason, reference, and user. |
| `platform.idempotency_records` | Key, fingerprint, status, and final response, scoped by organization and user. |
| `platform.outbox`, `platform.inbox`, `platform.failed_jobs` | Publish, consume, and failure state for background work. |
| `platform.audit_log` | Append-only history of sensitive changes. |
| `notifications.notifications` | Notification, recipient, seen-at, traceable to the related Inbox row. |

All commercial and tenant-scoped operational tables have `tenant_id`. Global authentication tables such as sessions are the exception and have their own authorization and lifecycle. Record ids are UUIDs. Random ids are **not** a substitute for authorization.

A `StockPosition` is created on the **first inventory receipt** for a new product. A uniqueness constraint controls concurrent creation. Reserving a product with no position is treated as **zero stock**. The reserve path must not create stock rows "just in case".

### 12.2 Foreign keys

Tenant-scoped references use **composite foreign keys that include `tenant_id`**. An order line can only reference a product in the same organization. SKU uniqueness is per organization, not global.

A foreign key across modules is only for data integrity and must be recorded as an explicit architecture decision. It does **not** allow a consuming module to read another module's internal tables. **Cascade deletes across modules are forbidden.** Used commercial data is typically deactivated, not deleted.

### 12.3 Layered multi-tenancy defence

1. Identify a valid session.
2. Check the user's membership in the selected organization and build an immutable `ActorContext`. `ActorContext` is not built from a free-form request body.
3. Commercial repositories take the organization explicitly and always include it in queries.
4. Enable **Row-Level Security (RLS)** on commercial tables. The normal application role is **not** table owner, not superuser, and not `BYPASSRLS`. Policies cover read and write. Organization context is applied with `SET LOCAL` **only inside the current transaction**, so a reused connection cannot keep a previous tenant. Isolation tests must run as the **real runtime role**; running them as table owner can hide failures.
5. Auth and the list of the user's own organizations happen **before** an organization is chosen; that path must not depend on an as-yet-unconfirmed tenant. Admin membership changes use an independent permission path in the same organization and use an organization lock to race-protect removal of the last admin.
6. The worker takes tenant context from the message, but only accepts messages from the trusted queue, validates the envelope, and opens an independent tenant-scoped transaction.
7. Relay uses a limited database role that can see Outbox and needed metadata across organizations, and **cannot** read orders or customers.
8. The scheduler takes active organization ids from an operational list and runs each organization's work in a transaction limited to that organization.

RLS does not replace membership checks, SQL-injection defence, or protection of connection secrets. A compromised app that can choose tenant context is still dangerous.

### 12.4 Indexes and stock balance

Initial indexes include: organization + SKU; order status and time; order customer; reservation expiry time; Outbox status and attempt time. Order lists use **cursor pagination** with a stable order `(created_at, id)`. Page size is at most **100**. Filters come from an allow-list.

The sum of physical movement deltas must equal `on_hand`, and the sum of reserved deltas must equal `reserved`. The sum of reservations in `HELD` and `ALLOCATED` must equal position reserved counters. An ops command checks this balance and **reports** discrepancies. Silent automatic stock "repair" is forbidden.

## 13. API contract and errors

Base path: `/api/v1`. OpenAPI is emitted by the backend. HTTP input and output are validated with Pydantic models that **do not enter the domain**. Frontend types are **generated from OpenAPI**.

Money in JSON is a **string of decimal digits**, e.g. `"1250000"`, plus a currency field `"IRR"`. Some legal totals exceed JavaScript's safe `number` integer range. The frontend must not coerce money to `number`; if it must compute, it uses `BigInt` or a suitable decimal tool. Authoritative totals still come from the server. OpenAPI must document the string type and limits.

All commercial requests include the selected organization id in the path. The backend checks membership.

| Example route | Behaviour |
|---|---|
| `GET /auth/login`, `GET /auth/callback` | Start and complete OIDC login. Not commercial commands; no commercial idempotency key. |
| `GET /api/v1/me` | Session identity and organizations the user may access. |
| `POST /api/v1/auth/logout` | Invalidates the local session with CSRF protection; Keycloak logout is also supported on the standard path. |
| `GET/POST /api/v1/tenants/{tenant_id}/products` | List and create products with the appropriate permission. |
| `PATCH /api/v1/tenants/{tenant_id}/products/{id}` | Update a product with version control and an audit record. |
| `GET/POST /api/v1/tenants/{tenant_id}/customers` | List and create customers. Customer edit has a separate `PATCH`. |
| `GET /api/v1/tenants/{tenant_id}/inventory` | Show on-hand, reserved, and available quantities. |
| `POST /api/v1/tenants/{tenant_id}/inventory/receipts` | Receipt with a positive quantity and a reference. |
| `POST /api/v1/tenants/{tenant_id}/inventory/adjustments` | Positive or negative adjustment with a required reason. |
| `GET/POST /api/v1/tenants/{tenant_id}/orders` | List orders and create a draft. |
| `GET/PATCH /api/v1/tenants/{tenant_id}/orders/{id}` | Read order detail, or edit **draft only**. |
| `POST .../orders/{id}/reserve` | Reserve all lines at current prices and return the expiry. |
| `POST .../orders/{id}/confirm` | Firm a valid, unexpired reservation. |
| `POST .../orders/{id}/cancel` | Cancel an allowed order and release a reservation if present. |
| `POST .../orders/{id}/ship` | Record complete goods issue for a confirmed order. |
| `GET .../dashboard`, `GET .../audit-log` | Limited report and allowed history for that organization. |
| `GET .../members`, `PATCH .../members/{id}` | Existing members and role changes, for the organization admin. |
| `GET .../notifications`, `POST .../notifications/{id}/read` | The current user's notifications and mark-as-read. |

In shortened paths, `...` means `/api/v1/tenants/{tenant_id}`.

Error format follows [RFC 9457 Problem Details](https://www.rfc-editor.org/rfc/rfc9457.html) with `Content-Type: application/problem+json`. Clients branch on `code`, not on the Persian text. Contract example (not a live response):

```json
{
  "type": "urn:stockpilot:problem:insufficient-stock",
  "title": "موجودی برای رزرو سفارش کافی نیست.",
  "status": 409,
  "code": "INSUFFICIENT_STOCK",
  "detail": "برای کالای SKU-100 فقط ۵ واحد قابل فروش است، اما سفارش ۷ واحد نیاز دارد.",
  "instance": "/api/v1/tenants/example/orders/example/reserve",
  "trace_id": "example-trace-id",
  "errors": [
    {"sku": "SKU-100", "requested": 7, "available": 5}
  ]
}
```

Status mapping: `401` invalid session; `403` no permission in the user's own organization; `404` inaccessible resource (including cross-tenant); `409` business or version conflict; `422` invalid input; `429` rate limit. Unknown errors must not leak internals or SQL.

Resource creation returns `201`. Status commands usually return `200` with a fresh order view. Notification scheduling must **not** turn a successful reserve into `202`; the reservation is definitely stored when the response is returned. The error model must also appear in OpenAPI.

Known business codes include at least: `INSUFFICIENT_STOCK`, `RESERVATION_EXPIRED`, `IDEMPOTENCY_KEY_REUSED`, `VERSION_CONFLICT`.

Health: `GET /health/live` means the API process is up. `GET /health/ready` checks PostgreSQL connectivity and schema version. RabbitMQ health is a separate signal and is **not** a condition for accepting an order (Outbox allows progress). Keycloak has its own signal; when it is down, login and session renewal are limited, but a valid local session does not necessarily die immediately.

## 14. Authentication, session, and application security

One shared Keycloak realm for user identity. A realm per organization is not required in v1, because membership and organizational roles live in the product database. Keycloak authenticates; the application decides commercial access.

Login uses Authorization Code with **PKCE**. FastAPI is the server-side of the UI: it redirects to Keycloak, validates the response with Authlib, and then creates a local session. `state`, `nonce`, and PKCE data are short-lived and one-time. The redirect URI is chosen from a fixed allow-list, never from free user input.

The browser receives only a random session id in a cookie. The raw session value is not stored; a hash is stored for lookup. The operational cookie has `HttpOnly`, `Secure`, `SameSite=Lax`, and the application host scope. `SameSite` alone is not enough against CSRF: mutating requests also have a session-bound CSRF token and Origin checks.

OIDC tokens are not placed in `localStorage` or in a JavaScript-readable cookie. If they must be kept for refresh and standard logout, they are stored **server-side**, encrypted, with a key **outside** the database. The session id is rotated after login and after sensitive events.

Signature, issuer, audience, expiry, and nonce are validated on the login response. Refresh uses a session lock so parallel requests cannot consume one refresh token at the same time. V1 local session: **30 minutes** idle timeout and **maximum 8 hours** lifetime; continuation depends on a still-valid identity and a successful refresh. A Keycloak outage must not allow creating a new session or an invalid renewal.

Organizational role is re-checked from server-side membership on every request, so a revoked access does not wait for token expiry. Application logout immediately invalidates the local session. Disabling an account in Keycloak may not affect a local session until the next check or token end; that window must be limited and documented with short token lifetime, periodic checks, and back-channel logout if needed. Do not claim immediate global logout across all services without implementing it. (**OPEN DECISION**: exact back-channel logout policy.)

OIDC issuer name must be the same from the browser's and the API's point of view. Even in development, define a stable name with DNS or a network alias. Do not "fix" `localhost` in the browser vs `keycloak:8080` inside a container by disabling issuer checks.

Other controls:

- Operational APIs only from the application origin. No open public CORS.
- Input size limits; parameterized SQL; sort columns never taken as raw user-supplied names.
- Customer and order notes are plain text; raw HTML is not accepted.
- CSP, frame-ancestors protection, and baseline security headers are set on Caddy. The UI must not build HTML from raw server error strings.
- Keycloak brute-force limits on login forms. API request and body size limits in the inbound adapter. Initial mutating-command limit: **60 requests per minute per session**, to be adjusted after testing (**OPEN DECISION** for the final number).
- For v1 with one API process, an in-memory limiter is acceptable for ordinary load; its reset-on-process-restart limitation must be documented. It is not a financial guarantee or a substitute for concurrency control. If the API is multi-instance, the limit must be enforced at a shared point.
- Logs must not contain passwords, access tokens, refresh tokens, session cookies, or full login request bodies.
- The audit log cannot be edited or deleted by a runtime application role, but a database administrator still has technical power. Do not describe it as a legally tamper-proof audit book.
- Data-retention, backup-access, and personal-data retention periods are **OPEN DECISION** and must be agreed with the product owner before a real pilot.

## 15. Frontend

- React + TypeScript **strict** + Vite. No Next.js (no SEO/SSR requirement).
- TanStack Query and React Router for server state and routing. Do not recopy server state into a parallel global store.
- Forms: React Hook Form + Zod. UI: MUI with RTL configuration, including portals and overlays, following MUI's RTL guide. Pick one component set and stay with it.
- UI language is **Persian** and **right-to-left**. Identifiers, SKUs, and technical samples stay in LTR islands so their order is not reversed. `direction: rtl` alone is not enough: use a suitable font, readable spacing, and complete labels.
- Main pages: login, organization picker, dashboard, product list and form, customers, inventory and its ledger, order list, draft form, order detail, notifications, member management.
- Order detail shows current status, allowed actions, frozen lines, reservation deadline, and a change timeline, in one place.
- After switching organization, all tenant-sensitive UI data is cleared or keyed by `tenant_id`. TanStack Query keys **must** include `tenant_id`. On logout, user data cache is cleared so the next person on the same browser does not see previous data.
- Draft prices are labelled as a **current-price estimate**. The reserve result shows the frozen prices. The countdown is guidance only; expiry is decided on the server.
- No optimistic updates for reserve, ship, or inventory changes; the UI waits for a definitive response.
- Every page has loading, empty, error, and forbidden states. Insufficient-stock errors show product name and available quantity. On version conflict, the UI reloads fresh data and does **not** automatically resubmit the stale change. The action button disables while in flight; idempotency is still enforced on the backend.
- Forms have labels, associated error messages, keyboard tab order, and a visible focus indicator. Main pages are checked on desktop and at about **390px** width. Dense tables may have explicit horizontal scroll. Colour is never the only status cue; a status title is shown as well.

Frontend build uses **Node.js 24 LTS**. In production, Caddy serves the built static files; `frontend-dev` (Vite + HMR) exists only in development Compose.

## 16. Tech stack and version policy

| Area | Selected tool | Notes |
|---|---|---|
| Backend language | Python 3.13 | Conservative compatibility baseline, not "newest". Run a dependency compatibility test before pinning. |
| Web | FastAPI, Pydantic, Uvicorn | Typed API, boundary validation, OpenAPI. Domain stays independent of these. |
| Data access | SQLAlchemy 2.x, Psycopg 3 | Transactions, explicit locks, mapping. ORM model ≠ domain model. |
| Migrations | Alembic | Versioned, reviewable schema changes. Applied as a dedicated deploy job. |
| Python deps | uv | Reproducible installs in Docker. Commit `uv.lock`. |
| Database | PostgreSQL 17 | Transactions, constraints, row locks, RLS. |
| Queue / workers | RabbitMQ 4.x, Celery 5.x (stable) | Background transport, delivery confirms, controlled retry. Business results live in PostgreSQL; a separate result backend is not required. |
| Identity | Keycloak, Authlib | Standard OIDC; organizational roles stay in the app. |
| Frontend | React, TypeScript strict, Vite | SPA admin panel. |
| UI data / routing | TanStack Query, React Router | |
| Forms / UI | React Hook Form, Zod, MUI RTL | |
| Edge | Caddy | Static files, routing, HTTPS. |
| Monitoring | Prometheus, Grafana | Limited, understandable operational metrics, dashboards, and alerts. |
| Tracing | OpenTelemetry traces + id in logs | Central trace storage (Collector, Tempo) is an **optional** extension, not in the core estimate. OTel Python: traces and metrics are stable; logs are still evolving — JSON logs stay independent of optional OTel logs. |
| Backup | PostgreSQL tools (`pg_dump`) and restic | Consistent logical dump, encrypted, to an independent backup store. |
| Tests | pytest, HTTPX, Hypothesis, Vitest, Playwright, Locust | |
| Quality / security | Ruff, mypy, ESLint, Import Linter, pip-audit, Trivy, Gitleaks | Do not add overlapping Python formatters/linters; use Ruff. |
| Build / release | Docker Compose, GitHub Actions, GHCR | Local and operational execution should be similar. Versioned images from CI. |

Backend images are built from an official Python base. Do **not** use the older prebuilt FastAPI image (FastAPI docs mark it deprecated). Follow the official uv-in-Docker guide for locked installs.

**Version policy:** Node.js 24 LTS is selected for the frontend build. React, Vite, Authlib, Keycloak, and remaining dependencies are locked to a compatible stable set in **week 1**. Exact **patch versions are an OPEN DECISION** until that compatibility test is run; this pack must not invent patch numbers. Record chosen patches, image digests, and the compatibility result in a version list in the repo.

Released images are stored with a version tag **and** a digest. Do not use `latest` for release. Python deps lock in `uv.lock`; frontend deps lock in `package-lock.json`. CI installs with uv's locked mode and `npm ci`. The Playwright image version must match the Playwright package in the project.

During the eight weeks, no major tool upgrades unless a security defect or incompatibility blocks progress.

## 17. Docker Compose services

| Service | Role |
|---|---|
| `edge` | Long-running Caddy. The operational image also contains the built React files. |
| `api` | Same backend image, Uvicorn command. |
| `worker` | Same backend image, Celery command, limited concurrency. |
| `relay` | Same backend image, Outbox publisher. |
| `scheduler` | Same backend image, periodic reservation expiry and limited cleanups. |
| `postgres` | Product and Keycloak databases with separate users. |
| `rabbitmq` | Durable task queues. Management UI is not public. |
| `keycloak` | Identity, operational settings, stable hostname, separate database. |
| `migrate` | One-shot migration job. The schema-owner role is available **only** to this job. |
| `ops` | One-shot tool for bootstrap, demo data, balance check, replay, and maintenance. Idempotent bootstrap; `seed-demo` is a separate command and is not run by default in production. |
| `prometheus`, `grafana` | Enabled with profile `observability`. Must have been run for an operational delivery. |
| `ops-exporter` | Same observability profile. Read-only metrics for Outbox lag, scheduler, job failures, and backup. |
| `frontend-dev` | Development only: Vite and HMR. |
| `backend-checks`, `frontend-checks` | Profile `test`, one-shot quality and tests. |
| `e2e`, `load-test` | Profile `test`. Browser tests and Locust load tests. |
| `backup` | Operational image with `pg_dump` and restic; one-shot backup command. |
| `backup-scheduler` | Lightweight ops-image service that runs the same backup command on schedule. It does **not** have the Docker socket and does not create other containers from inside Docker. Backup authority is not given to the commercial `scheduler`. |

`compose.yaml` holds shared and core services. `compose.dev.yaml` adds code mounts, dev commands, and local access. `compose.prod.yaml` uses versioned images, removes host code mounts, and applies operational limits and secrets. Generated env and secret files are not in Git. On the Windows 11 development host, these files are still run with Docker Desktop; images remain Linux. Host-side examples in the README must be PowerShell (one command per line). Vite in `frontend-dev` must enable `usePolling` so hot reload works on Windows bind mounts.

Optional profiles not in the core estimate: `email-dev` (Mailpit) only if optional email is implemented; `tracing` (Collector, Tempo). Observability may be turned off in development to save resources; that does not remove monitoring from the delivery.

Network and hardening highlights (full hardening is completed in week 7, but do not design against them):

- In production, only Caddy web ports are published. PostgreSQL, RabbitMQ, and Keycloak/Grafana admin UIs are not public. Needed Keycloak login paths are reachable through Caddy; the separate admin console is restricted.
- Persistent volumes for PostgreSQL, RabbitMQ, Caddy certificates, and Grafana data. A volume is not a backup.
- Secrets are mounted only into the service that needs them. The app reads the secret file. Encrypting and protecting the source file on the host remains an operations duty.
- App containers run as non-root, with `no-new-privileges` and dropped unused capabilities, as far as practical a read-only filesystem plus `tmpfs` for temp. Official infra images: inspect real write and privilege needs; do not apply a setting that silently breaks the service.
- The Docker socket is **not** given to API, worker, relay, scheduler, or in-app AI tools. CI build tooling is a controlled exception.
- Graceful shutdown must allow in-flight work to finish; do not replace it with sudden kill as the normal path.
- `depends_on` only orders creation. Wait for health with `service_healthy`, and for migrations with `service_completed_successfully`.
- Compose on one server does not provide automatic recovery from total host loss or multi-region availability. `unhealthy` alone does not guarantee recreation. Unrecoverable errors should exit visibly; alerts, runbooks, and a restart policy complement that.
- Startup order: build dev images → start PostgreSQL and Keycloak → migrate → identity config and initial membership → then API and processors.

## 18. Repository structure

This is a monorepo. Module boundaries are enforced by dependency rules, not by splitting every folder into its own Git repo.

```text
stockpilot/
├── AGENTS.md
├── README.md
├── compose.yaml
├── compose.dev.yaml
├── compose.prod.yaml
├── .env.example
├── .github/workflows/
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── alembic/
│   ├── src/stockpilot/
│   │   ├── bootstrap/
│   │   ├── modules/
│   │   │   ├── access/
│   │   │   ├── catalog/
│   │   │   ├── sales/
│   │   │   │   ├── domain/
│   │   │   │   ├── application/
│   │   │   │   │   ├── commands/
│   │   │   │   │   ├── queries/
│   │   │   │   │   └── ports.py
│   │   │   │   ├── adapters/inbound/
│   │   │   │   ├── adapters/outbound/
│   │   │   │   └── public.py
│   │   │   ├── inventory/
│   │   │   └── notifications/
│   │   └── platform/
│   │       ├── persistence/
│   │       ├── outbox/
│   │       ├── observability/
│   │       └── security/
│   └── tests/
│       ├── unit/
│       ├── application/
│       ├── contracts/
│       ├── integration/
│       └── architecture/
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── package-lock.json
│   └── src/
│       ├── app/
│       ├── features/
│       ├── shared/ui/
│       └── generated/api/
├── infra/
│   ├── caddy/
│   ├── keycloak/
│   ├── postgres/
│   ├── prometheus/
│   ├── grafana/
│   └── backup/
├── tests/
│   ├── e2e/
│   └── load/
└── docs/
    ├── product/
    ├── architecture/
    │   └── decisions/
    ├── api/
    ├── tasks/
    ├── runbooks/
    └── evidence/
```

The full layer tree is shown only for `sales`. Other modules use the same boundaries to the extent they need them. `frontend/src/generated/api` is generated output and is not edited by hand.

## 19. Testing strategy and non-removable critical tests

Database tests use a PostgreSQL of the **same major version as production**. SQLite is not acceptable proof of RLS, locking, or transactions in this project. Compose prepares test services. The API is reachable on the Docker network by the name the browser tests use.

| Level | Example and purpose |
|---|---|
| Domain unit | Reserve beyond stock is rejected; a shipped order cannot be cancelled; money calculation is correct. No network or database. |
| Application | In-memory repositories: coordination order, permission checks, business outcomes. These tests do **not** prove real locks. |
| Adapter contract | The same suite runs against in-memory and PostgreSQL repositories so load/save and tenant limits mean the same thing. |
| Integration | Transactions, RLS, foreign keys, migrations, Outbox, and real Celery-to-RabbitMQ connectivity. |
| Concurrency | Two or more real PostgreSQL connections, started together, race reserve, confirm-vs-expire, and cancel-vs-ship. |
| Property-based | Hypothesis builds sequences of receipt, reserve, release, and ship, and checks non-negativity and stock balance. |
| UI | Forms, error messages, organization switch, and version-conflict behaviour with Vitest and component tools. |
| End-to-end | Playwright: real login, create order, reserve, confirm, ship, and isolation of two organizations, in the browser. |
| Load and resilience | Locust measures latency and errors under a defined load; controlled queue and worker stops are also scenarios. |

### Non-removable critical tests

These must exist and must not be deleted to "go green":

- Concurrent reserve of the last remaining stock
- Multi-line reserve with one short line (nothing reserved)
- Replay of the same request (idempotency)
- Cancel executed a second time (stock must not increase twice)
- Race between expiry and confirm
- Race between cancel and ship
- Price change during reserve
- Concurrent attempt to remove the last admin
- A request that crosses two organizations
- Duplicate queue message
- Transaction rollback: a failure while saving a movement or event rolls back **both** order and stock
- In-confirm expiry: the expiry result is committed even though the confirm HTTP response is `409`

For background-processing failure, test at least three cut points: after the order is stored and before publish; after publish and before Relay marks success; after the notification is stored and before the worker acks. In all three, the business result must be neither lost nor doubled.

Flaky tests must not be "fixed" by mandatory reruns and then forgotten. A repeatable security, tenant-isolation, or stock-balance failure always blocks release. Branch coverage target for **domain and application** is at least **85%**. Coverage alone does not authorize release: missing an oversell test blocks delivery even with high coverage. Tests that only restate field values or internal structure do not count toward this bar.

## 20. Quality gates

Every pull request must pass: formatting and static checks, type checks, relevant tests, architecture (import) contracts, required migrations, and regenerated UI contract types.

CI path: format/types; domain and application tests; architecture contracts; migrate on an empty database; PostgreSQL and RabbitMQ integration tests; frontend build; main browser tests. For migration changes, also test upgrade from the previous schema. Full load tests and failure drills run at release or on a dedicated job; they need not repeat for a copy change.

Release line also includes Python and JavaScript dependency scans, secret scanning, and image scanning (Trivy). A clean scan is not a complete security proof. A critical or high vulnerability with a published fix blocks release. If an immediate fix is impossible, a limited, time-boxed exception must record cause, impact, mitigation, and owner. Disabling scanning in general is not acceptable. A published image carries a dependency list and a commit id.

External GitHub Actions are pinned to a version or digest. Default workflow permissions are read-only; package-publish permission is granted only to the needed job. Untrusted pull requests do not get deployment secrets. Credentials are not printed in command output.

## 21. Observability

Application logs are JSON on stdout: time, level, service name, request id, trace id, and when needed organization id and a business reference. Docker log rotation and size limits are required so disks are not filled. Central log search is not mandatory in v1; ops tools filter service logs by trace id.

The API exposes latency, request count, and error metrics. `ops-exporter` collects operational queue metrics and heartbeats. RabbitMQ exposes its own metrics. Do not naively aggregate metrics from several Celery processes in one in-memory store.

Do **not** put order, user, or organization ids on unbounded Prometheus labels. Trace a single order via logs and traces.

OpenTelemetry is used to build request traces and to propagate `traceparent` onto messages. Recording ids in logs is required in v1. Central trace storage is optional.

Initial alert thresholds (starting values, to be tuned after one week of real behaviour — final notification **channel** is **OPEN DECISION**, chosen by the project owner):

| Signal | Starting threshold and action |
|---|---|
| Rise in `5xx` | If the error ratio in 5 minutes exceeds 1%, inspect the recent change and PostgreSQL health. In very low traffic, also consider event count. |
| Age of oldest unpublished Outbox row | Over 60 seconds for several scrape intervals means lag. Inspect Relay, the queue, and routing errors. |
| Consume queue and final failures | Continuous queue growth or any new final failure must be visible. Diagnose before replay. |
| Unreleased expired reservation | A reservation still held more than two minutes after expiry triggers inspection of the scheduler and long locks. |
| PostgreSQL connections and locks | Approaching 80% of the connection budget, or long locks, needs query and transaction review. |
| Disk | Over 80% warns; over 90% is immediate action. Deleting a volume is not the default fix. |
| Backup freshness | No successful backup in 14 hours warns (base schedule is every 12 hours). A successful command without confirmed transfer to the independent destination is not enough. |
| Stock balance | Any reported discrepancy requires immediate investigation and stopping the offending operation. |

Each runbook covers: symptom, diagnosis steps, action, and how to prove health is back. Topics required by the plan: queue outage (orders continue, lag is visible, messages publish after recovery without manually deleting Outbox); worker stop (inspect pending messages and final failures before restart); database slowness (tie request id to transaction and lock); lost secret (key rotation and effect on sessions); data corruption (stop writes, restore first in a separate environment).

Worker, Relay, and scheduler record heartbeats, and the age of the oldest unfinished work is also watched. Heartbeat alone is not enough.

## 22. Backup and restore

Pilot **design goals** (not yet measured — **OPEN DECISION** until a timed drill): lose at most **24 hours** of data on total failure (RPO) and restore service in at most **two hours** (RTO). If the business cannot accept losing even a few hours of orders, the backup plan must later move to WAL archiving and point-in-time recovery; that upgrade is not in the base version.

Every **12 hours**, consistent logical dumps of the product and Keycloak databases are taken with `pg_dump`, checked, encrypted with restic, and sent to an **independent** store. During the two dumps, identity and membership admin changes are paused so identity and membership do not diverge; ordinary order recording can continue with a consistent database snapshot.

Daily backups are kept **14 days**; monthly backups **three months**. This policy is for practice data and must be aligned with the organization's retention policy before real use (**OPEN DECISION**). Each backup's metadata includes snapshot time, schema version, application image version, and file checksums. The backup role may read full data despite RLS, in a controlled way; that credential is not given to the API.

Backups must be stored **off the application host**. The design-compatible option is a second host with `rest-server` in Docker and a separate disk, with a limited encrypted connection. Simulating the destination with a volume on the same laptop is useful for learning, and is **not** a restore-after-host-loss test.

Environment config, database-user creation, Keycloak settings, and required keys also have a recovery plan. Token-decryption keys and the restic repository password must not live only inside the same backup that needs those keys to open. A secure independent copy is held by a named operations owner.

Every week, the newest backup is restored onto a Compose project with a **separate name, network, and volumes**. The runbook covers: restore files from restic, restore databases, set roles, start the matching application version, login, membership check, and the stock-balance command. Success of restic commands alone is not product health.

After restore, all old local sessions are invalidated. An old queue is not blindly attached to the restored database. On a full restore, a fresh queue is created and events still in the restored Outbox are replayed in a controlled process. Existing Inbox effects prevent duplicate notifications.

`docker compose down -v`, volume deletion, or restoring onto production is **not** a normal development command. The drill runbook checks the environment name and uses an independent name for the restore environment. The drill report records elapsed time and observed errors.

## 23. CI/CD, deployment, and rollback

Development happens on short-lived branches. Each pull request changes one clear behaviour and states the problem, what was tested, and whether a migration is required. The main branch updates only after required checks pass.

For a release, the backend image and the edge image (with frontend) are built **once**. API, worker, relay, and scheduler use the **same backend digest**. That digest is promoted first to staging and, after evaluation, to production. Rebuilding from the same tag in each environment is forbidden. Images are not built from source on the production server.

Server release steps:

1. Identify version and digests; confirm a fresh, reachable backup exists.
2. Review Compose and required secrets; pull images.
3. Stop processors in a controlled way and allow in-flight work a finish window. If the migration is incompatible with the current version, put the API write path into maintenance too.
4. Run migration as a one-shot job with the dedicated role. If it fails, the new version is not started.
5. Start services on the coordinated version; check health, login, and a short commercial path.
6. Watch errors, latency, Outbox, and the scheduler after release, and record the result.

Migrations should be incremental and backward-compatible where possible (Expand/Contract: add column, run code that supports both shapes, backfill, drop the old column in a later release).

Rolling code back to a previous digest is allowed only when schema and remaining messages are compatible with that version. Reverting a destructive migration or restoring over newer data can destroy data and is not the default rollback. In that situation, fix forward or use a planned restore.

V1 is a single-server deploy and may have a short maintenance window. Actual downtime must be measured and reported. Public HTTPS needs a domain, correct DNS, and persistent certificate storage.

## 24. Clean Code and SOLID in this project

- Names express business intent: `reserve_order`, not `process_data`; `InsufficientStock`, not a generic `ValueError` at the use-case boundary.
- Short functions are desirable, but do not split a coherent rule just to meet an arbitrary line cap.
- Comments explain **why** (for example, why lines are sorted before locking). Do not narrate `x += 1`. Types, test names, and behaviour examples are the main documentation of code.
- Configuration is loaded from the environment into a specific model. Domain code does not read env vars ad hoc. Infrastructure errors are translated into understandable boundary errors. Unknown errors are not swallowed with `except Exception: pass`.
- Reject catch-all dictionaries for every input, pervasive `Any`, and methods with many behavioural flags.
- Do not build a huge public repository, a `BaseService` for everything, or a hand-rolled DI framework. Explicit constructor injection and a small composition root are enough.

| SOLID principle | Concrete use here |
|---|---|
| SRP | `Order` enforces status rules; the order repository persists; the publisher talks to the queue. An order does not do SQL and messaging at once. |
| OCP | A future notification channel is added by implementing a defined port. Do not build a complex plugin system for unknown possibilities. |
| LSP | An in-memory test repository and the PostgreSQL repository honour the same contract, including "not found" and tenant limits. Shared contract tests catch drift. |
| ISP | A dashboard read path is not forced to implement stock-reserve methods. Read and command ports stay small and consumer-shaped. |
| DIP | A use case knows `OrderRepository` and `InventoryCommands`. SQLAlchemy and the local inventory adapter are chosen in bootstrap. |

Forbidden patterns already stated elsewhere, restated for agents: do not change order status directly; do not update stock outside the unit of work; do not `commit` inside a repository or inventory adapter; do not skip tenant context and permission on a commercial path.

## 25. Eight-week plan, gates, and ADRs

The product manager's phasing (seven phases) maps onto the plan's eight weeks and the T01–T16 task ids. Use both. Week 3 and week 4 stay one phase but keep **separate** exit criteria.

| Phase | Week | Tasks | Exit criterion |
|---|---|---|---|
| 1 Foundation | 1 | T01–T04 | From a fresh clone, the API and a sample UI start; initial migration runs; domain tests and import checks pass in CI. |
| 2 Identity, orgs, master data | 2 | T05–T07 | Real login and two independent organizations work; unauthorized users are rejected; creating and viewing a product in the same org is possible from the UI. |
| 3 Inventory and order core | 3–4 | T08–T11 | Week 3: receipt and adjustment work; a competitive reserve on a real database cannot oversell; the ledger is visible. Week 4: draft, reserve, confirm, cancel, expire, and ship work from the API, with their transactions and critical tests passing. |
| 4 Complete UI | 5 | T12 | A sales user and a warehouse user can complete the main path in the Persian browser; stock and version errors are clear; basic admin pages work. |
| 5 Background processing | 6 | T13, first part of T14 | Queue outage and recovery neither lose nor duplicate notifications; the scheduler releases reservations without the queue; replay is documented. |
| 6 Operations and release readiness | 7 | Rest of T14, T15 | Staging is published with a specific digest; a test alert is received; an off-host backup exists; initial load and restore reports are recorded. |
| 7 Acceptance and delivery | 8 | T16 | All v1 criteria are complete; evidence report, run guides, release version, and a full demo are ready; no open critical defect. |

**Control points:** If login and tenant isolation are not demonstrable at the end of week 2, fix those foundations first and drop UI polish and dashboard priority. If reserve and cancel are not correct from the API at the end of week 4, stop adding features and spend buffer on that main path. Access control, stock balance, and restore must not be dropped to keep a calendar looking green.

ADRs to record when the decision is made (issue, options, choice, consequences):

| ADR | Question the note must answer |
|---|---|
| `ADR-001` Modular monolith | Why no microservices in v1, and which boundaries must be kept? |
| `ADR-002` Order and inventory transaction | Why several aggregates change in one transaction, and what will extraction cost? |
| `ADR-003` Tenant isolation | How do membership, repository filters, RLS, and composite foreign keys work together? |
| `ADR-004` Login and session | Why does the browser hold an opaque session, and why are tokens stored server-side? |
| `ADR-005` Outbox and Inbox | What is the delivery contract, how are duplicates handled, and what is not exactly-once? |
| `ADR-006` Synchronous data model | Why was sync SQLAlchemy chosen, and how is the async identity path isolated? |
| `ADR-007` Money and price | Why integer rial, and at what moment is price frozen? |
| `ADR-008` Single-server deploy | What are the availability limits and the restore method at this infrastructure level? |

## 26. Final v1 acceptance checklist (section 29)

- [ ] The quickstart was followed on a fresh environment and did not require installing Python or Node.js on the host.
- [ ] Two organizations and distinct roles exist with independent demo data, and cross-organization access is denied.
- [ ] Draft, reserve, confirm, ship, and also cancel and expire, are demonstrable in the browser.
- [ ] Concurrent reserve, repeated requests, and racing status transitions do not leave stock inconsistent.
- [ ] Price, quantity, currency, and reservation deadline are displayed and calculated per contract.
- [ ] A queue outage and a worker stop neither permanently lose nor duplicate notifications, and controlled replay works.
- [ ] Critical tests, type checks, architecture contracts, and release scans pass, or a limited justified exception is recorded.
- [ ] The Persian UI, loading and error states, organization switching, and keyboard access were checked on the main pages.
- [ ] Release images have specific digests, and staging used the same final image.
- [ ] Dashboard and alerting detected a test failure, and the notification path was tested.
- [ ] An off-host backup was taken and restored in an independent environment; after restore, login, membership, and stock balance were checked.
- [ ] The load report, known limits, release downtime, and restore-drill result are recorded.
- [ ] There is no open critical defect in authorization, tenant isolation, stock balance, or restore.

Delivery artifacts: backend and frontend source, lockfiles, Dockerfiles, dev and production Compose files, migrations, pipeline, sample config without secrets, demo data, plus start guide, domain rules, architecture diagrams, ADRs, API contract, deploy guide, failure and restore runbooks, and an evidence report.

About a ten-minute demo should show: login, isolation of two organizations, order creation, insufficient stock, successful reserve, confirm, and ship; then a queue stop with order recording still working; then notifications catching up. The restore drill may be a separate timed report; it need not all fit in that short demo.

## 27. OPEN DECISIONS

Do not invent a value for these. Flag them and ask the developer or product owner:

1. **Exact patch versions** and image digests of tools and libraries — to be pinned in week 1 after a compatibility test, then recorded in-repo.
2. **Alert notification channel** — chosen by the project owner. A local test receiver is enough in a practice environment; a real pilot must prove an alert was actually received.
3. **Data retention, backup access, and personal-data retention period** — must be set with the product owner before a real pilot. The 14-day / 3-month backup keep policy is for practice data only.
4. **Performance targets and RPO/RTO** — design goals, not yet measured: p95 under 300 ms for ordinary reads and under 800 ms for order commands; infrastructural `5xx` under 1%; zero stock-rule violations; RPO 24 h; RTO 2 h. Reference load setup in the plan: a Linux host with 4 vCPU, 8 GiB RAM, SSD; dataset of 10 orgs, 10k products, 100k orders, about 500k lines; 15 virtual users, about 10 req/s target, 70% read / 30% commercial commands, 20 minutes, load generated from a separate host. Report image version, hardware, data volume, and scenario with the numbers. If targets are missed, inspect SQL plans, indexes, connection count, and lock duration first — do not start with a cache or more processes without evidence.
5. **Optional email, central tracing (Collector/Tempo), and any postponed product feature** — only if required work is finished and a separate estimate is chosen.
6. **Monthly infrastructure cost** — the plan names cost components (app host, independent backup destination, domain, image storage, AI tooling) but assumes no vendor prices.
7. **Automatic Inbox purge** — not enabled in v1; any future policy is still open.
8. **Increasing API process count** — only after load measurement.
9. **Final mutating rate-limit number** — starts at 60 requests per minute per session, to be adjusted after testing.
10. **Keycloak back-channel logout / immediate global logout** — do not claim it without an implementation; the exact policy is open.
11. **Calendar placement of two items the source plan did not pin to a week** (product-manager interpretation, not a new requirement): the organization bootstrap tool is needed in week 2 so login and two orgs can be demonstrated; dependency/secret/image scans (pip-audit, Gitleaks, Trivy) are placed on the week-7 release pipeline. Implement the capabilities when the dependent exit criteria require them.

Host capacity notes from the plan (estimates, not guarantees): development is more comfortable with about 16 GiB RAM; a reference server starts at 4 vCPU, 8 GiB RAM, about 80 GiB SSD; off-host backup needs independent space. On the Windows 11 development machine, allocate at least 8 GiB to Docker Desktop's WSL engine; the 16 GiB figure is total machine memory, not the Docker VM alone.

## 28. What "professional" means here

Professional quality comes from a model that can be understood, failure paths that are correct, and a system that can be run again from a fresh clone. If the acceptance list is complete, the eight-week output is a limited but coherent product whose architecture, code, operations, and decisions can stand a serious technical review — not a superficial demo.
