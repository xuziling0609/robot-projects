#!/bin/bash
set -euo pipefail

# 加载环境变量（读取端口配置）
if [ -f .env ]; then
    source .env
else
    echo "错误：未找到 .env 配置文件"
    exit 1
fi

# ====================== 1. 检测服务器架构 ======================
detect_arch() {
    local arch
    arch=$(uname -m)
    case "${arch}" in
        x86_64|amd64)
            echo "amd64"
            ;;
        aarch64|arm64)
            echo "arm64"
            ;;
        *)
            echo "不支持的架构: ${arch}" >&2
            exit 1
            ;;
    esac
}

ARCH=$(detect_arch)
export ARCH
echo "✅ 检测架构成功：${ARCH}"

# 同步检测到的架构回写至 .env
if [ -f .env ]; then
    if grep -q "^ARCH=" .env; then
        sed -i "s/^ARCH=.*/ARCH=${ARCH}/" .env
    else
        echo "ARCH=${ARCH}" >> .env
    fi
fi


# ====================== 2. 检测 Docker 环境 ======================
check_docker() {
    local target_docker_ver="24.0.9"
    if command -v docker >/dev/null 2>&1; then
        local current_ver
        current_ver=$(docker version --format '{{.Server.Version}}' 2>/dev/null || docker version --format '{{.Client.Version}}' 2>/dev/null || docker -v 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -n 1 || echo "")
        echo "✅ Docker 版本: $(docker --version)"
        if [ -n "$current_ver" ] && [ "$current_ver" != "$target_docker_ver" ]; then
            echo "⚠️  注意：当前 Docker 版本 (${current_ver}) 与推荐版本 (${target_docker_ver}) 不一致"
            echo "    如需更换为匹配版本，可执行: sudo ./0-setup-docker.sh"
        fi

        local current_root
        current_root=$(docker info -f '{{.DockerRootDir}}' 2>/dev/null || echo "")
        if [ -n "$current_root" ]; then
            echo "📁 Docker 数据目录: ${current_root}"
        fi
        if [ -n "${DOCKER_DIR:-}" ] && [ -n "$current_root" ] && [ "${current_root%/}" != "${DOCKER_DIR%/}" ]; then
            echo "⚠️  注意：当前 Docker 数据目录 (${current_root}) 与 .env 配置 (${DOCKER_DIR}) 不一致"
            echo "    如需迁移至指定目录，可执行: sudo ./0-setup-docker.sh"
        fi
    else
        echo "❌ 未安装 Docker！"
        echo "💡 提示：项目已提供一键离线检测与安装脚本，请执行: sudo ./0-setup-docker.sh"
        exit 1
    fi

    if docker compose version >/dev/null 2>&1; then
        echo "✅ Docker Compose 版本: $(docker compose version)"
    elif command -v docker-compose >/dev/null 2>&1; then
        echo "✅ Docker Compose (V1) 版本: $(docker-compose --version)"
    else
        echo "❌ 未检测到 Docker Compose，请执行: sudo ./0-setup-docker.sh 快速安装"
        exit 1
    fi
}

echo
echo "==================== 检测 Docker 环境 ===================="
check_docker


# ====================== 3. 端口占用检查 ======================
check_port() {
    local port=$1
    local app_name=$2

    if command -v ss >/dev/null 2>&1; then
        if ss -tuln | grep -q ":${port} "; then
            echo "❌ 端口冲突：${app_name} (端口: ${port}) 已被占用"
            exit 1
        fi
    elif command -v netstat >/dev/null 2>&1; then
        if netstat -tuln | grep -q ":${port} "; then
            echo "❌ 端口冲突：${app_name} (端口: ${port}) 已被占用"
            exit 1
        fi
    else
        echo "⚠️  无法检查端口占用（未安装 ss/netstat），继续部署..."
    fi
}

echo
echo "==================== 检查端口占用 ===================="
if [ "${DB_TYPE:-}" = "mysql" ]; then
    check_port "${PORT_MYSQL}" "MySQL"
elif [ "${DB_TYPE:-}" = "opengauss" ]; then
    check_port "${PORT_OPENGAUSS}" "openGauss"
else
    check_port "${PORT_OPENGAUSS}" "openGauss"
    check_port "${PORT_MYSQL}" "MySQL"
fi
check_port "${PORT_REDIS}" "Redis"
check_port "${PORT_EMQX_MQTT}" "EMQX-MQTT"
check_port "${PORT_EMQX_MQTTS}" "EMQX-MQTTS"
check_port "${PORT_EMQX_WS}" "EMQX-WS"
check_port "${PORT_EMQX_WSS}" "EMQX-WSS"
check_port "${PORT_EMQX_DASHBOARD}" "EMQX-Dashboard"
check_port "${PORT_NGINX_HTTP}" "Nginx-HTTP"
check_port "${PORT_NGINX_HTTPS}" "Nginx-HTTPS"
check_port "${PORT_JAVA}" "Java后端"
check_port "${PORT_SEAWEEDFS_MASTER:-9333}" "SeaweedFS-Master"
check_port "${PORT_SEAWEEDFS_VOLUME:-8085}" "SeaweedFS-Volume"
check_port "${PORT_SEAWEEDFS_FILER:-8888}" "SeaweedFS-Filer"
check_port "${PORT_GO2RTC_API:-1984}" "go2rtc-API"
check_port "${PORT_GO2RTC_RTSP:-8554}" "go2rtc-RTSP"
check_port "${PORT_GO2RTC_WEBRTC:-8555}" "go2rtc-WebRTC"

echo "✅ 所有端口未占用"
echo