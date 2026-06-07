#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  download.sh — DataAgent 全量语料下载编排（2TB 世界观语料）              ║
# ║                                                                          ║
# ║  在本机/下载服务器运行，驱动 data-collector/ 的 26 个采集器分批下载。     ║
# ║  下载产物落到 data/kb_sources/，格式与 bulk_importer 兼容，可直接入库。   ║
# ║                                                                          ║
# ║  用法:                                                                   ║
# ║    ./scripts/download.sh                    # 交互式：按优先级逐批下载            ║
# ║    ./scripts/download.sh --all              # 一次性全量下载（前台）             ║
# ║    ./scripts/download.sh --priority N       # 只下载优先级 ≤ N 的采集器          ║
# ║    ./scripts/download.sh --target KEY       # 只下载指定采集器（如 wikipedia_zh） ║
# ║    ./scripts/download.sh --background       # 后台运行全量（nohup，日志到 logs/） ║
# ║    ./scripts/download.sh --rss              # 启动 RSS 增量守护进程               ║
# ║    ./scripts/download.sh --status           # 查看各采集器进度                    ║
# ║    ./scripts/download.sh --setup            # 仅安装依赖（首次运行）              ║
# ║                                                                          ║
# ║  并发控制（可加在任意下载模式后）:                                       ║
# ║    --concurrency N   同时并行运行 N 个采集器（默认 config 的 4）         ║
# ║    例: ./scripts/download.sh --background --concurrency 6                ║
# ║                                                                          ║
# ║  环境变量:                                                               ║
# ║    HTTP_PROXY=http://...  采集器代理（裁判文书/企业信用等反爬站点必需）   ║
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
COLLECTOR_DIR="${ROOT_DIR}/scripts/data_collection"
KB_OUT="${ROOT_DIR}/data/kb_sources"
LOG_DIR="${ROOT_DIR}/logs/collector"
mkdir -p "${LOG_DIR}"

# 选择 Python
if   [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then PY="${ROOT_DIR}/.venv/bin/python"
elif [[ -x "${COLLECTOR_DIR}/.venv/bin/python" ]]; then PY="${COLLECTOR_DIR}/.venv/bin/python"
else PY="python3"; fi

run_collector() { cd "${COLLECTOR_DIR}" && "${PY}" run.py "$@"; }

# Workers from --concurrency
CONCURRENCY="${CONCURRENCY:-4}"
WORKERS_ARG=""
[[ -n "$CONCURRENCY" ]] && WORKERS_ARG="--workers ${CONCURRENCY}"

# ── 依赖安装 ──────────────────────────────────────────────────────────────────
do_setup() {
  step "安装采集器依赖"
  "${PY}" -m pip install -q -r "${COLLECTOR_DIR}/requirements.txt"
  if "${PY}" -c "import playwright" 2>/dev/null; then
    "${PY}" -m playwright install chromium 2>/dev/null || warn "playwright chromium 安装失败（部分动态页面采集器受影响）"
  fi
  ok "依赖安装完成"
}

# ── 磁盘空间检查 ──────────────────────────────────────────────────────────────
check_disk() {
  step "磁盘空间检查"
  local avail_kb
  avail_kb=$(df -k "${ROOT_DIR}" | tail -1 | awk '{print $4}')
  local avail_gb=$((avail_kb / 1024 / 1024))
  info "可用空间: ${avail_gb} GB"
  if [[ $avail_gb -lt 2500 ]]; then
    warn "全量下载预计需 ~2TB，当前可用 ${avail_gb}GB 可能不足。"
    warn "建议预留 ≥2500GB，或先用 --priority 分批下载。"
  else
    ok "空间充足（≥2500GB）"
  fi
}

# ── 代理提示 ──────────────────────────────────────────────────────────────────
check_proxy() {
  if [[ -z "${HTTP_PROXY:-}" ]] && ! grep -qE '^\s*proxy:\s*"\S' "${COLLECTOR_DIR}/config.yaml" 2>/dev/null; then
    warn "未配置代理。裁判文书网/企业信用等反爬站点会失败。"
    warn "  设置: export HTTP_PROXY=http://你的代理:端口  或编辑 config.yaml 的 proxy 字段"
  fi
}

# ── 各优先级批次 ──────────────────────────────────────────────────────────────
batch_label() {
  case "$1" in
    0) echo "基础世界观语料（维基/CC-100/OpenKG，直接下载最稳）" ;;
    1) echo "法律核心（裁判文书网，体量最大，需代理）" ;;
    2) echo "金融企业核心（银行/央企/上市公司/互联网大厂年报）" ;;
    3) echo "政策/国际/行业域（外交/咨询/医疗/教育/能源/科技/海关）" ;;
    4) echo "补充维度（农业/房产/交通/人口/工商/人才/文化/体育）" ;;
    5) echo "实时增量（新闻 RSS，守护进程）" ;;
  esac
}

# ── 主流程 ────────────────────────────────────────────────────────────────────
MODE="interactive"
TARGET=""
PRIORITY=99
CONCURRENCY=""   # 空=用 config.yaml 的 collector_concurrency

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)         MODE="all" ;;
    --background)  MODE="background" ;;
    --rss)         MODE="rss" ;;
    --status)      MODE="status" ;;
    --setup)       MODE="setup" ;;
    --priority)    PRIORITY="${2:?--priority 需要数值}"; MODE="priority"; shift ;;
    --target)      TARGET="${2:?--target 需要采集器 key}"; MODE="target"; shift ;;
    --concurrency) CONCURRENCY="${2:?--concurrency 需要数值}"; shift ;;
    -h|--help)     sed -n '/^# ╔/,/^# ╚/p' "$0" | sed 's/^# //'; exit 0 ;;
    *) err "未知参数: $1（--help 查看帮助）" ;;
  esac
  shift
done

# 并发参数透传给 run.py
CONC_ARG=()
[[ -n "$CONCURRENCY" ]] && CONC_ARG=(--workers "$CONCURRENCY")

[[ -d "${COLLECTOR_DIR}" ]] || err "未找到 data-collector/ 目录"

case "$MODE" in
  setup)
    do_setup
    ;;

  status)
    run_collector status
    echo ""
    if [[ -d "${KB_OUT}" ]]; then
      info "已下载语料目录数: $(find "${KB_OUT}" -maxdepth 1 -type d 2>/dev/null | tail -n +2 | wc -l | tr -d ' ')"
      info "kb_sources 总大小: $(du -sh "${KB_OUT}" 2>/dev/null | cut -f1)"
    fi
    ;;

  target)
    check_proxy
    step "下载采集器: ${TARGET}"
    run_collector crawl --target "${TARGET}" ${WORKERS_ARG}
    ;;

  priority)
    do_setup; check_disk; check_proxy
    step "并发下载优先级 ≤ ${PRIORITY} 的采集器"
    run_collector crawl --target all --priority "${PRIORITY}" ${WORKERS_ARG}
    ;;

  all)
    do_setup; check_disk; check_proxy
    step "并发全量下载（按优先级 0→5 调度，2023年起）"
    run_collector crawl --target all --since 2023 ${WORKERS_ARG}
    ;;

  background)
    do_setup; check_disk; check_proxy
    local_ts="$(date +%Y%m%d_%H%M%S)"
    LOG_FILE="${LOG_DIR}/download_all_${local_ts}.log"
    CONC_INLINE="${CONCURRENCY:+--concurrency ${CONCURRENCY}}"
    step "后台并发全量下载 → ${LOG_FILE}"
    nohup bash -c "cd '${COLLECTOR_DIR}' && '${PY}' run.py crawl --target all --since 2023 ${CONC_INLINE}" \
      > "${LOG_FILE}" 2>&1 &
    echo $! > "${LOG_DIR}/download.pid"
    ok "已后台启动（PID $(cat "${LOG_DIR}/download.pid")）"
    info "查看进度: ./scripts/download.sh --status"
    info "查看日志: tail -f ${LOG_FILE}"
    info "停止:     kill \$(cat ${LOG_DIR}/download.pid)"
    ;;

  rss)
    do_setup
    LOG_FILE="${LOG_DIR}/rss_daemon.log"
    step "启动 RSS 增量守护进程 → ${LOG_FILE}"
    nohup bash -c "cd '${COLLECTOR_DIR}' && '${PY}' run.py rss --daemon" \
      > "${LOG_FILE}" 2>&1 &
    echo $! > "${LOG_DIR}/rss.pid"
    ok "RSS 守护进程已启动（PID $(cat "${LOG_DIR}/rss.pid")，每小时拉取一次）"
    ;;

  interactive)
    do_setup; check_disk; check_proxy
    echo ""
    echo -e "${BOLD}═══ DataAgent 全量语料下载（交互式分批）═══${NC}"
    echo "  数据落到: ${KB_OUT}"
    echo "  下载完成后用 ./scripts/embed.sh 入库（或 ./scripts/build_offline.sh --with-data 打包）"
    echo ""
    for p in 0 1 2 3 4; do
      echo -e "${CYAN}── 批次 P${p}: $(batch_label $p) ──${NC}"
      read -r -p "  现在下载这一批吗？[y/N/q] " ans
      case "$ans" in
        y|Y) run_collector crawl --target all --priority "$p" --since 2023 ${WORKERS_ARG} ;;
        q|Q) info "已退出"; exit 0 ;;
        *)   info "跳过 P${p}" ;;
      esac
    done
    echo ""
    read -r -p "启动 RSS 增量守护进程？[y/N] " ans
    [[ "$ans" =~ ^[yY]$ ]] && { nohup bash -c "cd '${COLLECTOR_DIR}' && '${PY}' run.py rss --daemon" > "${LOG_DIR}/rss_daemon.log" 2>&1 & ok "RSS 守护进程已启动"; }
    echo ""
    ok "下载流程结束。运行 ./scripts/download.sh --status 查看汇总。"
    ;;
esac
