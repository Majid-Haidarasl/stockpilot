"""Integration: import-product-images under stockpilot_app + actor rules."""

from __future__ import annotations

import io
import json
import os
import zipfile
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from PIL import Image
from sqlalchemy import create_engine

from stockpilot.bootstrap.import_product_images import (
    import_product_images,
    resolve_import_actor,
)
from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.modules.access.domain.models import Role
from stockpilot.modules.catalog.adapters.outbound.image_repo import ProductImageRepository
from stockpilot.modules.catalog.adapters.outbound.repo import CatalogRepository
from stockpilot.platform.persistence.uow import UnitOfWork

pytestmark = pytest.mark.skipif(
    not os.environ.get("STOCKPILOT_DATABASE_URL")
    or not os.environ.get("STOCKPILOT_MIGRATION_DATABASE_URL"),
    reason="Database URLs not configured",
)


def _migrator():
    return create_engine(os.environ["STOCKPILOT_MIGRATION_DATABASE_URL"], pool_pre_ping=True)


def _runtime():
    return create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)


def _png(color: tuple[int, int, int] = (10, 20, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (80, 60), color).save(buf, format="PNG")
    return buf.getvalue()


def _seed_org(
    *,
    role: Role = Role.ADMIN,
    email: str | None = None,
) -> tuple[UUID, UUID, str, str]:
    slug = f"imp-{uuid4().hex[:8]}"
    actor_email = email or f"{slug}@test.local"
    with UnitOfWork(engine=_migrator()) as uow:
        access = AccessRepository(uow.connection)
        tenant_id = access.ensure_tenant(slug=slug, name=f"Import {slug}")
        user_id = access.upsert_user(
            issuer="test-issuer",
            subject=f"imp-{uuid4()}",
            email=actor_email,
            display_name="Importer",
        )
        access.ensure_membership(tenant_id=tenant_id, user_id=user_id, role=role)
        CatalogRepository(uow.connection).create_product(
            tenant_id=tenant_id,
            sku="IMP-SKU-1",
            title="Import Product",
            unit_price_rial=1000,
        )
    return tenant_id, user_id, slug, actor_email


def _make_zip(path: Path, *, sku: str = "IMP-SKU-1", extra_sku: str | None = None) -> None:
    png = _png()
    manifest = [{"sku": sku, "image_file": f"images/{sku}.png"}]
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr(f"images/{sku}.png", png)
        if extra_sku:
            zf.writestr(
                "manifest.json",
                json.dumps(
                    [
                        {"sku": sku, "image_file": f"images/{sku}.png"},
                        {"sku": extra_sku, "image_file": f"images/{extra_sku}.png"},
                    ]
                ),
            )
            zf.writestr(f"images/{extra_sku}.png", _png((90, 90, 10)))


def test_resolve_actor_not_a_member() -> None:
    tenant_id, _user_id, slug, _email = _seed_org(role=Role.ADMIN)
    with UnitOfWork(engine=_migrator()) as uow:
        access = AccessRepository(uow.connection)
        outsider_email = f"out-{uuid4().hex[:6]}@test.local"
        access.upsert_user(
            issuer="test-issuer",
            subject=f"out-{uuid4()}",
            email=outsider_email,
            display_name="Outsider",
        )
    with pytest.raises(SystemExit, match="not a member|عضو"):
        resolve_import_actor(
            engine=_runtime(),
            tenant_slug=slug,
            actor_email=outsider_email,
        )
    del tenant_id


def test_resolve_actor_viewer_rejected() -> None:
    _tenant_id, _user_id, slug, email = _seed_org(role=Role.VIEWER)
    with pytest.raises(SystemExit, match="admin or sales|مدیر یا فروش"):
        resolve_import_actor(
            engine=_runtime(),
            tenant_slug=slug,
            actor_email=email,
        )


def test_import_success_unknown_sku_duplicate_dry_run(tmp_path: Path) -> None:
    tenant_id, user_id, slug, email = _seed_org(role=Role.SALES)
    media = tmp_path / "media"
    media.mkdir()
    zip_path = tmp_path / "imgs.zip"
    png = _png()
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(
            "manifest.json",
            json.dumps(
                [
                    {"sku": "IMP-SKU-1", "image_file": "images/IMP-SKU-1.png"},
                    {"sku": "UNKNOWN-SKU", "image_file": "images/UNKNOWN-SKU.png"},
                ]
            ),
        )
        zf.writestr("images/IMP-SKU-1.png", png)
        zf.writestr("images/UNKNOWN-SKU.png", _png((1, 1, 1)))

    actor = resolve_import_actor(
        engine=_runtime(),
        tenant_slug=slug,
        actor_email=email,
    )
    assert actor.user_id == user_id
    assert actor.tenant_id == tenant_id
    assert actor.role == Role.SALES.value

    dry = import_product_images(
        engine=_runtime(),
        actor=actor,
        zip_path=zip_path,
        dry_run=True,
        media_dir=media,
    )
    assert dry.imported == 0
    assert any(s == "IMP-SKU-1" and r == "dry_run" for s, r in dry.skipped)
    assert list(media.iterdir()) == []

    first = import_product_images(
        engine=_runtime(),
        actor=actor,
        zip_path=zip_path,
        dry_run=False,
        media_dir=media,
    )
    assert first.imported == 1
    assert any(s == "UNKNOWN-SKU" and r == "unknown_sku" for s, r in first.skipped)

    with UnitOfWork(
        engine=_runtime(),
        user_id=user_id,
        tenant_id=tenant_id,
        role=Role.SALES.value,
    ) as uow:
        product = CatalogRepository(uow.connection).get_product_by_sku(tenant_id, "IMP-SKU-1")
        assert product is not None
        rows = ProductImageRepository(uow.connection).list_for_product(
            tenant_id, UUID(str(product["id"]))
        )
        assert len(rows) == 1
        assert rows[0]["created_by"] == user_id

    second = import_product_images(
        engine=_runtime(),
        actor=actor,
        zip_path=zip_path,
        dry_run=False,
        media_dir=media,
    )
    assert second.imported == 0
    assert any(s == "IMP-SKU-1" and r == "IMAGE_DUPLICATE" for s, r in second.skipped)


def test_import_rejects_zip_slip_path(tmp_path: Path) -> None:
    _tenant_id, _user_id, slug, email = _seed_org(role=Role.ADMIN)
    media = tmp_path / "media"
    media.mkdir()
    zip_path = tmp_path / "slip.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(
            "manifest.json",
            json.dumps([{"sku": "IMP-SKU-1", "image_file": "../evil.png"}]),
        )
        info = zipfile.ZipInfo("../evil.png")
        zf.writestr(info, _png())

    actor = resolve_import_actor(
        engine=_runtime(),
        tenant_slug=slug,
        actor_email=email,
    )
    with pytest.raises(SystemExit, match="Unsafe|Zip-slip|Absolute"):
        # Fail during path normalize of manifest image_file before/while processing
        import_product_images(
            engine=_runtime(),
            actor=actor,
            zip_path=zip_path,
            dry_run=False,
            media_dir=media,
        )
