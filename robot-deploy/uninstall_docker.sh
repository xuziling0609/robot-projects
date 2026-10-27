#!/usr/bin/env bash
# ==============================================================================
# 智能机器人平台 - Docker & Docker Compose 一键完全卸载与清理脚本
# 支持系统: Kylin Linux 银河麒麟、openEuler、CentOS、Ubuntu、Debian 等
# ==============================================================================

set -euo pipefail

# 终端输出颜色定义
RED="\033[31m"
GREEN="\033[32m"
YELLOW="\033[33m"
BLUE="\033[36m"
BOLD="\033[1m"
PLAIN="\033[0m"

# 确保以 root 权限运行
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}[错误] 请使用 sudo 或 root 用户运行此脚本！${PLAIN}"
    echo -e "${YELLOW}示例: sudo bash $0${PLAIN}"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 读取 .env 配置文件（提取自定义 DOCKER_DIR 路径）
if [ -f "${SCRIPT_DIR}/.env" ]; then
    # shellcheck disable=SC1091
    source "${SCRIPT_DIR}/.env"
elif [ -f ".env" ]; then
    # shellcheck disable=SC1091
    source .env
fi

CUSTOM_DOCKER_DIR="${DOCKER_DIR:-}"
CUSTOM_DOCKER_DIR="${CUSTOM_DOCKER_DIR%/}"

# 支持参数：-y / --yes 自动确认卸载
AUTO_YES=false
PURGE_DATA=false
for arg in "$@"; do
    case "$arg" in
        -y|--yes)
            AUTO_YES=true
            ;;
        --purge-data)
            PURGE_DATA=true
            ;;
    esac
done

echo -e "${BLUE}====================================================${PLAIN}"
echo -e "${BLUE}      Docker & Docker Compose 一键卸载与环境清理     ${PLAIN}"
echo -e "${BLUE}====================================================${PLAIN}"

# ====================== 1. 现状检测与卸载前安全确认 ======================
echo -e "\n${GREEN}[1/5] 正在检测本机现有 Docker 环境与业务数据状态...${PLAIN}"

CONTAINER_COUNT=0
IMAGE_COUNT=0
VOLUME_COUNT=0
HAS_RUNNING_DATA=false

if command -v docker >/dev/null 2>&1; then
    DOCKER_VER=$(docker --version 2>/dev/null || echo "已安装")
    echo -e "   - 检测到 Docker:     ${YELLOW}${DOCKER_VER}${PLAIN}"
    if docker info >/dev/null 2>&1; then
        CONTAINER_COUNT=$(docker ps -a -q 2>/dev/null | wc -l || echo 0)
        IMAGE_COUNT=$(docker images -q 2>/dev/null | sort -u | wc -l || echo 0)
        VOLUME_COUNT=$(docker volume ls -q 2>/dev/null | wc -l || echo 0)
        echo -e "   - 容器总数:         ${YELLOW}${CONTAINER_COUNT}${PLAIN} 个"
        echo -e "   - 镜像总数:         ${YELLOW}${IMAGE_COUNT}${PLAIN} 个"
        echo -e "   - 数据卷数:         ${YELLOW}${VOLUME_COUNT}${PLAIN} 个"
        if [ "${CONTAINER_COUNT}" -gt 0 ] || [ "${IMAGE_COUNT}" -gt 0 ] || [ "${VOLUME_COUNT}" -gt 0 ]; then
            HAS_RUNNING_DATA=true
        fi
    fi
else
    echo -e "   - 未检测到运行中的 docker 命令，将继续清理残留配置与文件。"
fi

if [ -n "${CUSTOM_DOCKER_DIR}" ] && [ -d "${CUSTOM_DOCKER_DIR}" ]; then
    DOCKER_DIR_SIZE=$(du -sh "${CUSTOM_DOCKER_DIR}" 2>/dev/null | awk '{print $1}' || echo "0B")
    echo -e "   - 自定义数据目录:   ${BLUE}${CUSTOM_DOCKER_DIR}${PLAIN} (占用: ${DOCKER_DIR_SIZE})"
fi

if [ -d "/var/lib/docker" ]; then
    DEFAULT_DIR_SIZE=$(du -sh "/var/lib/docker" 2>/dev/null | awk '{print $1}' || echo "0B")
    echo -e "   - 默认存储目录:     ${BLUE}/var/lib/docker${PLAIN} (占用: ${DEFAULT_DIR_SIZE})"
fi

# 若包含运行中的业务数据，且非自动确认模式，给出明确风险告警
if [ "${AUTO_YES}" != "true" ]; then
    if [ "${HAS_RUNNING_DATA}" = "true" ]; then
        echo -e "\n${RED}==================== ⚠️  重要告警：检测到已有业务容器/镜像 ====================${PLAIN}"
        echo -e "卸载 Docker 将立即停止所有正在运行的容器服务！"
        echo -e "${RED}================================================================================${PLAIN}"
    fi

    read -r -p "是否确定卸载本机 Docker 及 Docker Compose？请输入 yes 确认 [yes/N]: " confirm_start
    case "${confirm_start}" in
        [yY][eE][sS]|[yY])
            echo -e "${GREEN}>>> 用户已确认，开始执行卸载流程...${PLAIN}"
            ;;
        *)
            echo -e "\n${RED}❌ 已取消卸载操作，系统保持原样未做改动。${PLAIN}"
            exit 0
            ;;
    esac
fi

# ====================== 2. 停止并禁用所有相关服务 ======================
echo -e "\n${GREEN}[2/5] 正在停止并禁用 Docker 及 Containerd 服务...${PLAIN}"
systemctl stop docker.socket docker containerd 2>/dev/null || true
systemctl disable docker.socket docker containerd 2>/dev/null || true

# 终止可能残留的孤立容器进程与守护进程
killall -9 dockerd containerd containerd-shim runc 2>/dev/null || true

# ====================== 3. 卸载包管理器软件包 ======================
echo -e "\n${GREEN}[3/5] 正在卸载系统软件包管理器安装的 Docker 组件...${PLAIN}"

# 1. 适配 Debian / Ubuntu / 银河麒麟 (deb) 系统
if command -v apt-get >/dev/null 2>&1; then
    echo -e "      清理 apt 软件包..."
    DOCKER_APT_PACKAGES=(
        docker
        docker-engine
        docker.io
        docker-doc
        docker-compose
        docker-compose-v2
        docker-compose-plugin
        docker-ce
        docker-ce-cli
        docker-ce-rootless-extras
        docker-buildx-plugin
        containerd
        containerd.io
        runc
        podman-docker
    )
    apt-get purge -y "${DOCKER_APT_PACKAGES[@]}" 2>/dev/null || true
    apt-get autoremove -y --purge 2>/dev/null || true
    apt-get clean 2>/dev/null || true

# 2. 适配 CentOS / RHEL / openEuler / 银河麒麟 (rpm) 系统
elif command -v yum >/dev/null 2>&1; then
    echo -e "      清理 yum 软件包..."
    yum remove -y docker docker-client docker-client-latest docker-common \
        docker-latest docker-latest-logrotate docker-logrotate docker-engine \
        docker-ce docker-ce-cli containerd.io runc 2>/dev/null || true
elif command -v dnf >/dev/null 2>&1; then
    echo -e "      清理 dnf 软件包..."
    dnf remove -y docker docker-client docker-client-latest docker-common \
        docker-latest docker-latest-logrotate docker-logrotate docker-engine \
        docker-ce docker-ce-cli containerd.io runc 2>/dev/null || true
fi

# ====================== 4. 清理二进制程序与配置文件 ======================
echo -e "\n${GREEN}[4/5] 正在清理 Docker & Docker Compose 二进制程序与系统配置...${PLAIN}"

# 清理 CLI 工具与离线静态二进制文件
rm -f /usr/bin/docker /usr/bin/dockerd /usr/bin/docker-init /usr/bin/docker-proxy
rm -f /usr/bin/containerd /usr/bin/containerd-shim* /usr/bin/ctr /usr/bin/runc
rm -f /usr/local/bin/docker /usr/local/bin/dockerd /usr/local/bin/docker-init /usr/local/bin/docker-proxy
rm -f /usr/local/bin/containerd /usr/local/bin/containerd-shim* /usr/local/bin/ctr /usr/local/bin/runc
rm -f /usr/bin/docker-compose /usr/local/bin/docker-compose

# 清理 CLI 插件目录
rm -rf /usr/local/lib/docker/cli-plugins
rm -rf /usr/libexec/docker/cli-plugins
rm -rf /usr/lib/docker/cli-plugins

# 清理 systemd 服务单元
rm -rf /etc/systemd/system/docker.service*
rm -rf /etc/systemd/system/docker.socket*
rm -rf /etc/systemd/system/containerd.service*
systemctl daemon-reload 2>/dev/null || true

# 清理软件源与密钥文件
rm -f /etc/apt/sources.list.d/docker.list /etc/apt/keyrings/docker.* /etc/apt/trusted.gpg.d/docker.gpg 2>/dev/null || true
rm -f /etc/yum.repos.d/docker*.repo 2>/dev/null || true

# 清理运行期临时套接字与 PID 目录
rm -rf /run/docker /run/containerd /var/run/docker.sock /var/run/containerd 2>/dev/null || true

# ====================== 5. 存储数据目录处理 ======================
echo -e "\n${GREEN}[5/5] 检查容器数据与镜像存储目录...${PLAIN}"

DO_CLEAN_DATA=false
if [ "${PURGE_DATA}" = "true" ]; then
    DO_CLEAN_DATA=true
elif [ "${AUTO_YES}" != "true" ]; then
    echo -e "${YELLOW}----------------------------------------------------${PLAIN}"
    echo -e "数据存储目录包括: "
    echo -e "   - 默认目录:   /var/lib/docker, /var/lib/containerd"
    if [ -n "${CUSTOM_DOCKER_DIR}" ] && [ "${CUSTOM_DOCKER_DIR}" != "/var/lib/docker" ]; then
        echo -e "   - 自定义目录: ${CUSTOM_DOCKER_DIR}"
    fi
    echo -e "${YELLOW}----------------------------------------------------${PLAIN}"
    read -r -p "是否彻底删除所有镜像、容器、卷及配置文件？[y/N]: " confirm_clean
    case "${confirm_clean}" in
        [yY][eE][sS]|[yY])
            DO_CLEAN_DATA=true
            ;;
        *)
            DO_CLEAN_DATA=false
            ;;
    esac
fi

if [ "${DO_CLEAN_DATA}" = "true" ]; then
    echo -e "${RED}正在清除所有 Docker 历史数据目录与配置...${PLAIN}"
    rm -rf /var/lib/docker
    rm -rf /var/lib/containerd
    rm -rf /etc/docker
    if [ -n "${CUSTOM_DOCKER_DIR}" ] && [ "${CUSTOM_DOCKER_DIR}" != "/" ]; then
        rm -rf "${CUSTOM_DOCKER_DIR}"
    fi
    rm -rf ~/.docker
    # 清理所有普通用户的 ~/.docker
    for u_home in /home/*; do
        if [ -d "${u_home}/.docker" ]; then
            rm -rf "${u_home}/.docker"
        fi
    done
    echo -e "${GREEN}数据目录与配置文件已完全清除。${PLAIN}"
else
    echo -e "${BLUE}已安全保留数据目录（/var/lib/docker${CUSTOM_DOCKER_DIR:+ 与 ${CUSTOM_DOCKER_DIR}}），重新安装后可无缝复用。${PLAIN}"
fi

# ====================== 验证结果 ======================
echo -e "\n${GREEN}====================================================${PLAIN}"
echo -e "${GREEN}🎉 Docker & Docker Compose 卸载完成！${PLAIN}"
if ! command -v docker >/dev/null 2>&1 && ! command -v docker-compose >/dev/null 2>&1; then
    echo -e "   - Docker 状态:         ${GREEN}已卸载${PLAIN}"
    echo -e "   - Docker Compose 状态: ${GREEN}已卸载${PLAIN}"
    echo -e "   - 服务守护进程:        ${GREEN}已停止并清理${PLAIN}"
else
    echo -e "   - ${YELLOW}提示：仍检测到 PATH 环境变量残留，建议重新打开终端会话。${PLAIN}"
fi
echo -e "${GREEN}====================================================${PLAIN}"
echo -e "${BLUE}若需重新安装 Docker 24.0.9，可随时执行:${PLAIN}"
echo -e "   ${YELLOW}sudo ./0-setup-docker.sh${PLAIN}"
