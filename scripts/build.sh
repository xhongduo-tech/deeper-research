#!/bin/bash
# ==============================================================================
# 深研AI 多智能体平台 - 构建脚本
# 在可连接外网的机器上运行，用于构建所有 Docker 镜像
# 构建完成后使用 scripts/export.sh 导出镜像用于离线部署
# ==============================================================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}=== 深研AI 多智能体平台 - 构建脚本 ===${NC}"
echo -e "${YELLOW}此脚本需要在可连接外网的机器上运行${NC}"
echo ""

# 切换到脚本所在目录的上级（项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"
echo "项目目录: $PROJECT_ROOT"
echo ""

# ------------------------------------------------------------------------------
# 检查依赖
# ------------------------------------------------------------------------------
echo "检查依赖..."

if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: 未找到 Docker，请先安装 Docker Desktop${NC}"
    echo "下载地址: https://www.docker.com/products/docker-desktop"
    exit 1
fi

DOCKER_VERSION=$(docker version --format '{{.Server.Version}}' 2>/dev/null)
echo -e "${GREEN}Docker 版本: $DOCKER_VERSION${NC}"

# 检查 docker compose (v2) 或 docker-compose (v1)
if docker compose version &> /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo -e "${RED}错误: 未找到 docker compose 或 docker-compose${NC}"
    exit 1
fi
echo -e "${GREEN}Docker Compose: $COMPOSE_CMD${NC}"
echo ""

# ------------------------------------------------------------------------------
# 目标平台（默认 linux/amd64，适用于行内 x86_64 服务器）
# Mac Apple Silicon 交叉编译时必须指定此参数
# 如需本机测试（arm64），运行: export BUILD_PLATFORM=linux/arm64
#
# 可选环境变量:
#   BUILD_PLATFORM=linux/amd64|linux/arm64   目标平台
#   NO_CACHE=1                               强制无缓存(首次/出错时建议)
# ------------------------------------------------------------------------------
TARGET_PLATFORM="${BUILD_PLATFORM:-linux/amd64}"
NO_CACHE_FLAG=""
if [[ "${NO_CACHE:-0}" == "1" ]]; then
    NO_CACHE_FLAG="--no-cache"
fi
echo -e "${YELLOW}目标平台: $TARGET_PLATFORM${NC}"
if [[ -n "$NO_CACHE_FLAG" ]]; then
    echo -e "${YELLOW}构建模式: 无缓存${NC}"
fi

# Apple Silicon 交叉编译 x86 时必须有 QEMU binfmt
if [[ "$(uname -m)" == "arm64" && "$TARGET_PLATFORM" == "linux/amd64" ]]; then
    if ! docker run --rm --privileged tonistiigi/binfmt --version &>/dev/null; then
        echo -e "${YELLOW}启用 QEMU binfmt(首次跨架构构建需要)...${NC}"
        docker run --privileged --rm tonistiigi/binfmt --install all || true
    fi
fi
echo ""

# 确保 buildx 可用（Docker Desktop 已内置）
if ! docker buildx version &>/dev/null; then
    echo -e "${RED}错误: 未找到 docker buildx，请升级到 Docker Desktop 4.x+${NC}"
    exit 1
fi

# 创建/使用 multi-platform builder（首次会自动创建）
if ! docker buildx inspect deep-research-builder &>/dev/null; then
    docker buildx create --name deep-research-builder --driver docker-container --use
    docker buildx inspect --bootstrap deep-research-builder
else
    docker buildx use deep-research-builder
fi

# ------------------------------------------------------------------------------
# 构建镜像
# ------------------------------------------------------------------------------
echo -e "${BLUE}构建后端镜像...${NC}"
docker buildx build \
    --platform "$TARGET_PLATFORM" \
    $NO_CACHE_FLAG \
    --load \
    -t deep-research-backend:latest \
    ./backend/
echo -e "${GREEN}后端镜像构建完成${NC}"
echo ""

echo -e "${BLUE}构建前端镜像...${NC}"
docker buildx build \
    --platform "$TARGET_PLATFORM" \
    $NO_CACHE_FLAG \
    --load \
    -t deep-research-frontend:latest \
    ./frontend/
echo -e "${GREEN}前端镜像构建完成${NC}"
echo ""

# ------------------------------------------------------------------------------
# 拉取依赖镜像
# ------------------------------------------------------------------------------
echo -e "${BLUE}拉取依赖镜像...${NC}"
docker pull --platform "$TARGET_PLATFORM" redis:7-alpine
echo -e "${GREEN}依赖镜像拉取完成${NC}"
echo ""

# ------------------------------------------------------------------------------
# 汇总
# ------------------------------------------------------------------------------
echo -e "${GREEN}======================================"
echo "所有镜像构建完成！"
echo -e "======================================${NC}"
echo ""
echo "已构建的镜像:"
docker images | grep -E "(deep-research|redis:7)" | awk '{printf "  %-40s %-15s %s\n", $1, $2, $7" "$8}'
echo ""
echo -e "${YELLOW}下一步: 运行 scripts/export.sh 导出镜像用于离线部署${NC}"
echo ""
