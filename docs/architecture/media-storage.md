# Product media storage

Phase 4.5 introduces local filesystem storage for product images. The API
exposes an `ObjectStorage` port so the backing store can change later without
rewriting catalog use cases.

## Compose volume

| Item | Value |
|---|---|
| Named volume | `stockpilot_media` |
| Mount in `api` | `/var/lib/stockpilot/media` |
| Env | `STOCKPILOT_MEDIA_DIR` (default `/var/lib/stockpilot/media`) |

Declared in `compose.yaml` under `volumes.stockpilot_media` and mounted on the
`api` service. Do **not** use `docker compose down -v` in day-to-day work; that
would delete Postgres and media volumes.

## Object keys

Keys are content-addressed and tenant-prefixed:

- `{tenant_id}/{sha256}.webp` — 800×800 main WebP
- `{tenant_id}/{sha256}.thumb.webp` — 200×200 thumbnail WebP

`sha256` is of the **normalized main WebP** bytes, not the upload. Original
filenames are never used in paths. Path traversal is rejected.

The same picture on two products in one tenant shares one file. Deletes and
rollback cleanup re-check the database and unlink only when no committed
`catalog.product_images` row in that tenant still references the key.

## Limits

| Env | Default | Meaning |
|---|---|---|
| `STOCKPILOT_IMAGE_MAX_BYTES` | `5242880` (5 MiB) | Max upload size before decode |
| `STOCKPILOT_IMAGE_MAX_PIXELS` | `24000000` | Pillow decompression-bomb guard |

## Phase 6 backup (T15)

When off-host backup is implemented, **include the `stockpilot_media` volume**
together with the Postgres dumps. Restoring only the database leaves image URLs
broken; restoring only media without matching rows leaves orphan files. Record
schema revision and app image version with the snapshot metadata as for DBs.
