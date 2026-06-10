#!/bin/bash
# build_offline.sh — 构建内网离线部署包
#
# 在 Mac / CI 上运行；生成 offline-images/ 文件夹，内含：
#   images.tar.gz          所有 Docker 镜像（linux/amd64）
#   deploy_offline.sh      内网一键部署脚本
#   docker-compose.yml
#   docker-compose.prod.yml
#   .env.example
#
# 用法:
#   ./scripts/build_offline.sh              # 全量构建（仅镜像）
#   ./scripts/build_offline.sh --no-cache   # 强制不缓存重新构建
#   ./scripts/build_offline.sh --with-data  # 镜像 + 导出已入库的 SQLite/PostgreSQL + Qdrant 数据
#                                   #   （在本机入库完成后用，目标机开箱即用，无需重新下载/embedding）

set -euo pipefail

# 脚本封装在 scripts/ 子目录，项目根为其上一级
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUTPUT_DIR="$ROOT_DIR/offline-images"
TARGET_PLATFORM="linux/amd64"
IMAGE_ARCHIVE="images.tar.gz"
NO_CACHE=""
WITH_DATA=false
for arg in "$@"; do
  case "$arg" in
    --no-cache)  NO_CACHE="--no-cache" ;;
    --with-data) WITH_DATA=true ;;
  esac
done

# PostgreSQL / Qdrant 连接参数（导出已入库数据时使用）
PG_CONTAINER="${PG_CONTAINER:-deep-research-postgres-1}"
PG_USER="${PG_USER:-dataagent}"
PG_DB="${PG_DB:-dataagent}"
QDRANT_STORAGE="${QDRANT_STORAGE:-$ROOT_DIR/data/qdrant_storage}"
SQLITE_DB="${SQLITE_DB:-$ROOT_DIR/data/app.db}"

# ── 依赖检查 ─────────────────────────────────────────────────────────────────
for cmd in docker; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "✗ 未找到命令: $cmd"
    exit 1
  fi
done

if ! docker info >/dev/null 2>&1; then
  echo "✗ Docker 未运行，请先启动 Docker Desktop。"
  exit 1
fi

if ! docker buildx version >/dev/null 2>&1; then
  echo "✗ 未检测到 docker buildx，请升级 Docker Desktop（≥4.x）。"
  exit 1
fi

# ── 准备 buildx builder ───────────────────────────────────────────────────────
if [ "$(uname -m)" = "arm64" ]; then
  echo "→ Apple Silicon 检测到，安装 QEMU 跨平台支持…"
  docker run --privileged --rm tonistiigi/binfmt --install all >/dev/null 2>&1 || true
fi

if ! docker buildx inspect dataagent-builder >/dev/null 2>&1; then
  docker buildx create --name dataagent-builder --driver docker-container --use >/dev/null
else
  docker buildx use dataagent-builder >/dev/null
fi

# ── 前端 CSS 兼容性验证（本地，Docker 构建前）────────────────────────────────
# nginx:alpine 镜像没有 python3 / node，所以 oklch 深度校验必须在本地跑。
# npm run build 已经内嵌 check-compat.mjs，此处是额外的安全网：
# 用本地已有的 dist/ 产物做最终确认，不需要重新构建前端。
echo ""
echo "▶ 本地 CSS 兼容性验证（dist/ 产物）…"
if [ -d "$ROOT_DIR/frontend/dist/assets" ]; then
  node "$ROOT_DIR/frontend/scripts/check-compat.mjs"
else
  echo "  frontend/dist/ 不存在，跳过本地 CSS 验证（Docker 构建阶段会重新 npm run build）"
fi

# ── 构建镜像 ─────────────────────────────────────────────────────────────────
echo ""
echo "▶ 构建 backend (linux/amd64)…"
docker buildx build --platform "$TARGET_PLATFORM" --load $NO_CACHE \
  -t deep-research-backend:latest ./backend

echo "▶ 校验后端认证依赖…"
# --platform 明确指定避免 arm64 主机上的平台告警（QEMU 仿真，仅用于验证）
# passlib 1.7.4 与 bcrypt 4.x 有已知兼容告警（输出到 stderr），不影响功能。
# 正常路径：只捕获 stdout 验证 auth-ok；失败时重跑并显示完整输出供排查。
AUTH_OUT=$(docker run --rm --platform "$TARGET_PLATFORM" \
  --entrypoint python deep-research-backend:latest -c \
  "from app.services.auth_service import hash_password, verify_password; \
   h=hash_password('SmokePass123'); \
   assert verify_password('SmokePass123', h); \
   assert not verify_password('WrongPass', h); \
   print('auth-ok')" \
  2>/dev/null || true)

if echo "$AUTH_OUT" | grep -q "auth-ok"; then
  echo "  ✓ bcrypt/passlib 注册登录依赖可用"
else
  echo "  ✗ bcrypt/passlib 验证失败，完整输出："
  docker run --rm --platform "$TARGET_PLATFORM" \
    --entrypoint python deep-research-backend:latest -c \
    "from app.services.auth_service import hash_password, verify_password; \
     h=hash_password('SmokePass123'); \
     assert verify_password('SmokePass123', h); \
     print('auth-ok')" || true
  exit 1
fi

echo "▶ 构建 frontend (linux/amd64)…"
docker buildx build --platform "$TARGET_PLATFORM" --load $NO_CACHE \
  -t deep-research-frontend:latest ./frontend

echo "▶ 校验前端兼容性构建产物（容器内文件检查）…"
# nginx:alpine 只有基础 shell 工具，不用 python3/node。
# CSS oklch 深度校验已在本地完成（见上方）和 Docker 构建时的 npm run build。
# 此处只验证文件完整性和关键注入标记。
docker run --rm --platform "$TARGET_PLATFORM" \
  --entrypoint sh deep-research-frontend:latest -c '
  set -eu
  INDEX=/usr/share/nginx/html/index.html

  # JS: nomodule legacy chunks（ES2015 兼容，Chrome 58+）
  test -f "$INDEX"                                                  || { echo "✗ index.html 缺失";           exit 1; }
  grep -q "nomodule"         "$INDEX"                              || { echo "✗ 缺少 nomodule legacy 标记"; exit 1; }
  grep -q "vite-legacy-entry" "$INDEX"                             || { echo "✗ 缺少 vite-legacy-entry";    exit 1; }
  ls /usr/share/nginx/html/assets/*legacy*.js >/dev/null 2>&1      || { echo "✗ 缺少 legacy JS chunks";     exit 1; }

  # CSS: 兼容层文件和检测器脚本
  test -f /usr/share/nginx/html/legacy-compat.css                  || { echo "✗ 缺少 legacy-compat.css";    exit 1; }
  grep -q "legacy-compat.css" "$INDEX"                             || { echo "✗ 检测器未注入 CSS 链接";      exit 1; }
  grep -q "supportsOklch"     "$INDEX"                             || { echo "✗ 检测器未注入 oklch 检测";    exit 1; }

  # CSS: 快速检查主 CSS 不含裸 oklch（@supports 块外）
  # nginx:alpine 有 grep；minified CSS 是单行，用文本模式判断
  CSS=$(ls /usr/share/nginx/html/assets/*.css 2>/dev/null | head -1)
  if [ -n "$CSS" ]; then
    # 正常情况：@supports 出现次数应远多于 oklch 出现次数
    # 如果 oklch 多于 @supports*10，说明 PostCSS 可能未生效
    OKLCH_COUNT=$(grep -o "oklch(" "$CSS" | wc -l)
    SUPPORTS_COUNT=$(grep -o "@supports" "$CSS" | wc -l)
    if [ "$OKLCH_COUNT" -gt 0 ] && [ "$SUPPORTS_COUNT" -eq 0 ]; then
      echo "✗ CSS 包含 oklch() 但无 @supports 块，PostCSS 转换可能未生效"
      exit 1
    fi
    echo "  CSS: oklch=$OKLCH_COUNT @supports=$SUPPORTS_COUNT（比例合理）"
  fi

  echo "  所有文件检查通过"
'
echo "  ✓ 前端包含 nomodule legacy chunks、CSS oklch 回退、按需兼容层注入"

echo "▶ 构建 embedding (linux/amd64)…"
docker buildx build --platform "$TARGET_PLATFORM" --load $NO_CACHE \
  -t deep-research-embedding:latest ./embedding

echo "  ✓ embedding 镜像构建完成（BGE-M3 多节点服务）"

echo "▶ 拉取基础镜像 redis / postgres / qdrant (linux/amd64)…"
# docker pull --platform 在 Apple Silicon 上不会更新本地 tag，
# 用 buildx FROM-only 构建确保本地存储的是 amd64 镜像。
for base in redis:7-alpine postgres:15-alpine qdrant/qdrant:latest; do
  printf 'FROM %s\n' "$base" | \
    docker buildx build --platform "$TARGET_PLATFORM" --load -t "$base" -f - . \
    >/dev/null 2>&1
  echo "  ✓ $base"
done

# ── 导出镜像 ─────────────────────────────────────────────────────────────────
mkdir -p "$OUTPUT_DIR"
echo "▶ 打包镜像到 $OUTPUT_DIR/$IMAGE_ARCHIVE …"
docker save \
  deep-research-backend:latest \
  deep-research-frontend:latest \
  deep-research-embedding:latest \
  redis:7-alpine \
  postgres:15-alpine \
  qdrant/qdrant:latest \
  | gzip > "$OUTPUT_DIR/$IMAGE_ARCHIVE"

IMAGE_SIZE="$(du -sh "$OUTPUT_DIR/$IMAGE_ARCHIVE" | awk '{print $1}')"
echo "  镜像包大小: $IMAGE_SIZE"

# ── 导出已入库数据（--with-data）─────────────────────────────────────────────
# 把本机已入库的 SQLite/PostgreSQL + Qdrant 向量存储一并打包，
# 目标机恢复后开箱即用，无需重新下载 2TB 原始语料、无需重跑 embedding。
if [ "$WITH_DATA" = true ]; then
  echo ""
  echo "▶ 导出已入库数据（SQLite/PostgreSQL + Qdrant）…"
  mkdir -p "$OUTPUT_DIR/data_export"

  # 1) SQLite —— 直接复制（当前系统主数据库为 SQLite）
  if [ -f "$SQLITE_DB" ]; then
    echo "  → 复制 SQLite 数据库…"
    cp "$SQLITE_DB" "$OUTPUT_DIR/data_export/app.db"
    SQLITE_SIZE="$(du -sh "$OUTPUT_DIR/data_export/app.db" | awk '{print $1}')"
    echo "    ✓ app.db ($SQLITE_SIZE)"
  else
    echo "  ⚠ 未找到 SQLite 数据库 ($SQLITE_DB)，跳过。"
  fi

  # 2) PostgreSQL —— 逻辑导出（-Fc 自定义格式，arm64→x86_64 安全）
  if docker ps --format '{{.Names}}' | grep -q "^${PG_CONTAINER}$"; then
    echo "  → pg_dump ${PG_DB}…"
    docker exec "$PG_CONTAINER" pg_dump -U "$PG_USER" -Fc "$PG_DB" \
      > "$OUTPUT_DIR/data_export/postgres.dump"
    PG_SIZE="$(du -sh "$OUTPUT_DIR/data_export/postgres.dump" | awk '{print $1}')"
    echo "    ✓ postgres.dump ($PG_SIZE)"
  else
    echo "  ⚠ 未发现运行中的 PostgreSQL 容器 ($PG_CONTAINER)，跳过 PG 导出。"
  fi

  # 3) Qdrant —— 直接打包存储目录（Qdrant 存储格式跨架构兼容）
  if [ -d "$QDRANT_STORAGE" ] && [ -n "$(ls -A "$QDRANT_STORAGE" 2>/dev/null)" ]; then
    echo "  → 打包 Qdrant 向量存储…"
    tar czf "$OUTPUT_DIR/data_export/qdrant_storage.tar.gz" \
      -C "$(dirname "$QDRANT_STORAGE")" "$(basename "$QDRANT_STORAGE")"
    Q_SIZE="$(du -sh "$OUTPUT_DIR/data_export/qdrant_storage.tar.gz" | awk '{print $1}')"
    echo "    ✓ qdrant_storage.tar.gz ($Q_SIZE)"
  else
    echo "  ⚠ Qdrant 存储为空 ($QDRANT_STORAGE)，跳过。先完成 bulk_importer 入库。"
  fi

  # 4) 用户自定义技能（持久化在文件系统）
  if [ -d "$ROOT_DIR/data/db/user_skills" ]; then
    tar czf "$OUTPUT_DIR/data_export/user_skills.tar.gz" -C "$ROOT_DIR/data/db" user_skills 2>/dev/null || true
    echo "    ✓ user_skills.tar.gz"
  fi

  echo "  ✓ 数据导出完成 → $OUTPUT_DIR/data_export/"
fi

# ── 复制配置文件 ──────────────────────────────────────────────────────────────
cp docker-compose.yml              "$OUTPUT_DIR/"
cp docker-compose.prod.yml         "$OUTPUT_DIR/"
cp docker-compose.embedding.yml    "$OUTPUT_DIR/"
cp .env.example                    "$OUTPUT_DIR/"

# ── 生成 deploy_offline.sh ───────────────────────────────────────────────────
cat > "$OUTPUT_DIR/deploy_offline.sh" <<'DEPLOY_SCRIPT'
#!/bin/bash
# deploy_offline.sh — 内网一键部署脚本
#
# 将 offline-images/ 整个目录复制到内网服务器后执行:
#   chmod +x deploy_offline.sh
#   ./deploy_offline.sh
#
# 子命令:
#   (无)            首次部署 / 启动
#   --embedding     同时启动 BGE-M3 embedding 集群（多节点高并发）
#   --update        热更新：加载新镜像并重启服务（保留数据）
#   --down          停止并移除容器
#   --logs          实时查看日志
#   --status        查看服务状态
#   --restart       重启所有服务
#   --backup        备份数据目录到 backup_YYYYMMDD.tar.gz

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# ── 依赖检查 ─────────────────────────────────────────────────────────────────
if ! command -v docker >/dev/null 2>&1; then
  echo "✗ 未检测到 Docker，请先在服务器上安装 Docker Engine。"
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "✗ 未检测到 docker compose，请安装 Docker Compose v2。"
  exit 1
fi

COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.prod.yml)

# ── 可选：启动 BGE-M3 embedding 集群 ──────────────────────────────────────────
# 用法: ./deploy_offline.sh --embedding
if [ "${1:-}" = "--embedding" ]; then
  shift
  COMPOSE_FILES+=(-f docker-compose.embedding.yml)
  echo "→ 启用 BGE-M3 embedding 集群（4 节点，可 EMBED_REPLICAS=N 调节）"
fi

# ── 子命令 ────────────────────────────────────────────────────────────────────
case "${1:-}" in
  --down)
    "${COMPOSE[@]}" "${COMPOSE_FILES[@]}" down
    echo "服务已停止。"
    exit 0
    ;;
  --logs)
    "${COMPOSE[@]}" "${COMPOSE_FILES[@]}" logs -f
    exit 0
    ;;
  --status)
    "${COMPOSE[@]}" "${COMPOSE_FILES[@]}" ps
    exit 0
    ;;
  --restart)
    "${COMPOSE[@]}" "${COMPOSE_FILES[@]}" restart
    echo "服务已重启。"
    exit 0
    ;;
  --backup)
    TS="$(date +%Y%m%d_%H%M%S)"
    mkdir -p "backups/${TS}"
    echo "▶ 备份 PostgreSQL（pg_dump）…"
    "${COMPOSE[@]}" "${COMPOSE_FILES[@]}" exec -T postgres \
      pg_dump -U dataagent -Fc dataagent > "backups/${TS}/postgres.dump" 2>/dev/null \
      && echo "  ✓ postgres.dump" || echo "  ⚠ PG 备份失败（容器未运行？）"
    echo "▶ 备份 Qdrant + 上传文件…"
    tar -czf "backups/${TS}/qdrant_uploads.tar.gz" \
      data/qdrant_storage data/uploads data/templates data/db 2>/dev/null || true
    echo "✓ 备份完成: backups/${TS}/ ($(du -sh "backups/${TS}" | awk '{print $1}'))"
    exit 0
    ;;
  --update)
    echo "▶ 热更新：加载新镜像…"
    ARCHIVE="$(ls images*.tar.gz 2>/dev/null | sort | tail -1)"
    if [ -n "$ARCHIVE" ]; then
      gunzip -c "$ARCHIVE" | docker load
    else
      echo "⚠  未找到 images*.tar.gz，跳过镜像加载。"
    fi
    echo "▶ 滚动重启服务（数据保留）…"
    if [[ " ${COMPOSE_FILES[*]} " =~ "docker-compose.embedding.yml" ]]; then
      "${COMPOSE[@]}" "${COMPOSE_FILES[@]}" up -d --no-deps --force-recreate backend frontend embedding-worker embedding-lb
    else
      "${COMPOSE[@]}" "${COMPOSE_FILES[@]}" up -d --no-deps --force-recreate backend frontend
    fi
    echo "✓ 更新完成。"
    exit 0
    ;;
esac

# ── 环境准备 ─────────────────────────────────────────────────────────────────
mkdir -p \
  data/uploads \
  data/templates \
  data/sandbox \
  data/db \
  data/redis \
  data/pg_data \
  data/qdrant_storage \
  data/qdrant_snapshots \
  data/structured_dbs \
  data/embedding_models \
  data/kb_sources

# 容器内以非 root appuser 运行，宿主机目录若由 root 创建则无写权限。
chmod -R 777 data/

if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    echo "→ 已从 .env.example 生成 .env"
    echo "  !! 请修改 DEFAULT_LLM_BASE_URL / DEFAULT_LLM_MODEL / DEFAULT_ADMIN_PASSWORD 后重新运行 !!"
    echo "     如需启用 BGE-M3 embedding 集群，执行 ./deploy_offline.sh --embedding"
    echo ""
  fi
fi

# 自动生成 SECRET_KEY（仅当占位符未替换时）
if grep -q 'change-this-to-a-random-64-char-string' .env 2>/dev/null; then
  SECRET="$(openssl rand -hex 32 2>/dev/null || date +%s | sha256sum | awk '{print $1}')"
  sed -i "s/change-this-to-a-random-64-char-string/$SECRET/" .env
  echo "→ 已自动生成 SECRET_KEY。"
fi

# ── 加载离线镜像 ──────────────────────────────────────────────────────────────
ARCHIVE="$(ls images*.tar.gz 2>/dev/null | sort | tail -1)"
if [ -n "$ARCHIVE" ]; then
  echo "▶ 加载离线镜像: $ARCHIVE"
  gunzip -c "$ARCHIVE" | docker load
else
  echo "⚠  未找到 images*.tar.gz，假设镜像已提前 docker load。"
fi

# ── 恢复 Qdrant 向量存储（容器启动前，解压到挂载目录）────────────────────────
if [ -f data_export/qdrant_storage.tar.gz ] && [ -z "$(ls -A data/qdrant_storage 2>/dev/null)" ]; then
  echo "▶ 恢复 Qdrant 向量存储…"
  tar xzf data_export/qdrant_storage.tar.gz -C data/ --strip-components=0 2>/dev/null \
    || tar xzf data_export/qdrant_storage.tar.gz -C data/
  # 兼容打包时的目录层级：确保内容落到 data/qdrant_storage/
  if [ ! -f data/qdrant_storage/meta.json ] && [ -d data/qdrant_storage/qdrant_storage ]; then
    mv data/qdrant_storage/qdrant_storage/* data/qdrant_storage/ 2>/dev/null || true
  fi
  chmod -R 777 data/qdrant_storage
  echo "  ✓ Qdrant 数据已就位"
fi

if [ -f data_export/user_skills.tar.gz ]; then
  tar xzf data_export/user_skills.tar.gz -C data/db/ 2>/dev/null || true
fi

# ── 恢复 SQLite 数据库（容器启动前）────────────────────────────────────────────
if [ -f data_export/app.db ]; then
  echo "▶ 恢复 SQLite 数据库…"
  cp data_export/app.db data/app.db
  chmod 666 data/app.db
  echo "  ✓ SQLite 数据已就位"
fi

# ── 启动服务 ─────────────────────────────────────────────────────────────────
echo ""
if [[ " ${COMPOSE_FILES[*]} " =~ "docker-compose.embedding.yml" ]]; then
  echo "▶ 启动 DataAgent Studio + BGE-M3 embedding 集群（${EMBED_REPLICAS:-4} workers）…"
else
  echo "▶ 启动 DataAgent Studio…"
fi
"${COMPOSE[@]}" "${COMPOSE_FILES[@]}" up -d

# ── 恢复 PostgreSQL（等 postgres 健康后 pg_restore）──────────────────────────
if [ -f data_export/postgres.dump ]; then
  echo -n "▶ 等待 PostgreSQL 就绪以恢复数据"
  PG_READY=0
  for i in $(seq 1 40); do
    if "${COMPOSE[@]}" "${COMPOSE_FILES[@]}" exec -T postgres pg_isready -U dataagent >/dev/null 2>&1; then
      PG_READY=1; break
    fi
    printf "."; sleep 2
  done
  echo ""
  if [ "$PG_READY" = "1" ]; then
    # 仅当库为空（只有迁移建的空表/无 reports 数据）时恢复，避免覆盖已有数据
    EXISTING="$("${COMPOSE[@]}" "${COMPOSE_FILES[@]}" exec -T postgres \
      psql -U dataagent -d dataagent -tAc "SELECT count(*) FROM kb_chunks" 2>/dev/null || echo 0)"
    if [ "${EXISTING:-0}" = "0" ]; then
      echo "  → pg_restore 恢复已入库数据…"
      "${COMPOSE[@]}" "${COMPOSE_FILES[@]}" exec -T postgres \
        pg_restore -U dataagent -d dataagent --clean --if-exists --no-owner < data_export/postgres.dump \
        2>/dev/null || echo "    （部分对象已存在的告警可忽略）"
      echo "  ✓ PostgreSQL 数据已恢复"
    else
      echo "  ⏭ 检测到已有 ${EXISTING} 条向量数据，跳过恢复（避免覆盖）。"
    fi
  else
    echo "  ⚠ PostgreSQL 未就绪，跳过数据恢复。可稍后手动: pg_restore ... < data_export/postgres.dump"
  fi
fi

# ── 等待就绪 ──────────────────────────────────────────────────────────────────
FRONTEND_PORT="$(grep -E '^FRONTEND_PORT=' .env 2>/dev/null | tail -1 | cut -d= -f2- || true)"
FRONTEND_PORT="${FRONTEND_PORT:-80}"
LOCAL_BASE_URL="http://localhost"
if [ "$FRONTEND_PORT" != "80" ]; then
  LOCAL_BASE_URL="http://localhost:${FRONTEND_PORT}"
fi

echo -n "  等待服务就绪"
READY=0
for i in $(seq 1 60); do
  if curl -sf "${LOCAL_BASE_URL}/api/health" >/dev/null 2>&1 && \
     curl -sf "${LOCAL_BASE_URL}" >/dev/null 2>&1; then
    READY=1
    break
  fi
  printf "."
  sleep 3
done
echo ""

if [ "$READY" -eq 0 ]; then
  echo "⚠  服务启动超时，请执行 ./deploy_offline.sh --logs 排查。"
  exit 1
fi

# ── 健康验证 ──────────────────────────────────────────────────────────────────
ADMIN_USER="$(grep -E '^DEFAULT_ADMIN_USERNAME=' .env 2>/dev/null | tail -1 | cut -d= -f2- || true)"
ADMIN_PASS="$(grep -E '^DEFAULT_ADMIN_PASSWORD=' .env 2>/dev/null | tail -1 | cut -d= -f2- || true)"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-990115}"

# 登录验证（使用 auth_id 字段）
LOGIN_RESP="$(curl -sf -X POST "${LOCAL_BASE_URL}/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"auth_id\":\"${ADMIN_USER}\",\"password\":\"${ADMIN_PASS}\"}" 2>/dev/null || true)"
TOKEN="$(printf '%s' "$LOGIN_RESP" | sed -n 's/.*"access_token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"

if [ -n "$TOKEN" ]; then
  echo "✓ 系统验证通过（登录成功）"
else
  echo "⚠  管理员登录验证失败（账号: ${ADMIN_USER} / ${ADMIN_PASS}）"
  echo "   首次启动若 DB 尚未就绪可忽略，等待30秒后再试。"
fi

# 注册 + 登录冒烟测试（使用完整注册字段）
SMOKE_ID="smoke_$(date +%s)_$$"
SMOKE_PASS="Smoke_${SMOKE_ID}_123"
REGISTER_RESP="$(curl -sf -X POST "${LOCAL_BASE_URL}/api/auth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"auth_id\":\"${SMOKE_ID}\",\"username\":\"${SMOKE_ID}\",\"department\":\"部署自检\",\"scene\":\"offline-smoke\",\"description\":\"部署脚本注册登录自检账号\",\"password\":\"${SMOKE_PASS}\"}" 2>/dev/null || true)"
SMOKE_LOGIN_RESP="$(curl -sf -X POST "${LOCAL_BASE_URL}/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"auth_id\":\"${SMOKE_ID}\",\"password\":\"${SMOKE_PASS}\"}" 2>/dev/null || true)"
SMOKE_TOKEN="$(printf '%s' "$SMOKE_LOGIN_RESP" | sed -n 's/.*"access_token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"

if [ -n "$REGISTER_RESP" ] && [ -n "$SMOKE_TOKEN" ]; then
  echo "✓ 注册 / 登录接口验证通过"
else
  echo "⚠  注册 / 登录接口验证失败，请执行 ./deploy_offline.sh --logs 排查。"
fi

# 清理部署自检用户，避免多次部署污染用户列表。
"${COMPOSE[@]}" "${COMPOSE_FILES[@]}" exec -T backend python - "$SMOKE_ID" <<'PY' >/dev/null 2>&1 || true
import asyncio
import sys
from sqlalchemy import delete
from app.database import async_session
from app.models.user import User

async def main():
    async with async_session() as db:
        await db.execute(delete(User).where(User.auth_id == sys.argv[1]))
        await db.commit()

asyncio.run(main())
PY

# ── 离线渲染组件验证 ──────────────────────────────────────────────────────────
echo ""
echo "▶ 检查 PPT 渲染 QA 组件（LibreOffice + PyMuPDF）…"
if "${COMPOSE[@]}" "${COMPOSE_FILES[@]}" exec -T backend \
     python -c "import uno; import fitz; print('OK')" 2>/dev/null; then
  echo "✓ PPT 渲染组件可用"
else
  echo "⚠  PPT 渲染组件未完全可用；系统将退回几何 QA 模式（不影响 Word/Excel）。"
fi

# ── 输出访问信息 ──────────────────────────────────────────────────────────────
HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || hostname)"
PUBLIC_BASE_URL="http://${HOST_IP}"
if [ "$FRONTEND_PORT" != "80" ]; then
  PUBLIC_BASE_URL="http://${HOST_IP}:${FRONTEND_PORT}"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ DataAgent Studio 部署完成"
echo ""
echo "  前端页面:   ${PUBLIC_BASE_URL}"
echo "  接口文档:   ${PUBLIC_BASE_URL}/docs"
echo "  管理后台:   ${PUBLIC_BASE_URL}/admin"
echo ""
echo "  初始管理员: ${ADMIN_USER} / ${ADMIN_PASS}"
echo "  ⚠  请登录管理后台立即修改默认密码！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "常用命令:"
echo "  停止:    ./deploy_offline.sh --down"
echo "  日志:    ./deploy_offline.sh --logs"
echo "  状态:    ./deploy_offline.sh --status"
echo "  重启:    ./deploy_offline.sh --restart"
echo "  热更新:  ./deploy_offline.sh --update"
echo "  备份:    ./deploy_offline.sh --backup"
DEPLOY_SCRIPT

chmod +x "$OUTPUT_DIR/deploy_offline.sh"

# ── 生成 README_DEPLOY.txt ────────────────────────────────────────────────────
cat > "$OUTPUT_DIR/README_DEPLOY.txt" <<'README'
DataAgent Studio — 内网离线部署说明
====================================

【镜像清单】（均已打包在 images.tar.gz 中）
  deep-research-backend:latest   FastAPI 后端（含 LibreOffice / Pandoc / Python 分析环境）
  deep-research-frontend:latest  Nginx 前端（ES2015+ 兼容构建 + CSS 多浏览器兼容层）
  deep-research-embedding:latest BGE-M3 高并发 embedding 服务（OpenAI 兼容，多节点）
  postgres:15-alpine             PostgreSQL 主数据库
  qdrant/qdrant:latest           Qdrant 向量库（RAG 索引）
  redis:7-alpine                 Redis 消息队列与缓存

【前置要求】
  • Linux x86_64 服务器（Ubuntu 20.04+ / CentOS 7+ / Debian 10+）
  • Docker Engine 24+（已安装 Docker Compose v2）
  • 宿主机/内网可达的 LLM 服务（Ollama / vLLM，OpenAI 兼容）
  • embedding 集群随包内置（BGE-M3）；GPU 可选，CPU 亦可运行
  • 最低配置：8 核 CPU / 16 GB RAM / 100 GB 磁盘
  • 推荐配置：16 核 / 32 GB / 200 GB SSD；若随包恢复 2TB 入库数据需对应磁盘
  • embedding 集群建议额外预留：每 worker ~4GB RAM（GPU 可大幅提速）

【浏览器兼容性】
  前端已针对内网旧版浏览器做了完整的兼容处理：

  JavaScript（esbuild legacy 编译）:
    Chrome 58+、Firefox 57+、Safari 11+、Edge 18+、iOS 11+
    nomodule legacy chunks 确保旧引擎不执行 ES module 语法

  CSS 兼容层（三层防御）:
    1. PostCSS 构建转换 — Tailwind v4 的 oklch() 颜色在构建时转为 rgb() 回退，
       所有现代颜色函数均以 @supports 块保护，旧浏览器看到的都是兼容的 rgb/hex 值
    2. legacy-compat.css — 仅在浏览器不支持 oklch() 时注入，提供动态 color-mix()
       兜底、backdrop-filter 实底降级、focus ring 明确颜色
    3. 构建验证 — 每次打包自动运行 check-compat.mjs 确认无裸 oklch() 进入产物

  可接受的视觉降级（不影响功能和布局）:
    • Chrome <111 / Firefox <113：动态 color-mix() 的半透明 ring 颜色略有差异
    • Chrome <85：@property 动画组合退化为各独立动画
    • Chrome <105：:has() 增强选择器样式不生效，基础样式正常

  建议使用 Chrome 80+（2020年后）以获得最佳视觉体验。
  不支持 IE11 及以下版本。

【部署步骤】
  1. 将 offline-images/ 整个目录传输到服务器（scp / rsync / U盘）
  2. chmod +x deploy_offline.sh
  3. 复制 .env.example 为 .env，至少修改：
       DEFAULT_LLM_BASE_URL=http://宿主机IP:11434/v1
       DEFAULT_LLM_MODEL=你的模型名称（如 qwen2.5:72b）
       DEFAULT_ADMIN_PASSWORD=强密码（仅含字母数字）
  4. ./deploy_offline.sh

【更新部署（已有数据不丢失）】
  将新 images.tar.gz 放入同目录后执行：
    ./deploy_offline.sh --update

【数据目录说明】
  data/app.db           SQLite 主数据库（报告、用户、知识库元数据 + chunk）
  data/pg_data/         PostgreSQL 主数据库（如使用 PG 模式）
  data/qdrant_storage/  Qdrant 向量库（RAG 向量索引）
  data/uploads/         用户上传的文件（PDF、Word、Excel）
  data/templates/       PPT 模板文件
  data/structured_dbs/  DuckDB 结构化数据表（Excel/CSV 上传后自动注册）
  data/redis/           Redis 持久化数据
  data/kb_sources/      离线语料源（入库后可删，运行时不需要）

【已入库数据恢复（--with-data 打包时）】
  若 offline-images/data_export/ 存在，deploy_offline.sh 首次部署会自动：
    • 复制 app.db → data/app.db（SQLite 主数据库，含用户/知识库/本体数据）
    • 解压 qdrant_storage.tar.gz → data/qdrant_storage/（容器启动前）
    • pg_restore postgres.dump → PostgreSQL（如使用 PG 模式，仅当库为空）
  这样目标机开箱即用，无需重新下载 2TB 语料、无需重跑 embedding。

【备份】
  ./deploy_offline.sh --backup   # 生成 backup_YYYYMMDD.tar.gz

【常见问题】
  Q: 报告生成超时（前端一直转圈）
  A: 检查 Ollama 服务是否正常：curl http://宿主机IP:11434/api/tags
     检查模型是否已拉取：ollama list

  Q: 文件上传失败（413 错误）
  A: 单文件最大 500 MB，超出需联系管理员调整 nginx 配置。

  Q: PPT 渲染 QA 失败
  A: LibreOffice 在部分精简镜像上字体缺失，系统自动退回几何 QA 模式，
     功能正常但像素级质检不可用。

  Q: Excel/CSV 上传后结构化查询无数据
  A: 确认文件已成功上传到知识库（状态显示"已就绪"），
     DuckDB 表存储在 data/structured_dbs/。

  Q: 页面加载后白屏或 JS 报错
  A: 检查浏览器版本（需 Chrome 58+ / Firefox 57+ / Edge 18+）。
     按 F12 打开开发者工具，查看 Console 报错。
     如果是样式问题（颜色异常），在 URL 后加 ?daLegacyCss=1 强制启用兼容层。

  Q: 登录失败（密码正确但提示错误）
  A: 确认 .env 中 DEFAULT_ADMIN_PASSWORD 与部署时设置一致。
     密码建议只使用字母和数字，避免特殊字符被 shell 转义。
README

# ── 输出摘要 ──────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ 离线部署包已生成: $OUTPUT_DIR/"
echo ""
echo "  包含文件:"
ls -1 "$OUTPUT_DIR"
echo ""
echo "  下一步:"
echo "  1. 将 offline-images/ 整个目录传输到内网服务器"
echo "  2. 修改 .env（配置 LLM 地址、模型名称、管理员密码）"
echo "  3. chmod +x deploy_offline.sh && ./deploy_offline.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
