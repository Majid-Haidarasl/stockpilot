# Ubiquitous language

These words have the same meaning in conversation, API names, tests, and code. Do not invent synonyms that change the meaning (for example, do not treat “reservation” as a completed sale).

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

## Stable identifiers

Keep these names stable in code and contracts:

`Order`, `OrderLine`, `StockPosition`, `Reservation`, `Product`, `Money`, `Quantity`, `ActorContext`, `InventoryCommands`, `ReserveStock`, `RequestedStock`.

## Modules (bounded contexts in v1)

| Module | Owns |
|---|---|
| `access` | Organization, membership, organizational role (Keycloak owns identity/passwords) |
| `catalog` | Product, current price, active flag |
| `sales` | Customer, order, lines, order status cycle |
| `inventory` | Stock position, reservation, stock movement ledger |
| `notifications` | In-app notifications and read state |
| `platform` | Shared technical capabilities only (persistence utilities, outbox, observability, security) |

Cross-module imports go through each module’s `public.py` contract only.
