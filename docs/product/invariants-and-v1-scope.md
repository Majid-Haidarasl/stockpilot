# Invariants, v1 scope, and open decisions

## Business invariants (must never be violated)

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

## Numeric limits

| Limit | Value |
|---|---|
| Max quantity per line | **100,000** |
| Max unit price | **10^12 IRR** (one trillion rial) |
| Max lines per order | **20** (no duplicate products) |
| Max order total (with 20-line cap) | `2 × 10^18` IRR (fits signed 64-bit) |
| Max `on_hand` per product | **1,000,000,000** |
| Money storage | **64-bit integer** rial — never `float` |
| Reservation TTL | **30 minutes** |
| Currency (all orgs in v1) | Iranian rial, code `IRR` (UI must say “rial” explicitly) |

`Money` holds an integer rial amount and a currency code; summing different currencies is forbidden. `Quantity` is a positive integer for order lines (zero stock is allowed; a line quantity cannot be zero).

## Conscious v1 constraints

- Each organization has **one warehouse** only.
- Quantities are **integers** (no weighted/metered goods).
- Shipment is **complete**; partial shipment does not exist.
- No discount, tax, shipping fee, or FX in v1 totals. Order total = sum of (line quantity × frozen unit price).
- No public self-registration, email invitation, subscription billing, or real payment gateway.
- Browser session is the v1 auth model. There is **no public third-party API or API key**.
- Initial org creation / Keycloak user linking is ops-tool only.

## Postponed after v1

Multi-warehouse, returns, accounting, legal invoices, real payments, public webhooks, file attachments, heavy exports, specialised search, a mobile app, and advanced analytics are **out of the eight-week plan**. Email is optional; in-app notifications cover v1 communication.

Intentionally not added in v1: Redis (sessions in PostgreSQL), Kafka, Elasticsearch, Kubernetes, service mesh, Event Sourcing, standalone feature flags, S3/MinIO. Zero-downtime release and a high SLA are **not** v1 deliverables.

## OPEN DECISIONS

Do **not** invent values for these. Ask the developer / product owner:

1. **Exact patch versions** and image digests — pin in week 1 after compatibility test (`docs/architecture/versions.md`).
2. **Alert notification channel** — chosen by the project owner.
3. **Data retention, backup access, and personal-data retention period** — before a real pilot. The 14-day / 3-month backup keep policy is for practice data only.
4. **Performance targets and RPO/RTO** — design goals, not yet measured (p95 reads &lt; 300 ms, order commands &lt; 800 ms; infrastructural 5xx &lt; 1%; RPO 24 h; RTO 2 h).
5. **Optional email, central tracing (Collector/Tempo), and any postponed product feature** — only after required work, with a separate estimate.
6. **Monthly infrastructure cost** — components named; vendor prices not assumed.
7. **Automatic Inbox purge** — not enabled in v1.
8. **Increasing API process count** — only after load measurement.
9. **Final mutating rate-limit number** — starts at 60 req/min/session; adjust after testing.
10. **Keycloak back-channel logout / immediate global logout** — do not claim without implementation.
11. Calendar placement of bootstrap tool (needed week 2) and dependency/secret/image scans (placed week 7 on the release pipeline) — capabilities when exit criteria require them.
