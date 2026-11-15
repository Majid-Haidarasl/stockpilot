# Phase 4.5 Run 6 — Product Images UI + Bulk Import

**Date:** 2026-11-15  
**Repo:** `D:\Me\Last Term\WEB\stockpilot`  
**Host:** Windows 11, Docker Desktop (WSL2), PowerShell 5.1  

---

## Verdict

Product image UI (list thumbs, gallery dialog, draft thumbs) plus safe ops zip import under the **runtime DB role**, with a real tenant **admin/sales** actor for `created_by`. No migration. Phase 5+ untouched.

| Check | Result |
|---|---|
| Backend-checks | **116 passed** |
| Vitest | **80 passed** (35 files) |
| Playwright e2e (`-p stockpilot-e2e`) | **7 passed** (no selector changes; no new e2e added) |
| Migration | **None** |
| New deps | **None** |
| Phase 5+ (T13–T16) | **Untouched** |

---

## Import actor / RLS / ownership

| Item | Confirmed |
|---|---|
| CLI | `import-product-images --tenant … --zip … --actor-email … [--dry-run]` |
| Actor emails (seeded) | Per-tenant `admin@<slug>.test` (Path A); also `viewer@baran.test` for UI |
| `created_by` / audit | Resolved user id (NOT NULL); refuses non-member and viewer |
| DB role for writes | **`stockpilot_app`** via `STOCKPILOT_DATABASE_URL` on `ops` (compose.yaml); migrator refused if present in URL |
| `UnitOfWork` | `user_id` + `tenant_id` + `role` set (same as API) |
| Ops process user | **`uid=1000(app) gid=1000(app)`** |
| Media volume | `stockpilot_media` mounted on `ops` and `api` at `/var/lib/stockpilot/media` |
| Serve check | aftab primary thumb **HTTP 200** `image/webp`; baran primary thumb **HTTP 200** `image/webp` (2102 bytes) |

---

## Bulk import summaries (Path A)

Zip’s 30 SKUs are spread across **15 seed tenants**. Path A = same per-tenant CLI path for each owning tenant (`--actor-email admin@<slug>.test`, `stockpilot_app`, RLS). No catalog changes.

### Earlier single-tenant runs

| Tenant | Actor | imported | skipped | failed | Notes |
|---|---|---:|---:|---:|---|
| aftab | `admin@aftab.test` | 1 | 29 | 0 | `LAP-ASUS-UX3405MA-16-1T` |
| baran | `admin@baran.test` | 4 | 26 | 0 | 4 phone SKUs |

### Path A loop (all 15 matching tenants; re-run safe)

| Tenant | Actor | imported | skipped | failed |
|---|---|---:|---:|---:|
| aftab | `admin@aftab.test` | 0 | 30 | 0 |
| baran | `admin@baran.test` | 0 | 30 | 0 |
| sepehr | `admin@sepehr.test` | 1 | 29 | 0 |
| golestan | `admin@golestan.test` | 2 | 28 | 0 |
| pars-technic | `admin@pars-technic.test` | 1 | 29 | 0 |
| padideh | `admin@padideh.test` | 1 | 29 | 0 |
| arya-phone | `admin@arya-phone.test` | 1 | 29 | 0 |
| rasad | `admin@rasad.test` | 4 | 26 | 0 |
| urumiatech | `admin@urumiatech.test` | 2 | 28 | 0 |
| zagros-mobile | `admin@zagros-mobile.test` | 3 | 27 | 0 |
| alvand | `admin@alvand.test` | 4 | 26 | 0 |
| sabalan-game | `admin@sabalan-game.test` | 3 | 27 | 0 |
| hormoz-net | `admin@hormoz-net.test` | 3 | 27 | 0 |
| naqshjahan | `admin@naqshjahan.test` | 1 | 29 | 0 |
| lian-print | `admin@lian-print.test` | 2 | 28 | 0 |
| **TOTAL (this loop)** | | **28** | **422** | **0** |

aftab/baran show `imported=0` here because duplicates skip (`IMAGE_DUPLICATE`). Lifetime after Path A: **33** `product_images` rows across **15** tenants covering **30** unique zip SKUs (3 SKUs shared across tenants); **failed=0**.

---

## UI behaviour shipped

- Products list + mobile rows: fixed 40px `ProductThumb` from `primary_thumbnail_url` (auth blob cache); «تصاویر» opens gallery.
- `ProductImagesDialog`: primary preview + strip; admin/sales upload (button + drop), remaining-of-5, client pre-check, star / up-down / delete + ConfirmDialog «حذف تصویر»; warehouse/viewer read-only.
- Draft picker / line rows: decorative thumbs from loaded products map; missing product → placeholder only.
- Query keys: `productImages`, `media` under `["tenant", …]`; `clearTenantSensitiveCache` revokes blob URLs (Vitest covered).

---

## Files changed (high level)

**Backend:** `bootstrap/import_product_images.py`, `bootstrap/ops.py`, `access/.../repo.py` (`get_user_by_email`), `compose.yaml` (ops `STOCKPILOT_DATABASE_URL`, `STOCKPILOT_MEDIA_DIR`, `stockpilot_media`), unit + integration import tests, `.gitignore` (`.local/`).

**Frontend:** `ProductImagesDialog` (+ tests), `ProductThumb`, `useAuthMediaUrl`, `catalogPermissions`, `ProductsPage`, `DraftOrderPage`, `OrderDetailPage`, `keys` / `cache` / `mediaCache` / `queryClient`, `api` client (`apiFetchBlob`, `apiUpload`) + types.

**Docs:** this report + `docs/reports/phase45-run6-screenshots/`.

**Not touched:** `compose.prod.yaml`, RabbitMQ/worker/relay/inbox/scheduler/Grafana/GHCR/Locust/T13–T16.

---

## Screenshots (self-reviewed)

Directory: [`docs/reports/phase45-run6-screenshots/`](phase45-run6-screenshots/)

| File | Notes |
|---|---|
| `products-list-light-desktop.png` | Zenbook row shows real primary thumb; placeholders elsewhere |
| `product-gallery-admin-light-desktop.png` | Admin gallery + upload zone «۴ از ۵» |
| `upload-error-light-desktop.png` | Client reject GIF → «فقط تصویر JPEG، PNG یا WebP پذیرفته می‌شود.» |
| `product-gallery-viewer-light-desktop.png` | `viewer@baran.test` iPhone gallery; «مشاهده تصاویر (فقط خواندنی)»; no upload/delete |
| `products-list-dark-desktop.png` | Soft Slate Sky dark; thumb still visible |
| `product-gallery-admin-dark-desktop.png` | Admin gallery in dark |
| `products-list-mobile-390.png` | Mobile cards + «تصاویر» |
| `draft-picker-light-desktop.png` | Draft line thumb slot next to «کالا» |

---

## Exact PowerShell commands (one per block; no `-v`)

```powershell
docker compose -f compose.yaml -f compose.dev.yaml up -d --wait postgres
```

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --profile test build backend-checks frontend-checks ops api
```

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm backend-checks
```

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm frontend-checks
```

```powershell
docker compose -f compose.yaml -f compose.dev.yaml up -d --wait postgres keycloak api frontend-dev
```

```powershell
docker compose -f compose.yaml -f compose.dev.yaml run --rm ops python -m stockpilot.bootstrap.ops bootstrap --environment development
```

```powershell
# Path A — one tenant (example)
docker compose -f compose.yaml -f compose.dev.yaml run --rm -v "${PWD}\.local\images:/import:ro" ops python -m stockpilot.bootstrap.ops import-product-images --tenant aftab --zip /import/stockpilot-product-images.zip --actor-email admin@aftab.test
```

```powershell
# Path A — all 15 matching tenants (same per-tenant code path)
$tenants = @(
  @{ slug = "aftab"; email = "admin@aftab.test" },
  @{ slug = "baran"; email = "admin@baran.test" },
  @{ slug = "sepehr"; email = "admin@sepehr.test" },
  @{ slug = "golestan"; email = "admin@golestan.test" },
  @{ slug = "pars-technic"; email = "admin@pars-technic.test" },
  @{ slug = "padideh"; email = "admin@padideh.test" },
  @{ slug = "arya-phone"; email = "admin@arya-phone.test" },
  @{ slug = "rasad"; email = "admin@rasad.test" },
  @{ slug = "urumiatech"; email = "admin@urumiatech.test" },
  @{ slug = "zagros-mobile"; email = "admin@zagros-mobile.test" },
  @{ slug = "alvand"; email = "admin@alvand.test" },
  @{ slug = "sabalan-game"; email = "admin@sabalan-game.test" },
  @{ slug = "hormoz-net"; email = "admin@hormoz-net.test" },
  @{ slug = "naqshjahan"; email = "admin@naqshjahan.test" },
  @{ slug = "lian-print"; email = "admin@lian-print.test" }
)
foreach ($t in $tenants) {
  docker compose -f compose.yaml -f compose.dev.yaml run --rm -v "${PWD}\.local\images:/import:ro" ops python -m stockpilot.bootstrap.ops import-product-images --tenant $($t.slug) --zip /import/stockpilot-product-images.zip --actor-email $($t.email)
}
```

```powershell
docker compose -p stockpilot-e2e -f compose.yaml -f compose.e2e.yaml --profile test run --rm e2e
```

```powershell
docker compose -p stockpilot-e2e -f compose.yaml -f compose.e2e.yaml --profile test down
```

---

## Limitations

- Path A: each tenant only owns a subset of the 30 zip SKUs → per-tenant `unknown_sku` skips are expected; shared SKUs produce >30 image rows (33).
- Optional “sales uploads → list thumb” e2e not added (kept existing 7 green).
- Host Docker CLI was not on PATH; used `...\DockerDesktop\resources\bin\docker.exe` for this run.
- No `--all-matching-tenants` CLI flag; PowerShell loop reuses the exact same per-tenant import path.
