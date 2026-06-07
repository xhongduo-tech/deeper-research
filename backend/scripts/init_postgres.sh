#!/usr/bin/env bash
# init_postgres.sh — 初始化 PostgreSQL 数据库并运行 Alembic 迁移
# 用法: ./backend/scripts/init_postgres.sh
#
# 前置条件: PostgreSQL 已在 localhost:5432 运行
#   docker compose up -d postgres   ← 推荐方式

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROOT_DIR="$(cd "${BACKEND_DIR}/.." && pwd)"

# 选择 venv
if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  PYTHON="${ROOT_DIR}/.venv/bin/python"
  ALEMBIC="${ROOT_DIR}/.venv/bin/alembic"
else
  PYTHON="python3"
  ALEMBIC="alembic"
fi

echo "=== DataAgent: 初始化 PostgreSQL ==="

# 1. 等待 PostgreSQL 就绪
echo -n "等待 PostgreSQL..."
for i in $(seq 1 30); do
  if nc -z localhost 5432 2>/dev/null; then
    echo " 就绪"
    break
  fi
  echo -n "."
  sleep 1
  if [[ $i -eq 30 ]]; then
    echo ""
    echo "ERROR: PostgreSQL 30s 内未就绪。请先运行: docker compose up -d postgres"
    exit 1
  fi
done

# 2. 运行 Alembic 迁移（自动建表）
echo "运行数据库迁移..."
cd "${BACKEND_DIR}"
PYTHONPATH=. "${ALEMBIC}" upgrade head

echo "✅ 数据库初始化完成"
echo ""
echo "下一步运行后端:"
echo "  ./dev.sh"
