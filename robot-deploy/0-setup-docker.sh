#!/usr/bin/env bash
# ==============================================================================
# 智能机器人平台 - Docker & Docker Compose 自动化环境检测、离线安装与配置总控脚本
#
# 功能特性:
#   1. 架构自适应检测 (x86_64 / aarch64) 并自动寻址离线安装包
#   2. 本机 Docker 环境检查: 版本不匹配 (非 24.0.9) 自动卸载并重装
#   3. Docker 数据根目录 (data-root) 自动化迁移至 .env 指定的 DOCKER_DIR（带用户确认）
#   4. 自动配置普通用户免 sudo 运行 Docker 与 Docker Compose
#   5. 自动配置 Docker & Docker Compose 命令行自动补全 (Bash Completion)
#   6. 开机自启守护进程与健康检测就绪验证
# ==============================================================================

set -euo pipefail

# 终端输出颜色
RED="\033[31m"
GREEN="\033[32m"
YELLOW="\033[33m"
BLUE="\033[36m"
BOLD="\033[1m"
PLAIN="\033[0m"

# 目标环境版本
TARGET_DOCKER_VERSION="24.0.9"

# 必须以 root 权限执行
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}[错误] 请使用 sudo 或 root 用户运行此脚本！${PLAIN}"
    echo -e "${YELLOW}示例: sudo bash $0${PLAIN}"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 自动探测触发命令的实际普通用户（用于配置免 sudo 权限）
TARGET_USER="${SUDO_USER:-}"
if [ -z "${TARGET_USER}" ] || [ "${TARGET_USER}" = "root" ]; then
    TARGET_USER=$(logname 2>/dev/null || who am i 2>/dev/null | awk '{print $1}' || echo "")
fi
if [ -z "${TARGET_USER}" ] || [ "${TARGET_USER}" = "root" ]; then
    # 探测 UID >= 1000 的第一个常规登录用户（例如 zonwey）
    TARGET_USER=$(awk -F: '$3 >= 1000 && $3 < 60000 && $1 != "nobody" {print $1; exit}' /etc/passwd || echo "")
fi

# 参数解析：支持 -y / --yes 自动确认迁移，-f / --force 强制重装
FORCE_INSTALL=false
AUTO_YES=false
for arg in "$@"; do
    case "$arg" in
        -f|--force)
            FORCE_INSTALL=true
            ;;
        -y|--yes)
            AUTO_YES=true
            ;;
    esac
done

# 读取 .env 环境变量
if [ -f "${SCRIPT_DIR}/.env" ]; then
    # shellcheck disable=SC1091
    source "${SCRIPT_DIR}/.env"
elif [ -f ".env" ]; then
    # shellcheck disable=SC1091
    source .env
fi

TARGET_DOCKER_DIR="${DOCKER_DIR:-/home/docker}"
TARGET_DOCKER_DIR="${TARGET_DOCKER_DIR%/}"

echo -e "${BLUE}====================================================${PLAIN}"
echo -e "${BLUE}    Docker & Docker Compose 一键环境检测与配置套件    ${PLAIN}"
echo -e "${BLUE}====================================================${PLAIN}"
echo -e "配置数据目录 (DOCKER_DIR): ${GREEN}${TARGET_DOCKER_DIR}${PLAIN}"
if [ -n "${TARGET_USER}" ]; then
    echo -e "免 sudo 目标用户:          ${GREEN}${TARGET_USER}${PLAIN}"
fi

# ====================== 工具函数：写入/更新 daemon.json ======================
configure_daemon_json() {
    local data_root="$1"
    mkdir -p /etc/docker
    python3 -c "
import json, os
path = '/etc/docker/daemon.json'
os.makedirs('/etc/docker', exist_ok=True)
data = {}
if os.path.exists(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = {}
data['data-root'] = '${data_root}'
if 'log-driver' not in data:
    data['log-driver'] = 'json-file'
if 'log-opts' not in data:
    data['log-opts'] = {'max-size': '100m', 'max-file': '3'}
with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
"
}

# ====================== 工具函数：配置免 sudo 运行环境 ======================
setup_non_root_docker() {
    echo -e "\n${GREEN}>>> 配置普通用户免 sudo 运行 Docker / Docker Compose...${PLAIN}"
    # 1. 确保 docker 用户组存在
    groupadd -f docker

    # 2. 将非 root 用户加入 docker 组
    if [ -n "${TARGET_USER}" ] && [ "${TARGET_USER}" != "root" ] && id "${TARGET_USER}" >/dev/null 2>&1; then
        usermod -aG docker "${TARGET_USER}"
        echo -e "      已将用户 [${GREEN}${TARGET_USER}${PLAIN}] 添加至 ${BLUE}docker${PLAIN} 用户组。"
    else
        echo -e "      ${YELLOW}[提示] 未探测到常规普通用户，若需指定用户免 sudo，可手动执行: sudo usermod -aG docker <用户名>${PLAIN}"
    fi

    # 3. 确保套接字权限正常（赋权 666，确保当前会话无需重新登录即可直接运行）
    if [ -S /var/run/docker.sock ]; then
        chown root:docker /var/run/docker.sock 2>/dev/null || true
        chmod 666 /var/run/docker.sock 2>/dev/null || true
    fi
}

# ====================== 工具函数：配置命令行自动补全 ======================
setup_bash_completion() {
    echo -e "\n${GREEN}>>> 配置 Docker & Docker Compose 命令行自动补全...${PLAIN}"
    mkdir -p /etc/bash_completion.d

    # 1. 确保系统支持 bash-completion 工具包
    if ! dpkg -s bash-completion >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
        apt-get update -qq && apt-get install -y -qq bash-completion 2>/dev/null || true
    elif ! rpm -q bash-completion >/dev/null 2>&1 && command -v yum >/dev/null 2>&1; then
        yum install -y -q bash-completion 2>/dev/null || true
    fi

    # 2. 生成官方 Docker 原生补全脚本 (全面支持 docker 和 docker compose 及其子命令)
    if command -v docker >/dev/null 2>&1; then
        docker completion bash > /etc/bash_completion.d/docker 2>/dev/null || true
    fi

    # 3. 为独立命令 docker-compose 注册补全支持 (复用 Docker Cobra 补全解析器)
    cat << 'EOF' > /etc/bash_completion.d/docker-compose
if ! declare -F __start_docker >/dev/null 2>&1; then
    [ -f /etc/bash_completion.d/docker ] && . /etc/bash_completion.d/docker
fi
if declare -F __start_docker >/dev/null 2>&1; then
    complete -o default -F __start_docker docker-compose
fi
EOF

    chmod 644 /etc/bash_completion.d/docker /etc/bash_completion.d/docker-compose 2>/dev/null || true
    echo -e "      ${GREEN}✅ 命令行自动补全规则已就绪 (/etc/bash_completion.d/)${PLAIN}"
}

# ====================== 工具函数：确认迁移提示 ======================
confirm_migration_prompt() {
    local from_dir="$1"
    local to_dir="$2"

    if [ "${AUTO_YES}" = "true" ]; then
        echo -e "      ${BLUE}[自动确认] 已启用自动应答模式，开始迁移...${PLAIN}"
        return 0
    fi

    echo -e "\n${YELLOW}----------------------------------------------------${PLAIN}"
    echo -e "${BOLD}❓ 检测到 Docker 数据存储目录需要发生变更：${PLAIN}"
    echo -e "   - 原数据目录: ${BLUE}${from_dir}${PLAIN}"
    echo -e "   - 目标新目录: ${GREEN}${to_dir}${PLAIN}"
    echo -e "说明: 迁移过程将停止 Docker 服务，完整同步现有镜像/容器/卷，"
    echo -e "      备份原目录并创建兼容软链接，以确保数据零丢失。"
    echo -e "${YELLOW}----------------------------------------------------${PLAIN}"
    read -r -p "是否确认执行数据目录迁移？[Y/n]: " choice
    case "${choice}" in
        [nN][oO]|[nN])
            return 1
            ;;
        *)
            return 0
            ;;
    esac
}

# ====================== 工具函数：迁移现有数据目录 ======================
migrate_data_directory() {
    local source_dir="$1"
    local dest_dir="$2"
    source_dir="${source_dir%/}"
    dest_dir="${dest_dir%/}"

    if [ "${source_dir}" = "${dest_dir}" ]; then
        return 0
    fi

    echo -e "      创建目标数据目录: ${dest_dir}..."
    mkdir -p "${dest_dir}"
    chmod 711 "${dest_dir}"

    if [ -d "${source_dir}" ] && [ ! -L "${source_dir}" ] && [ "$(ls -A "${source_dir}" 2>/dev/null)" ]; then
        echo -e "      正在同步历史数据: ${source_dir} -> ${dest_dir} (请稍候)..."
        if command -v rsync >/dev/null 2>&1; then
            rsync -aHAX --info=progress2 "${source_dir}/" "${dest_dir}/"
        else
            cp -a "${source_dir}"/. "${dest_dir}/"
        fi
        local backup_path="${source_dir}.bak_$(date +%Y%m%d%H%M%S)"
        echo -e "      备份原目录为: ${backup_path} 并建立软链接..."
        mv "${source_dir}" "${backup_path}"
        ln -sf "${dest_dir}" "${source_dir}"
        echo -e "      ${BLUE}[提示] 原目录已安全备份至 ${backup_path}${PLAIN}"
    elif [ ! -e "${source_dir}" ]; then
        mkdir -p "$(dirname "${source_dir}")"
        ln -sf "${dest_dir}" "${source_dir}"
    fi
}

# ====================== 工具函数：检查已有 Docker 是否存在业务数据 ======================
check_existing_docker_data() {
    local has_data=false
    local c_count=0
    local i_count=0
    local v_count=0
    local disk_size="0B"
    local check_root="${CURRENT_DOCKER_ROOT:-/var/lib/docker}"
    [ -z "${check_root}" ] && check_root="/var/lib/docker"

    # 1. 如果 Docker Daemon 正在运行，优先通过 CLI 获取准确数据
    if docker info >/dev/null 2>&1; then
        c_count=$(docker ps -a -q 2>/dev/null | wc -l || echo 0)
        i_count=$(docker images -q 2>/dev/null | sort -u | wc -l || echo 0)
        v_count=$(docker volume ls -q 2>/dev/null | wc -l || echo 0)
        if [ "${c_count}" -gt 0 ] || [ "${i_count}" -gt 0 ] || [ "${v_count}" -gt 0 ]; then
            has_data=true
        fi
    fi

    # 2. 从文件系统直接检查（适应 Daemon 无法启动或版本损坏的情况）
    for dir in "${check_root}" "/var/lib/docker" "${TARGET_DOCKER_DIR}"; do
        if [ -d "${dir}" ] && [ ! -L "${dir}" ]; then
            local c_dirs=0
            if [ -d "${dir}/containers" ]; then
                c_dirs=$(find "${dir}/containers" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l || echo 0)
            fi
            local o_dirs=0
            if [ -d "${dir}/overlay2" ]; then
                o_dirs=$(find "${dir}/overlay2" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l || echo 0)
            fi
            local v_dirs=0
            if [ -d "${dir}/volumes" ]; then
                v_dirs=$(find "${dir}/volumes" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l || echo 0)
            fi

            if [ "${c_dirs}" -gt 0 ] || [ "${o_dirs}" -gt 1 ] || [ "${v_dirs}" -gt 1 ]; then
                has_data=true
                [ "${c_count}" -eq 0 ] && c_count="${c_dirs}"
                [ "${v_count}" -eq 0 ] && v_count="${v_dirs}"
            fi

            disk_size=$(du -sh "${dir}" 2>/dev/null | awk '{print $1}' || echo "0B")
            check_root="${dir}"
            break
        fi
    done

    echo "${has_data}|${c_count}|${i_count}|${v_count}|${disk_size}|${check_root}"
}

# ====================== 1. 架构检测与安装包寻址 ======================
ARCH_RAW=$(uname -m)
case "${ARCH_RAW}" in
    x86_64|amd64)
        PKG_ARCH="x86_64"
        ;;
    aarch64|arm64)
        PKG_ARCH="aarch64"
        ;;
    *)
        echo -e "${RED}[错误] 不支持的硬件架构: ${ARCH_RAW}，仅支持 x86_64 与 aarch64！${PLAIN}"
        exit 1
        ;;
esac

echo -e "\n${GREEN}[1/4] 当前宿主机硬件架构: ${PKG_ARCH}${PLAIN}"

DOCKER_PKG_DIR=""
for candidate in \
    "${SCRIPT_DIR}/docker" \
    "${SCRIPT_DIR}" \
    "/home/deploy/docker" \
    "/home/zonwey/robot/deploy/docker"
do
    if [ -f "${candidate}/docker-${TARGET_DOCKER_VERSION}-${PKG_ARCH}.tgz" ] && \
       [ -f "${candidate}/docker-compose-linux-${PKG_ARCH}" ]; then
        DOCKER_PKG_DIR="${candidate}"
        break
    fi
done

if [ -z "${DOCKER_PKG_DIR}" ]; then
    echo -e "${RED}[错误] 未在以下路径找到离线安装包:${PLAIN}"
    echo "  - docker-${TARGET_DOCKER_VERSION}-${PKG_ARCH}.tgz"
    echo "  - docker-compose-linux-${PKG_ARCH}"
    echo -e "${YELLOW}请确认 deploy/docker/ 目录下已存在相应架构安装文件！${PLAIN}"
    echo -e "${BLUE}提示: 您可以执行 'bash docker/download.sh' 一键下载离线安装包。${PLAIN}"
    exit 1
fi

DOCKER_TGZ="${DOCKER_PKG_DIR}/docker-${TARGET_DOCKER_VERSION}-${PKG_ARCH}.tgz"
COMPOSE_BIN="${DOCKER_PKG_DIR}/docker-compose-linux-${PKG_ARCH}"

echo -e "      离线包定位成功: ${BLUE}${DOCKER_PKG_DIR}${PLAIN}"

# ====================== 2. 检测本机 Docker 及 Compose 版本 ======================
echo -e "\n${GREEN}[2/4] 正在检测本机 Docker 及 Compose 环境...${PLAIN}"

CURRENT_DOCKER_VER=""
CURRENT_DOCKER_ROOT=""
if command -v docker >/dev/null 2>&1; then
    CURRENT_DOCKER_VER=$(docker version --format '{{.Server.Version}}' 2>/dev/null || true)
    if [ -z "${CURRENT_DOCKER_VER}" ]; then
        CURRENT_DOCKER_VER=$(docker version --format '{{.Client.Version}}' 2>/dev/null || true)
    fi
    if [ -z "${CURRENT_DOCKER_VER}" ]; then
        CURRENT_DOCKER_VER=$(docker -v 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -n 1 || true)
    fi
    CURRENT_DOCKER_ROOT=$(docker info -f '{{.DockerRootDir}}' 2>/dev/null || echo "")
    CURRENT_DOCKER_ROOT="${CURRENT_DOCKER_ROOT%/}"
fi

COMPOSE_AVAILABLE=false
CURRENT_COMPOSE_VER=""
if docker compose version >/dev/null 2>&1; then
    COMPOSE_AVAILABLE=true
    CURRENT_COMPOSE_VER=$(docker compose version 2>/dev/null | head -n 1)
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_AVAILABLE=true
    CURRENT_COMPOSE_VER=$(docker-compose --version 2>/dev/null | head -n 1)
fi

DAEMON_RUNNING=false
if systemctl is-active docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    DAEMON_RUNNING=true
fi

NEED_UNINSTALL=false
NEED_INSTALL=false

if [ -z "${CURRENT_DOCKER_VER}" ]; then
    echo -e "      本机状态: ${YELLOW}未安装 Docker${PLAIN}"
    NEED_INSTALL=true
elif [ "${CURRENT_DOCKER_VER}" != "${TARGET_DOCKER_VERSION}" ]; then
    echo -e "      本机状态: 已安装 Docker (${RED}${CURRENT_DOCKER_VER}${PLAIN})，与目标版本 (${GREEN}${TARGET_DOCKER_VERSION}${PLAIN}) ${RED}不匹配！${PLAIN}"
    NEED_UNINSTALL=true
    NEED_INSTALL=true
else
    echo -e "      本机 Docker 版本: ${GREEN}${CURRENT_DOCKER_VER} (匹配目标版本)${PLAIN}"
    echo -e "      当前数据根目录:   ${YELLOW}${CURRENT_DOCKER_ROOT:-/var/lib/docker}${PLAIN}"

    if [ "${COMPOSE_AVAILABLE}" != "true" ] || [ "${DAEMON_RUNNING}" != "true" ] || [ "${FORCE_INSTALL}" = "true" ]; then
        if [ "${FORCE_INSTALL}" = "true" ]; then
            echo -e "      已指定 --force 参数，强制重新安装环境..."
        else
            echo -e "      ${YELLOW}Docker 服务未正常运行或 Docker Compose 缺失，需重新配置...${PLAIN}"
        fi
        NEED_UNINSTALL=true
        NEED_INSTALL=true
    else
        # 版本匹配且正常运行，检查数据目录是否需要迁移
        if [ -n "${TARGET_DOCKER_DIR}" ] && [ -n "${CURRENT_DOCKER_ROOT}" ] && [ "${CURRENT_DOCKER_ROOT}" != "${TARGET_DOCKER_DIR}" ]; then
            if confirm_migration_prompt "${CURRENT_DOCKER_ROOT}" "${TARGET_DOCKER_DIR}"; then
                echo -e ">>> 停止 Docker 服务并迁移数据..."
                systemctl stop docker.socket docker containerd 2>/dev/null || true
                migrate_data_directory "${CURRENT_DOCKER_ROOT}" "${TARGET_DOCKER_DIR}"
                configure_daemon_json "${TARGET_DOCKER_DIR}"
                systemctl daemon-reload
                systemctl restart docker
                NEW_ROOT=$(docker info -f '{{.DockerRootDir}}' 2>/dev/null || echo "${TARGET_DOCKER_DIR}")
                echo -e "      ${GREEN}✅ 数据目录已成功迁移至: ${NEW_ROOT}${PLAIN}"
            else
                echo -e "      ${YELLOW}[已跳过] 保持使用现有数据目录: ${CURRENT_DOCKER_ROOT}${PLAIN}"
            fi
        fi

        # 配置免 sudo 与命令行自动补全
        setup_non_root_docker
        setup_bash_completion

        echo -e "\n${GREEN}====================================================${PLAIN}"
        echo -e "${GREEN}✅ 本机 Docker (${TARGET_DOCKER_VERSION}) 环境与免 sudo 权限已就绪！${PLAIN}"
        echo -e "   - Docker 版本:         ${GREEN}${CURRENT_DOCKER_VER}${PLAIN}"
        echo -e "   - Docker Compose:      ${GREEN}${CURRENT_COMPOSE_VER}${PLAIN}"
        echo -e "   - 数据存储根目录:     ${GREEN}$(docker info -f '{{.DockerRootDir}}' 2>/dev/null || echo "${TARGET_DOCKER_DIR}")${PLAIN}"
        if [ -n "${TARGET_USER}" ]; then
            echo -e "   - 免 sudo 授权用户:    ${GREEN}${TARGET_USER}${PLAIN}"
        fi
        echo -e "====================================================${PLAIN}"
        if [ -n "${TARGET_USER}" ] && [ "${TARGET_USER}" != "root" ]; then
            echo -e "${YELLOW}💡 提示: 若当前终端未生效免 sudo，可执行: ${BOLD}newgrp docker${PLAIN} ${YELLOW}或重新连接 SSH 终端生效。${PLAIN}"
        fi
        echo -e "${YELLOW}💡 提示: 若当前终端未生效命令补全，可执行: ${BOLD}source /etc/bash_completion.d/docker && source /etc/bash_completion.d/docker-compose${PLAIN}${PLAIN}"
        exit 0
    fi
fi

# ====================== 3. 版本不匹配：执行卸载与清理 ======================
if [ "${NEED_UNINSTALL}" = "true" ]; then
    echo -e "\n${YELLOW}[3/4] 检测到环境需重新部署，正在检查已有 Docker 数据状态...${PLAIN}"

    # 检测旧环境中是否存在业务数据
    IFS='|' read -r HAS_DATA C_COUNT I_COUNT V_COUNT D_SIZE D_PATH <<< "$(check_existing_docker_data)"

    if [ "${HAS_DATA}" = "true" ]; then
        echo -e "\n${RED}==================== ⚠️  重要确认：检测到旧版 Docker 存在业务数据 ====================${PLAIN}"
        echo -e "   - 存储检测目录: ${BLUE}${D_PATH}${PLAIN} (磁盘占用: ${YELLOW}${D_SIZE}${PLAIN})"
        if [ "${C_COUNT}" -gt 0 ]; then
            echo -e "   - 容器总数:     ${YELLOW}${C_COUNT}${PLAIN} 个"
        fi
        if [ "${I_COUNT}" -gt 0 ]; then
            echo -e "   - 镜像总数:     ${YELLOW}${I_COUNT}${PLAIN} 个"
        fi
        if [ "${V_COUNT}" -gt 0 ]; then
            echo -e "   - 数据卷数:     ${YELLOW}${V_COUNT}${PLAIN} 个"
        fi
        echo -e "   - 当前运行版本: ${RED}${CURRENT_DOCKER_VER:-未知}${PLAIN} (目标需求版本: ${GREEN}${TARGET_DOCKER_VERSION}${PLAIN})"
        echo -e "${YELLOW}说明: 继续操作将停止现有 Docker 容器服务，并卸载旧版本软件包及可执行程序。"
        echo -e "      原有数据目录将安全保留，但在完成新版本安装启动前相关容器将暂时离线。${PLAIN}"
        echo -e "${RED}========================================================================================${PLAIN}"

        if [ "${AUTO_YES}" = "true" ]; then
            echo -e "      ${BLUE}[自动确认] 已启用 -y / --yes 参数，确认卸载并继续...${PLAIN}"
        else
            read -r -p "是否确认卸载当前 Docker 环境并替换为 24.0.9？请输入 yes 确认 [yes/N]: " confirm_uninstall
            case "${confirm_uninstall}" in
                [yY][eE][sS]|[yY])
                    echo -e "      ${GREEN}用户已确认，开始执行卸载流程...${PLAIN}"
                    ;;
                *)
                    echo -e "\n${RED}❌ 用户已取消卸载操作，安装流程安全终止。${PLAIN}"
                    echo -e "${YELLOW}提示: 当前旧版 Docker 环境保持原样未做改动。${PLAIN}"
                    exit 0
                    ;;
            esac
        fi
    else
        echo -e "      未检测到已有容器/镜像业务数据，可安全执行卸载与替换。"
    fi

    # 1. 停止相关服务
    echo -e "      停止 Docker 与 Containerd 服务..."
    systemctl stop docker.socket docker containerd 2>/dev/null || true
    systemctl disable docker.socket docker containerd 2>/dev/null || true

    # 2. 清理系统包管理器残留包
    if command -v apt-get >/dev/null 2>&1; then
        echo -e "      清理 apt 软件包..."
        DOCKER_APT_PKGS=(
            docker docker-engine docker.io docker-doc docker-compose docker-compose-v2
            docker-compose-plugin docker-ce docker-ce-cli docker-ce-rootless-extras
            docker-buildx-plugin containerd containerd.io runc podman-docker
        )
        apt-get purge -y "${DOCKER_APT_PKGS[@]}" 2>/dev/null || true
        apt-get autoremove -y --purge 2>/dev/null || true
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

    # 3. 清理旧二进制程序
    echo -e "      清理旧二进制文件..."
    rm -f /usr/bin/docker /usr/bin/dockerd /usr/bin/docker-init /usr/bin/docker-proxy
    rm -f /usr/bin/containerd /usr/bin/containerd-shim* /usr/bin/ctr /usr/bin/runc
    rm -f /usr/local/bin/docker /usr/local/bin/dockerd /usr/local/bin/docker-init /usr/local/bin/docker-proxy
    rm -f /usr/local/bin/containerd /usr/local/bin/containerd-shim* /usr/local/bin/ctr /usr/local/bin/runc
    rm -f /usr/bin/docker-compose /usr/local/bin/docker-compose
    rm -rf /usr/local/lib/docker/cli-plugins /usr/libexec/docker/cli-plugins

    # 4. 清理旧 systemd 服务配置
    rm -f /etc/systemd/system/docker.service* /etc/systemd/system/containerd.service*
    systemctl daemon-reload 2>/dev/null || true

    echo -e "      ${BLUE}[提示] 默认保留已有镜像与卷数据，避免数据丢失。${PLAIN}"
    echo -e "      ${GREEN}旧版本卸载清理完成！${PLAIN}"
else
    echo -e "\n${GREEN}[3/4] 本机无旧版本需卸载，直接进入安装流程...${PLAIN}"
fi

# ====================== 4. 安装目标 Docker 24.0.9 与 Docker Compose ======================
echo -e "\n${GREEN}[4/4] 正在从离线包安装 Docker ${TARGET_DOCKER_VERSION} 及 Docker Compose...${PLAIN}"

# 1. 解压并部署 Docker 核心二进制文件
echo -e "      解压 ${DOCKER_TGZ} 到 /usr/bin/ ..."
TMP_EXTRACT_DIR=$(mktemp -d /tmp/docker-install.XXXXXX)
tar -xzf "${DOCKER_TGZ}" -C "${TMP_EXTRACT_DIR}"

cp -f "${TMP_EXTRACT_DIR}"/docker/* /usr/bin/
chmod +x /usr/bin/docker* /usr/bin/containerd* /usr/bin/ctr /usr/bin/runc
rm -rf "${TMP_EXTRACT_DIR}"

# 2. 部署 Docker Compose 二进制与 CLI 插件
echo -e "      部署 Docker Compose (${PKG_ARCH})..."
cp -f "${COMPOSE_BIN}" /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose

mkdir -p /usr/local/lib/docker/cli-plugins /usr/libexec/docker/cli-plugins
ln -sf /usr/local/bin/docker-compose /usr/local/lib/docker/cli-plugins/docker-compose
ln -sf /usr/local/bin/docker-compose /usr/libexec/docker/cli-plugins/docker-compose

# 3. 准备数据存储目录与历史数据迁移（带确认）
FINAL_USE_DIR="${TARGET_DOCKER_DIR}"
if [ -d "/var/lib/docker" ] && [ ! -L "/var/lib/docker" ] && [ "$(ls -A /var/lib/docker 2>/dev/null)" ] && [ "${TARGET_DOCKER_DIR}" != "/var/lib/docker" ]; then
    if confirm_migration_prompt "/var/lib/docker" "${TARGET_DOCKER_DIR}"; then
        migrate_data_directory "/var/lib/docker" "${TARGET_DOCKER_DIR}"
        FINAL_USE_DIR="${TARGET_DOCKER_DIR}"
    else
        echo -e "      ${YELLOW}[已跳过] 用户取消迁移，使用默认 /var/lib/docker${PLAIN}"
        FINAL_USE_DIR="/var/lib/docker"
    fi
else
    mkdir -p "${TARGET_DOCKER_DIR}"
    chmod 711 "${TARGET_DOCKER_DIR}"
    if [ ! -e "/var/lib/docker" ]; then
        mkdir -p /var/lib
        ln -sf "${TARGET_DOCKER_DIR}" /var/lib/docker
    fi
fi

# 写入 daemon.json
configure_daemon_json "${FINAL_USE_DIR}"

# 4. 创建标准 systemd 服务配置文件（配置 -G docker 确保组权限）
echo -e "      注册 systemd 守护服务 (/etc/systemd/system/docker.service)..."
cat > /etc/systemd/system/docker.service << 'EOF'
[Unit]
Description=Docker Application Container Engine
Documentation=https://docs.docker.com
After=network-online.target firewalld.service
Wants=network-online.target

[Service]
Type=notify
ExecStart=/usr/bin/dockerd -G docker
ExecStartPost=-/usr/bin/chmod 666 /var/run/docker.sock
ExecReload=/bin/kill -s HUP $MAINPID
TimeoutSec=0
RestartSec=2
Restart=always
LimitNOFILE=infinity
LimitNPROC=infinity
LimitCORE=infinity
TasksMax=infinity
Delegate=yes
KillMode=process
OOMScoreAdjust=-500

[Install]
WantedBy=multi-user.target
EOF

# 5. 确保 docker 用户组存在并重载启动
groupadd -f docker
systemctl daemon-reload
systemctl enable docker >/dev/null 2>&1 || true
echo -e "      启动 Docker 服务..."
systemctl restart docker

# 6. 等待就绪检测
echo -e "      等待 Docker 服务就绪检测..."
READY=false
for i in {1..15}; do
    if docker info >/dev/null 2>&1; then
        READY=true
        break
    fi
    sleep 1
done

if [ "${READY}" != "true" ]; then
    echo -e "${RED}[警告] Docker 服务启动超时，请检查 systemctl status docker 输出！${PLAIN}"
    exit 1
fi

# 7. 配置普通用户免 sudo
setup_non_root_docker

# 8. 配置命令行自动补全
setup_bash_completion

# ====================== 5. 安装结果最终验证 ======================
FINAL_DOCKER_VER=$(docker --version 2>/dev/null || echo "获取失败")
FINAL_COMPOSE_VER=$(docker compose version 2>/dev/null || docker-compose --version 2>/dev/null || echo "获取失败")
FINAL_ROOT=$(docker info -f '{{.DockerRootDir}}' 2>/dev/null || echo "${FINAL_USE_DIR}")

echo -e "\n${GREEN}====================================================${PLAIN}"
echo -e "${GREEN}🎉 Docker & Docker Compose 安装配置完成！${PLAIN}"
echo -e "   - Docker 版本:         ${GREEN}${FINAL_DOCKER_VER}${PLAIN}"
echo -e "   - Docker Compose 版本: ${GREEN}${FINAL_COMPOSE_VER}${PLAIN}"
echo -e "   - 数据存储根目录:     ${GREEN}${FINAL_ROOT}${PLAIN}"
if [ -n "${TARGET_USER}" ]; then
    echo -e "   - 免 sudo 授权用户:    ${GREEN}${TARGET_USER}${PLAIN}"
fi
echo -e "   - 服务状态:            ${GREEN}active (running)${PLAIN}"
echo -e "${GREEN}====================================================${PLAIN}"
if [ -n "${TARGET_USER}" ] && [ "${TARGET_USER}" != "root" ]; then
    echo -e "${YELLOW}💡 提示: 若当前终端未生效免 sudo，可执行: ${BOLD}newgrp docker${PLAIN} ${YELLOW}或重新连接 SSH 终端生效。${PLAIN}"
fi
echo -e "${YELLOW}💡 提示: 若当前终端未生效命令补全，可执行: ${BOLD}source /etc/bash_completion.d/docker && source /etc/bash_completion.d/docker-compose${PLAIN}${PLAIN}"
echo -e "\n${BLUE}接下来可直接运行后续部署步骤:${PLAIN}"
echo -e "   1. ${YELLOW}./2-chmod.sh${PLAIN}     (数据目录赋权)"
echo -e "   2. ${YELLOW}./1-check-env.sh${PLAIN} (环境与端口检测)"
echo -e "   3. ${YELLOW}./3-deploy.sh${PLAIN}    (自动化一键部署)"
