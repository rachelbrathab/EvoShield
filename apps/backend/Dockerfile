# syntax=docker/dockerfile:1
# EvoShield backend — production-leaning image.
# Multi-stage, uv-managed deps, non-root runtime user, built-in healthcheck.
# Pin the uv builder image to a released uv version (image naming convention:
# <uv-version>-python3.12). Bump deliberately, then re-verify the lockfile.
FROM ghcr.io/astral-sh/uv:0.11.33-python3.12 AS builder

WORKDIR /app

# Install dependencies first so the layer cache survives source changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Run as an unprivileged user — never as root in production.
RUN groupadd --system app && useradd --system --gid app app

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4).status==200 else 1)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
