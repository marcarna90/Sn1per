# syntax=docker/dockerfile:1
# Neo-Orchestro backend image (API, worker and migrations share it).
# Designed & Developed by Ronald TSR.
#
# Pin the base image by digest in release builds (Dependabot/Renovate can maintain it).

# ---------- builder: hash-locked dependencies, wheels only (nothing is compiled here) --------
FROM python:3.13-slim-bookworm AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY requirements.txt ./
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --require-hashes --only-binary=:all: -r requirements.txt \
 && /opt/venv/bin/pip uninstall -y pip

# ---------- runtime: no pip, no compiler, non-root ---------------------------------------------
FROM python:3.13-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH=/app/src

RUN groupadd --system --gid 10001 neo \
 && useradd --system --uid 10001 --gid neo --home-dir /nonexistent --shell /usr/sbin/nologin neo

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src

USER 10001:10001
EXPOSE 8000

# Meaningful for the API; the worker overrides it in docker-compose.yml.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3).status == 200 else 1)"]

CMD ["uvicorn", "neo_orchestro.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-server-header"]
