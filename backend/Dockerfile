# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: dependencies
#   Build arg INSTALL_BROWSER=0 skips Playwright (~1.5 GB) for dev/CI builds
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

ARG INSTALL_BROWSER=0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# ── System libs ───────────────────────────────────────────────────────────────
# Split into two RUN to keep each layer small and avoid OOM on constrained builders
RUN apt-get update && apt-get install -y --no-install-recommends \
        libmagic1 gcc g++ curl \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-noto-cjk fontconfig poppler-utils \
        libreoffice-impress libreoffice-writer libreoffice-calc pandoc \
    && rm -rf /var/lib/apt/lists/*

# ── Playwright browser system libs (optional) ─────────────────────────────────
RUN if [ "$INSTALL_BROWSER" = "1" ]; then \
      apt-get update && apt-get install -y --no-install-recommends \
        libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
        libdbus-1-3 libatspi2.0-0 libx11-6 libxcomposite1 libxdamage1 \
        libxext6 libxfixes3 libxrandr2 libgbm1 libxcb1 libxkbcommon0 \
        libpango-1.0-0 libcairo2 libasound2 libgtk-3-0 libgdk-pixbuf-xlib-2.0-0 \
      && rm -rf /var/lib/apt/lists/* ; \
    fi

# ── Python deps ───────────────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Playwright browser (optional) ─────────────────────────────────────────────
RUN if [ "$INSTALL_BROWSER" = "1" ]; then \
      playwright install chromium && chmod -R 755 /ms-playwright ; \
    fi

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: runtime
# ─────────────────────────────────────────────────────────────────────────────
FROM base AS runtime

WORKDIR /app

# Copy application source (respects .dockerignore)
COPY . .

# Pre-create runtime dirs so volumes mount cleanly regardless of order
RUN mkdir -p /app/uploads /app/templates /app/sandbox_workspace /app/data

# Non-root user
RUN useradd --no-create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--log-level", "info"]
