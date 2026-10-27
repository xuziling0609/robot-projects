#!/usr/bin/env bash
# ==============================================================================
# 边缘机器人智能网关 - systemd 系统自启服务安装脚本 (install_service.sh)
# 职责：
# 1. 自动定位工程目录与非 root 真实运行用户 (防数据/日志权限污染)；
# 2. 检查 .venv 虚拟环境，缺失时自动引导/拉起 setup_env.sh 初始化；
# 3. 配置 sudoers 免密规则，保障 SystemPlugin 远程自愈重启能力；
# 4. 生成 /etc/systemd/system/robot-gateway.service 并注册开机自启；
# 5. 立即启动服务并展示运行状态。
# ==============================================================================

set -e

# 彩色控制台高亮
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

SERVICE_NAME="robot-gateway"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
SUDOERS_FILE="/etc/sudoers.d/${SERVICE_NAME}"

# --- [新增] 前置网络检测配置 ---
# 请将此 IP 修改为您需要等待联通的目标 IP（如上级工控机、网关或核心路由器）
TARGET_PING_IP="192.168.123.178"
# 等待超时上限（秒），防止目标 IP 持续不通导致服务启动无限阻塞卡死
PING_TIMEOUT_SEC=300

# 1. 权限检测
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}❌ 安装服务必须使用 root 权限执行！${NC}"
    echo -e "   请执行: ${YELLOW}sudo $0${NC}"
    exit 1
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${PROJECT_DIR}"

echo -e "${CYAN}${BOLD}==============================================================${NC}"
echo -e "${CYAN}${BOLD} 📦 边缘机器人智能网关 - systemd 守护服务安装程序${NC}"
echo -e "${CYAN}${BOLD}==============================================================${NC}"
echo -e "📁 项目安装路径: ${BLUE}${PROJECT_DIR}${NC}"
echo -e "🌐 前置检测目标: ${BLUE}${TARGET_PING_IP} (超时上限: ${PING_TIMEOUT_SEC}s)${NC}"

# 2. 自动检测真实运行用户 (优先采用 sudo 前的用户，防 root 污染数据目录)
if [ -n "${SUDO_USER}" ] && [ "${SUDO_USER}" != "root" ]; then
    RUN_USER="${SUDO_USER}"
else
    # 若直接以 root 登录运行，尝试查找项目目录属主
    RUN_USER=$(stat -c '%U' "${PROJECT_DIR}" 2>/dev/null || echo "root")
fi
RUN_GROUP=$(id -gn "${RUN_USER}" 2>/dev/null || echo "root")

echo -e "👤 服务运行属主: ${GREEN}${RUN_USER}:${RUN_GROUP}${NC}\n"

# 3. 检查虚拟环境与解释器
VENV_PYTHON="${PROJECT_DIR}/.venv/bin/python"
if [ ! -f "${VENV_PYTHON}" ]; then
    echo -e "${YELLOW}⚠️ 未检测到虚拟环境 (${VENV_PYTHON})！${NC}"
    SETUP_SCRIPT=""
    if [ -f "${PROJECT_DIR}/1_setup_env.sh" ]; then
        SETUP_SCRIPT="${PROJECT_DIR}/1_setup_env.sh"
    elif [ -f "${PROJECT_DIR}/setup_env.sh" ]; then
        SETUP_SCRIPT="${PROJECT_DIR}/setup_env.sh"
    fi

    if [ -n "${SETUP_SCRIPT}" ]; then
        SCRIPT_NAME=$(basename "${SETUP_SCRIPT}")
        echo -e "   正在以用户 ${GREEN}${RUN_USER}${NC} 自动拉起 ${CYAN}./${SCRIPT_NAME}${NC} 完成前置依赖安装..."
        chmod +x "${SETUP_SCRIPT}"
        su - "${RUN_USER}" -c "cd '${PROJECT_DIR}' && ./${SCRIPT_NAME}"
    else
        echo -e "${RED}❌ 未找到 1_setup_env.sh，请先在工程根目录执行 pdm install 初始化环境！${NC}"
        exit 1
    fi
fi

if [ ! -f "${VENV_PYTHON}" ]; then
    echo -e "${RED}❌ 虚拟环境初始化失败，未找到 ${VENV_PYTHON}。${NC}"
    exit 1
fi

# 确保 main.py 存在
if [ ! -f "${PROJECT_DIR}/main.py" ]; then
    echo -e "${RED}❌ 未找到入口程序 ${PROJECT_DIR}/main.py！${NC}"
    exit 1
fi

# 确保工程目录属主正确
chown -R "${RUN_USER}:${RUN_GROUP}" "${PROJECT_DIR}/data" "${PROJECT_DIR}/logs" 2>/dev/null || true

# 4. 配置 sudoers 免密规则 (供 SystemPlugin 自愈重启网关与整机)
echo -e "${YELLOW}[1/4] 🔐 配置 sudoers 免密自愈白名单...${NC}"

SYSTEMCTL_BIN=$(which systemctl || echo "/bin/systemctl")
REBOOT_BIN=$(which reboot || echo "/sbin/reboot")

# 构建精细化的免密白名单，仅允许重启/状态查询本服务和系统重启
cat > "${SUDOERS_FILE}" <<EOF
# 边缘机器人智能网关服务免密自愈授权 (由 install_service.sh 自动生成)
${RUN_USER} ALL=(ALL) NOPASSWD: ${SYSTEMCTL_BIN} restart ${SERVICE_NAME}, ${SYSTEMCTL_BIN} status ${SERVICE_NAME}, ${SYSTEMCTL_BIN} is-active ${SERVICE_NAME}, ${SYSTEMCTL_BIN} start ${SERVICE_NAME}, ${SYSTEMCTL_BIN} stop ${SERVICE_NAME}, ${REBOOT_BIN}, /usr/sbin/reboot, /sbin/reboot
EOF

chmod 0440 "${SUDOERS_FILE}"
# 校验 sudoers 语法安全性
if command -v visudo >/dev/null 2>&1; then
    if ! visudo -c -f "${SUDOERS_FILE}" >/dev/null 2>&1; then
        echo -e "${RED}❌ sudoers 语法校验失败，正在回滚...${NC}"
        rm -f "${SUDOERS_FILE}"
        exit 1
    fi
fi
echo -e "   ${GREEN}✅ 提权白名单已写入: ${SUDOERS_FILE}${NC}"

# 5. 生成 systemd service 文件
echo -e "\n${YELLOW}[2/4] 📝 生成 systemd 服务配置文件...${NC}"
cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=Robot Edge Gateway Service (边缘机器人智能网关核心中枢)
After=network.target network-online.target time-sync.target mosquitto.service
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_GROUP}
WorkingDirectory=${PROJECT_DIR}
# --- 前置网络检测：循环 ping 指定 IP 直到成功，单次超时 1 秒，间隔 2 秒 ---
ExecStartPre=/bin/bash -c 'until /bin/ping -c 1 -W 1 ${TARGET_PING_IP} >/dev/null 2>&1; do echo "Waiting for network target ${TARGET_PING_IP}..."; sleep 2; done'
# 启动超时保护：若超过指定时间仍无法 ping 通则判定启动失败，交给 Restart 策略重试
TimeoutStartSec=${PING_TIMEOUT_SEC}
ExecStart=${VENV_PYTHON} ${PROJECT_DIR}/main.py
Restart=always
RestartSec=3s
TimeoutStopSec=10s
KillSignal=SIGTERM
KillMode=mixed

# 环境变量与控制台重定向
Environment=PYTHONUNBUFFERED=1
Environment=LANG=zh_CN.UTF-8
Environment=LC_ALL=zh_CN.UTF-8
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

# 文件描述符限制
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF

chmod 0644 "${SERVICE_FILE}"
echo -e "   ${GREEN}✅ 服务单元已写入: ${SERVICE_FILE}${NC}"

# 6. 重载并注册自启
echo -e "\n${YELLOW}[3/4] 🔄 重载 systemd 并配置开机自启...${NC}"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"
echo -e "   ${GREEN}✅ 开机自启服务已启用 (${SERVICE_NAME}.service)${NC}"

# 7. 启动服务与状态校验
echo -e "\n${YELLOW}[4/4] 🚀 正在启动服务并校验运行状态...${NC}"
systemctl restart "${SERVICE_NAME}.service"
sleep 2

if systemctl is-active --quiet "${SERVICE_NAME}.service"; then
    echo -e "   ${GREEN}🎉 服务已成功启动并进入运行状态 (active)!${NC}\n"
else
    echo -e "   ${RED}⚠️ 服务启动可能遇到异常，请查看日志！${NC}\n"
fi

echo -e "${CYAN}${BOLD}==============================================================${NC}"
echo -e "${GREEN}${BOLD} ✨ ${SERVICE_NAME} 系统服务安装部署完成！${NC}"
echo -e "${CYAN}${BOLD}==============================================================${NC}"
echo -e "常用服务管理运维命令："
echo -e "  查看服务实时状态: ${CYAN}systemctl status ${SERVICE_NAME}${NC}"
echo -e "  查看实时动态日志: ${CYAN}journalctl -u ${SERVICE_NAME} -f -n 50${NC}"
echo -e "  重启网关服务进程: ${CYAN}sudo systemctl restart ${SERVICE_NAME}${NC}"
echo -e "  停止网关服务进程: ${CYAN}sudo systemctl stop ${SERVICE_NAME}${NC}"
UNINSTALL_HINT="sudo ./uninstall_service.sh"
[ -f "${PROJECT_DIR}/3_uninstall_service.sh" ] && UNINSTALL_HINT="sudo ./3_uninstall_service.sh"
echo -e "  一键卸载系统服务: ${CYAN}${UNINSTALL_HINT}${NC}\n"
