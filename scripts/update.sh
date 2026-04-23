#!/bin/bash
# ==============================================================================
# 深研AI 多智能体平台 - 版本更新脚本
# 将新版本镜像归档文件放置在当前目录后运行此脚本
# ==============================================================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}=== 深研AI 多智能体平台 - 版本更新 ===${NC}"
echo ""

# 检查 docker compose
if docker compose version &> /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo -e "${RED}错误: 未找到 docker compose 或 docker-compose${NC}"
    exit 1
fi

# ------------------------------------------------------------------------------
# 查找最新镜像归档
# ------------------------------------------------------------------------------
ARCHIVE=$(ls deep-research-*.tar.gz 2>/dev/null | sort -V | tail -1)
if [ -z "$ARCHIVE" ]; then
    echo -e "${RED}错误: 未找到镜像文件 deep-research-*.tar.gz${NC}"
    echo "请将新版本镜像文件传输到当前目录后再运行"
    exit 1
fi

echo "发现镜像文件: $ARCHIVE"
echo ""

# ------------------------------------------------------------------------------
# 备份当前数据库
# ------------------------------------------------------------------------------
echo -e "${BLUE}备份当前数据...${NC}"
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backup_$BACKUP_DATE"
mkdir -p "$BACKUP_DIR"

if [ -d ./data/db ]; then
    cp -r ./data/db "$BACKUP_DIR/db"
    echo -e "  数据库备份: ${GREEN}$BACKUP_DIR/db${NC}"
fi

echo -e "${GREEN}备份完成${NC}"
echo ""

# ------------------------------------------------------------------------------
# 加载新版本镜像
# ------------------------------------------------------------------------------
echo -e "${BLUE}加载新版本镜像...${NC}"
docker load < "$ARCHIVE"
echo -e "${GREEN}镜像加载完成${NC}"
echo ""

# ------------------------------------------------------------------------------
# 滚动更新服务（保持 Redis 不重启以避免数据丢失）
# ------------------------------------------------------------------------------
echo -e "${BLUE}更新应用服务...${NC}"
$COMPOSE_CMD -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps backend frontend

echo ""
echo "等待服务重启（15 秒）..."
sleep 15

# ------------------------------------------------------------------------------
# 健康检查
# ------------------------------------------------------------------------------
echo "检查服务状态..."
if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
    echo -e "  后端:  ${GREEN}[正常]${NC}"
else
    echo -e "  后端:  ${YELLOW}[启动中...]${NC}"
fi

if curl -sf http://localhost:80 > /dev/null 2>&1; then
    echo -e "  前端:  ${GREEN}[正常]${NC}"
else
    echo -e "  前端:  ${YELLOW}[启动中...]${NC}"
fi

echo ""
echo -e "${GREEN}======================================"
echo "更新完成！"
echo -e "======================================${NC}"
echo ""
echo "若更新后出现问题，可回滚："
echo "  1. $COMPOSE_CMD down"
echo "  2. cp -r $BACKUP_DIR/db ./data/db"
echo "  3. 加载旧版本镜像并重新 $COMPOSE_CMD up -d"
echo ""
echo "查看日志: $COMPOSE_CMD logs -f"
echo ""
