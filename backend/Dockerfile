FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# 构建参数：是否安装浏览器控制相关依赖与 Playwright Chromium 二进制。
# Mac 本机开发可传 --build-arg INSTALL_BROWSER=0 降低内存压力和构建耗时。
# 生产 x86 默认安装。
ARG INSTALL_BROWSER=1

# ------------------------------------------------------------------
# 第 1 层：核心系统依赖（文件解析 + 中文字体 + 构建工具链）
# 拆成多个 RUN 以降低单次 apt 峰值内存，避免 Mac Docker Desktop OOM。
# ------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    gcc \
    g++ \
    wget \
    curl \
    git \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    fonts-noto-cjk-extra \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------
# 第 2 层（可选）：Playwright Chromium 所需系统库
# 仅在 INSTALL_BROWSER=1 时安装；Mac 本机测试可跳过。
# ------------------------------------------------------------------
RUN if [ "$INSTALL_BROWSER" = "1" ]; then \
      apt-get update && apt-get install -y --no-install-recommends \
        libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
        libdrm2 libdbus-1-3 libatspi2.0-0 libx11-6 libxcomposite1 \
        libxdamage1 libxext6 libxfixes3 libxrandr2 libgbm1 libxcb1 \
        libxkbcommon0 libpango-1.0-0 libcairo2 libasound2 libgtk-3-0 \
        libgdk-pixbuf-xlib-2.0-0 \
      && rm -rf /var/lib/apt/lists/* ; \
    else \
      echo "跳过浏览器系统依赖 (INSTALL_BROWSER=0)" ; \
    fi

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright Chromium 浏览器二进制（仅在 INSTALL_BROWSER=1 时安装）
RUN if [ "$INSTALL_BROWSER" = "1" ]; then \
      playwright install chromium && chmod -R 755 /ms-playwright ; \
    else \
      echo "跳过 Playwright Chromium 下载" ; \
    fi

# 应用目录
RUN mkdir -p /app/uploads /app/templates /app/sandbox_workspace /app/uploads/outputs /app/data

# 应用代码
COPY . .

# 非 root 用户
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--log-level", "info"]
