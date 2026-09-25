FROM ghcr.io/astral-sh/uv:0.11.2@sha256:c4f5de312ee66d46810635ffc5df34a1973ba753e7241ce3a08ef979ddd7bea5 AS uv
FROM python:3.12-slim-bookworm@sha256:d97792894a6a4162cae14da44542a83c75e56c77a27b92d58f3f83b7bc961292
COPY --from=uv /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH=/app/.venv/bin:$PATH
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/app ./app
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./
USER 10001:10001
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]
