# ──────────────────────────────────────────────────────────────────────
# Stage 1: builder — install deps into a venv with uv
# ──────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# Build tools needed for pure-Python wheels (e.g. asyncpg, pillow, pymupdf)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast, deterministic Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./

# Install runtime deps only — torch/transformers/etc. live in the
# `local-vlm` extra and are deliberately excluded from this image.
# `--no-install-project` avoids needing the source tree at this layer
# so dep changes alone re-use the cached layer.
RUN uv venv /opt/venv \
    && uv sync --frozen --no-dev --no-install-project

# ──────────────────────────────────────────────────────────────────────
# Stage 2: runtime — slim image, app code, venv copied in
# ──────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app

# tini gives us proper PID-1 signal handling for graceful shutdown
RUN apt-get update && apt-get install -y --no-install-recommends \
        tini \
        libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app && useradd --system --gid app --home /app app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=app:app src ./src
COPY --chown=app:app configs ./configs
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app alembic.ini ./alembic.ini

# Uploads land here in production; the compose file bind-mounts a host
# volume on top so files survive container rebuilds.
RUN mkdir -p /app/data/uploads && chown -R app:app /app/data

USER app
EXPOSE 8010

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8010", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
