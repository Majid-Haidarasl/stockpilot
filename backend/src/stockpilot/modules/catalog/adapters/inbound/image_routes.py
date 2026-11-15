"""HTTP API for product images."""

from __future__ import annotations

import hashlib
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from stockpilot.modules.access.public import ActorContext, require_actor, require_csrf
from stockpilot.modules.catalog.adapters.outbound.image_repo import ProductImageRepository
from stockpilot.modules.catalog.adapters.outbound.image_service import (
    ImageServiceError,
    ProductImageService,
    prepare_image,
)
from stockpilot.modules.catalog.adapters.outbound.local_media import LocalMediaStorage
from stockpilot.modules.catalog.adapters.outbound.pillow_images import PillowImageProcessor
from stockpilot.platform.http.problems import problem
from stockpilot.platform.persistence.idempotency import (
    IdempotencyInProgress,
    IdempotencyKeyReused,
    IdempotencyStore,
    StoredResponse,
    fingerprint,
)
from stockpilot.platform.persistence.uow import UnitOfWork
from stockpilot.platform.settings import get_settings

router = APIRouter(tags=["product-images"])

CONTRACT_VERSION = "v1"
MAX_IMAGES = 5


class ProductImageOut(BaseModel):
    id: str
    product_id: str
    content_type: str
    width: int
    height: int
    size_bytes: int
    sha256: str
    is_primary: bool
    sort_order: int
    url: str
    thumbnail_url: str
    created_at: str


class ReorderBody(BaseModel):
    image_ids: list[str] = Field(min_length=1, max_length=MAX_IMAGES)


def _service() -> ProductImageService:
    settings = get_settings()
    return ProductImageService(
        storage=LocalMediaStorage(settings.media_dir),
        processor=PillowImageProcessor(
            max_bytes=settings.image_max_bytes,
            max_pixels=settings.image_max_pixels,
        ),
        max_bytes=settings.image_max_bytes,
        max_pixels=settings.image_max_pixels,
    )


def image_file_url(tenant_id: UUID, image_id: UUID) -> str:
    return f"/api/v1/tenants/{tenant_id}/images/{image_id}/file"


def image_thumb_url(tenant_id: UUID, image_id: UUID) -> str:
    return f"/api/v1/tenants/{tenant_id}/images/{image_id}/thumbnail"


def primary_thumbnail_url(tenant_id: UUID, image_id: UUID | None) -> str | None:
    if image_id is None:
        return None
    return image_thumb_url(tenant_id, image_id)


def _to_out(row: dict[str, Any], tenant_id: UUID) -> ProductImageOut:
    image_id = UUID(str(row["id"]))
    return ProductImageOut(
        id=str(image_id),
        product_id=str(row["product_id"]),
        content_type=str(row["content_type"]),
        width=int(row["width"]),
        height=int(row["height"]),
        size_bytes=int(row["size_bytes"]),
        sha256=str(row["sha256"]),
        is_primary=bool(row["is_primary"]),
        sort_order=int(row["sort_order"]),
        url=image_file_url(tenant_id, image_id),
        thumbnail_url=image_thumb_url(tenant_id, image_id),
        created_at=row["created_at"].isoformat()
        if hasattr(row["created_at"], "isoformat")
        else str(row["created_at"]),
    )


def _error(exc: ImageServiceError) -> Any:
    return problem(status=exc.status, code=exc.code, title=exc.title)


@router.get("/api/v1/tenants/{tenant_id}/products/{product_id}/images")
def list_images(
    tenant_id: UUID,
    product_id: UUID,
    actor: Annotated[ActorContext, Depends(require_actor)],
) -> list[ProductImageOut] | Any:
    with UnitOfWork(user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value) as uow:
        repo = ProductImageRepository(uow.connection)
        if repo.get_product(tenant_id, product_id) is None:
            return problem(status=404, code="NOT_FOUND", title="Not found")
        rows = repo.list_for_product(tenant_id, product_id)
    return [_to_out(r, tenant_id) for r in rows]


@router.post(
    "/api/v1/tenants/{tenant_id}/products/{product_id}/images",
    status_code=201,
)
async def upload_image(
    tenant_id: UUID,
    product_id: UUID,
    actor: Annotated[ActorContext, Depends(require_actor)],
    _: Annotated[Any, Depends(require_csrf)],
    file: Annotated[UploadFile, File()],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ProductImageOut | Any:
    if not actor.can_manage_catalog_writes():
        return problem(status=403, code="FORBIDDEN", title="Forbidden")
    if not idempotency_key:
        return problem(
            status=422,
            code="VALIDATION_ERROR",
            title="Idempotency-Key header is required",
        )

    raw = await file.read()
    service = _service()
    try:
        prepared = prepare_image(raw=raw, tenant_id=tenant_id, processor=service.processor)
    except ImageServiceError as exc:
        return _error(exc)

    path = f"/api/v1/tenants/{tenant_id}/products/{product_id}/images"
    fp = fingerprint(
        method="POST",
        path=path,
        contract_version=CONTRACT_VERSION,
        body={"sha256": prepared.sha256},
    )

    created_keys: list[str] = []
    committed = False
    try:
        with UnitOfWork(
            user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value
        ) as uow:
            store = IdempotencyStore(uow.connection)
            try:
                prior = store.begin(
                    tenant_id=tenant_id,
                    user_id=actor.user_id,
                    operation="products.image_upload",
                    key=idempotency_key,
                    fp=fp,
                )
            except IdempotencyKeyReused:
                return problem(
                    status=409,
                    code="IDEMPOTENCY_KEY_REUSED",
                    title="Idempotency-Key reused with a different body",
                )
            except IdempotencyInProgress as exc:
                resp = problem(
                    status=409,
                    code="IDEMPOTENCY_IN_PROGRESS",
                    title="Request with this Idempotency-Key is still in progress",
                )
                resp.headers["Retry-After"] = str(exc.retry_after)
                return resp
            if prior is not None:
                if prior.status >= 400:
                    return problem(
                        status=prior.status,
                        code=str(prior.body.get("code", "REPLAY")),
                        title=str(prior.body.get("title", "Replayed response")),
                    )
                return ProductImageOut.model_validate(prior.body)

            try:
                row = service.add_prepared(
                    uow=uow,
                    tenant_id=tenant_id,
                    product_id=product_id,
                    actor_user_id=actor.user_id,
                    prepared=prepared,
                    created_keys=created_keys,
                )
            except ImageServiceError as exc:
                store.complete(
                    tenant_id=tenant_id,
                    user_id=actor.user_id,
                    operation="products.image_upload",
                    key=idempotency_key,
                    response=StoredResponse(
                        status=exc.status,
                        body={"code": exc.code, "title": exc.title},
                        headers={},
                    ),
                )
                return _error(exc)

            out = _to_out(row, tenant_id)
            store.complete(
                tenant_id=tenant_id,
                user_id=actor.user_id,
                operation="products.image_upload",
                key=idempotency_key,
                response=StoredResponse(status=201, body=out.model_dump(mode="json"), headers={}),
            )
            committed = True
            return out
    finally:
        if not committed and created_keys:
            service.unlink_if_unreferenced(
                tenant_id=tenant_id, keys=created_keys, user_id=actor.user_id
            )


@router.get("/api/v1/tenants/{tenant_id}/images/{image_id}/file")
def get_image_file(
    tenant_id: UUID,
    image_id: UUID,
    request: Request,
    actor: Annotated[ActorContext, Depends(require_actor)],
) -> Response:
    return _serve_variant(
        tenant_id=tenant_id,
        image_id=image_id,
        actor=actor,
        request=request,
        thumb=False,
    )


@router.get("/api/v1/tenants/{tenant_id}/images/{image_id}/thumbnail")
def get_image_thumbnail(
    tenant_id: UUID,
    image_id: UUID,
    request: Request,
    actor: Annotated[ActorContext, Depends(require_actor)],
) -> Response:
    return _serve_variant(
        tenant_id=tenant_id,
        image_id=image_id,
        actor=actor,
        request=request,
        thumb=True,
    )


def _serve_variant(
    *,
    tenant_id: UUID,
    image_id: UUID,
    actor: ActorContext,
    request: Request,
    thumb: bool,
) -> Response:
    service = _service()
    with UnitOfWork(user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value) as uow:
        row = ProductImageRepository(uow.connection).get(tenant_id, image_id)
        if row is None:
            return problem(status=404, code="NOT_FOUND", title="Not found")
        key = str(row["thumb_key"] if thumb else row["storage_key"])
        etag_source = str(row["sha256"]) + (":thumb" if thumb else ":main")
    etag = f'"{hashlib.sha256(etag_source.encode()).hexdigest()}"'
    if_none = request.headers.get("if-none-match")
    if if_none and if_none == etag:
        return Response(
            status_code=304,
            headers={"ETag": etag, "Cache-Control": "private, max-age=86400"},
        )
    try:
        data = service.read_bytes(key)
    except FileNotFoundError:
        return problem(status=404, code="NOT_FOUND", title="Not found")
    return Response(
        content=data,
        media_type="image/webp",
        headers={
            "Cache-Control": "private, max-age=86400",
            "ETag": etag,
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/api/v1/tenants/{tenant_id}/images/{image_id}/primary")
def set_primary(
    tenant_id: UUID,
    image_id: UUID,
    actor: Annotated[ActorContext, Depends(require_actor)],
    _: Annotated[Any, Depends(require_csrf)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ProductImageOut | Any:
    if not actor.can_manage_catalog_writes():
        return problem(status=403, code="FORBIDDEN", title="Forbidden")
    if not idempotency_key:
        return problem(
            status=422,
            code="VALIDATION_ERROR",
            title="Idempotency-Key header is required",
        )
    path = f"/api/v1/tenants/{tenant_id}/images/{image_id}/primary"
    fp = fingerprint(
        method="POST",
        path=path,
        contract_version=CONTRACT_VERSION,
        body={"image_id": str(image_id)},
    )
    service = _service()
    with UnitOfWork(user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value) as uow:
        store = IdempotencyStore(uow.connection)
        try:
            prior = store.begin(
                tenant_id=tenant_id,
                user_id=actor.user_id,
                operation="products.image_primary",
                key=idempotency_key,
                fp=fp,
            )
        except IdempotencyKeyReused:
            return problem(
                status=409,
                code="IDEMPOTENCY_KEY_REUSED",
                title="Idempotency-Key reused with a different body",
            )
        except IdempotencyInProgress as exc:
            resp = problem(
                status=409,
                code="IDEMPOTENCY_IN_PROGRESS",
                title="Request with this Idempotency-Key is still in progress",
            )
            resp.headers["Retry-After"] = str(exc.retry_after)
            return resp
        if prior is not None:
            return ProductImageOut.model_validate(prior.body)
        try:
            row = service.set_primary(
                uow=uow,
                tenant_id=tenant_id,
                image_id=image_id,
                actor_user_id=actor.user_id,
            )
        except ImageServiceError as exc:
            return _error(exc)
        out = _to_out(row, tenant_id)
        store.complete(
            tenant_id=tenant_id,
            user_id=actor.user_id,
            operation="products.image_primary",
            key=idempotency_key,
            response=StoredResponse(status=200, body=out.model_dump(mode="json"), headers={}),
        )
        return out


@router.post("/api/v1/tenants/{tenant_id}/products/{product_id}/images/reorder")
def reorder_images(
    tenant_id: UUID,
    product_id: UUID,
    body: ReorderBody,
    actor: Annotated[ActorContext, Depends(require_actor)],
    _: Annotated[Any, Depends(require_csrf)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> list[ProductImageOut] | Any:
    if not actor.can_manage_catalog_writes():
        return problem(status=403, code="FORBIDDEN", title="Forbidden")
    if not idempotency_key:
        return problem(
            status=422,
            code="VALIDATION_ERROR",
            title="Idempotency-Key header is required",
        )
    try:
        ordered = [UUID(x) for x in body.image_ids]
    except ValueError:
        return problem(status=422, code="VALIDATION_ERROR", title="Invalid image id")
    path = f"/api/v1/tenants/{tenant_id}/products/{product_id}/images/reorder"
    fp = fingerprint(
        method="POST",
        path=path,
        contract_version=CONTRACT_VERSION,
        body=body.model_dump(mode="json"),
    )
    service = _service()
    with UnitOfWork(user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value) as uow:
        store = IdempotencyStore(uow.connection)
        try:
            prior = store.begin(
                tenant_id=tenant_id,
                user_id=actor.user_id,
                operation="products.image_reorder",
                key=idempotency_key,
                fp=fp,
            )
        except IdempotencyKeyReused:
            return problem(
                status=409,
                code="IDEMPOTENCY_KEY_REUSED",
                title="Idempotency-Key reused with a different body",
            )
        except IdempotencyInProgress as exc:
            resp = problem(
                status=409,
                code="IDEMPOTENCY_IN_PROGRESS",
                title="Request with this Idempotency-Key is still in progress",
            )
            resp.headers["Retry-After"] = str(exc.retry_after)
            return resp
        if prior is not None:
            return [ProductImageOut.model_validate(item) for item in prior.body["items"]]
        try:
            rows = service.reorder(
                uow=uow,
                tenant_id=tenant_id,
                product_id=product_id,
                image_ids=ordered,
                actor_user_id=actor.user_id,
            )
        except ImageServiceError as exc:
            return _error(exc)
        out = [_to_out(r, tenant_id) for r in rows]
        store.complete(
            tenant_id=tenant_id,
            user_id=actor.user_id,
            operation="products.image_reorder",
            key=idempotency_key,
            response=StoredResponse(
                status=200,
                body={"items": [o.model_dump(mode="json") for o in out]},
                headers={},
            ),
        )
        return out


@router.delete("/api/v1/tenants/{tenant_id}/images/{image_id}")
def delete_image(
    tenant_id: UUID,
    image_id: UUID,
    actor: Annotated[ActorContext, Depends(require_actor)],
    _: Annotated[Any, Depends(require_csrf)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Any:
    if not actor.can_manage_catalog_writes():
        return problem(status=403, code="FORBIDDEN", title="Forbidden")
    if not idempotency_key:
        return problem(
            status=422,
            code="VALIDATION_ERROR",
            title="Idempotency-Key header is required",
        )
    path = f"/api/v1/tenants/{tenant_id}/images/{image_id}"
    fp = fingerprint(
        method="DELETE",
        path=path,
        contract_version=CONTRACT_VERSION,
        body={"image_id": str(image_id)},
    )
    service = _service()
    keys: list[str] = []
    with UnitOfWork(user_id=actor.user_id, tenant_id=actor.tenant_id, role=actor.role.value) as uow:
        store = IdempotencyStore(uow.connection)
        try:
            prior = store.begin(
                tenant_id=tenant_id,
                user_id=actor.user_id,
                operation="products.image_delete",
                key=idempotency_key,
                fp=fp,
            )
        except IdempotencyKeyReused:
            return problem(
                status=409,
                code="IDEMPOTENCY_KEY_REUSED",
                title="Idempotency-Key reused with a different body",
            )
        except IdempotencyInProgress as exc:
            resp = problem(
                status=409,
                code="IDEMPOTENCY_IN_PROGRESS",
                title="Request with this Idempotency-Key is still in progress",
            )
            resp.headers["Retry-After"] = str(exc.retry_after)
            return resp
        if prior is not None:
            return Response(status_code=prior.status)
        try:
            _deleted, keys = service.delete(
                uow=uow,
                tenant_id=tenant_id,
                image_id=image_id,
                actor_user_id=actor.user_id,
            )
        except ImageServiceError as exc:
            return _error(exc)
        store.complete(
            tenant_id=tenant_id,
            user_id=actor.user_id,
            operation="products.image_delete",
            key=idempotency_key,
            response=StoredResponse(status=204, body={}, headers={}),
        )
    service.unlink_if_unreferenced(tenant_id=tenant_id, keys=keys, user_id=actor.user_id)
    return Response(status_code=204)
