# Version pins (Phase 1 — recorded after Docker tests)

Host: Windows 11 + Docker Desktop (WSL2), AMD64. Containers are Linux.

**OPEN DECISION:** treat these as the week-1 compatibility baseline. Re-verify before a release line if upstream tags move. Do not invent untested patch numbers.

## Base images (pulled/tested 2026-11-11)

| Image | Tag used | Digest / note |
|---|---|---|
| `postgres` | `17` | `sha256:ff87138949ad9a46f32ff23bd6852b52ce024a13dffe9b4087be98292cdd3b4f` |
| `node` | `24-bookworm-slim` | `sha256:01d566e8d94d8c619591d78652babfccd3c6992a3dffa9ed5ab39e11cf6c70e9` |
| `python` | `3.13-slim` | Resolved during build as `python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90` (image may be intermediate-only in local cache) |
| `ghcr.io/astral-sh/uv` | `0.9.7` | `sha256:ba4857bf2a068e9bc0e64eed8563b065908a4cd6bfb66b531a9c424c8e25e142` |
| `ghcr.io/astral-sh/uv` (python bookworm helper) | `0.9.7-python3.13-bookworm` | `sha256:09cca80667a9bd6d4515f0052ba2cde84ca6b9b7dbccc583f44fd0d703ddf37b` |

## Backend packages (from `uv.lock`, verified in containers)

| Package | Version |
|---|---|
| Python (runtime in checks image) | 3.13.18 |
| CPython used to lock | 3.13.9 |
| fastapi | 0.162.4 |
| uvicorn | 0.54.0 |
| pydantic | 2.14.3 |
| sqlalchemy | 2.1.8 |
| alembic | 1.20.1 |
| psycopg | 3.3.8 |
| ruff | 0.17.4 |
| mypy | 2.4.1 |
| import-linter | 2.16 |
| pytest | 9.2.0 |
| httpx | 0.28.1 |

## Frontend packages (from `package-lock.json`, verified in containers)

| Package | Version (resolved) |
|---|---|
| Node image | 24 (bookworm-slim) |
| vite | 6.x (lockfile) |
| vitest | 3.2.7 |
| react / react-dom | 19.x |
| @mui/material | 6.x |
| typescript | ~5.7 |
| eslint | 9.x |

## GitHub Actions pins

| Action | Pin |
|---|---|
| `actions/checkout` | `@v4` (major tag; digest pin **TODO** before release hardening) |
| `docker/setup-buildx-action` | `@v3` (major tag; digest pin **TODO** before release hardening) |

## Quality coverage target

Domain/application branch coverage ≥ **85%** is recorded as the project target. It is **not** enforced as a CI gate in Phase 1 while the domain is mostly empty.
