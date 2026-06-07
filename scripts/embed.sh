#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  embed.sh — 调用 BGE-M3 集群把下载好的语料全面入库                       ║
# ║                                                                          ║
# ║  扫描 data/kb_sources/ → 分块 → BGE-M3 embedding → PostgreSQL + Qdrant    ║
# ║  支持断点续传（内容哈希），2TB 可中断后续跑。                             ║
# ║                                                                          ║
# ║  用法:                                                                   ║
# ║    ./scripts/embed.sh                  # 确保依赖就绪 → 全量入库（前台）          ║
# ║    ./scripts/embed.sh --background     # 后台入库（nohup，日志到 logs/）          ║
# ║    ./scripts/embed.sh --source DIR     # 指定语料目录（默认 data/kb_sources）     ║
# ║    ./scripts/embed.sh --status         # 查看入库进度（断点文件统计）             ║
# ║    ./scripts/embed.sh --cluster N      # 启动 N 节点 BGE-M3 集群再入库（默认单机） ║
# ║    ./scripts/embed.sh --stop           # 停止后台入库任务                         ║
# ║                                                                          ║
# ║  前置: PostgreSQL + Qdrant + BGE-M3 embedding 服务可达。                  ║
# ║        本脚本会自动用 Docker 拉起缺失的依赖。                             ║
# ╚══════════════════════════════════════════════════════════════════════════╝

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }
step()  { echo -e "\n${BOLD}${CYAN}▶ $*${NC}"; }

# 脚本封装在 scripts/ 子目录，项目根为其上一级
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
KB_SOURCE="${ROOT_DIR}/data/kb_sources"
PROGRESS_FILE="${ROOT_DIR}/data/bulk_import_progress.json"
LOG_DIR="${ROOT_DIR}/logs/embed"
mkdir -p "${LOG_DIR}"

if   [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then PY="${ROOT_DIR}/.venv/bin/python"
elif [[ -x "${BACKEND_DIR}/.venv/bin/python" ]]; then PY="${BACKEND_DIR}/.venv/bin/python"
else PY="python3"; fi

WORKERS=4

# 加载 .env（DATABASE_URL / QDRANT_URL / EMBED_BASE_URL）
[[ -f "${ROOT_DIR}/.env" ]] && set -a && source "${ROOT_DIR}/.env" && set +a

# ── 参数 ──────────────────────────────────────────────────────────────────────
MODE="run"
CLUSTER_N=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --background) MODE="background" ;;
    --status)     MODE="status" ;;
    --stop)       MODE="stop" ;;
    --source)     KB_SOURCE="${2:?--source 需要目录}"; shift ;;
    --cluster)    CLUSTER_N="${2:?--cluster 需要节点数}"; shift ;;
    --workers)    WORKERS="${2:?--workers 需要数值}"; shift ;;
    -h|--help)    sed -n '/^# ╔/,/^# ╚/p' "$0" | sed 's/^# //'; exit 0 ;;
    *) err "未知参数: $1（--help 查看帮助）" ;;
  esac
  shift
done

compose() {
  if docker compose version >/dev/null 2>&1; then docker compose "$@";
  else docker-compose "$@"; fi
}

port_up() { nc -z localhost "$1" 2>/dev/null; }

# ── --status ──────────────────────────────────────────────────────────────────
if [[ "$MODE" == "status" ]]; then
  step "入库进度"
  if [[ -f "$PROGRESS_FILE" ]]; then
    "${PY}" - "$PROGRESS_FILE" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
files = d.get("files", {})
print(f"  已入库文档: {len(files)}")
print(f"  已写入切片: {d.get('chunks_ingested', 0)}")
PY
  else
    info "尚无入库进度文件（还未开始）"
  fi
  if [[ -f "${LOG_DIR}/embed.pid" ]] && kill -0 "$(cat "${LOG_DIR}/embed.pid")" 2>/dev/null; then
    ok "后台入库进行中（PID $(cat "${LOG_DIR}/embed.pid")）"
  fi
  exit 0
fi

# ── --stop ────────────────────────────────────────────────────────────────────
if [[ "$MODE" == "stop" ]]; then
  if [[ -f "${LOG_DIR}/embed.pid" ]]; then
    kill "$(cat "${LOG_DIR}/embed.pid")" 2>/dev/null && ok "已停止后台入库" || warn "进程已不存在"
    rm -f "${LOG_DIR}/embed.pid"
  else
    info "无后台入库任务"
  fi
  exit 0
fi

# ── 前置检查 ──────────────────────────────────────────────────────────────────
step "前置依赖检查"

[[ -d "$KB_SOURCE" ]] || err "语料目录不存在: $KB_SOURCE（请先 ./download.sh 下载）"
KB_COUNT=$(find "$KB_SOURCE" -maxdepth 1 -type d 2>/dev/null | tail -n +2 | wc -l | tr -d ' ')
[[ "$KB_COUNT" -gt 0 ]] || err "语料目录为空: $KB_SOURCE"
ok "发现 ${KB_COUNT} 个知识库目录待入库"

# 1) PostgreSQL
if port_up 5432; then
  ok "PostgreSQL 就绪 :5432"
else
  info "启动 PostgreSQL…"
  compose -f "${ROOT_DIR}/docker-compose.yml" up -d postgres >/dev/null 2>&1
  for i in $(seq 1 30); do port_up 5432 && break; sleep 1; done
  port_up 5432 && ok "PostgreSQL 已启动" || err "PostgreSQL 启动失败"
  # 建表
  if [[ -x "${BACKEND_DIR}/scripts/init_postgres.sh" ]]; then
    info "运行数据库迁移建表…"
    "${BACKEND_DIR}/scripts/init_postgres.sh" >/dev/null 2>&1 || warn "迁移可能已执行过"
  fi
fi

# 2) Qdrant
if port_up 6333; then
  ok "Qdrant 就绪 :6333"
else
  info "启动 Qdrant…"
  compose -f "${ROOT_DIR}/docker-compose.yml" up -d qdrant >/dev/null 2>&1
  for i in $(seq 1 20); do port_up 6333 && break; sleep 1; done
  port_up 6333 && ok "Qdrant 已启动" || err "Qdrant 启动失败"
fi

# 3) BGE-M3 embedding 服务
EMBED_URL="${EMBED_BASE_URL:-http://localhost:8000/v1}"
EMBED_HEALTH="${EMBED_URL%/v1}/health"
if curl -sf "$EMBED_HEALTH" >/dev/null 2>&1; then
  ok "BGE-M3 embedding 服务就绪 ($EMBED_URL)"
elif [[ "$CLUSTER_N" -gt 0 ]]; then
  step "启动 BGE-M3 集群（${CLUSTER_N} 节点）"
  EMBED_REPLICAS="$CLUSTER_N" compose \
    -f "${ROOT_DIR}/docker-compose.yml" up -d embedding-worker embedding-lb >/dev/null 2>&1 || true
  info "等待集群加载模型（首次需下载 BGE-M3 ~2GB）…"
  for i in $(seq 1 120); do curl -sf "http://localhost:8080/health" >/dev/null 2>&1 && break; sleep 3; done
  if curl -sf "http://localhost:8080/health" >/dev/null 2>&1; then
    ok "BGE-M3 集群就绪（LB :8080）"
    export EMBED_BASE_URL="http://localhost:8080/v1"
  else
    err "BGE-M3 集群启动超时，查看: docker compose logs embedding-worker"
  fi
else
  err "BGE-M3 embedding 服务不可达 ($EMBED_URL)。
  选项1: 用 --cluster N 启动内置集群，如 ./scripts/embed.sh --cluster 4
  选项2: 在 .env 配置 EMBED_BASE_URL 指向已部署的 embedding 服务"
fi

# ── 执行入库 ──────────────────────────────────────────────────────────────────
run_import() {
  cd "${BACKEND_DIR}"
  PYTHONPATH=. "${PY}" -m app.services.bulk_importer \
    --source "${KB_SOURCE}" \
    --progress "${PROGRESS_FILE}" \
    --workers "${WORKERS}"
}

if [[ "$MODE" == "background" ]]; then
  TS="$(date +%Y%m%d_%H%M%S)"
  LOG_FILE="${LOG_DIR}/embed_${TS}.log"
  step "后台入库 → ${LOG_FILE}"
  nohup bash -c "cd '${BACKEND_DIR}' && PYTHONPATH=. '${PY}' -m app.services.bulk_importer --source '${KB_SOURCE}' --progress '${PROGRESS_FILE}' --workers ${WORKERS}" \
    > "${LOG_FILE}" 2>&1 &
  echo $! > "${LOG_DIR}/embed.pid"
  ok "已后台启动入库（PID $(cat "${LOG_DIR}/embed.pid")）"
  info "查看进度: ./scripts/embed.sh --status"
  info "查看日志: tail -f ${LOG_FILE}"
  info "停止:     ./scripts/embed.sh --stop"
else
  step "开始全量入库（前台）—— 源: ${KB_SOURCE}"
  info "断点续传：已入库文档会自动跳过，可随时 Ctrl+C 后重跑"
  run_import
  echo ""
  ok "入库完成。验证: ./scripts/embed.sh --status"
  info "知识库已可在前端「知识库」页查看，生成报告时自动 RAG 召回。"
fi
