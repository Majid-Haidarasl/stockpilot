"""Product image use cases shared by HTTP and future bulk import (Run 6)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from stockpilot.modules.catalog.adapters.outbound.image_repo import ProductImageRepository
from stockpilot.modules.catalog.adapters.outbound.pillow_images import (
    ImageValidationError,
    PillowImageProcessor,
)
from stockpilot.modules.catalog.application.ports import ImageProcessor, ObjectStorage
from stockpilot.platform.persistence.uow import UnitOfWork


class ImageServiceError(Exception):
    def __init__(self, code: str, title: str, *, status: int = 422) -> None:
        self.code = code
        self.title = title
        self.status = status
        super().__init__(title)


@dataclass(frozen=True, slots=True)
class PreparedImage:
    main_bytes: bytes
    thumb_bytes: bytes
    width: int
    height: int
    sha256: str
    storage_key: str
    thumb_key: str
    size_bytes: int


def prepare_image(
    *,
    raw: bytes,
    tenant_id: UUID,
    processor: ImageProcessor,
) -> PreparedImage:
    """Validate and re-encode outside any DB lock."""
    try:
        normalized = processor.normalize(raw)
    except ImageValidationError as exc:
        raise ImageServiceError(exc.code, exc.title, status=422) from exc
    return PreparedImage(
        main_bytes=normalized.main_bytes,
        thumb_bytes=normalized.thumb_bytes,
        width=normalized.width,
        height=normalized.height,
        sha256=normalized.sha256,
        storage_key=f"{tenant_id}/{normalized.sha256}.webp",
        thumb_key=f"{tenant_id}/{normalized.sha256}.thumb.webp",
        size_bytes=len(normalized.main_bytes),
    )


class ProductImageService:
    """Coordinates DB rows and storage for product images.

    Call prepare_image() before opening a UnitOfWork. Hold the product row lock
    only for count/insert/audit (and for primary/reorder/delete mutations).
    """

    def __init__(
        self,
        *,
        storage: ObjectStorage,
        processor: ImageProcessor | None = None,
        max_bytes: int = 5_242_880,
        max_pixels: int = 24_000_000,
    ) -> None:
        self._storage = storage
        self._processor = processor or PillowImageProcessor(
            max_bytes=max_bytes, max_pixels=max_pixels
        )

    @property
    def processor(self) -> ImageProcessor:
        return self._processor

    def add_prepared(
        self,
        *,
        uow: UnitOfWork,
        tenant_id: UUID,
        product_id: UUID,
        actor_user_id: UUID,
        prepared: PreparedImage,
        created_keys: list[str],
    ) -> dict[str, Any]:
        """Insert image under product lock and write storage.

        Appends newly created storage keys to created_keys. Caller must, after
        a UnitOfWork that did not successfully finish the upload, call
        unlink_if_unreferenced so a concurrent commit that reused the same
        content-addressed file is not deleted.
        """
        repo = ProductImageRepository(uow.connection)
        product = repo.lock_product(tenant_id, product_id)
        if product is None:
            raise ImageServiceError("NOT_FOUND", "Not found", status=404)
        if repo.count_for_product(tenant_id, product_id) >= 5:
            raise ImageServiceError(
                "IMAGE_LIMIT_REACHED",
                "A product may have at most 5 images",
                status=409,
            )
        if repo.find_by_sha(tenant_id, product_id, prepared.sha256) is not None:
            raise ImageServiceError(
                "IMAGE_DUPLICATE",
                "This image is already registered for this product",
                status=409,
            )

        is_primary = repo.count_for_product(tenant_id, product_id) == 0
        sort_order = 0 if is_primary else repo.next_sort_order(tenant_id, product_id)
        row = repo.insert(
            tenant_id=tenant_id,
            product_id=product_id,
            storage_key=prepared.storage_key,
            thumb_key=prepared.thumb_key,
            content_type="image/webp",
            width=prepared.width,
            height=prepared.height,
            size_bytes=prepared.size_bytes,
            sha256=prepared.sha256,
            is_primary=is_primary,
            sort_order=sort_order,
            created_by=actor_user_id,
        )
        repo.write_audit(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action_type="product.image_added",
            entity_id=product_id,
            payload={"image_id": str(row["id"]), "sha256": prepared.sha256},
        )

        # Product row lock first, then content advisory lock, then put.
        # Holds until this transaction ends so concurrent unlink waits.
        repo.lock_content_sha(tenant_id, prepared.sha256)

        # Do not delete inside this transaction: our uncommitted insert would
        # make key_referenced true. Cleanup happens after UoW rollback.
        main_put = self._storage.put(
            prepared.storage_key, prepared.main_bytes, content_type="image/webp"
        )
        if main_put.created:
            created_keys.append(prepared.storage_key)
        thumb_put = self._storage.put(
            prepared.thumb_key, prepared.thumb_bytes, content_type="image/webp"
        )
        if thumb_put.created:
            created_keys.append(prepared.thumb_key)
        return row

    def set_primary(
        self,
        *,
        uow: UnitOfWork,
        tenant_id: UUID,
        image_id: UUID,
        actor_user_id: UUID,
    ) -> dict[str, Any]:
        repo = ProductImageRepository(uow.connection)
        current = repo.get(tenant_id, image_id)
        if current is None:
            raise ImageServiceError("NOT_FOUND", "Not found", status=404)
        product_id = UUID(str(current["product_id"]))
        if repo.lock_product(tenant_id, product_id) is None:
            raise ImageServiceError("NOT_FOUND", "Not found", status=404)
        repo.clear_primary(tenant_id, product_id)
        updated = repo.set_primary(tenant_id, image_id)
        if updated is None:
            raise ImageServiceError("NOT_FOUND", "Not found", status=404)
        repo.write_audit(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action_type="product.image_primary_set",
            entity_id=product_id,
            payload={"image_id": str(image_id)},
        )
        return updated

    def reorder(
        self,
        *,
        uow: UnitOfWork,
        tenant_id: UUID,
        product_id: UUID,
        image_ids: list[UUID],
        actor_user_id: UUID,
    ) -> list[dict[str, Any]]:
        repo = ProductImageRepository(uow.connection)
        if repo.lock_product(tenant_id, product_id) is None:
            raise ImageServiceError("NOT_FOUND", "Not found", status=404)
        existing = repo.list_for_product(tenant_id, product_id)
        existing_ids = {UUID(str(r["id"])) for r in existing}
        if set(image_ids) != existing_ids or len(image_ids) != len(existing_ids):
            raise ImageServiceError(
                "VALIDATION_ERROR",
                "image_ids must list every image for this product exactly once",
                status=422,
            )
        repo.update_sort_orders(tenant_id, product_id, image_ids)
        repo.write_audit(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action_type="product.image_reordered",
            entity_id=product_id,
            payload={"image_ids": [str(i) for i in image_ids]},
        )
        return repo.list_for_product(tenant_id, product_id)

    def delete(
        self,
        *,
        uow: UnitOfWork,
        tenant_id: UUID,
        image_id: UUID,
        actor_user_id: UUID,
    ) -> tuple[dict[str, Any], list[str]]:
        """Delete row under product lock. Returns (deleted_row, keys_to_maybe_unlink)."""
        repo = ProductImageRepository(uow.connection)
        current = repo.get(tenant_id, image_id)
        if current is None:
            raise ImageServiceError("NOT_FOUND", "Not found", status=404)
        product_id = UUID(str(current["product_id"]))
        if repo.lock_product(tenant_id, product_id) is None:
            raise ImageServiceError("NOT_FOUND", "Not found", status=404)
        deleted = repo.delete(tenant_id, image_id)
        if deleted is None:
            raise ImageServiceError("NOT_FOUND", "Not found", status=404)
        if bool(deleted["is_primary"]):
            repo.promote_next_primary(tenant_id, product_id)
        repo.write_audit(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action_type="product.image_deleted",
            entity_id=product_id,
            payload={"image_id": str(image_id)},
        )
        keys = [str(deleted["storage_key"]), str(deleted["thumb_key"])]
        return deleted, keys

    def unlink_if_unreferenced(
        self, *, tenant_id: UUID, keys: list[str], user_id: UUID | None = None
    ) -> None:
        """After UoW commit/rollback, delete files only if no committed row uses them.

        Takes the same content advisory lock as upload-before-put so a concurrent
        uncommitted insert cannot be invisible to key_referenced while we unlink.
        """
        if not keys:
            return
        by_sha: dict[str, list[str]] = {}
        for key in keys:
            by_sha.setdefault(_sha_from_storage_key(key), []).append(key)
        with UnitOfWork(user_id=user_id, tenant_id=tenant_id) as uow:
            repo = ProductImageRepository(uow.connection)
            for sha256, sha_keys in by_sha.items():
                repo.lock_content_sha(tenant_id, sha256)
                for key in sha_keys:
                    if not repo.key_referenced(tenant_id, key):
                        self._storage.delete(key)

    def read_bytes(self, key: str) -> bytes:
        return self._storage.get(key)


def _sha_from_storage_key(key: str) -> str:
    name = key.rsplit("/", 1)[-1]
    if name.endswith(".thumb.webp"):
        return name[: -len(".thumb.webp")]
    if name.endswith(".webp"):
        return name[: -len(".webp")]
    raise ValueError(f"Unexpected storage key: {key}")
