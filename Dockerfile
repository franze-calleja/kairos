# syntax=docker/dockerfile:1

# --- Stage 1: build the React frontend ---------------------------------
FROM node:24-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python runtime ---------------------------------------------
FROM python:3.14-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_NO_CACHE=1 \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/app/data/kairos.db

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/kairos ./kairos
RUN uv sync --frozen --no-dev
COPY --from=frontend /frontend/dist ./kairos/static

RUN useradd --create-home --uid 1000 kairos \
    && mkdir -p /app/data /app/backups \
    && chown -R kairos:kairos /app/data /app/backups
USER kairos

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["/app/backend/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"]
CMD ["/app/backend/.venv/bin/uvicorn", "kairos.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
