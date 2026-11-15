"""Safe bulk import of product images from a zip + manifest.json (ops Run 6)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID
from zipfile import ZipFile, ZipInfo

from sqlalchemy.engine import Engine

from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.modules.access.domain.models import Role
from stockpilot.modules.catalog.adapters.outbound.image_service import (
    ImageServiceError,
    ProductImageService,
    prepare_image,
)
from stockpilot.modules.catalog.adapters.outbound.local_media import LocalMediaStorage
from stockpilot.modules.catalog.adapters.outbound.repo import CatalogRepository
from stockpilot.platform.persistence.uow import UnitOfWork
from stockpilot.platform.settings import get_settings

_WRITE_ROLES = frozenset({Role.ADMIN.value, Role.SALES.value})
_MAX_MANIFEST_ENTRIES = 500
_MAX_UNCOMPRESSED_TOTAL = 80 * 1024 * 1024  # 80 MiB
_MAX_SINGLE_FILE = 10 * 1024 * 1024  # 10 MiB (server still enforces image max)


@dataclass
class ImportCounters:
    imported: int = 0
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (sku, reason)
    failed: list[tuple[str, str]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ImportActor:
    user_id: UUID
    tenant_id: UUID
    role: str
    email: str
    tenant_slug: str


def resolve_import_actor(
    *,
    engine: Engine,
    tenant_slug: str,
    actor_email: str,
) -> ImportActor:
    """Resolve --actor-email under stockpilot_app RLS (no migrator).

    Membership existence is the active membership model (no status column).
    Actor must be admin or sales of the target tenant.
    """
    email = actor_email.strip()
    slug = tenant_slug.strip()
    if not email or not slug:
        raise SystemExit("tenant slug and --actor-email are required")

    with UnitOfWork(engine=engine) as uow:
        access = AccessRepository(uow.connection)
        user = access.get_user_by_email(email)
        if user is None:
            raise SystemExit(
                f"Actor not found: no user with email {email!r} (کاربر با این ایمیل یافت نشد)"
            )
        user_id = UUID(str(user["id"]))

    with UnitOfWork(engine=engine, user_id=user_id) as uow:
        access = AccessRepository(uow.connection)
        memberships = access.list_memberships_for_user(user_id)
        match = next((m for m in memberships if str(m["slug"]) == slug), None)
        if match is None:
            raise SystemExit(
                f"Actor {email!r} is not a member of tenant {slug!r} (کاربر عضو این سازمان نیست)"
            )
        role = str(match["role"])
        if role not in _WRITE_ROLES:
            raise SystemExit(
                f"Actor {email!r} has role {role!r} on {slug!r}; "
                f"import requires admin or sales "
                f"(فقط نقش مدیر یا فروش مجاز است)"
            )
        return ImportActor(
            user_id=user_id,
            tenant_id=UUID(str(match["tenant_id"])),
            role=role,
            email=email,
            tenant_slug=slug,
        )


def _normalize_zip_path(raw: str) -> str:
    path = raw.replace("\\", "/")
    # Do not use str.lstrip("./") — it strips any mix of '.' and '/' and can
    # turn "../evil.png" into "evil.png", hiding zip-slip.
    while path.startswith("./"):
        path = path[2:]
    if not path or path.startswith("/") or path.startswith("../"):
        raise SystemExit(f"Unsafe zip path rejected: {raw!r}")
    parts = tuple(p for p in path.split("/") if p not in ("", "."))
    if not parts or any(p == ".." for p in parts) or any(":" in p for p in parts):
        raise SystemExit(f"Unsafe zip path rejected: {raw!r}")
    return "/".join(parts)


def _assert_safe_zipinfo(info: ZipInfo, *, expected: str) -> None:
    name = info.filename.replace("\\", "/")
    normalized = _normalize_zip_path(name)
    if normalized != expected:
        raise SystemExit(f"Zip entry name mismatch for {expected!r}: {name!r}")
    if name.startswith("/") or name.startswith("\\") or ".." in Path(name).parts:
        raise SystemExit(f"Zip-slip path rejected: {name!r}")
    is_symlink = getattr(info, "is_symlink", None)
    if callable(is_symlink) and is_symlink():
        raise SystemExit(f"Symlink zip entry rejected: {name!r}")
    unix_mode = (info.external_attr >> 16) & 0o170000
    if unix_mode == 0o120000:  # S_IFLNK
        raise SystemExit(f"Symlink zip entry rejected: {name!r}")
    if info.file_size > _MAX_SINGLE_FILE:
        raise SystemExit(f"Zip entry too large ({info.file_size} bytes): {name!r}")


def load_manifest_entries(zf: ZipFile) -> list[dict[str, Any]]:
    try:
        raw = zf.read("manifest.json")
    except KeyError as exc:
        raise SystemExit("manifest.json missing from zip") from exc
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Invalid manifest.json: {exc}") from exc
    if not isinstance(data, list):
        raise SystemExit("manifest.json must be a JSON array")
    if len(data) > _MAX_MANIFEST_ENTRIES:
        raise SystemExit(f"manifest.json has {len(data)} entries; max {_MAX_MANIFEST_ENTRIES}")
    return data


def read_manifest_image(
    zf: ZipFile,
    *,
    image_file: str,
    names: set[str],
) -> bytes:
    rel = _normalize_zip_path(image_file)
    if rel not in names and rel + "/" not in names:
        # Exact member lookup
        pass
    try:
        info = zf.getinfo(rel)
    except KeyError:
        # Try forward-slash variants already normalized
        raise SystemExit(f"Manifest image missing from zip: {rel!r}") from None
    _assert_safe_zipinfo(info, expected=rel)
    data = zf.read(info)
    return data


def import_product_images(
    *,
    engine: Engine,
    actor: ImportActor,
    zip_path: Path,
    dry_run: bool = False,
    media_dir: Path | None = None,
) -> ImportCounters:
    settings = get_settings()
    storage_root = Path(media_dir) if media_dir is not None else Path(settings.media_dir)
    counters = ImportCounters()

    if not zip_path.is_file():
        raise SystemExit(f"Zip not found: {zip_path}")

    with ZipFile(zip_path, "r") as zf:
        # Reject absolute / slip in all namelist entries upfront for listed files only.
        namelist = zf.namelist()
        name_set = {_normalize_zip_path(n) for n in namelist if not n.endswith("/")}
        entries = load_manifest_entries(zf)

        total_uncompressed = 0
        for entry in entries:
            if not isinstance(entry, dict):
                raise SystemExit("Each manifest entry must be an object")
            sku = str(entry.get("sku") or "").strip()
            image_file = str(entry.get("image_file") or "").strip()
            if not sku or not image_file:
                counters.failed.append((sku or "?", "missing sku or image_file"))
                continue
            # Path safety failures abort the whole import (do not skip silently).
            rel = _normalize_zip_path(image_file)
            if rel not in name_set:
                counters.failed.append((sku, f"missing file {rel}"))
                continue
            info = zf.getinfo(rel)
            _assert_safe_zipinfo(info, expected=rel)
            total_uncompressed += info.file_size
            if total_uncompressed > _MAX_UNCOMPRESSED_TOTAL:
                raise SystemExit(f"Zip uncompressed size exceeds {_MAX_UNCOMPRESSED_TOTAL} bytes")

            if dry_run:
                # Resolve product only; do not write.
                with UnitOfWork(
                    engine=engine,
                    user_id=actor.user_id,
                    tenant_id=actor.tenant_id,
                    role=actor.role,
                ) as uow:
                    product = CatalogRepository(uow.connection).get_product_by_sku(
                        actor.tenant_id, sku
                    )
                if product is None:
                    counters.skipped.append((sku, "unknown_sku"))
                else:
                    counters.skipped.append((sku, "dry_run"))
                continue

            try:
                raw = read_manifest_image(zf, image_file=image_file, names=name_set)
            except SystemExit as exc:
                counters.failed.append((sku, str(exc)))
                continue

            service = ProductImageService(storage=LocalMediaStorage(storage_root))
            created_keys: list[str] = []
            try:
                prepared = prepare_image(
                    raw=raw,
                    tenant_id=actor.tenant_id,
                    processor=service.processor,
                )
            except ImageServiceError as exc:
                counters.failed.append((sku, exc.code))
                continue

            try:
                with UnitOfWork(
                    engine=engine,
                    user_id=actor.user_id,
                    tenant_id=actor.tenant_id,
                    role=actor.role,
                ) as uow:
                    catalog = CatalogRepository(uow.connection)
                    product = catalog.get_product_by_sku(actor.tenant_id, sku)
                    if product is None:
                        counters.skipped.append((sku, "unknown_sku"))
                        continue
                    product_id = UUID(str(product["id"]))
                    try:
                        service.add_prepared(
                            uow=uow,
                            tenant_id=actor.tenant_id,
                            product_id=product_id,
                            actor_user_id=actor.user_id,
                            prepared=prepared,
                            created_keys=created_keys,
                        )
                    except ImageServiceError as exc:
                        if exc.code == "IMAGE_DUPLICATE":
                            counters.skipped.append((sku, "IMAGE_DUPLICATE"))
                        elif exc.code == "IMAGE_LIMIT_REACHED":
                            counters.skipped.append((sku, "IMAGE_LIMIT_REACHED"))
                        else:
                            counters.failed.append((sku, exc.code))
                        continue
                counters.imported += 1
            except Exception as exc:  # noqa: BLE001 — report per-SKU failure
                if created_keys:
                    service.unlink_if_unreferenced(
                        tenant_id=actor.tenant_id,
                        keys=created_keys,
                        user_id=actor.user_id,
                    )
                counters.failed.append((sku, str(exc)))

    return counters


def format_summary(
    *,
    counters: ImportCounters,
    actor: ImportActor,
    dry_run: bool,
    db_role: str,
) -> str:
    lines = [
        "=== StockPilot product image import ===",
        f"tenant={actor.tenant_slug} actor={actor.email} role={actor.role}",
        f"db_role={db_role} dry_run={dry_run}",
        f"imported={counters.imported} "
        f"skipped={len(counters.skipped)} failed={len(counters.failed)}",
        f"وارد شده={counters.imported} "
        f"رد شده={len(counters.skipped)} ناموفق={len(counters.failed)}",
    ]
    for sku, reason in counters.skipped:
        lines.append(f"  skip {sku}: {reason}")
    for sku, reason in counters.failed:
        lines.append(f"  fail {sku}: {reason}")
    return "\n".join(lines)
