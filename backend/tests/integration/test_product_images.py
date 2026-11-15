"""Product images: upload, isolation, primary rules, shared files, migration."""

from __future__ import annotations

import io
import os
import subprocess
import threading
import time
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, text

from stockpilot.bootstrap.app import create_app
from stockpilot.modules.access.adapters.inbound.deps import (
    SessionPrincipal,
    require_actor,
    require_csrf,
    require_session,
)
from stockpilot.modules.access.adapters.outbound.repo import AccessRepository
from stockpilot.modules.access.domain.models import ActorContext, Role
from stockpilot.modules.catalog.adapters.outbound.image_service import (
    ProductImageService,
    prepare_image,
)
from stockpilot.modules.catalog.adapters.outbound.local_media import LocalMediaStorage
from stockpilot.modules.catalog.adapters.outbound.repo import CatalogRepository
from stockpilot.platform.persistence.uow import UnitOfWork
from stockpilot.platform.security.crypto import hash_token

pytestmark = pytest.mark.skipif(
    not os.environ.get("STOCKPILOT_DATABASE_URL")
    or not os.environ.get("STOCKPILOT_MIGRATION_DATABASE_URL"),
    reason="Database URLs not configured",
)


def _migrator():
    return create_engine(os.environ["STOCKPILOT_MIGRATION_DATABASE_URL"], pool_pre_ping=True)


def _runtime():
    return create_engine(os.environ["STOCKPILOT_DATABASE_URL"], pool_pre_ping=True)


def _seed(role: Role = Role.SALES) -> tuple[UUID, UUID, ActorContext]:
    with UnitOfWork(engine=_migrator()) as uow:
        access = AccessRepository(uow.connection)
        tenant_id = access.ensure_tenant(slug=f"img-{uuid4().hex[:8]}", name="Img Org")
        user_id = access.upsert_user(
            issuer="test-issuer",
            subject=f"img-{uuid4()}",
            email=f"img-{uuid4().hex}@test",
            display_name="Img",
        )
        access.ensure_membership(tenant_id=tenant_id, user_id=user_id, role=role)
    actor = ActorContext(
        user_id=user_id,
        tenant_id=tenant_id,
        role=role,
        issuer="test-issuer",
        subject="img",
    )
    return tenant_id, user_id, actor


def _product(tenant_id: UUID, user_id: UUID, sku: str | None = None) -> dict:
    with UnitOfWork(engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin") as uow:
        return CatalogRepository(uow.connection).create_product(
            tenant_id=tenant_id,
            sku=sku or f"SKU-{uuid4().hex[:6]}",
            title="Image Product",
            unit_price_rial=1000,
        )


def _client(actor: ActorContext) -> TestClient:
    app = create_app()
    app.dependency_overrides[require_actor] = lambda: actor
    app.dependency_overrides[require_csrf] = lambda: None
    return TestClient(app)


def _png(width: int = 120, height: int = 80, color: tuple[int, int, int] = (10, 20, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (90, 90), (1, 2, 3)).save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _webp() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (70, 40), (9, 8, 7)).save(buf, format="WEBP", quality=80)
    return buf.getvalue()


def _upload(
    client: TestClient,
    tenant_id: UUID,
    product_id: UUID,
    data: bytes,
    *,
    filename: str = "photo.png",
    content_type: str = "image/png",
    key: str | None = None,
) -> object:
    return client.post(
        f"/api/v1/tenants/{tenant_id}/products/{product_id}/images",
        files={"file": (filename, data, content_type)},
        headers={"Idempotency-Key": key or str(uuid4())},
    )


def test_upload_png_jpeg_webp_become_webp_800_200(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media = tmp_path / "media"
    media.mkdir()
    monkeypatch.setenv("STOCKPILOT_MEDIA_DIR", str(media))
    # Reset settings cache if any — Settings() reads env each call via get_settings.
    from stockpilot.platform import settings as settings_mod

    monkeypatch.setattr(settings_mod, "get_settings", lambda: settings_mod.Settings())

    tenant_id, user_id, actor = _seed(Role.ADMIN)
    product = _product(tenant_id, user_id)
    client = _client(actor)

    for raw, name, ctype in (
        (_png(), "a.png", "image/png"),
        (_jpeg(), "b.jpg", "image/jpeg"),
        (_webp(), "c.webp", "image/webp"),
    ):
        response = _upload(client, tenant_id, product["id"], raw, filename=name, content_type=ctype)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["content_type"] == "image/webp"
        assert body["width"] == 800
        assert body["height"] == 800
        file_resp = client.get(body["url"])
        thumb_resp = client.get(body["thumbnail_url"])
        assert file_resp.status_code == 200
        assert thumb_resp.status_code == 200
        assert file_resp.headers["content-type"] == "image/webp"
        assert file_resp.headers["x-content-type-options"] == "nosniff"
        assert "private" in file_resp.headers["cache-control"]
        main = Image.open(io.BytesIO(file_resp.content))
        thumb = Image.open(io.BytesIO(thumb_resp.content))
        assert main.size == (800, 800)
        assert thumb.size == (200, 200)


def test_reject_fake_extension_too_big_sixth_viewer_csrf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media = tmp_path / "media"
    media.mkdir()
    monkeypatch.setenv("STOCKPILOT_MEDIA_DIR", str(media))
    monkeypatch.setenv("STOCKPILOT_IMAGE_MAX_BYTES", "200")
    from stockpilot.platform import settings as settings_mod

    monkeypatch.setattr(settings_mod, "get_settings", lambda: settings_mod.Settings())

    tenant_id, user_id, actor = _seed(Role.SALES)
    product = _product(tenant_id, user_id)
    client = _client(actor)

    fake = _upload(
        client,
        tenant_id,
        product["id"],
        b"definitely-not-an-image",
        filename="lie.jpg",
        content_type="image/jpeg",
    )
    assert fake.status_code == 422
    assert fake.json()["code"] == "IMAGE_TYPE_NOT_ALLOWED"

    huge = _upload(client, tenant_id, product["id"], _png(400, 400))
    assert huge.status_code == 422
    assert huge.json()["code"] == "IMAGE_TOO_LARGE"

    # Fresh settings with normal byte limit for sixth-image / role tests
    monkeypatch.setenv("STOCKPILOT_IMAGE_MAX_BYTES", "5242880")
    monkeypatch.setattr(settings_mod, "get_settings", lambda: settings_mod.Settings())
    tenant2, user2, actor2 = _seed(Role.SALES)
    product2 = _product(tenant2, user2)
    client2 = _client(actor2)
    colors = (
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 0),
        (255, 0, 255),
    )
    for color in colors:
        ok = _upload(client2, tenant2, product2["id"], _png(color=color))
        assert ok.status_code == 201, ok.text
    sixth = _upload(client2, tenant2, product2["id"], _png(color=(0, 255, 255)))
    assert sixth.status_code == 409
    assert sixth.json()["code"] == "IMAGE_LIMIT_REACHED"

    tenant_v, user_v, viewer = _seed(Role.VIEWER)
    product_v = _product(tenant_v, user_v)
    viewer_client = _client(viewer)
    denied = _upload(viewer_client, tenant_v, product_v["id"], _png())
    assert denied.status_code == 403
    assert denied.json()["code"] == "FORBIDDEN"

    # CSRF: session present, real require_csrf, missing X-CSRF-Token → 403
    app = create_app()
    app.dependency_overrides[require_actor] = lambda: actor2
    app.dependency_overrides[require_session] = lambda: SessionPrincipal(
        session_id=uuid4(),
        user_id=actor2.user_id,
        issuer="test-issuer",
        subject="img",
        email=None,
        display_name=None,
        csrf_token_hash=hash_token("expected-csrf"),
    )
    csrf_client = TestClient(app)
    csrf = csrf_client.post(
        f"/api/v1/tenants/{tenant2}/products/{product2['id']}/images",
        files={"file": ("x.png", _png(), "image/png")},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert csrf.status_code == 403


def test_pixel_bomb_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    media = tmp_path / "media"
    media.mkdir()
    monkeypatch.setenv("STOCKPILOT_MEDIA_DIR", str(media))
    monkeypatch.setenv("STOCKPILOT_IMAGE_MAX_PIXELS", "50")
    from stockpilot.platform import settings as settings_mod

    monkeypatch.setattr(settings_mod, "get_settings", lambda: settings_mod.Settings())
    tenant_id, user_id, actor = _seed(Role.ADMIN)
    product = _product(tenant_id, user_id)
    response = _upload(_client(actor), tenant_id, product["id"], _png(40, 40))
    assert response.status_code == 422
    assert response.json()["code"] == "IMAGE_DIMENSIONS_TOO_LARGE"


def test_tenant_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    media = tmp_path / "media"
    media.mkdir()
    monkeypatch.setenv("STOCKPILOT_MEDIA_DIR", str(media))
    from stockpilot.platform import settings as settings_mod

    monkeypatch.setattr(settings_mod, "get_settings", lambda: settings_mod.Settings())

    tenant_a, user_a, actor_a = _seed(Role.ADMIN)
    tenant_b, _user_b, actor_b = _seed(Role.ADMIN)
    product_a = _product(tenant_a, user_a)
    uploaded = _upload(_client(actor_a), tenant_a, product_a["id"], _png())
    assert uploaded.status_code == 201
    image_id = uploaded.json()["id"]
    client_b = _client(actor_b)

    assert (
        client_b.get(f"/api/v1/tenants/{tenant_b}/products/{product_a['id']}/images").status_code
        == 404
    )
    assert client_b.get(f"/api/v1/tenants/{tenant_b}/images/{image_id}/file").status_code == 404
    assert (
        client_b.get(f"/api/v1/tenants/{tenant_b}/images/{image_id}/thumbnail").status_code == 404
    )
    assert (
        client_b.post(
            f"/api/v1/tenants/{tenant_b}/images/{image_id}/primary",
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code
        == 404
    )
    assert (
        client_b.delete(
            f"/api/v1/tenants/{tenant_b}/images/{image_id}",
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code
        == 404
    )


def test_primary_rules_and_promote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    media = tmp_path / "media"
    media.mkdir()
    monkeypatch.setenv("STOCKPILOT_MEDIA_DIR", str(media))
    from stockpilot.platform import settings as settings_mod

    monkeypatch.setattr(settings_mod, "get_settings", lambda: settings_mod.Settings())

    tenant_id, user_id, actor = _seed(Role.ADMIN)
    product = _product(tenant_id, user_id)
    client = _client(actor)
    first = _upload(client, tenant_id, product["id"], _png(color=(1, 1, 1)))
    second = _upload(client, tenant_id, product["id"], _png(color=(2, 2, 2)))
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["is_primary"] is True
    assert second.json()["is_primary"] is False

    set_primary = client.post(
        f"/api/v1/tenants/{tenant_id}/images/{second.json()['id']}/primary",
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert set_primary.status_code == 200
    assert set_primary.json()["is_primary"] is True
    listed = client.get(f"/api/v1/tenants/{tenant_id}/products/{product['id']}/images")
    primaries = [row for row in listed.json() if row["is_primary"]]
    assert len(primaries) == 1
    assert primaries[0]["id"] == second.json()["id"]

    deleted = client.delete(
        f"/api/v1/tenants/{tenant_id}/images/{second.json()['id']}",
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert deleted.status_code == 204
    listed2 = client.get(f"/api/v1/tenants/{tenant_id}/products/{product['id']}/images")
    assert len(listed2.json()) == 1
    assert listed2.json()[0]["is_primary"] is True
    assert listed2.json()[0]["id"] == first.json()["id"]


def test_idempotent_upload_no_duplicate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    media = tmp_path / "media"
    media.mkdir()
    monkeypatch.setenv("STOCKPILOT_MEDIA_DIR", str(media))
    from stockpilot.platform import settings as settings_mod

    monkeypatch.setattr(settings_mod, "get_settings", lambda: settings_mod.Settings())

    tenant_id, user_id, actor = _seed(Role.ADMIN)
    product = _product(tenant_id, user_id)
    client = _client(actor)
    key = str(uuid4())
    raw = _png()
    first = _upload(client, tenant_id, product["id"], raw, key=key)
    second = _upload(client, tenant_id, product["id"], raw, key=key)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    listed = client.get(f"/api/v1/tenants/{tenant_id}/products/{product['id']}/images")
    assert len(listed.json()) == 1


def test_duplicate_same_product_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    media = tmp_path / "media"
    media.mkdir()
    monkeypatch.setenv("STOCKPILOT_MEDIA_DIR", str(media))
    from stockpilot.platform import settings as settings_mod

    monkeypatch.setattr(settings_mod, "get_settings", lambda: settings_mod.Settings())

    tenant_id, user_id, actor = _seed(Role.ADMIN)
    product = _product(tenant_id, user_id)
    client = _client(actor)
    raw = _png(color=(44, 55, 66))
    assert _upload(client, tenant_id, product["id"], raw).status_code == 201
    dup = _upload(client, tenant_id, product["id"], raw)
    assert dup.status_code == 409
    assert dup.json()["code"] == "IMAGE_DUPLICATE"


def test_shared_file_survives_delete_and_failed_upload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media = tmp_path / "media"
    media.mkdir()
    monkeypatch.setenv("STOCKPILOT_MEDIA_DIR", str(media))
    from stockpilot.platform import settings as settings_mod

    monkeypatch.setattr(settings_mod, "get_settings", lambda: settings_mod.Settings())

    tenant_id, user_id, actor = _seed(Role.ADMIN)
    product_a = _product(tenant_id, user_id, sku="SHARE-A")
    product_b = _product(tenant_id, user_id, sku="SHARE-B")
    client = _client(actor)
    raw = _png(color=(77, 88, 99))
    up_a = _upload(client, tenant_id, product_a["id"], raw)
    up_b = _upload(client, tenant_id, product_b["id"], raw)
    assert up_a.status_code == 201
    assert up_b.status_code == 201
    assert up_a.json()["sha256"] == up_b.json()["sha256"]

    deleted = client.delete(
        f"/api/v1/tenants/{tenant_id}/images/{up_a.json()['id']}",
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert deleted.status_code == 204
    assert client.get(up_b.json()["url"]).status_code == 200
    assert client.get(up_b.json()["thumbnail_url"]).status_code == 200

    # Failed upload of already-used image (duplicate on B) must not remove file.
    dup = _upload(client, tenant_id, product_b["id"], raw)
    assert dup.status_code == 409
    assert client.get(up_b.json()["url"]).status_code == 200


def test_shared_content_advisory_lock_interleavings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two connections: rollback-cleanup vs uncommitted upload, and delete-cleanup vs upload."""
    media = tmp_path / "media"
    media.mkdir()
    monkeypatch.setenv("STOCKPILOT_MEDIA_DIR", str(media))
    from stockpilot.platform import settings as settings_mod

    monkeypatch.setattr(settings_mod, "get_settings", lambda: settings_mod.Settings())

    tenant_id, user_id, actor = _seed(Role.ADMIN)
    product_a = _product(tenant_id, user_id, sku="RACE-A")
    product_b = _product(tenant_id, user_id, sku="RACE-B")
    client = _client(actor)
    raw = _png(color=(12, 34, 56))
    service = ProductImageService(storage=LocalMediaStorage(media))
    prepared = prepare_image(raw=raw, tenant_id=tenant_id, processor=service.processor)

    # --- Interleaving 1: P1 creates file then rolls back; P2 upload overlaps ---
    errors: list[BaseException] = []
    p1_put_done = threading.Event()

    def p1_create_then_rollback() -> None:
        created: list[str] = []
        try:
            with UnitOfWork(
                engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin"
            ) as uow:
                service.add_prepared(
                    uow=uow,
                    tenant_id=tenant_id,
                    product_id=UUID(str(product_a["id"])),
                    actor_user_id=user_id,
                    prepared=prepared,
                    created_keys=created,
                )
                p1_put_done.set()
                raise RuntimeError("force rollback")
        except RuntimeError:
            # Contends with P2 for the content advisory lock.
            service.unlink_if_unreferenced(tenant_id=tenant_id, keys=created, user_id=user_id)
        except BaseException as exc:  # noqa: BLE001 — collect for main thread
            errors.append(exc)

    def p2_upload_and_commit() -> None:
        created: list[str] = []
        try:
            assert p1_put_done.wait(timeout=10)
            with UnitOfWork(
                engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin"
            ) as uow:
                service.add_prepared(
                    uow=uow,
                    tenant_id=tenant_id,
                    product_id=UUID(str(product_b["id"])),
                    actor_user_id=user_id,
                    prepared=prepared,
                    created_keys=created,
                )
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    t1 = threading.Thread(target=p1_create_then_rollback)
    t2 = threading.Thread(target=p2_upload_and_commit)
    t1.start()
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)
    assert not errors, errors

    listed_b = client.get(f"/api/v1/tenants/{tenant_id}/products/{product_b['id']}/images")
    assert listed_b.status_code == 200
    assert len(listed_b.json()) == 1
    row_b = listed_b.json()[0]
    assert client.get(row_b["url"]).status_code == 200
    assert client.get(row_b["thumbnail_url"]).status_code == 200

    # --- Interleaving 2: delete last committed row while upload of same sha is open ---
    product_c = _product(tenant_id, user_id, sku="RACE-C")
    del_ready = threading.Event()
    upload_hold = threading.Event()
    errors.clear()

    def upload_c_hold_open() -> None:
        created: list[str] = []
        try:
            with UnitOfWork(
                engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin"
            ) as uow:
                service.add_prepared(
                    uow=uow,
                    tenant_id=tenant_id,
                    product_id=UUID(str(product_c["id"])),
                    actor_user_id=user_id,
                    prepared=prepared,
                    created_keys=created,
                )
                del_ready.set()
                assert upload_hold.wait(timeout=15)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    def delete_b_then_cleanup() -> None:
        try:
            assert del_ready.wait(timeout=10)
            image_id = UUID(str(row_b["id"]))
            keys: list[str] = []
            with UnitOfWork(
                engine=_runtime(), user_id=user_id, tenant_id=tenant_id, role="admin"
            ) as uow:
                _deleted, keys = service.delete(
                    uow=uow,
                    tenant_id=tenant_id,
                    image_id=image_id,
                    actor_user_id=user_id,
                )
            cleanup_done = threading.Event()

            def cleanup() -> None:
                try:
                    service.unlink_if_unreferenced(tenant_id=tenant_id, keys=keys, user_id=user_id)
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)
                finally:
                    cleanup_done.set()

            threading.Thread(target=cleanup).start()
            # Let cleanup block on the content advisory lock held by upload_c.
            time.sleep(0.3)
            upload_hold.set()
            assert cleanup_done.wait(timeout=15)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
            upload_hold.set()

    t3 = threading.Thread(target=upload_c_hold_open)
    t4 = threading.Thread(target=delete_b_then_cleanup)
    t3.start()
    t4.start()
    t3.join(timeout=30)
    t4.join(timeout=30)
    assert not errors, errors

    listed_c = client.get(f"/api/v1/tenants/{tenant_id}/products/{product_c['id']}/images")
    assert listed_c.status_code == 200
    assert len(listed_c.json()) == 1
    row_c = listed_c.json()[0]
    assert client.get(row_c["url"]).status_code == 200
    assert client.get(row_c["thumbnail_url"]).status_code == 200


def test_primary_thumbnail_on_product_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    media = tmp_path / "media"
    media.mkdir()
    monkeypatch.setenv("STOCKPILOT_MEDIA_DIR", str(media))
    from stockpilot.platform import settings as settings_mod

    monkeypatch.setattr(settings_mod, "get_settings", lambda: settings_mod.Settings())

    tenant_id, user_id, actor = _seed(Role.ADMIN)
    product = _product(tenant_id, user_id)
    client = _client(actor)
    before = client.get(f"/api/v1/tenants/{tenant_id}/products")
    assert before.status_code == 200
    match = next(p for p in before.json() if p["id"] == str(product["id"]))
    assert match["primary_thumbnail_url"] is None

    uploaded = _upload(client, tenant_id, product["id"], _png())
    assert uploaded.status_code == 201
    after = client.get(f"/api/v1/tenants/{tenant_id}/products")
    match2 = next(p for p in after.json() if p["id"] == str(product["id"]))
    assert match2["primary_thumbnail_url"] == uploaded.json()["thumbnail_url"]


def test_migration_up_down_preserves_products() -> None:
    """Downgrade/upgrade 0009 on stockpilot_test only; restore head in finally."""
    migrator_url = os.environ["STOCKPILOT_MIGRATION_DATABASE_URL"]
    backend_root = Path(__file__).resolve().parents[2]
    with UnitOfWork(engine=_migrator()) as uow:
        access = AccessRepository(uow.connection)
        tenant_id = access.ensure_tenant(slug=f"mig-{uuid4().hex[:8]}", name="Mig Org")
        user_id = access.upsert_user(
            issuer="test-issuer",
            subject=f"mig-{uuid4()}",
            email=f"mig-{uuid4().hex}@test",
            display_name="Mig",
        )
        access.ensure_membership(tenant_id=tenant_id, user_id=user_id, role=Role.ADMIN)
        product = CatalogRepository(uow.connection).create_product(
            tenant_id=tenant_id,
            sku=f"MIG-{uuid4().hex[:6]}",
            title="Keep Me",
            unit_price_rial=1,
        )
        product_id = str(product["id"])

    env = {**os.environ, "STOCKPILOT_MIGRATION_DATABASE_URL": migrator_url}
    try:
        down = subprocess.run(
            ["alembic", "downgrade", "0008_audit_log_seq"],
            cwd=backend_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert down.returncode == 0, down.stderr
        with UnitOfWork(engine=_migrator()) as uow:
            exists = uow.connection.execute(
                text("SELECT 1 FROM catalog.products WHERE id = :id"),
                {"id": product_id},
            ).first()
            assert exists is not None
            table = uow.connection.execute(
                text(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'catalog' AND table_name = 'product_images'
                    """
                )
            ).first()
            assert table is None
        up = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=backend_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert up.returncode == 0, up.stderr
        with UnitOfWork(engine=_migrator()) as uow:
            table = uow.connection.execute(
                text(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'catalog' AND table_name = 'product_images'
                    """
                )
            ).first()
            assert table is not None
            exists = uow.connection.execute(
                text("SELECT 1 FROM catalog.products WHERE id = :id"),
                {"id": product_id},
            ).first()
            assert exists is not None
    finally:
        subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=backend_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
