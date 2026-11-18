"""Operator bootstrap / seed / balance commands (runs as migrator DB role)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import Engine, create_engine, text

from stockpilot.bootstrap.import_product_images import (
    format_summary,
    import_product_images,
    resolve_import_actor,
)
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
from stockpilot.modules.sales.adapters.outbound.customer_repo import CustomerRepository
from stockpilot.platform.db_roles import (
    ensure_stockpilot_backup,
    ensure_stockpilot_metrics,
    ensure_stockpilot_relay,
)
from stockpilot.platform.failed_jobs.replay import replay_failed_jobs
from stockpilot.platform.heartbeats.store import fetch_outbox_lag
from stockpilot.platform.persistence.db import get_engine
from stockpilot.platform.persistence.uow import UnitOfWork
from stockpilot.platform.settings import get_settings

# Idempotent e2e fixtures (not seed-demo).
_E2E_SKU = "E2E-SKU-1"
_E2E_CUSTOMER_NAME = "E2E Customer"
_E2E_UNIT_PRICE = 125000
_E2E_STOCK_QTY = 50

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
_DEV_OR_TEST_ENVIRONMENTS = frozenset({"development", "dev", "test"})


def _migration_engine() -> Engine:
    url = os.environ.get("STOCKPILOT_MIGRATION_DATABASE_URL")
    if not url:
        raise SystemExit("STOCKPILOT_MIGRATION_DATABASE_URL is required for ops")
    return create_engine(url, pool_pre_ping=True)


def cmd_ensure_db_roles() -> None:
    """Idempotent create/update of relay, metrics, backup roles. Never logs secrets."""
    admin_url = os.environ.get("STOCKPILOT_ADMIN_DATABASE_URL")
    if not admin_url:
        raise SystemExit(
            "STOCKPILOT_ADMIN_DATABASE_URL is required for ensure-db-roles "
            "(ops service only; never pass to api/relay/migrate)"
        )
    relay_password = os.environ.get("STOCKPILOT_RELAY_PASSWORD")
    metrics_password = os.environ.get("STOCKPILOT_METRICS_PASSWORD")
    backup_password = os.environ.get("STOCKPILOT_BACKUP_PASSWORD")
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    with engine.connect() as conn:
        ensure_stockpilot_relay(conn, password=relay_password)
        ensure_stockpilot_metrics(conn, password=metrics_password)
        ensure_stockpilot_backup(conn, password=backup_password)
    # Do not print passwords or the admin URL.
    print("ensure-db-roles: stockpilot_relay ready", flush=True)
    print("ensure-db-roles: stockpilot_metrics ready", flush=True)
    print("ensure-db-roles: stockpilot_backup ready", flush=True)


def _assert_dev_only(environment: str, *, command: str) -> None:
    env = environment.strip().lower()
    settings_env = get_settings().environment.strip().lower()
    if env in _PROD_ENVIRONMENTS or settings_env in _PROD_ENVIRONMENTS:
        raise SystemExit(
            f"{command} is development-only and refuses production/staging environments"
        )


def _assert_dev_or_test(environment: str, *, command: str) -> None:
    """Allow only development/test (stricter allow-list used by e2e ops)."""
    env = environment.strip().lower()
    settings_env = get_settings().environment.strip().lower()
    if env not in _DEV_OR_TEST_ENVIRONMENTS or settings_env not in _DEV_OR_TEST_ENVIRONMENTS:
        raise SystemExit(
            f"{command} only allowed when --environment and STOCKPILOT_ENVIRONMENT "
            "are development or test"
        )


# Prefixes used by integration-test fixtures (never seed/demo company slugs).
_TEST_TENANT_SLUG_PREFIXES = ("inv-", "rsv-")


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
    _assert_dev_only(environment, command="seed-demo")
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
        mismatches = [
            r
            for r in report
            if not r["physical_ok"] or not r["reserved_ok"] or not r["reservation_ok"]
        ]
        print(f"balance-check positions={len(report)} mismatches={len(mismatches)}", flush=True)
        for item in mismatches:
            print(
                "MISMATCH "
                f"tenant={item['tenant_id']} product={item['product_id']} "
                f"on_hand={item['on_hand']} physical_sum={item['physical_sum']} "
                f"reserved={item['reserved']} reserved_sum={item['reserved_sum']} "
                f"reservation_sum={item['reservation_reserved_sum']}",
                flush=True,
            )
        if mismatches:
            raise SystemExit(1)


def cmd_seed_e2e(environment: str) -> None:
    """Minimal idempotent fixtures for Playwright (aftab/baran only; not seed-demo)."""
    _assert_dev_or_test(environment, command="seed-e2e")
    settings = get_settings()
    engine = _migration_engine()
    issuer = settings.oidc_issuer

    with UnitOfWork(engine=engine) as uow:
        access = AccessRepository(uow.connection)
        catalog = CatalogRepository(uow.connection)
        customers = CustomerRepository(uow.connection)
        inventory = InventoryRepository(uow.connection)

        tenant_ids: dict[str, UUID] = {}
        for org in DEMO_ORGS:
            tenant_ids[org["slug"]] = access.ensure_tenant(slug=org["slug"], name=org["name"])

        # Dual-org membership for org-switch e2e: sales@aftab also viewer on baran.
        sales_subject = (
            os.environ.get("STOCKPILOT_SUBJECT_AFTAB_SALES") or "bootstrap:sales@aftab.test"
        )
        sales_user_id = access.upsert_user(
            issuer=issuer,
            subject=sales_subject,
            email="sales@aftab.test",
            display_name="sales",
        )
        access.ensure_membership(
            tenant_id=tenant_ids["aftab"],
            user_id=sales_user_id,
            role=Role.SALES,
        )
        access.ensure_membership(
            tenant_id=tenant_ids["baran"],
            user_id=sales_user_id,
            role=Role.VIEWER,
        )

        for slug in ("aftab", "baran"):
            tenant_id = tenant_ids[slug]
            product = catalog.get_product_by_sku(tenant_id, _E2E_SKU)
            if product is None:
                product = catalog.create_product(
                    tenant_id=tenant_id,
                    sku=_E2E_SKU,
                    title=f"E2E Product ({slug})",
                    unit_price_rial=_E2E_UNIT_PRICE,
                    is_active=True,
                    stock_warning_threshold=5,
                )
            product_id = UUID(str(product["id"]))

            existing_customers = customers.list_customers(tenant_id)
            customer = next(
                (c for c in existing_customers if c.get("name") == _E2E_CUSTOMER_NAME),
                None,
            )
            if customer is None:
                customers.create_customer(
                    tenant_id=tenant_id,
                    name=_E2E_CUSTOMER_NAME,
                    phone=None,
                    email=f"e2e-customer@{slug}.test",
                    notes="seed-e2e",
                )

            # Keep sellable stock topped up so repeated e2e runs do not starve reserves.
            position = inventory.ensure_position_for_update(
                tenant_id=tenant_id, product_id=product_id
            )
            available = int(position.on_hand) - int(position.reserved)
            if available < _E2E_STOCK_QTY:
                need = _E2E_STOCK_QTY - available
                # Unique reference each run — same deficit amount must not collide
                # with uq_movements_tenant_reference on repeated e2e bring-ups.
                reference = f"seed-e2e:{slug}:{_E2E_SKU}:topup:{need}:{uuid4().hex[:12]}"
                position.apply_receipt(need)
                inventory.save_position(position)
                inventory.insert_movement(
                    tenant_id=tenant_id,
                    product_id=product_id,
                    physical_delta=need,
                    reserved_delta=0,
                    reason="seed-e2e receipt",
                    reference=reference,
                    actor_user_id=None,
                )

    print("seed-e2e complete", flush=True)


def cmd_e2e_backdate_reservation(environment: str, order_id: str) -> None:
    """Set reservation expires_at in the past (dev/test only; no public expire API)."""
    _assert_dev_or_test(environment, command="e2e-backdate-reservation")
    engine = _migration_engine()
    with UnitOfWork(engine=engine) as uow:
        result = uow.connection.execute(
            text(
                """
                UPDATE sales.orders
                SET expires_at = now() - interval '1 minute',
                    updated_at = now()
                WHERE id = :id AND status = 'RESERVED'
                RETURNING id
                """
            ),
            {"id": order_id},
        ).first()
        if result is None:
            raise SystemExit(f"e2e-backdate-reservation: no RESERVED order found for id={order_id}")
    print(f"e2e-backdate-reservation complete order_id={order_id}", flush=True)


def cmd_cleanup_test_tenants(environment: str) -> None:
    """Remove leftover integration-test tenants (inv-*, rsv-*) from the demo DB."""
    _assert_dev_only(environment, command="cleanup-test-tenants")
    engine = _migration_engine()
    removed: list[str] = []
    with UnitOfWork(engine=engine) as uow:
        like_clauses = " OR ".join(
            f"slug LIKE :p{i}" for i in range(len(_TEST_TENANT_SLUG_PREFIXES))
        )
        params = {f"p{i}": f"{prefix}%" for i, prefix in enumerate(_TEST_TENANT_SLUG_PREFIXES)}
        tenants = uow.connection.execute(
            text(f"SELECT id, slug FROM access.tenants WHERE {like_clauses}"),
            params,
        ).fetchall()
        for tenant_id, slug in tenants:
            tid = {"t": tenant_id}
            for sql in (
                "DELETE FROM inventory.reservation_lines WHERE tenant_id = :t",
                "DELETE FROM inventory.reservations WHERE tenant_id = :t",
                "DELETE FROM inventory.movements WHERE tenant_id = :t",
                "DELETE FROM inventory.stock_positions WHERE tenant_id = :t",
                "DELETE FROM catalog.products WHERE tenant_id = :t",
                "DELETE FROM sales.customers WHERE tenant_id = :t",
                "DELETE FROM platform.audit_log WHERE tenant_id = :t",
                "DELETE FROM access.memberships WHERE tenant_id = :t",
                "DELETE FROM access.tenants WHERE id = :t",
            ):
                uow.connection.execute(text(sql), tid)
            removed.append(str(slug))
    print(
        f"cleanup-test-tenants complete removed={len(removed)} "
        f"slugs={','.join(removed) if removed else '(none)'}",
        flush=True,
    )


def cmd_queue_signals() -> None:
    """Print heartbeats + live Outbox lag (migrator; ops diagnostics)."""
    engine = _migration_engine()
    with engine.connect() as conn:
        rows = (
            conn.execute(
                text(
                    """
                    SELECT service_name, last_success_at, details, updated_at
                    FROM platform.heartbeats
                    ORDER BY service_name
                    """
                )
            )
            .mappings()
            .all()
        )
        unpublished_count, oldest_age = fetch_outbox_lag(conn)
    print("queue-signals heartbeats:", flush=True)
    if not rows:
        print("  (none)", flush=True)
    for row in rows:
        print(
            f"  {row['service_name']} last_success_at={row['last_success_at']} "
            f"details={row['details']}",
            flush=True,
        )
    print(
        f"queue-signals lag unpublished_count={unpublished_count} "
        f"oldest_unpublished_age_seconds={oldest_age}",
        flush=True,
    )


def cmd_replay_failed_jobs(
    *,
    job_id: str | None,
    tenant_slug: str | None,
    include_replayed: bool,
    limit: int,
    replayed_by: str | None,
    confirm: bool,
) -> None:
    """Republish failed_jobs envelopes (same event_id). Dry-run unless --confirm."""
    engine = _migration_engine()
    broker = os.environ.get("STOCKPILOT_CELERY_BROKER_URL")
    parsed_id: UUID | None = None
    if job_id:
        try:
            parsed_id = UUID(job_id)
        except ValueError as exc:
            raise SystemExit(f"invalid --id: {job_id}") from exc
    outcome = replay_failed_jobs(
        engine=engine,
        broker_url=broker,
        job_id=parsed_id,
        tenant_slug=tenant_slug,
        include_replayed=include_replayed,
        limit=limit,
        replayed_by=replayed_by,
        confirm=confirm,
    )
    mode = "confirm" if confirm else "dry-run"
    print(
        f"replay-failed-jobs mode={mode} selected={outcome.selected} "
        f"dry_run={outcome.dry_run} replayed={outcome.replayed} "
        f"skipped_unscoped={outcome.skipped_unscoped} "
        f"skipped_replayed={outcome.skipped_replayed} "
        f"skipped_no_envelope={outcome.skipped_no_envelope} "
        f"failed={outcome.failed}"
    )
    for line in outcome.messages:
        print(line)
    if outcome.failed:
        raise SystemExit(1)


def cmd_import_product_images(
    *,
    tenant_slug: str,
    zip_path: Path,
    actor_email: str,
    dry_run: bool,
) -> None:
    """Import product images using runtime DB role (stockpilot_app) + media volume."""
    # Ensure settings/engine use STOCKPILOT_DATABASE_URL (runtime role), not migrator.
    engine = get_engine()
    actor = resolve_import_actor(
        engine=engine,
        tenant_slug=tenant_slug,
        actor_email=actor_email,
    )
    # Confirm we are not on migrator (best-effort from URL username).
    db_url = str(engine.url)
    if "stockpilot_migrator" in db_url:
        raise SystemExit(
            "import-product-images refuses STOCKPILOT_DATABASE_URL with migrator role; "
            "use stockpilot_app"
        )
    db_role = "stockpilot_app"
    if "stockpilot_app" in db_url:
        db_role = "stockpilot_app"
    counters = import_product_images(
        engine=engine,
        actor=actor,
        zip_path=zip_path,
        dry_run=dry_run,
    )
    print(
        format_summary(
            counters=counters,
            actor=actor,
            dry_run=dry_run,
            db_role=db_role,
        ),
        flush=True,
    )
    if counters.failed:
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

    cleanup = sub.add_parser(
        "cleanup-test-tenants",
        help="Dev-only: remove leftover inv-*/rsv-* integration-test tenants",
    )
    cleanup.add_argument("--environment", default="development")

    seed_e2e = sub.add_parser(
        "seed-e2e",
        help="Dev/test-only: minimal idempotent fixtures for Playwright e2e",
    )
    seed_e2e.add_argument("--environment", default="development")

    backdate = sub.add_parser(
        "e2e-backdate-reservation",
        help="Dev/test-only: set RESERVED order expires_at in the past",
    )
    backdate.add_argument("--environment", default="development")
    backdate.add_argument("--order-id", required=True)

    balance = sub.add_parser("balance-check", help="Report stock ledger vs counter mismatches")
    balance.add_argument("--tenant-slug", default=None)

    sub.add_parser(
        "ensure-db-roles",
        help="Idempotent create/update stockpilot_relay + stockpilot_metrics",
    )

    img_import = sub.add_parser(
        "import-product-images",
        help="Import product images from zip+manifest for one tenant (runtime DB role)",
    )
    img_import.add_argument("--tenant", required=True, help="Tenant slug (e.g. aftab)")
    img_import.add_argument(
        "--zip",
        required=True,
        dest="zip_path",
        help="Path to zip inside container",
    )
    img_import.add_argument(
        "--actor-email",
        required=True,
        help="Existing admin or sales member email used for created_by + audit",
    )
    img_import.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report without writing images",
    )

    sub.add_parser(
        "queue-signals",
        help="Print platform.heartbeats rows and live Outbox lag (ops diagnostics)",
    )

    replay = sub.add_parser(
        "replay-failed-jobs",
        help="Republish failed_jobs envelopes (same event_id); dry-run unless --confirm",
    )
    replay.add_argument("--id", dest="job_id", default=None, help="Single failed_jobs id")
    replay.add_argument("--tenant-slug", default=None)
    replay.add_argument(
        "--include-replayed",
        action="store_true",
        help="Include rows with replayed_at set (default: skip them)",
    )
    replay.add_argument("--limit", type=int, default=20)
    replay.add_argument(
        "--replayed-by",
        default=None,
        help="Operator identity (required with --confirm)",
    )
    replay.add_argument(
        "--confirm",
        action="store_true",
        help="Publish and mark replayed (default is dry-run)",
    )

    args = parser.parse_args(argv)
    if args.command == "bootstrap":
        cmd_bootstrap(args.environment)
    elif args.command == "seed-demo":
        cmd_seed_demo(args.environment, Path(args.sample_path))
    elif args.command == "seed-e2e":
        cmd_seed_e2e(args.environment)
    elif args.command == "e2e-backdate-reservation":
        cmd_e2e_backdate_reservation(args.environment, args.order_id)
    elif args.command == "cleanup-test-tenants":
        cmd_cleanup_test_tenants(args.environment)
    elif args.command == "balance-check":
        cmd_balance_check(args.tenant_slug)
    elif args.command == "ensure-db-roles":
        cmd_ensure_db_roles()
    elif args.command == "import-product-images":
        cmd_import_product_images(
            tenant_slug=args.tenant,
            zip_path=Path(args.zip_path),
            actor_email=args.actor_email,
            dry_run=bool(args.dry_run),
        )
    elif args.command == "queue-signals":
        cmd_queue_signals()
    elif args.command == "replay-failed-jobs":
        cmd_replay_failed_jobs(
            job_id=args.job_id,
            tenant_slug=args.tenant_slug,
            include_replayed=bool(args.include_replayed),
            limit=int(args.limit),
            replayed_by=args.replayed_by,
            confirm=bool(args.confirm),
        )
    else:
        raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main(sys.argv[1:])
