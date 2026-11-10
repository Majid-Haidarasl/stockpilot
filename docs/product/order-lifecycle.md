# Order lifecycle and inventory effects

## States and allowed transitions

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

## Inventory effect table

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

### Numeric example

- Start: `on_hand = 10`, `reserved = 0` → `available = 10`
- Reserve 3: `on_hand = 10`, `reserved = 3` → `available = 7`
- Confirm: numbers unchanged (`10` / `3`)
- Ship: `on_hand = 7`, `reserved = 0` → `available = 7`

`available` is always computed as `on_hand - reserved`. It is **not** an independently editable column.

## Reservation rules

- In v1 an order has **at most one reservation**.
- `Reservation` is its own aggregate root, with at most 20 lines.
- Reservation lifetime is **30 minutes**, stored in `expires_at`.
- Database times use `timestamptz`. The API contract uses **UTC**. The UI displays time in the user's selected time zone.
- The clock that authorizes a transition is the trusted **server** clock (after the order row is locked; operationally from the database). The browser clock is not authoritative.
- The scheduler inspects expired reservations about **every minute**, in limited batches.
- Confirmation **also** re-checks expiry. If the deadline has passed, the same use case expires the order, releases stock, records that change, and then returns **`409`** with code `RESERVATION_EXPIRED`. This is a recordable business outcome. Do **not** throw an error that rolls back the expiry transaction.
- Confirm, cancel, and expire all lock the **same order row first**.
- A confirmed order does not expire with the passage of time; its stock stays held until ship or cancel.
- Expiry is a scheduler and administrative operation. There is **no public browser endpoint** to expire an order.
