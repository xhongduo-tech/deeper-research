#!/bin/bash
# ==============================================================================
# 深研AI 多智能体平台 - 离线部署脚本
# 在内网服务器上运行，加载镜像并启动所有服务
# 无需访问互联网
# ==============================================================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}=== 深研AI 多智能体平台 - 离线部署 ===${NC}"
echo ""

# ------------------------------------------------------------------------------
# 检查 Docker
# ------------------------------------------------------------------------------
echo "检查运行环境..."

if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: 未找到 Docker，请联系运维人员安装 Docker CE${NC}"
    echo ""
    echo "CentOS 安装参考:"
    echo "  yum install -y docker-ce docker-ce-cli containerd.io"
    echo "  systemctl enable --now docker"
    exit 1
fi

DOCKER_VERSION=$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo "unknown")
echo -e "  Docker 版本: ${GREEN}$DOCKER_VERSION${NC}"

if docker compose version &> /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
    COMPOSE_VERSION=$(docker compose version --short 2>/dev/null || echo "unknown")
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
    COMPOSE_VERSION=$(docker-compose version --short 2>/dev/null || echo "unknown")
else
    echo -e "${RED}错误: 未找到 docker compose 或 docker-compose${NC}"
    echo "请安装 docker-compose: pip install docker-compose"
    exit 1
fi
echo -e "  Docker Compose: ${GREEN}$COMPOSE_VERSION ($COMPOSE_CMD)${NC}"
echo ""

# ------------------------------------------------------------------------------
# 加载镜像
# ------------------------------------------------------------------------------
ARCHIVE=$(ls deep-research-*.tar.gz 2>/dev/null | sort -V | tail -1)
if [ -z "$ARCHIVE" ]; then
    echo -e "${RED}错误: 未找到镜像文件 deep-research-*.tar.gz${NC}"
    echo "请确认镜像文件已传输到当前目录: $(pwd)"
    exit 1
fi

echo -e "${BLUE}加载 Docker 镜像: $ARCHIVE${NC}"
echo "（此过程可能需要数分钟，请耐心等待...）"
docker load < "$ARCHIVE"
echo -e "${GREEN}镜像加载完成${NC}"
echo ""

# 验证镜像
echo "验证镜像..."
for IMG in "deep-research-backend:latest" "deep-research-frontend:latest" "redis:7-alpine"; do
    if docker image inspect "$IMG" &> /dev/null; then
        echo -e "  ${GREEN}[OK]${NC} $IMG"
    else
        echo -e "  ${RED}[缺失]${NC} $IMG"
        echo -e "${RED}错误: 镜像 $IMG 加载失败，镜像文件可能损坏${NC}"
        exit 1
    fi
done
echo ""

# ------------------------------------------------------------------------------
# 创建数据目录
# ------------------------------------------------------------------------------
echo "创建数据目录..."
mkdir -p data/uploads data/templates data/sandbox data/db data/redis
echo -e "${GREEN}数据目录创建完成${NC}"
echo ""

# ------------------------------------------------------------------------------
# 配置环境变量
# ------------------------------------------------------------------------------
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
    else
        echo -e "${RED}错误: 未找到 .env.example，部署包可能不完整${NC}"
        exit 1
    fi

    # 生成随机密钥
    if command -v openssl &> /dev/null; then
        SECRET=$(openssl rand -hex 32)
    else
        SECRET=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1 2>/dev/null || echo "please-change-this-secret-key-manually")
    fi
    sed -i "s/change-this-to-a-random-64-char-string/$SECRET/" .env
    echo -e "${YELLOW}已自动生成随机密钥并写入 .env${NC}"
fi

# ------------------------------------------------------------------------------
# 确认 LLM 配置
# ------------------------------------------------------------------------------
echo -e "${YELLOW}======================================"
echo "请确认 LLM 配置（编辑 .env 文件）"
echo -e "======================================${NC}"
echo ""
echo "当前配置:"
echo "  DEFAULT_LLM_BASE_URL = $(grep '^DEFAULT_LLM_BASE_URL' .env | cut -d= -f2-)"
echo "  DEFAULT_LLM_MODEL    = $(grep '^DEFAULT_LLM_MODEL' .env | cut -d= -f2-)"
echo "  DEFAULT_LLM_API_KEY  = $(grep '^DEFAULT_LLM_API_KEY' .env | cut -d= -f2-)"
echo ""
echo -e "${YELLOW}如需修改，请 Ctrl+C 退出后编辑 .env 文件再重新运行${NC}"
echo ""
read -p "配置正确，继续部署？(y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "已取消。请编辑 .env 文件后重新运行:"
    echo "  vi .env"
    echo "  bash deploy.sh"
    exit 0
fi
echo ""

# ------------------------------------------------------------------------------
# 启动服务
# ------------------------------------------------------------------------------
echo -e "${BLUE}启动服务...${NC}"
# 使用 prod overlay：锁定 linux/amd64 平台、关闭 Redis 外部端口、增加资源限制
$COMPOSE_CMD -f docker-compose.yml -f docker-compose.prod.yml up -d

echo ""
echo "等待服务完全启动（30 秒）..."
sleep 30

# ------------------------------------------------------------------------------
# 健康检查
# ------------------------------------------------------------------------------
echo "检查服务状态..."
echo ""

BACKEND_OK=false
FRONTEND_OK=false

if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
    echo -e "  后端 (8000):   ${GREEN}[正常]${NC}"
    BACKEND_OK=true
else
    echo -e "  后端 (8000):   ${YELLOW}[启动中/未响应]${NC}"
fi

if curl -sf http://localhost:80 > /dev/null 2>&1; then
    echo -e "  前端 (80):     ${GREEN}[正常]${NC}"
    FRONTEND_OK=true
else
    echo -e "  前端 (80):     ${YELLOW}[启动中/未响应]${NC}"
fi

# 检查 Redis
if $COMPOSE_CMD -f docker-compose.yml -f docker-compose.prod.yml exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
    echo -e "  Redis (6379):  ${GREEN}[正常]${NC}"
else
    echo -e "  Redis (6379):  ${YELLOW}[检测超时]${NC}"
fi

# 获取服务器 IP
SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || ip addr show | grep 'inet ' | grep -v 127.0.0.1 | head -1 | awk '{print $2}' | cut -d/ -f1)

echo ""
echo -e "${GREEN}======================================"
echo "部署完成！"
echo -e "======================================${NC}"
echo ""
echo "访问地址: http://$SERVER_IP"
echo "管理后台: http://$SERVER_IP/admin"
echo "默认账号: admin"
echo "默认密码: admin123456"
echo ""
echo -e "${RED}⚠️  首次登录后请立即修改密码！${NC}"
echo ""
echo "常用命令:"
echo "  查看日志:    $COMPOSE_CMD logs -f"
echo "  查看状态:    $COMPOSE_CMD ps"
echo "  停止服务:    $COMPOSE_CMD down"
echo "  重启服务:    $COMPOSE_CMD restart"
echo "  更新版本:    bash update.sh"
echo ""

if [ "$BACKEND_OK" = false ] || [ "$FRONTEND_OK" = false ]; then
    echo -e "${YELLOW}部分服务可能仍在启动中，请稍等片刻后再次访问。${NC}"
    echo "若持续无法访问，请检查日志: $COMPOSE_CMD logs -f"
    echo ""
fi
