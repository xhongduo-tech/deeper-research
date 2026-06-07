#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  dev.sh — DataAgent Studio  Mac 本地开发一键脚本                         ║
# ║                                                                          ║
# ║  用法:                                                                   ║
# ║    ./scripts/dev.sh                   # 启动后端 + 前端 dev server               ║
# ║    ./scripts/dev.sh --rebuild         # 重装 npm 依赖后启动                       ║
# ║    ./scripts/dev.sh --backend         # 仅重启后端                               ║
# ║    ./scripts/dev.sh --frontend        # 仅重启前端 dev server                    ║
# ║    ./scripts/dev.sh --clean           # 清空 SQLite 数据库后全量启动              ║
# ║    ./scripts/dev.sh --test            # 对运行中实例执行 API 冒烟测试              ║
# ║    ./scripts/dev.sh --docker          # 用 Docker Compose 启动（生产镜像）        ║
# ║    ./scripts/dev.sh --rebuild --docker # 重建镜像后启动 Docker 栈                ║
# ║    ./scripts/dev.sh --stop            # 停止所有本地进程                          ║
# ║    ./scripts/dev.sh --status          # 查看各服务运行状态                        ║
# ║    ./scripts/dev.sh --logs            # 跟踪后端日志                              ║
# ║    ./scripts/dev.sh --logs --frontend # 跟踪前端日志                              ║
# ║                                                                          ║
# ║  可组合标志（顺序无关）:                                                  ║
# ║    ./scripts/dev.sh --clean --test                                               ║
# ║    ./scripts/dev.sh --rebuild --test                                             ║
# ║                                                                          ║
# ║  选项:                                                                   ║
# ║    --api-port PORT    后端端口（默认 8000）                               ║
# ║    --ui-port  PORT    前端端口（默认 5173）                               ║
# ║    --no-browser       不自动打开浏览器                                    ║
# ╚══════════════════════════════════════════════════════════════════════════╝

set -euo pipefail

# ── 颜色 ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()      { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }
step()    { echo -e "\n${BOLD}${CYAN}▶ $*${NC}"; }
divider() { echo -e "${CYAN}──────────────────────────────────────────────────${NC}"; }

# ── 路径 ──────────────────────────────────────────────────────────────────
# 脚本封装在 scripts/ 子目录；SCRIPT_DIR 指向项目根（其上一级）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${SCRIPT_DIR}/backend"
FRONTEND_DIR="${SCRIPT_DIR}/frontend"
LOG_DIR="${SCRIPT_DIR}/logs"
BACKEND_LOG="${LOG_DIR}/dev-backend.log"
FRONTEND_LOG="${LOG_DIR}/dev-frontend.log"
PID_FILE="${LOG_DIR}/pids/dev.pid"

# ── 默认配置 ───────────────────────────────────────────────────────────────
API_PORT=8000
UI_PORT=5173
OPEN_BROWSER=true

# ── 标志位 ────────────────────────────────────────────────────────────────
DO_START=true
DO_REBUILD=false
DO_BACKEND_ONLY=false
DO_FRONTEND_ONLY=false
DO_CLEAN=false
DO_TEST=false
DO_DOCKER=false
DO_STOP=false
DO_STATUS=false
DO_LOGS=false
LOG_TARGET="backend"   # backend | frontend

# ── 参数解析 ──────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --rebuild)      DO_REBUILD=true ;;
    --backend)      DO_BACKEND_ONLY=true; DO_FRONTEND_ONLY=false ;;
    --frontend)     DO_FRONTEND_ONLY=true; DO_BACKEND_ONLY=false ;;
    --clean)        DO_CLEAN=true ;;
    --test)         DO_TEST=true ;;
    --docker)       DO_DOCKER=true ;;
    --stop)         DO_STOP=true;   DO_START=false ;;
    --status)       DO_STATUS=true; DO_START=false ;;
    --logs)
      DO_LOGS=true; DO_START=false
      if [[ "${2:-}" == "--frontend" ]]; then LOG_TARGET="frontend"; shift; fi
      ;;
    --no-browser)   OPEN_BROWSER=false ;;
    --api-port)     API_PORT="${2:?--api-port requires a value}"; shift ;;
    --ui-port)      UI_PORT="${2:?--ui-port requires a value}"; shift ;;
    -h|--help)      sed -n '/^# ╔/,/^# ╚/p' "$0" | sed 's/^# //'; exit 0 ;;
    *) error "未知参数: $1  (用 --help 查看帮助)" ;;
  esac
  shift
done

mkdir -p "${LOG_DIR}" "${LOG_DIR}/pids"

# ══════════════════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════════════════

save_pid() {
  local name="$1" pid="$2"
  # 追加写，每个名字保留最新一行
  local tmp; tmp=$(grep -v "^${name}=" "${PID_FILE}" 2>/dev/null || true)
  echo "$tmp" > "${PID_FILE}" 2>/dev/null || true
  echo "${name}=${pid}" >> "${PID_FILE}"
}

read_pid() {
  local name="$1"
  [[ -f "${PID_FILE}" ]] || return 1
  grep "^${name}=" "${PID_FILE}" | tail -1 | cut -d= -f2
}

is_running() {
  local pid="${1:-}"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

port_in_use() {
  lsof -ti :"$1" >/dev/null 2>&1
}

wait_for_port() {
  local port="$1" name="$2" max="${3:-30}"
  local i=0
  while ! lsof -ti :"$port" >/dev/null 2>&1; do
    i=$((i+1))
    [[ $i -ge $max ]] && { echo ""; error "${name} 在端口 ${port} 启动超时（${max}s），查看日志: ${BACKEND_LOG}"; }
    printf "."
    sleep 1
  done
  echo ""
}

open_browser_url() {
  local url="$1"
  if [[ "$OPEN_BROWSER" == true ]]; then
    sleep 1
    open "$url" 2>/dev/null || true
  fi
}

resolve_python() {
  # 优先使用 backend/.venv，其次根目录 .venv，最后系统 python3
  if [[ -x "${BACKEND_DIR}/.venv/bin/python" ]]; then
    echo "${BACKEND_DIR}/.venv/bin/python"
  elif [[ -x "${SCRIPT_DIR}/.venv/bin/python" ]]; then
    echo "${SCRIPT_DIR}/.venv/bin/python"
  else
    echo "python3"
  fi
}

resolve_venv_dir() {
  if [[ -d "${BACKEND_DIR}/.venv" ]]; then
    echo "${BACKEND_DIR}/.venv"
  else
    echo "${SCRIPT_DIR}/.venv"
  fi
}

# ══════════════════════════════════════════════════════════════════════════
# --stop
# ══════════════════════════════════════════════════════════════════════════
cmd_stop() {
  step "停止本地进程"

  if [[ -f "${PID_FILE}" ]]; then
    while IFS='=' read -r name pid; do
      [[ -z "$name" || -z "$pid" ]] && continue
      if is_running "$pid"; then
        kill "$pid" 2>/dev/null && ok "已停止 ${name} (PID ${pid})"
      fi
    done < "${PID_FILE}"
    rm -f "${PID_FILE}"
  fi

  # 兜底：按端口 kill
  for port in "$API_PORT" "$UI_PORT"; do
    local pids
    pids=$(lsof -ti :"$port" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
      echo "$pids" | xargs kill 2>/dev/null && ok "已释放端口 ${port}"
    fi
  done

  # 精确匹配进程名
  pkill -f "uvicorn app.main:app.*${API_PORT}" 2>/dev/null || true
  pkill -f "vite.*${UI_PORT}"                 2>/dev/null || true

  ok "所有本地进程已停止"
}

# ══════════════════════════════════════════════════════════════════════════
# --status
# ══════════════════════════════════════════════════════════════════════════
cmd_status() {
  divider
  echo -e "${BOLD}服务状态${NC}"
  divider

  # 后端
  if port_in_use "$API_PORT"; then
    local health
    health=$(curl -sf "http://127.0.0.1:${API_PORT}/api/health" 2>/dev/null \
             | python3 -c "import json,sys; print(json.load(sys.stdin).get('status','?'))" 2>/dev/null \
             || echo "无响应")
    echo -e "  后端 API   ${GREEN}● 运行中${NC}  http://127.0.0.1:${API_PORT}  (health: ${health})"
  else
    echo -e "  后端 API   ${RED}○ 未运行${NC}"
  fi

  # 前端
  if port_in_use "$UI_PORT"; then
    echo -e "  前端 UI    ${GREEN}● 运行中${NC}  http://127.0.0.1:${UI_PORT}"
  else
    echo -e "  前端 UI    ${RED}○ 未运行${NC}"
  fi

  # Redis
  if redis-cli -h 127.0.0.1 ping >/dev/null 2>&1; then
    echo -e "  Redis      ${GREEN}● 运行中${NC}  127.0.0.1:6379"
  elif port_in_use 6379; then
    echo -e "  Redis      ${GREEN}● 运行中${NC}  (Docker/其他)"
  else
    echo -e "  Redis      ${RED}○ 未运行${NC}"
  fi

  # PostgreSQL
  if port_in_use 5432; then
    echo -e "  PostgreSQL ${GREEN}● 运行中${NC}  127.0.0.1:5432"
  else
    echo -e "  PostgreSQL ${RED}○ 未运行${NC}   运行: docker compose up -d postgres"
  fi

  # Qdrant
  if port_in_use 6333; then
    echo -e "  Qdrant     ${GREEN}● 运行中${NC}  http://127.0.0.1:6333"
  else
    echo -e "  Qdrant     ${RED}○ 未运行${NC}   运行: docker compose up -d qdrant"
  fi

  # Docker
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    local running
    running=$(docker compose -f "${SCRIPT_DIR}/docker-compose.yml" ps --services --filter status=running 2>/dev/null || true)
    if [[ -n "$running" ]]; then
      echo -e "  Docker     ${GREEN}● 运行中${NC}  $(echo "$running" | tr '\n' ' ')"
    else
      echo -e "  Docker     ${RED}○ 未运行${NC}"
    fi
  fi

  # 数据库
  local db_path="${SCRIPT_DIR}/data/db/app.db"
  if [[ -f "$db_path" ]]; then
    local size; size=$(du -sh "$db_path" | cut -f1)
    echo -e "  数据库     ${GREEN}● 存在${NC}    ${db_path}  (${size})"
  else
    echo -e "  数据库     ${YELLOW}○ 不存在${NC}   ${db_path}"
  fi

  divider
}

# ══════════════════════════════════════════════════════════════════════════
# --logs
# ══════════════════════════════════════════════════════════════════════════
cmd_logs() {
  local log_file="${BACKEND_LOG}"
  [[ "$LOG_TARGET" == "frontend" ]] && log_file="${FRONTEND_LOG}"

  if [[ ! -f "$log_file" ]]; then
    warn "未找到日志文件: ${log_file}"
    info "请先启动（./scripts/dev.sh）"
    exit 0
  fi
  info "跟踪 ${LOG_TARGET} 日志（Ctrl+C 退出）"
  tail -f "$log_file"
}

# ══════════════════════════════════════════════════════════════════════════
# 检查依赖
# ══════════════════════════════════════════════════════════════════════════
check_prereqs() {
  step "检查依赖"

  local missing=()
  command -v python3 >/dev/null 2>&1 || missing+=("python3 (brew install python)")
  command -v node    >/dev/null 2>&1 || missing+=("node (brew install node)")
  command -v npm     >/dev/null 2>&1 || missing+=("npm (随 node 安装)")
  command -v curl    >/dev/null 2>&1 || missing+=("curl")

  if [[ ${#missing[@]} -gt 0 ]]; then
    error "缺少依赖:\n  ${missing[*]}"
  fi

  local py_ver node_ver
  py_ver=$(python3 --version 2>&1 | awk '{print $2}')
  node_ver=$(node --version)
  ok "Python ${py_ver}  Node ${node_ver}"
}

# ══════════════════════════════════════════════════════════════════════════
# 确保 Redis 可用
# ══════════════════════════════════════════════════════════════════════════
ensure_redis() {
  step "Redis"

  # 已在运行？
  if redis-cli -h 127.0.0.1 ping >/dev/null 2>&1 || port_in_use 6379; then
    ok "Redis 已就绪  127.0.0.1:6379"
    return 0
  fi

  # 本机有 redis-server？
  if command -v redis-server >/dev/null 2>&1; then
    info "启动本机 redis-server..."
    redis-server --daemonize yes --logfile "${LOG_DIR}/redis.log" \
      --maxmemory 256mb --maxmemory-policy allkeys-lru >/dev/null 2>&1
    sleep 1
    if redis-cli ping >/dev/null 2>&1; then
      ok "Redis 已启动 (本机)"
      return 0
    fi
  fi

  # 用 Docker 启动 redis 容器？
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    info "用 Docker 启动 Redis..."
    if docker compose version >/dev/null 2>&1; then
      docker compose -f "${SCRIPT_DIR}/docker-compose.yml" up -d redis >/dev/null 2>&1
    else
      docker-compose -f "${SCRIPT_DIR}/docker-compose.yml" up -d redis >/dev/null 2>&1
    fi
    local i=0
    while ! redis-cli -h 127.0.0.1 ping >/dev/null 2>&1; do
      i=$((i+1)); [[ $i -ge 15 ]] && break; sleep 1; printf "."
    done
    echo ""
    if redis-cli -h 127.0.0.1 ping >/dev/null 2>&1 || port_in_use 6379; then
      ok "Redis 已启动 (Docker)"
      return 0
    fi
  fi

  error "Redis 未找到。\n  选项 1（推荐）: brew install redis && brew services start redis\n  选项 2: 启动 Docker Desktop 后重试"
}

# ══════════════════════════════════════════════════════════════════════════
# 确保 PostgreSQL 可用（本地开发）
# ══════════════════════════════════════════════════════════════════════════
ensure_postgres() {
  step "PostgreSQL"

  # 已在运行？
  if port_in_use 5432; then
    ok "PostgreSQL 已就绪  127.0.0.1:5432"
    return 0
  fi

  # 用 Docker 启动
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    info "用 Docker 启动 PostgreSQL..."
    if docker compose version >/dev/null 2>&1; then
      docker compose -f "${SCRIPT_DIR}/docker-compose.yml" up -d postgres >/dev/null 2>&1
    else
      docker-compose -f "${SCRIPT_DIR}/docker-compose.yml" up -d postgres >/dev/null 2>&1
    fi
    local i=0
    while ! port_in_use 5432; do
      i=$((i+1)); [[ $i -ge 30 ]] && break; sleep 1; printf "."
    done
    echo ""
    if port_in_use 5432; then
      ok "PostgreSQL 已启动 (Docker)  dataagent@localhost:5432/dataagent"
      return 0
    fi
  fi

  warn "PostgreSQL 未启动。可手动运行：\n  docker compose up -d postgres\n  或: brew install postgresql@15 && brew services start postgresql@15"
}

# ══════════════════════════════════════════════════════════════════════════
# 确保 Qdrant 可用（向量存储）
# ══════════════════════════════════════════════════════════════════════════
ensure_qdrant() {
  step "Qdrant (向量存储)"

  # 已在运行？
  if port_in_use 6333; then
    ok "Qdrant 已就绪  http://127.0.0.1:6333"
    return 0
  fi

  # 用 Docker 启动
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    info "用 Docker 启动 Qdrant..."
    if docker compose version >/dev/null 2>&1; then
      docker compose -f "${SCRIPT_DIR}/docker-compose.yml" up -d qdrant >/dev/null 2>&1
    else
      docker-compose -f "${SCRIPT_DIR}/docker-compose.yml" up -d qdrant >/dev/null 2>&1
    fi
    local i=0
    while ! port_in_use 6333; do
      i=$((i+1)); [[ $i -ge 20 ]] && break; sleep 1; printf "."
    done
    echo ""
    if port_in_use 6333; then
      ok "Qdrant 已启动 (Docker)  http://127.0.0.1:6333"
      return 0
    fi
  fi

  warn "Qdrant 未启动。可手动运行：\n  docker compose up -d qdrant\n  或: docker run -d -p 6333:6333 qdrant/qdrant"
}

# ══════════════════════════════════════════════════════════════════════════
# 配置 Python 虚拟环境 & 安装依赖
# ══════════════════════════════════════════════════════════════════════════
setup_venv() {
  step "Python 虚拟环境"

  local venv_dir; venv_dir="$(resolve_venv_dir)"

  if [[ ! -d "${venv_dir}" ]]; then
    info "创建虚拟环境 ${venv_dir}"
    python3 -m venv "${venv_dir}"
  fi

  local py_exec="${venv_dir}/bin/python"
  local pip_exec="${venv_dir}/bin/pip"

  local installed_hash req_hash
  installed_hash=$(cat "${venv_dir}/.req_hash" 2>/dev/null || echo "")
  req_hash=$(md5 -q "${BACKEND_DIR}/requirements.txt" 2>/dev/null \
             || md5sum "${BACKEND_DIR}/requirements.txt" | cut -d' ' -f1)

  if [[ "$installed_hash" != "$req_hash" ]]; then
    info "安装/更新 Python 依赖..."
    "${pip_exec}" install -q --upgrade pip
    "${pip_exec}" install -q -r "${BACKEND_DIR}/requirements.txt"
    echo "$req_hash" > "${venv_dir}/.req_hash"
    ok "Python 依赖安装完成"
  else
    ok "Python 依赖已是最新"
  fi
}

# ══════════════════════════════════════════════════════════════════════════
# 安装前端依赖（按需）
# ══════════════════════════════════════════════════════════════════════════
setup_frontend_deps() {
  step "前端依赖"

  local nm_hash pkg_hash
  nm_hash=$(cat "${FRONTEND_DIR}/node_modules/.install_hash" 2>/dev/null || echo "")
  pkg_hash=$(md5 -q "${FRONTEND_DIR}/package.json" 2>/dev/null \
             || md5sum "${FRONTEND_DIR}/package.json" | cut -d' ' -f1)

  if [[ "$DO_REBUILD" == true ]] || [[ "$nm_hash" != "$pkg_hash" ]] || [[ ! -d "${FRONTEND_DIR}/node_modules" ]]; then
    info "安装 npm 依赖..."
    npm --prefix "${FRONTEND_DIR}" install --silent
    echo "$pkg_hash" > "${FRONTEND_DIR}/node_modules/.install_hash"
    ok "npm 依赖安装完成"
  else
    ok "npm 依赖已是最新"
  fi
}

# ══════════════════════════════════════════════════════════════════════════
# 读取 .env 并导出
# ══════════════════════════════════════════════════════════════════════════
load_dotenv() {
  local env_file="${SCRIPT_DIR}/.env"

  if [[ ! -f "$env_file" ]]; then
    if [[ -f "${SCRIPT_DIR}/.env.example" ]]; then
      cp "${SCRIPT_DIR}/.env.example" "$env_file"
      info "已从 .env.example 生成 .env"
    fi
  fi

  # 自动生成 SECRET_KEY
  if grep -q 'change-this-to-a-random-64-char-string' "$env_file" 2>/dev/null; then
    local secret
    secret="$(openssl rand -hex 32 2>/dev/null || date +%s | md5 | head -c 32)"
    sed -i '' "s/change-this-to-a-random-64-char-string/${secret}/" "$env_file"
    info "已自动生成 SECRET_KEY"
  fi

  # 导出 .env 变量：逐行 export，跳过注释、空行、不含 = 的行
  while IFS= read -r line; do
    # 跳过注释和空行
    [[ "$line" =~ ^\s*# || -z "${line// /}" ]] && continue
    # 必须含 = 才是赋值行
    [[ "$line" != *=* ]] && continue
    local key="${line%%=*}"
    local val="${line#*=}"
    # 去掉值两端的引号（单引号或双引号）
    val="${val#\"}" ; val="${val%\"}"
    val="${val#\'}" ; val="${val%\'}"
    export "${key}"="${val}"
  done < "$env_file"
}

# ══════════════════════════════════════════════════════════════════════════
# 启动后端
# ══════════════════════════════════════════════════════════════════════════
start_backend() {
  step "启动后端 (端口 ${API_PORT})"

  if port_in_use "$API_PORT"; then
    warn "端口 ${API_PORT} 已被占用，尝试释放..."
    lsof -ti :"${API_PORT}" | xargs kill -9 2>/dev/null || true
    sleep 1
  fi

  local venv_dir; venv_dir="$(resolve_venv_dir)"
  local py_exec="${venv_dir}/bin/python"

  # 确保数据目录存在
  mkdir -p "${SCRIPT_DIR}/data/db" \
           "${SCRIPT_DIR}/data/uploads" \
           "${SCRIPT_DIR}/data/templates" \
           "${SCRIPT_DIR}/data/sandbox"

  # Pass all .env-derived variables explicitly so pydantic_settings picks them up
  # regardless of how bash handles env inheritance in nohup subprocesses.
  DATABASE_URL="sqlite+aiosqlite:///${SCRIPT_DIR}/data/db/app.db" \
  REDIS_URL="redis://127.0.0.1:6379" \
  UPLOAD_DIR="${SCRIPT_DIR}/data/uploads" \
  TEMPLATE_DIR="${SCRIPT_DIR}/data/templates" \
  SANDBOX_WORKSPACE="${SCRIPT_DIR}/data/sandbox" \
  DATA_DIR="${SCRIPT_DIR}/data/db" \
  SECRET_KEY="${SECRET_KEY:-}" \
  DEFAULT_ADMIN_USERNAME="${DEFAULT_ADMIN_USERNAME:-admin}" \
  DEFAULT_ADMIN_PASSWORD="${DEFAULT_ADMIN_PASSWORD:-}" \
  DEFAULT_LLM_BASE_URL="${DEFAULT_LLM_BASE_URL:-}" \
  DEFAULT_LLM_MODEL="${DEFAULT_LLM_MODEL:-}" \
  DEFAULT_LLM_API_KEY="${DEFAULT_LLM_API_KEY:-}" \
    nohup bash -c "cd '${BACKEND_DIR}' && exec '${py_exec}' -m uvicorn app.main:app \
      --host 127.0.0.1 \
      --port ${API_PORT} \
      --reload \
      --log-level info" \
    >> "${BACKEND_LOG}" 2>&1 &

  local backend_pid=$!
  save_pid "backend" "$backend_pid"
  disown "$backend_pid"

  printf "  等待后端就绪"
  wait_for_port "$API_PORT" "后端" 40
  ok "后端已就绪  http://127.0.0.1:${API_PORT}  (PID ${backend_pid})"
}

# ══════════════════════════════════════════════════════════════════════════
# 启动前端 dev server
# ══════════════════════════════════════════════════════════════════════════
start_frontend_dev() {
  step "启动前端 Dev Server (端口 ${UI_PORT})"

  if port_in_use "$UI_PORT"; then
    warn "端口 ${UI_PORT} 已被占用，尝试释放..."
    lsof -ti :"${UI_PORT}" | xargs kill -9 2>/dev/null || true
    sleep 1
  fi

  nohup npm --prefix "${FRONTEND_DIR}" run dev -- \
    --host 127.0.0.1 --port "${UI_PORT}" \
    >> "${FRONTEND_LOG}" 2>&1 < /dev/null &

  local frontend_pid=$!
  save_pid "frontend" "$frontend_pid"
  disown "$frontend_pid"

  printf "  等待前端就绪"
  wait_for_port "$UI_PORT" "前端" 30
  ok "前端已就绪  http://127.0.0.1:${UI_PORT}  (PID ${frontend_pid})"
}

# ══════════════════════════════════════════════════════════════════════════
# --test  API 冒烟测试
# ══════════════════════════════════════════════════════════════════════════
cmd_test() {
  step "API 冒烟测试"

  if ! port_in_use "$API_PORT"; then
    error "后端未运行，请先启动（./scripts/dev.sh）"
  fi

  local pass=0 fail=0

  run_case() {
    local name="$1" result="$2" expect="$3"
    if echo "$result" | grep -q "$expect" 2>/dev/null; then
      echo -e "  ${GREEN}✓${NC} ${name}"
      pass=$((pass+1))
    else
      echo -e "  ${RED}✗${NC} ${name}"
      echo "      期望含: ${expect}"
      echo "      实际:   $(echo "$result" | head -c 120)"
      fail=$((fail+1))
    fi
  }

  local base="http://127.0.0.1:${API_PORT}"

  # 1. health check
  run_case "GET /api/health" \
    "$(curl -sf "${base}/api/health" 2>/dev/null || echo '{}')" \
    '"status"'

  # 从 .env 读取管理员账号；尝试多个候选密码（含 aliases），找到有效的那个
  local admin_user admin_pass
  admin_user="${DEFAULT_ADMIN_USERNAME:-admin}"
  admin_pass=""
  for candidate in "${DEFAULT_ADMIN_PASSWORD:-}" "990115" "730926" "740419" "admin123456"; do
    [[ -z "$candidate" ]] && continue
    local resp
    resp=$(curl -sf -X POST "${base}/api/auth/login" \
      -H "Content-Type: application/json" \
      -d "{\"auth_id\":\"${admin_user}\",\"password\":\"${candidate}\"}" 2>/dev/null || echo "")
    if echo "$resp" | grep -q "access_token"; then
      admin_pass="$candidate"
      break
    fi
  done

  # 2. 管理员登录
  local admin_tok=""
  if [[ -n "$admin_pass" ]]; then
    admin_tok=$(curl -sf -X POST "${base}/api/auth/login" \
      -H "Content-Type: application/json" \
      -d "{\"auth_id\":\"${admin_user}\",\"password\":\"${admin_pass}\"}" 2>/dev/null \
      | python3 -c "import json,sys; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null \
      || echo "")
  fi
  run_case "POST /api/auth/login (admin)" "${admin_tok:+ok}" "ok"

  if [[ -n "$admin_tok" ]]; then
    # 3. 报告列表
    run_case "GET /api/reports" \
      "$(curl -sf "${base}/api/reports" \
          -H "Authorization: Bearer ${admin_tok}" 2>/dev/null || echo '[]')" \
      '\['

    # 4. 知识库列表
    run_case "GET /api/knowledge_base/" \
      "$(curl -sf "${base}/api/knowledge_base/" \
          -H "Authorization: Bearer ${admin_tok}" 2>/dev/null || echo '[]')" \
      '\['

    # 5. 后台配置（LLM 设置等）
    run_case "GET /api/admin/config" \
      "$(curl -sf "${base}/api/admin/config" \
          -H "Authorization: Bearer ${admin_tok}" 2>/dev/null || echo '{}')" \
      "llm"

    # 6. 可用模型列表
    run_case "GET /api/system/models" \
      "$(curl -sf "${base}/api/system/models" \
          -H "Authorization: Bearer ${admin_tok}" 2>/dev/null || echo '{}')" \
      "models"

    # 7. 注册新用户 + 登录
    local test_user="smoke_$(date +%s)"
    local test_pass="Smoke_Test_123"
    local reg_r
    reg_r=$(curl -sf -X POST "${base}/api/auth/register" \
      -H "Content-Type: application/json" \
      -d "{\"auth_id\":\"${test_user}\",\"username\":\"${test_user}\",\"department\":\"测试部\",\"scene\":\"dev-smoke\",\"description\":\"smoke test\",\"password\":\"${test_pass}\"}" \
      2>/dev/null || echo '{}')
    run_case "POST /api/auth/register" "$reg_r" "username"

    local user_tok
    user_tok=$(curl -sf -X POST "${base}/api/auth/login" \
      -H "Content-Type: application/json" \
      -d "{\"auth_id\":\"${test_user}\",\"password\":\"${test_pass}\"}" 2>/dev/null \
      | python3 -c "import json,sys; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null \
      || echo "")
    run_case "POST /api/auth/login (new user)" "${user_tok:+ok}" "ok"
  fi

  divider
  local total=$((pass+fail))
  if [[ $fail -eq 0 ]]; then
    ok "全部通过 ${pass}/${total} ✓"
  else
    echo -e "  ${RED}失败 ${fail}/${total}${NC}，${GREEN}通过 ${pass}/${total}${NC}"
    exit 1
  fi
}

# ══════════════════════════════════════════════════════════════════════════
# --docker  Docker Compose 模式
# ══════════════════════════════════════════════════════════════════════════
cmd_docker() {
  step "Docker Compose 启动"

  command -v docker >/dev/null 2>&1 || error "未找到 docker"
  docker info >/dev/null 2>&1       || error "Docker 未运行，请先启动 Docker Desktop"

  # 停止 native dev 进程（避免端口冲突，Docker 栈有自己的 Redis/backend）
  info "停止 native dev 进程..."
  [[ -f "${PID_FILE}" ]] && while IFS='=' read -r name pid; do
    [[ -z "$name" || -z "$pid" ]] && continue
    is_running "$pid" && kill "$pid" 2>/dev/null || true
  done < "${PID_FILE}" && rm -f "${PID_FILE}"
  # 释放 6379（native redis-server）
  if command -v redis-cli >/dev/null 2>&1 && redis-cli ping >/dev/null 2>&1; then
    redis-cli shutdown nosave 2>/dev/null || pkill -f "redis-server" 2>/dev/null || true
    sleep 1
  fi
  for port in "$API_PORT" "$UI_PORT" 6379; do
    local pids; pids=$(lsof -ti :"$port" 2>/dev/null || true)
    [[ -n "$pids" ]] && echo "$pids" | xargs kill 2>/dev/null || true
  done

  local compose_cmd
  if docker compose version >/dev/null 2>&1; then
    compose_cmd="docker compose"
  else
    compose_cmd="docker-compose"
  fi

  local compose_files="-f ${SCRIPT_DIR}/docker-compose.yml -f ${SCRIPT_DIR}/docker-compose.mac.yml"

  # .env & SECRET_KEY
  load_dotenv
  mkdir -p "${SCRIPT_DIR}/data/uploads" "${SCRIPT_DIR}/data/templates" \
           "${SCRIPT_DIR}/data/sandbox" "${SCRIPT_DIR}/data/db" \
           "${SCRIPT_DIR}/data/redis"

  if [[ "$DO_REBUILD" == true ]]; then
    info "重新构建镜像（arm64）..."
    # shellcheck disable=SC2086
    $compose_cmd $compose_files build
  fi

  # shellcheck disable=SC2086
  $compose_cmd $compose_files up -d

  info "等待服务就绪"
  local i=0
  while ! curl -sf "http://localhost/api/health" >/dev/null 2>&1; do
    i=$((i+1))
    [[ $i -ge 60 ]] && error "Docker 服务启动超时，查看日志: $compose_cmd $compose_files logs -f"
    printf "."
    sleep 2
  done
  echo ""

  divider
  echo -e "${BOLD}  Docker 模式已启动${NC}"
  echo -e "  ${CYAN}→ http://localhost${NC}        (前端)"
  echo -e "  ${CYAN}→ http://localhost/docs${NC}   (接口文档)"
  echo -e "  ${CYAN}→ http://localhost/admin${NC}  (管理后台)"
  divider

  open_browser_url "http://localhost"
}

# ══════════════════════════════════════════════════════════════════════════
# 主启动流程
# ══════════════════════════════════════════════════════════════════════════
cmd_start() {
  divider
  echo -e "${BOLD}  DataAgent Studio — 本地开发环境${NC}"
  echo -e "  API: :${API_PORT}  UI: :${UI_PORT}"
  divider

  check_prereqs
  load_dotenv

  # 清空数据库
  if [[ "$DO_CLEAN" == true ]]; then
    step "清空数据库"
    rm -f "${SCRIPT_DIR}/data/db/app.db"
    ok "数据库已清空"
  fi

  ensure_redis
  ensure_postgres
  ensure_qdrant
  setup_venv

  if [[ "$DO_FRONTEND_ONLY" != true ]]; then
    if [[ "$DO_BACKEND_ONLY" == true ]]; then
      local old_pid; old_pid=$(read_pid "backend" 2>/dev/null || true)
      if is_running "${old_pid:-}"; then
        kill "$old_pid" 2>/dev/null; sleep 1
        ok "旧后端进程已停止"
      fi
    fi
    start_backend
  fi

  if [[ "$DO_BACKEND_ONLY" != true ]]; then
    setup_frontend_deps
    start_frontend_dev
  fi

  if [[ "$DO_TEST" == true ]]; then
    sleep 2
    cmd_test
  fi

  divider
  echo -e "${BOLD}  启动完成${NC}"
  if [[ "$DO_BACKEND_ONLY" != true ]]; then
    echo -e "  ${CYAN}→ http://127.0.0.1:${UI_PORT}${NC}       (前端 HMR)"
  fi
  echo -e "  ${CYAN}→ http://127.0.0.1:${API_PORT}/api${NC}  (后端 API)"
  echo -e "  ${CYAN}→ http://127.0.0.1:${API_PORT}/docs${NC} (接口文档)"
  echo -e "  后端日志: tail -f ${BACKEND_LOG}"
  echo -e "  停止:     ${BOLD}./scripts/dev.sh --stop${NC}"
  divider

  if [[ "$DO_BACKEND_ONLY" != true ]]; then
    open_browser_url "http://127.0.0.1:${UI_PORT}"
  fi
}

# ══════════════════════════════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════════════════════════════
if   [[ "$DO_STOP"   == true ]]; then cmd_stop
elif [[ "$DO_STATUS" == true ]]; then cmd_status
elif [[ "$DO_LOGS"   == true ]]; then cmd_logs
elif [[ "$DO_DOCKER" == true ]]; then cmd_docker
elif [[ "$DO_TEST"   == true ]] && \
     [[ "$DO_REBUILD" == false ]] && \
     [[ "$DO_CLEAN"   == false ]] && \
     [[ "$DO_BACKEND_ONLY" == false ]] && \
     [[ "$DO_FRONTEND_ONLY" == false ]]; then cmd_test
else cmd_start
fi
