"""Operator bootstrap / seed / balance commands (runs as migrator DB role)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import Engine, create_engine, text

from stockpilot.bootstrap.sample_data import (
    load_sample_markdown,
    parse_companies,
    parse_inventory_rows,
)
from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.modules.access.domain.models import Role
from stockpilot.modules.catalog.adapters.outbound.repo import CatalogRepository
from stockpilot.modules.inventory.adapters.outbound.repo import InventoryRepository
from stockpilot.modules.inventory.domain.models import DEFAULT_WAREHOUSE
from stockpilot.platform.persistence.uow import UnitOfWork
from stockpilot.platform.settings import get_settings

DEMO_ORGS = (
    {"slug": "aftab", "name": "Aftab"},
    {"slug": "baran", "name": "Baran"},
)

DEMO_LINKS = (
    ("aftab", "admin@aftab.test", Role.ADMIN, "STOCKPILOT_SUBJECT_AFTAB_ADMIN"),
    ("aftab", "sales@aftab.test", Role.SALES, "STOCKPILOT_SUBJECT_AFTAB_SALES"),
    ("aftab", "warehouse@aftab.test", Role.WAREHOUSE, "STOCKPILOT_SUBJECT_AFTAB_WAREHOUSE"),
    ("baran", "admin@baran.test", Role.ADMIN, "STOCKPILOT_SUBJECT_BARAN_ADMIN"),
    ("baran", "viewer@baran.test", Role.VIEWER, "STOCKPILOT_SUBJECT_BARAN_VIEWER"),
)

_PROD_ENVIRONMENTS = frozenset({"production", "prod", "staging"})


def _migration_engine() -> Engine:
    url = os.environ.get("STOCKPILOT_MIGRATION_DATABASE_URL")
    if not url:
        raise SystemExit("STOCKPILOT_MIGRATION_DATABASE_URL is required for ops")
    return create_engine(url, pool_pre_ping=True)


def _assert_dev_only(environment: str) -> None:
    env = environment.strip().lower()
    settings_env = get_settings().environment.strip().lower()
    if env in _PROD_ENVIRONMENTS or settings_env in _PROD_ENVIRONMENTS:
        raise SystemExit(
            "seed-demo is development-only and refuses production/staging environments"
        )


def _default_sample_path() -> Path:
    configured = os.environ.get("STOCKPILOT_SAMPLE_DATA_PATH")
    if configured:
        return Path(configured)
    # Local checkout layout: backend/src/stockpilot/bootstrap -> repo docs/
    return Path(__file__).resolve().parents[4] / "docs" / "stockpilot-sample-data.md"


def cmd_bootstrap(environment: str) -> None:
    settings = get_settings()
    engine = _migration_engine()
    issuer = settings.oidc_issuer

    with UnitOfWork(engine=engine) as uow:
        repo = AccessRepository(uow.connection)
        tenant_ids: dict[str, UUID] = {}
        for org in DEMO_ORGS:
            tenant_ids[org["slug"]] = repo.ensure_tenant(slug=org["slug"], name=org["name"])
            repo.write_audit(
                tenant_id=tenant_ids[org["slug"]],
                actor_user_id=None,
                action_type="ops.bootstrap.tenant",
                entity_type="tenant",
                entity_id=tenant_ids[org["slug"]],
                payload={"slug": org["slug"], "environment": environment},
            )

        for org_slug, email, role, subject_env in DEMO_LINKS:
            subject = os.environ.get(subject_env) or f"bootstrap:{email}"
            user_id = repo.upsert_user(
                issuer=issuer,
                subject=subject,
                email=email,
                display_name=email.split("@")[0],
            )
            membership_id = repo.ensure_membership(
                tenant_id=tenant_ids[org_slug],
                user_id=user_id,
                role=role,
            )
            repo.write_audit(
                tenant_id=tenant_ids[org_slug],
                actor_user_id=None,
                action_type="ops.bootstrap.membership",
                entity_type="membership",
                entity_id=membership_id,
                payload={"email": email, "role": role.value, "subject": subject},
            )

    print("bootstrap complete", flush=True)


def cmd_seed_demo(environment: str, sample_path: Path) -> None:
    _assert_dev_only(environment)
    if not sample_path.is_file():
        raise SystemExit(f"Sample data file not found: {sample_path}")

    settings = get_settings()
    engine = _migration_engine()
    issuer = settings.oidc_issuer
    markdown = load_sample_markdown(sample_path)
    companies = parse_companies(markdown)
    inventory_rows = parse_inventory_rows(markdown)
    if len(companies) != 20:
        raise SystemExit(f"Expected 20 companies, parsed {len(companies)}")
    if len(inventory_rows) != 108:
        raise SystemExit(f"Expected 108 inventory rows, parsed {len(inventory_rows)}")

    created_products = 0
    created_receipts = 0
    skipped_receipts = 0

    with UnitOfWork(engine=engine) as uow:
        access = AccessRepository(uow.connection)
        catalog = CatalogRepository(uow.connection)
        inventory = InventoryRepository(uow.connection)
        tenant_ids: dict[str, UUID] = {}

        for company in companies:
            tenant_id = access.ensure_tenant(slug=company.slug, name=company.name_fa)
            tenant_ids[company.slug] = tenant_id
            subject = f"bootstrap:{company.admin_email}"
            user_id = access.upsert_user(
                issuer=issuer,
                subject=subject,
                email=company.admin_email,
                display_name=company.name_fa,
            )
            membership_id = access.ensure_membership(
                tenant_id=tenant_id,
                user_id=user_id,
                role=Role.ADMIN,
            )
            access.write_audit(
                tenant_id=tenant_id,
                actor_user_id=None,
                action_type="ops.seed.tenant",
                entity_type="tenant",
                entity_id=tenant_id,
                payload={"slug": company.slug, "membership_id": str(membership_id)},
            )

        for row in inventory_rows:
            tenant_id = tenant_ids[row.slug]
            existing = catalog.get_product_by_sku(tenant_id, row.sku)
            if existing is None:
                product = catalog.create_product(
                    tenant_id=tenant_id,
                    sku=row.sku,
                    title=row.title,
                    unit_price_rial=row.unit_price_rial,
                    is_active=True,
                    stock_warning_threshold=row.stock_warning_threshold,
                )
                created_products += 1
            else:
                product = existing

            product_id = UUID(str(product["id"]))
            reference = f"seed-demo:{row.slug}:{row.sku}"
            if inventory.movement_exists(tenant_id, reference):
                skipped_receipts += 1
                continue

            position = inventory.ensure_position_for_update(
                tenant_id=tenant_id,
                product_id=product_id,
                warehouse_code=DEFAULT_WAREHOUSE,
            )
            if row.on_hand > 0:
                position.apply_receipt(row.on_hand)
                inventory.save_position(position)
            inventory.insert_movement(
                tenant_id=tenant_id,
                product_id=product_id,
                physical_delta=row.on_hand,
                reserved_delta=0,
                reason="seed-demo receipt",
                reference=reference,
                actor_user_id=None,
                warehouse_code=DEFAULT_WAREHOUSE,
            )
            inventory.write_audit(
                tenant_id=tenant_id,
                actor_user_id=None,
                action_type="ops.seed.receipt",
                entity_id=position.id,
                payload={"sku": row.sku, "on_hand": row.on_hand},
            )
            created_receipts += 1

    print(
        "seed-demo complete "
        f"companies={len(companies)} products_created={created_products} "
        f"receipts_created={created_receipts} receipts_skipped={skipped_receipts}",
        flush=True,
    )


def cmd_balance_check(tenant_slug: str | None) -> None:
    engine = _migration_engine()
    with UnitOfWork(engine=engine) as uow:
        inventory = InventoryRepository(uow.connection)
        tenant_id: UUID | None = None
        if tenant_slug:
            row = uow.connection.execute(
                text("SELECT id FROM access.tenants WHERE slug = :slug"),
                {"slug": tenant_slug},
            ).first()
            if row is None:
                raise SystemExit(f"Unknown tenant slug: {tenant_slug}")
            tenant_id = UUID(str(row[0]))

        report = inventory.balance_report(tenant_id)
        mismatches = [r for r in report if not r["physical_ok"] or not r["reserved_ok"]]
        print(f"balance-check positions={len(report)} mismatches={len(mismatches)}", flush=True)
        for item in mismatches:
            print(
                "MISMATCH "
                f"tenant={item['tenant_id']} product={item['product_id']} "
                f"on_hand={item['on_hand']} physical_sum={item['physical_sum']} "
                f"reserved={item['reserved']} reserved_sum={item['reserved_sum']}",
                flush=True,
            )
        if mismatches:
            raise SystemExit(1)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="stockpilot-ops")
    sub = parser.add_subparsers(dest="command", required=True)

    boot = sub.add_parser("bootstrap", help="Idempotent org/user membership bootstrap")
    boot.add_argument("--environment", default="development")

    seed = sub.add_parser("seed-demo", help="Dev-only sample companies/products/stock seed")
    seed.add_argument("--environment", default="development")
    seed.add_argument(
        "--sample-path",
        default=str(_default_sample_path()),
        help="Path to stockpilot-sample-data.md",
    )

    balance = sub.add_parser("balance-check", help="Report stock ledger vs counter mismatches")
    balance.add_argument("--tenant-slug", default=None)

    args = parser.parse_args(argv)
    if args.command == "bootstrap":
        cmd_bootstrap(args.environment)
    elif args.command == "seed-demo":
        cmd_seed_demo(args.environment, Path(args.sample_path))
    elif args.command == "balance-check":
        cmd_balance_check(args.tenant_slug)
    else:
        raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main(sys.argv[1:])
