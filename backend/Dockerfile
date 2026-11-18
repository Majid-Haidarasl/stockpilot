# syntax=docker/dockerfile:1
# Official Python base + uv locked install. Do not use the deprecated FastAPI image.
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /usr/local/bin/uv

WORKDIR /app

RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --create-home app

FROM base AS deps
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

FROM base AS runtime
COPY --from=deps /app/.venv /app/.venv
COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src
COPY pyproject.toml uv.lock README.md ./
# Named volume first-mount copies this dir (uid 1000). Existing volumes may need
# a one-off root chown — see docs/runbooks/deploy.md.
RUN mkdir -p /var/lib/stockpilot/media \
    && chown -R app:app /var/lib/stockpilot \
    && chmod 775 /var/lib/stockpilot/media
USER app
EXPOSE 8000
CMD ["uvicorn", "stockpilot.bootstrap.app:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS checks
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic
COPY tests ./tests
RUN uv sync --frozen \
    && chown -R app:app /app
ENV PATH="/app/.venv/bin:$PATH"
USER app
WORKDIR /app
CMD ["bash", "-c", "python -m stockpilot.bootstrap.ensure_test_db && python -m stockpilot.bootstrap.ensure_rabbitmq_test_vhost && ruff check src tests && ruff format --check src tests && mypy && lint-imports && alembic upgrade head && python -m stockpilot.bootstrap.assert_schema_revision && pytest -q"]
