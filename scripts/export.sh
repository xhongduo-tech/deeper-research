#!/bin/bash
# ==============================================================================
# 深研AI 多智能体平台 - 镜像导出脚本
# 将所有 Docker 镜像打包为单一归档文件，用于传输到内网服务器
# 在运行此脚本前，请先运行 scripts/build.sh 完成镜像构建
# ==============================================================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 切换到项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

EXPORT_DIR="./dist"
DATE_TAG=$(date +%Y%m%d)
ARCHIVE_NAME="deep-research-${DATE_TAG}.tar.gz"

echo ""
echo -e "${BLUE}=== 深研AI 多智能体平台 - 镜像导出 ===${NC}"
echo ""

# ------------------------------------------------------------------------------
# 检查镜像是否存在
# ------------------------------------------------------------------------------
MISSING=""
for IMG in "deep-research-backend:latest" "deep-research-frontend:latest" "redis:7-alpine"; do
    if ! docker image inspect "$IMG" &> /dev/null; then
        MISSING="$MISSING  - $IMG\n"
    fi
done

if [ -n "$MISSING" ]; then
    echo -e "${RED}错误: 以下镜像不存在，请先运行 scripts/build.sh:${NC}"
    printf "$MISSING"
    exit 1
fi

# ------------------------------------------------------------------------------
# 创建导出目录
# ------------------------------------------------------------------------------
mkdir -p "$EXPORT_DIR"

# ------------------------------------------------------------------------------
# 导出镜像
# ------------------------------------------------------------------------------
echo -e "${BLUE}保存镜像到归档文件（此过程可能需要数分钟）...${NC}"
echo "  目标文件: $EXPORT_DIR/$ARCHIVE_NAME"
echo ""

docker save \
    deep-research-backend:latest \
    deep-research-frontend:latest \
    redis:7-alpine \
    | gzip > "$EXPORT_DIR/$ARCHIVE_NAME"

echo -e "${GREEN}镜像导出完成${NC}"
echo ""

# ------------------------------------------------------------------------------
# 复制配置文件
# ------------------------------------------------------------------------------
echo "复制配置文件..."
cp docker-compose.yml       "$EXPORT_DIR/"
cp docker-compose.prod.yml  "$EXPORT_DIR/"
cp .env.example             "$EXPORT_DIR/.env.example"
cp scripts/deploy.sh        "$EXPORT_DIR/deploy.sh"
cp scripts/update.sh        "$EXPORT_DIR/update.sh"
chmod +x "$EXPORT_DIR/deploy.sh" "$EXPORT_DIR/update.sh"

# 复制 nginx 配置目录
cp -r nginx "$EXPORT_DIR/"

echo "配置文件复制完成"
echo ""

# ------------------------------------------------------------------------------
# 生成部署说明
# ------------------------------------------------------------------------------
cat > "$EXPORT_DIR/部署说明.txt" << 'EOF'
深研AI 多智能体平台 - 离线部署包
================================

【系统要求】
- OS: CentOS 7+、Ubuntu 18.04+、Debian 10+ 或其他主流 Linux 发行版
- CPU: 4 核及以上（推荐 8 核）
- 内存: 8 GB 及以上（推荐 16 GB）
- 磁盘: 50 GB 及以上可用空间
- 软件: Docker CE 20.10+ 及 Docker Compose v2（或 docker-compose v1.29+）

【部署步骤】
1. 将此目录下所有文件上传到内网服务器
2. 在服务器上执行: bash deploy.sh
3. 根据提示编辑 .env 文件，配置内网 LLM 服务地址
4. 部署完成后访问: http://服务器IP

【LLM 配置说明】
编辑 .env 文件，设置以下参数指向内网大模型服务:
  DEFAULT_LLM_BASE_URL=http://你的模型服务IP:端口/v1
  DEFAULT_LLM_MODEL=模型名称
  DEFAULT_LLM_API_KEY=API密钥（如无需认证填 ollama）

【默认账号】
  账号: admin
  密码: admin123456
  ⚠️ 首次登录后请立即修改密码！

【常用命令】
  查看日志:  docker-compose logs -f
  停止服务:  docker-compose down
  重启服务:  docker-compose restart
  更新版本:  bash update.sh

【技术支持】
如遇问题请联系系统管理员或查阅 README.md 中的故障排查章节。
EOF

# ------------------------------------------------------------------------------
# 汇总
# ------------------------------------------------------------------------------
ARCHIVE_SIZE=$(du -sh "$EXPORT_DIR/$ARCHIVE_NAME" | cut -f1)
TOTAL_SIZE=$(du -sh "$EXPORT_DIR" | cut -f1)

echo -e "${GREEN}======================================"
echo "导出完成！"
echo -e "======================================${NC}"
echo ""
echo "导出目录: $EXPORT_DIR/"
echo "镜像归档: $ARCHIVE_NAME  (${ARCHIVE_SIZE})"
echo "目录总大小: ${TOTAL_SIZE}"
echo ""
echo -e "${YELLOW}传输说明:${NC}"
echo "  将整个 $EXPORT_DIR/ 目录传输到内网服务器"
echo "  推荐使用 scp 或 rsync，也可压缩后通过 U 盘拷贝"
echo ""
echo "  示例 scp 命令:"
echo "    scp -r $EXPORT_DIR/ user@内网服务器IP:/opt/deep-research/"
echo ""
echo "  传输完成后在服务器上运行:"
echo "    bash deploy.sh"
echo ""
