"""Operator bootstrap / seed commands (runs as migrator DB role)."""

from __future__ import annotations

import argparse
import os
import sys
from uuid import UUID

from sqlalchemy import Engine, create_engine

from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.modules.access.domain.models import Role
from stockpilot.platform.persistence.uow import UnitOfWork
from stockpilot.platform.settings import get_settings

DEMO_ORGS = (
    {"slug": "aftab", "name": "Aftab"},
    {"slug": "baran", "name": "Baran"},
)

# Keycloak subjects are filled after first login unless pre-seeded by issuer/subject.
# For week-2 demo, bootstrap links by email once users exist, or creates placeholder
# mappings when STOCKPILOT_BOOTSTRAP_SUBJECTS is provided.
DEMO_LINKS = (
    # org slug, email, role, optional subject override env key
    ("aftab", "admin@aftab.test", Role.ADMIN, "STOCKPILOT_SUBJECT_AFTAB_ADMIN"),
    ("aftab", "sales@aftab.test", Role.SALES, "STOCKPILOT_SUBJECT_AFTAB_SALES"),
    ("aftab", "warehouse@aftab.test", Role.WAREHOUSE, "STOCKPILOT_SUBJECT_AFTAB_WAREHOUSE"),
    ("baran", "admin@baran.test", Role.ADMIN, "STOCKPILOT_SUBJECT_BARAN_ADMIN"),
    ("baran", "viewer@baran.test", Role.VIEWER, "STOCKPILOT_SUBJECT_BARAN_VIEWER"),
)


def _migration_engine() -> Engine:
    url = os.environ.get("STOCKPILOT_MIGRATION_DATABASE_URL")
    if not url:
        raise SystemExit("STOCKPILOT_MIGRATION_DATABASE_URL is required for ops")
    return create_engine(url, pool_pre_ping=True)


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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="stockpilot-ops")
    sub = parser.add_subparsers(dest="command", required=True)

    boot = sub.add_parser("bootstrap", help="Idempotent org/user membership bootstrap")
    boot.add_argument("--environment", default="development")

    args = parser.parse_args(argv)
    if args.command == "bootstrap":
        cmd_bootstrap(args.environment)
    else:
        raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main(sys.argv[1:])
