#!/usr/bin/env bash
# ==============================================================================
# 边缘机器人智能网关 - systemd 系统服务卸载脚本 (uninstall_service.sh)
# 职责：
# 1. 停止运行中的 robot-gateway 服务进程；
# 2. 注销 systemd 开机自启软链并移除服务文件；
# 3. 清理 sudoers 免密自愈配置；
# 4. 重载守护进程，安全保留项目代码与数据文件。
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

# 1. 权限检测
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}❌ 卸载服务必须使用 root 权限执行！${NC}"
    echo -e "   请执行: ${YELLOW}sudo $0${NC}"
    exit 1
fi

echo -e "${CYAN}${BOLD}==============================================================${NC}"
echo -e "${CYAN}${BOLD} 🗑️ 边缘机器人智能网关 - systemd 服务卸载程序${NC}"
echo -e "${CYAN}${BOLD}==============================================================${NC}\n"

# 2. 检查并停止正在运行的服务
if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
    echo -e "${YELLOW}[1/4] 🛑 检测到服务正在运行，正在停止服务进程...${NC}"
    systemctl stop "${SERVICE_NAME}" || true
    echo -e "   ${GREEN}✅ 服务进程已平稳停止${NC}"
else
    echo -e "${YELLOW}[1/4] ℹ️ 服务当前未在运行${NC}"
fi

# 3. 禁用开机自启
echo -e "\n${YELLOW}[2/4] 🔌 注销 systemd 开机自启动...${NC}"
if systemctl is-enabled --quiet "${SERVICE_NAME}" 2>/dev/null; then
    systemctl disable "${SERVICE_NAME}" || true
    echo -e "   ${GREEN}✅ 已解除开机自启注册${NC}"
else
    echo -e "   ${YELLOW}ℹ️ 未注册开机自启或已禁用${NC}"
fi

# 4. 删除配置文件
echo -e "\n${YELLOW}[3/4] 🧹 清理系统服务单元与提权配置...${NC}"
if [ -f "${SERVICE_FILE}" ]; then
    rm -f "${SERVICE_FILE}"
    echo -e "   ${GREEN}✅ 已删除服务单元: ${SERVICE_FILE}${NC}"
fi

if [ -f "${SUDOERS_FILE}" ]; then
    rm -f "${SUDOERS_FILE}"
    echo -e "   ${GREEN}✅ 已清理提权白名单: ${SUDOERS_FILE}${NC}"
fi

# 5. 刷新 systemd 状态
echo -e "\n${YELLOW}[4/4] 🔄 刷新 systemd 状态缓存...${NC}"
systemctl daemon-reload
systemctl reset-failed "${SERVICE_NAME}" 2>/dev/null || systemctl reset-failed 2>/dev/null || true
echo -e "   ${GREEN}✅ systemd 状态已重置${NC}"

echo -e "\n${GREEN}${BOLD}==============================================================${NC}"
echo -e "${GREEN}${BOLD} 🎉 ${SERVICE_NAME} 系统服务已完全卸载！${NC}"
echo -e "${GREEN}${BOLD}==============================================================${NC}"
echo -e "🔒 安全提示："
echo -e "   项目源码、虚拟环境 (.venv/) 以及业务数据 (data/、logs/) 均已完整保留。"
INSTALL_HINT="sudo ./install_service.sh"
[ -f "${PROJECT_DIR}/2_install_service.sh" ] && INSTALL_HINT="sudo ./2_install_service.sh"
echo -e "   如需重新启用服务，可随时运行: ${CYAN}${INSTALL_HINT}${NC}\n"
