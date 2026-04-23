#!/bin/bash
# ==============================================================================
# 深研AI 多智能体平台 · Mac 本机启动脚本
#
# 用途: 在 Mac 上(Apple Silicon 或 Intel)一键启动整套服务用于开发/演示。
#       自动使用 docker-compose.mac.yml overlay,走 arm64 原生镜像,避免 QEMU。
# 非用途: 不用于 x86 服务器部署; 请使用 scripts/deploy.sh。
#
# 用法:
#     bash scripts/start-mac.sh            # 后台启动
#     bash scripts/start-mac.sh --build    # 强制重新构建镜像
#     bash scripts/start-mac.sh --logs     # 启动后跟随日志
#     bash scripts/start-mac.sh --stop     # 停止所有容器
#     bash scripts/start-mac.sh --reset    # 停止并清理本地数据(危险!)
# ==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.mac.yml)

# ------------------------------------------------------------------------------
# 参数
# ------------------------------------------------------------------------------
ACTION="up"
FOLLOW_LOGS=false
FORCE_BUILD=false
for arg in "$@"; do
    case "$arg" in
        --build) FORCE_BUILD=true ;;
        --logs) FOLLOW_LOGS=true ;;
        --stop) ACTION="stop" ;;
        --reset) ACTION="reset" ;;
        -h|--help)
            sed -n '2,15p' "$0" | sed 's/^# \?//'
            exit 0 ;;
        *) echo -e "${YELLOW}忽略未知参数: $arg${NC}" ;;
    esac
done

echo ""
echo -e "${BLUE}=== 深研AI · Mac 本机启动 ===${NC}"
echo "项目目录: $PROJECT_ROOT"
echo ""

# ------------------------------------------------------------------------------
# 1. 环境检查
# ------------------------------------------------------------------------------
if [[ "$(uname)" != "Darwin" ]]; then
    echo -e "${YELLOW}警告: 非 macOS 系统,当前脚本针对 Mac 设计。${NC}"
    echo -e "${YELLOW}      x86 服务器请使用 scripts/deploy.sh。${NC}"
fi

if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: 未找到 Docker。请先安装并启动 Docker Desktop:${NC}"
    echo "  https://www.docker.com/products/docker-desktop"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo -e "${RED}错误: Docker 已安装但未运行。请启动 Docker Desktop 后重试。${NC}"
    exit 1
fi

if docker compose version &> /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo -e "${RED}错误: 未找到 docker compose 或 docker-compose${NC}"
    exit 1
fi
echo -e "  Docker:         ${GREEN}$(docker version --format '{{.Server.Version}}' 2>/dev/null)${NC}"
echo -e "  Compose:        ${GREEN}$COMPOSE_CMD${NC}"
echo -e "  Architecture:   ${GREEN}$(uname -m)${NC} → linux/arm64(容器)"
echo ""

# ------------------------------------------------------------------------------
# 2. 处理 stop / reset 分支
# ------------------------------------------------------------------------------
if [[ "$ACTION" == "stop" ]]; then
    echo -e "${BLUE}停止服务...${NC}"
    $COMPOSE_CMD "${COMPOSE_FILES[@]}" down
    echo -e "${GREEN}已停止。${NC}"
    exit 0
fi

if [[ "$ACTION" == "reset" ]]; then
    echo -e "${YELLOW}⚠️  即将停止服务并清空 ./data 与上传文件!${NC}"
    read -p "确认执行? (yes/N) " reply
    if [[ "$reply" != "yes" ]]; then
        echo "已取消。"; exit 0
    fi
    $COMPOSE_CMD "${COMPOSE_FILES[@]}" down -v
    rm -rf ./data/db ./data/uploads ./data/sandbox ./data/redis
    echo -e "${GREEN}已重置。${NC}"
    exit 0
fi

# ------------------------------------------------------------------------------
# 3. 初始化 .env
# ------------------------------------------------------------------------------
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        # macOS 的 sed 需要 '' 参数
        if command -v openssl &> /dev/null; then
            SECRET=$(openssl rand -hex 32)
            sed -i '' "s|change-this-to-a-random-64-char-string|$SECRET|" .env
        fi
        echo -e "${GREEN}已创建 .env(从 .env.example 复制并生成随机密钥)${NC}"
        echo -e "${YELLOW}提示: Mac 本机测试可保留默认 LLM 占位配置,${NC}"
        echo -e "${YELLOW}      真实的大模型/向量模型稍后在 管理后台 → 系统设置 里填。${NC}"
    else
        echo -e "${RED}错误: 未找到 .env.example${NC}"
        exit 1
    fi
fi

# ------------------------------------------------------------------------------
# 4. 创建本地数据目录
# ------------------------------------------------------------------------------
mkdir -p data/uploads data/templates data/sandbox data/db data/redis
echo -e "${GREEN}数据目录就绪:${NC} ./data/{uploads,templates,sandbox,db,redis}"
echo ""

# ------------------------------------------------------------------------------
# 5. 启动
# ------------------------------------------------------------------------------
if [[ "$FORCE_BUILD" == true ]]; then
    echo -e "${BLUE}强制重新构建镜像...${NC}"
    $COMPOSE_CMD "${COMPOSE_FILES[@]}" build --no-cache
fi

echo -e "${BLUE}启动容器...${NC}"
$COMPOSE_CMD "${COMPOSE_FILES[@]}" up -d --build

echo ""
echo "等待服务就绪..."
# 最多等 60s
for i in $(seq 1 20); do
    sleep 3
    if curl -sf http://localhost:8000/api/health > /dev/null 2>&1 \
       && curl -sf http://localhost/ > /dev/null 2>&1; then
        break
    fi
done

# ------------------------------------------------------------------------------
# 6. 状态汇总
# ------------------------------------------------------------------------------
BACKEND_OK=false
FRONTEND_OK=false
REDIS_OK=false
curl -sf http://localhost:8000/api/health > /dev/null 2>&1 && BACKEND_OK=true
curl -sf http://localhost/ > /dev/null 2>&1 && FRONTEND_OK=true
$COMPOSE_CMD "${COMPOSE_FILES[@]}" exec -T redis redis-cli ping 2>/dev/null | grep -q PONG && REDIS_OK=true

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN} 启动结果${NC}"
echo -e "${GREEN}======================================${NC}"
printf "  %-16s " "后端 (8000):"
$BACKEND_OK  && echo -e "${GREEN}[OK]${NC}"  || echo -e "${YELLOW}[未响应]${NC}"
printf "  %-16s " "前端 (80):"
$FRONTEND_OK && echo -e "${GREEN}[OK]${NC}"  || echo -e "${YELLOW}[未响应]${NC}"
printf "  %-16s " "Redis (6379):"
$REDIS_OK    && echo -e "${GREEN}[OK]${NC}"  || echo -e "${YELLOW}[未响应]${NC}"
echo ""
echo "  访问地址:   http://localhost"
echo "  API 文档:   http://localhost:8000/docs"
echo "  管理后台:   http://localhost/admin"
echo "  默认账号:   admin / admin123456"
echo ""
echo "  查看日志:   bash scripts/start-mac.sh --logs"
echo "  停止服务:   bash scripts/start-mac.sh --stop"
echo "  清空数据:   bash scripts/start-mac.sh --reset"
echo ""

if ! $BACKEND_OK || ! $FRONTEND_OK; then
    echo -e "${YELLOW}部分服务仍未就绪,可能仍在启动中。查看日志:${NC}"
    echo "  $COMPOSE_CMD ${COMPOSE_FILES[*]} logs -f"
    echo ""
fi

if [[ "$FOLLOW_LOGS" == true ]]; then
    $COMPOSE_CMD "${COMPOSE_FILES[@]}" logs -f
fi
