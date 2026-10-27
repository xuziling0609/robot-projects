#!/bin/bash
# ==============================================================================
# 智能机器人综合管理平台 - 一键自动化部署脚本
# 支持架构: x86_64 / aarch64 (arm64)
# 支持数据库: openGauss 6.0 / MySQL 8.0 (交互式选择)
# ==============================================================================

set -euo pipefail
cd "$(dirname "$0")"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    echo "❌ 未安装 Docker Compose，请先运行 sudo ./0-setup-docker.sh 安装！"
    exit 1
fi

# ==============================
# 1. 加载环境变量
# ==============================
if [ -f .env ]; then
    # shellcheck disable=SC1091
    source ./.env
fi

# ==============================
# 2. 数据库类型选择（支持命令行传参与终端交互选择）
# ==============================
CHOSEN_DB=""
# 检查是否通过参数传入：如 ./3-deploy.sh mysql 或 ./3-deploy.sh opengauss
if [ -n "${1:-}" ]; then
    case "$1" in
        1|opengauss|openGauss)
            CHOSEN_DB="opengauss"
            ;;
        2|mysql|MySQL)
            CHOSEN_DB="mysql"
            ;;
        *)
            echo "⚠️ 未知的数据库参数: $1，将进入交互式选择..."
            ;;
    esac
fi

if [ -z "${CHOSEN_DB}" ]; then
    CURRENT_CONFIGURED="${DB_TYPE}"
    echo "===================================================="
    echo "请选择部署所使用的数据库引擎 (Database Selection):"
    echo "  1) openGauss (国产高可用关系型数据库 6.0.0，默认推荐)"
    echo "  2) MySQL     (主流开源关系型数据库 8.0.46)"
    echo "===================================================="
    read -r -p "请输入选项序号 [1/2] (当前配置/默认: ${CURRENT_CONFIGURED}): " input_choice
    case "${input_choice}" in
        2|[mM][yY][sS][qQ][lL])
            CHOSEN_DB="mysql"
            ;;
        1|[oO][pP][eE][nN][gG][aA][uU][sS][sS])
            CHOSEN_DB="opengauss"
            ;;
        "")
            CHOSEN_DB="${CURRENT_CONFIGURED}"
            ;;
        *)
            echo "⚠️ 输入无效，采用当前配置: ${CURRENT_CONFIGURED}"
            CHOSEN_DB="${CURRENT_CONFIGURED}"
            ;;
    esac
fi

export DB_TYPE="${CHOSEN_DB}"
export COMPOSE_PROFILES="${DB_TYPE}"
echo "✅ 已选定数据库: ${DB_TYPE}"

# 同步持久化回写至 .env，供 4-start.sh / 6-restart.sh 记忆使用
if [ -f .env ]; then
    if grep -q "^DB_TYPE=" .env; then
        sed -i "s/^DB_TYPE=.*/DB_TYPE=${DB_TYPE}/" .env
    else
        echo "DB_TYPE=${DB_TYPE}" >> .env
    fi
    sed -i '/^SPRING_DB_PROFILE=/d' .env
fi

# ==============================
# 3. 检测系统架构与初始化挂载目录权限
# ==============================
source ./1-check-env.sh
export ARCH

# 归一化架构标签，精准匹配 docker-image/ 下的归档包名 (-amd64.tar 与 -arm64.tar)
case "${ARCH}" in
    x86_64|amd64)
        ARCH_TAG="amd64"
        ALT_ARCH="x86_64"
        ;;
    aarch64|arm64)
        ARCH_TAG="arm64"
        ALT_ARCH="aarch64"
        ;;
    *)
        ARCH_TAG="${ARCH}"
        ALT_ARCH="${ARCH}"
        ;;
esac

./2-chmod.sh

# 兼容旧版本 runc，禁用 BuildKit 避免 flag provided but not defined: -keep
export DOCKER_BUILDKIT=0
export COMPOSE_DOCKER_CLI_BUILD=0

# ==============================
# 4. 创建 Docker 网络
# ==============================
if ! docker network inspect "$DOCKER_NETWORK" >/dev/null 2>&1; then
    echo "创建网络：$DOCKER_NETWORK"
    docker network create "$DOCKER_NETWORK"
else
    echo "网络已存在：$DOCKER_NETWORK（跳过）"
fi

# ==============================
# 5. 导入镜像（按架构精准寻址，已存在则跳过）
# ==============================
import_image() {
    local base_tar=$1
    local name=$2
    if docker image inspect "$name" >/dev/null 2>&1; then
        echo "✅ 镜像已存在：$name（跳过导入）"
        return
    fi

    local tar_path=""
    local candidates=(
        "${base_tar}-${ARCH_TAG}.tar"
        "${base_tar}-${ALT_ARCH}.tar"
        "${base_tar}-${ARCH}.tar"
        "${base_tar}.tar"
    )

    for dir in "docker-image" "docker-images" "${SCRIPT_DIR}/docker-image"; do
        for c in "${candidates[@]}"; do
            if [ -f "${dir}/${c}" ]; then
                tar_path="${dir}/${c}"
                break 2
            fi
        done
    done

    if [ -n "${tar_path}" ]; then
        echo "📦 正在导入离线镜像：${tar_path} -> ${name} ..."
        docker load -i "${tar_path}"
    else
        echo "⚠️ 未在 docker-image/ 找到 ${base_tar} 的离线归档，尝试直接拉取 $name..."
        docker pull "$name" || echo "❌ 拉取 $name 失败，请确认镜像源或离线包是否存在！(可执行 'bash docker-image/download.sh' 一键下载离线镜像)"
    fi
}

echo
echo "==================== 导入基础服务离线镜像 ===================="
import_image "amazoncorretto-21.0.11" "$IMAGE_CORRETTO"
import_image "emqx-5.8.9" "$IMAGE_EMQX"
import_image "redis-7.4.9" "$IMAGE_REDIS"
import_image "nginx-1.30.0" "$IMAGE_NGINX"
import_image "seaweedfs-4.47.0" "$IMAGE_SEAWEEDFS"
import_image "go2rtc-1.9.14" "$IMAGE_GO2RTC"

echo
echo "==================== 导入数据库镜像 [${DB_TYPE}] ===================="
if [ "${DB_TYPE}" = "opengauss" ]; then
    import_image "opengauss-6.0.0" "$IMAGE_OPENGAUSS"
elif [ "${DB_TYPE}" = "mysql" ]; then
    import_image "mysql-8.0.46" "$IMAGE_MYSQL"
fi

# ==============================
# 6. 启动所有服务容器（拉起选定数据库及全部业务服务）
# ==============================
echo
echo "启动所有服务容器 (Profile: ${DB_TYPE})..."
$COMPOSE_CMD --profile "$DB_TYPE" up -d --build --wait

# 清理构建过程中产生的悬空(none)镜像
docker image prune -f >/dev/null 2>&1 || true

echo
echo "===================================================="
echo "🎉 容器部署拉起完成！"
echo "  - 系统架构:     $ARCH (${ARCH_TAG})"
echo "  - 数据库引擎:   $DB_TYPE"
if [ "${DB_TYPE}" = "opengauss" ]; then
    echo "  - 数据库容器:   app-opengauss (端口: ${PORT_OPENGAUSS:-5432})"
    echo
    echo "👉 【下一步操作】：请手动执行数据库导入脚本："
    echo "   ./sql/import-sql.sh"
else
    echo "  - 数据库容器:   app-mysql (端口: ${PORT_MYSQL:-3306})"
    echo
    echo "👉 【下一步操作】：请手动执行数据库导入脚本："
    echo "   ./sql/import-sql.sh"
fi
echo "  - 缓存容器:     app-redis (端口: ${PORT_REDIS})"
echo "  - 访问服务:     容器间通信直接使用服务名作为域名"
echo "===================================================="