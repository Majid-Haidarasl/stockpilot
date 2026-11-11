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
CMD ["bash", "-c", "ruff check src tests && ruff format --check src tests && mypy && lint-imports && alembic upgrade head && pytest -q"]
