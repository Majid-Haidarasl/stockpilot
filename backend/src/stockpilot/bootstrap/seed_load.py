"""Load-test tenant seed (load-01..load-10 only).

Requires STOCKPILOT_ENVIRONMENT=production AND STOCKPILOT_ALLOW_LOAD_SEED=true.
Never touches aftab/baran or non-load slugs.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import Engine, text

from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.modules.access.domain.models import Role
from stockpilot.modules.catalog.adapters.outbound.repo import CatalogRepository
from stockpilot.modules.inventory.adapters.outbound.repo import InventoryRepository
from stockpilot.modules.sales.adapters.outbound.customer_repo import CustomerRepository
from stockpilot.modules.sales.adapters.outbound.order_repo import OrderRepository
from stockpilot.modules.sales.domain.order import Order, OrderLine
from stockpilot.platform.persistence.uow import UnitOfWork
from stockpilot.platform.settings import get_settings

LOAD_TENANT_COUNT_DEFAULT = 10
_LOAD_SEED_ENVIRONMENTS = frozenset({"production", "prod"})


def load_tenant_slugs(count: int | None = None) -> tuple[str, ...]:
    n = (
        count
        if count is not None
        else int(os.environ.get("STOCKPILOT_LOAD_TENANT_COUNT", str(LOAD_TENANT_COUNT_DEFAULT)))
    )
    if n < 1 or n > 10:
        raise SystemExit("STOCKPILOT_LOAD_TENANT_COUNT must be 1..10")
    return tuple(f"load-{i:02d}" for i in range(1, n + 1))


def assert_load_tenant_slug(slug: str) -> None:
    """Refuse any slug outside the fixed load-01..load-10 set."""
    allowed = {f"load-{i:02d}" for i in range(1, 11)}
    if slug not in allowed:
        raise SystemExit(
            f"seed-load refuses non-load slug {slug!r}; only load-01..load-10 are allowed"
        )


def assert_load_seed_allowed(*, environment: str) -> None:
    """Production-only + explicit opt-in flag (never on by default in real prod)."""
    env = environment.strip().lower()
    settings_env = get_settings().environment.strip().lower()
    if env not in _LOAD_SEED_ENVIRONMENTS or settings_env not in _LOAD_SEED_ENVIRONMENTS:
        raise SystemExit(
            "seed-load only allowed when --environment and STOCKPILOT_ENVIRONMENT are production"
        )
    flag = os.environ.get("STOCKPILOT_ALLOW_LOAD_SEED", "").strip().lower()
    if flag not in {"1", "true", "yes"}:
        raise SystemExit(
            "seed-load refused: set STOCKPILOT_ALLOW_LOAD_SEED=true "
            "(prod-like only; must not be enabled on real production deployments)"
        )


def _subjects_map() -> dict[str, str]:
    path = os.environ.get("STOCKPILOT_LOAD_SUBJECTS_FILE")
    if path and Path(path).is_file():
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise SystemExit("STOCKPILOT_LOAD_SUBJECTS_FILE must be a JSON object")
        return {str(k): str(v) for k, v in data.items()}
    raw = os.environ.get("STOCKPILOT_LOAD_SUBJECTS_JSON")
    if raw:
        data = json.loads(raw)
        return {str(k): str(v) for k, v in data.items()}
    return {}


def cmd_seed_load(
    environment: str,
    *,
    migration_engine_factory: Callable[[], Engine] | None = None,
) -> None:
    """Idempotent seed for load-01..load-N tenants (catalog, stock, draft orders)."""
    assert_load_seed_allowed(environment=environment)
    slugs = load_tenant_slugs()
    for slug in slugs:
        assert_load_tenant_slug(slug)

    products_per = int(os.environ.get("STOCKPILOT_LOAD_PRODUCTS_PER_TENANT", "100"))
    orders_per = int(os.environ.get("STOCKPILOT_LOAD_ORDERS_PER_TENANT", "200"))
    lines_per = int(os.environ.get("STOCKPILOT_LOAD_ORDER_LINES", "5"))
    stock_qty = int(os.environ.get("STOCKPILOT_LOAD_STOCK_QTY", "500"))
    if products_per < 1 or orders_per < 0 or lines_per < 1:
        raise SystemExit("invalid STOCKPILOT_LOAD_* sizing env")

    subjects = _subjects_map()
    settings = get_settings()
    issuer = settings.oidc_issuer
    if migration_engine_factory is None:
        from stockpilot.bootstrap.ops import _migration_engine

        engine: Engine = _migration_engine()
    else:
        engine = migration_engine_factory()

    created_products = 0
    created_orders = 0
    skipped_products = 0
    skipped_orders = 0

    with UnitOfWork(engine=engine) as uow:
        access = AccessRepository(uow.connection)
        catalog = CatalogRepository(uow.connection)
        customers = CustomerRepository(uow.connection)
        inventory = InventoryRepository(uow.connection)
        orders = OrderRepository(uow.connection)

        for slug in slugs:
            assert_load_tenant_slug(slug)
            tenant_id = access.ensure_tenant(slug=slug, name=f"Load Tenant {slug}")
            access.write_audit(
                tenant_id=tenant_id,
                actor_user_id=None,
                action_type="ops.seed_load.tenant",
                entity_type="tenant",
                entity_id=tenant_id,
                payload={"slug": slug},
            )

            for role, prefix in ((Role.ADMIN, "admin"), (Role.SALES, "sales")):
                email = f"{prefix}@{slug}.test"
                subject = subjects.get(email) or f"load:{email}"
                user_id = access.upsert_user(
                    issuer=issuer,
                    subject=subject,
                    email=email,
                    display_name=f"{prefix}-{slug}",
                )
                access.ensure_membership(tenant_id=tenant_id, user_id=user_id, role=role)

            existing_customers = customers.list_customers(tenant_id)
            customer = next(
                (c for c in existing_customers if c.get("name") == f"Load Customer {slug}"),
                None,
            )
            if customer is None:
                customer = customers.create_customer(
                    tenant_id=tenant_id,
                    name=f"Load Customer {slug}",
                    phone=None,
                    email=f"customer@{slug}.test",
                    notes="seed-load",
                )
            customer_id = UUID(str(customer["id"]))

            product_ids: list[UUID] = []
            for n in range(1, products_per + 1):
                sku = f"LOAD-{slug.upper()}-{n:04d}"
                row = catalog.get_product_by_sku(tenant_id, sku)
                if row is None:
                    row = catalog.create_product(
                        tenant_id=tenant_id,
                        sku=sku,
                        title=f"Load product {slug} {n}",
                        unit_price_rial=10_000 + n,
                        is_active=True,
                        stock_warning_threshold=5,
                    )
                    created_products += 1
                else:
                    skipped_products += 1
                product_id = UUID(str(row["id"]))
                product_ids.append(product_id)
                position = inventory.ensure_position_for_update(
                    tenant_id=tenant_id, product_id=product_id
                )
                available = int(position.on_hand) - int(position.reserved)
                if available < stock_qty:
                    need = stock_qty - available
                    reference = f"seed-load:{slug}:{sku}:topup:{need}"
                    # Idempotent reference: skip if movement already exists.
                    exists = uow.connection.execute(
                        text(
                            """
                            SELECT 1 FROM inventory.movements
                            WHERE tenant_id = :t AND reference = :r LIMIT 1
                            """
                        ),
                        {"t": str(tenant_id), "r": reference},
                    ).first()
                    if exists is None:
                        position.apply_receipt(need)
                        inventory.save_position(position)
                        inventory.insert_movement(
                            tenant_id=tenant_id,
                            product_id=product_id,
                            physical_delta=need,
                            reserved_delta=0,
                            reason="seed-load receipt",
                            reference=reference,
                            actor_user_id=None,
                        )

            # Draft orders for list-volume (no stock reservation).
            existing_count = uow.connection.execute(
                text(
                    """
                    SELECT COUNT(*) FROM sales.orders
                    WHERE tenant_id = :t AND status = 'DRAFT'
                    """
                ),
                {"t": str(tenant_id)},
            ).scalar_one()
            need_orders = max(0, orders_per - int(existing_count))
            for _ in range(need_orders):
                chosen = product_ids[: min(lines_per, len(product_ids))]
                lines = [
                    OrderLine(
                        id=uuid4(),
                        product_id=pid,
                        quantity=1,
                        product_sku=f"sku-{pid}",
                        product_title=f"title-{pid}",
                        unit_price_rial=10_000,
                    )
                    for pid in chosen
                ]
                # Prefer real sku/title from catalog when available.
                enriched: list[OrderLine] = []
                for line in lines:
                    prod = catalog.get_product(tenant_id, line.product_id)
                    if prod is None:
                        continue
                    enriched.append(
                        OrderLine(
                            id=uuid4(),
                            product_id=line.product_id,
                            quantity=1,
                            product_sku=str(prod["sku"]),
                            product_title=str(prod["title"]),
                            unit_price_rial=int(prod["unit_price_rial"]),
                        )
                    )
                if not enriched:
                    continue
                order = Order.new_draft(
                    tenant_id=tenant_id,
                    customer_id=customer_id,
                    lines=enriched,
                )
                orders.insert_order(order)
                created_orders += 1
            skipped_orders += max(0, orders_per - need_orders)

    print(
        "seed-load complete "
        f"tenants={len(slugs)} products_created={created_products} "
        f"products_skipped={skipped_products} orders_created={created_orders} "
        f"orders_already={skipped_orders}",
        flush=True,
    )
