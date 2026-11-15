# Phase 4.5 Run 5 — Product Images Backend

**Date:** 2026-11-15  
**Repo:** `D:\Me\Last Term\WEB\stockpilot`  
**Host:** Windows 11, Docker Desktop (WSL2), PowerShell  

---

## Verdict

Tenant-isolated product images (max 5, one primary) with local named-volume storage, magic-byte validation, Pillow WebP normalize, CSRF + Idempotency-Key writes, and additive OpenAPI. Bulk zip import is **not** in this run (Run 6).

| Check | Result |
|---|---|
| Backend-checks | **107 passed** |
| Vitest | **75 passed** (34 files) |
| Playwright e2e (`-p stockpilot-e2e`) | **7 passed** |
| Migration | `0009_product_images` (up on dev + test; down/up covered in test) |
| OpenAPI | Additive (new image paths + `primary_thumbnail_url`) |
| New deps | `pillow==13.0.0`, `python-multipart==0.0.33` |
| Phase 5+ (T13–T16) | **Untouched** |

---

## Migration

- Revision: `0009_product_images` (revises `0008_audit_log_seq`)
- Table: `catalog.product_images` with composite FK to `catalog.products (tenant_id, id)` via existing `uq_catalog_products_tenant_id` (from 0004; **not** re-added)
- Partial unique index: one primary per product
- Unique `(tenant_id, product_id, sha256)` → `IMAGE_DUPLICATE`
- RLS FORCE + `tenant_isolation` / `migrator_all`
- `STOCKPILOT_EXPECTED_SCHEMA_REVISION` → `0009_product_images`

---

## Endpoints

| Method | Path |
|---|---|
| `POST` | `/api/v1/tenants/{tenant_id}/products/{product_id}/images` |
| `GET` | `/api/v1/tenants/{tenant_id}/products/{product_id}/images` |
| `POST` | `/api/v1/tenants/{tenant_id}/products/{product_id}/images/reorder` |
| `GET` | `/api/v1/tenants/{tenant_id}/images/{image_id}/file` |
| `GET` | `/api/v1/tenants/{tenant_id}/images/{image_id}/thumbnail` |
| `POST` | `/api/v1/tenants/{tenant_id}/images/{image_id}/primary` |
| `DELETE` | `/api/v1/tenants/{tenant_id}/images/{image_id}` |

Additive on products: `ProductOut.primary_thumbnail_url: string \| null`

Roles for writes: `admin` / `sales` (`can_manage_catalog_writes`). Viewer → `403 FORBIDDEN`.

---

## Storage / env / volume

| Item | Value |
|---|---|
| Named volume | `stockpilot_media` (e2e project: `stockpilot-e2e_stockpilot_media`) |
| Mount | `/var/lib/stockpilot/media` on `api` |
| `STOCKPILOT_MEDIA_DIR` | default `/var/lib/stockpilot/media` (backend-checks: `/tmp/stockpilot-media-test`) |
| `STOCKPILOT_IMAGE_MAX_BYTES` | `5242880` |
| `STOCKPILOT_IMAGE_MAX_PIXELS` | `24000000` |
| Keys | `{tenant_id}/{sha256}.webp` + `.thumb.webp` |

Docs: [`docs/architecture/media-storage.md`](../architecture/media-storage.md) — Phase 6 backup must include this volume.

**Shared-file safety:** `put` uses `O_EXCL` (`created` flag). Rollback / delete unlink only after a **fresh DB re-check** that no committed row in the tenant references the key (covers concurrent upload to two products).

**E2e media:** isolated project created `stockpilot-e2e_stockpilot_media`; api healthy; 7 e2e passed.

---

## ADR-002 lock / deadlock

Reserve locks: idempotency → **order** → products (id order) → positions → reservation.  
Image writes lock **only** one `catalog.products` row (`FOR UPDATE`) and never orders/positions/reservations. No AB-BA cycle with reserve/confirm; worst case is waiting on the same product row. Set-primary, reorder, and delete use the same product-row lock so they cannot race with upload.

Encode (magic bytes / Pillow / sha256) runs **before** opening the UnitOfWork.

---

## Dependencies

| Package | Version | Note |
|---|---|---|
| pillow | **13.0.0** | Locked via `ghcr.io/astral-sh/uv:0.9.7-python3.13-bookworm` |
| python-multipart | **0.0.33** | FastAPI multipart |

`uv.lock` diff: **+75 lines** (pillow + python-multipart and their lock metadata; no unrelated package churn).

---

## OpenAPI diff (summary)

Additive only:

- New tag / paths for product images (list, upload, reorder, file, thumbnail, primary, delete)
- New schemas: `ProductImageOut`, `ReorderBody`, related request bodies
- `ProductOut.primary_thumbnail_url` (nullable)

No removals of existing product fields/paths.

---

## Files changed (high level)

**New:** `0009_product_images.py`, `image_routes.py`, `image_repo.py`, `image_service.py`, `local_media.py`, `pillow_images.py`, `application/ports.py`, integration + unit tests, `docs/architecture/media-storage.md`, this report.

**Updated:** `compose.yaml` (volume + env), `settings.py`, `Dockerfile` (media dir ownership), `catalog` product list/detail + `public.py`, `app.py`, `pyproject.toml` / `uv.lock`, `.env.example`, `versions.md`, `mapApiError` (+ Vitest), `Product` type, `openapi.json` + generated schema.

**Not touched:** `compose.prod.yaml`, T13–T16, RabbitMQ/worker/relay/inbox, Grafana, GHCR, Locust.

---

## Commands (one per block; no `-v`)

```powershell
docker compose -f compose.yaml -f compose.dev.yaml up -d --wait postgres
```

```powershell
docker compose -f compose.yaml -f compose.dev.yaml build migrate api
```

```powershell
docker compose -f compose.yaml -f compose.dev.yaml run --rm migrate
```

```powershell
docker compose -f compose.yaml -f compose.dev.yaml up -d --build --wait keycloak api frontend-dev
```

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --profile test build backend-checks openapi-export frontend-checks
```

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm backend-checks
```

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm frontend-checks
```

```powershell
docker compose -p stockpilot-e2e -f compose.yaml -f compose.e2e.yaml --profile test build
```

```powershell
docker compose -p stockpilot-e2e -f compose.yaml -f compose.e2e.yaml --profile test run --rm e2e
```

```powershell
docker compose -p stockpilot-e2e -f compose.yaml -f compose.e2e.yaml --profile test down
```

Lock (already done this run):

```powershell
docker run --rm -v "d:\Me\Last Term\WEB\stockpilot\backend:/app" -w /app ghcr.io/astral-sh/uv:0.9.7-python3.13-bookworm uv lock
```

---

## Notes from this run

1. First migrate attempt failed because `uq_catalog_products_tenant_id` already exists from `0004_inventory`; migration was corrected to reuse it.
2. First api unhealthy: FastAPI asserts against `status_code=204` on a handler that can return problem JSON; delete decorator no longer declares 204 (response still returns 204 on success).
3. First e2e build hit Docker Hub TLS timeout; retry succeeded.
