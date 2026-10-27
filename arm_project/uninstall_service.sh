#!/usr/bin/env bash
# ==============================================================
# RM65-6F 机械臂三维视觉追踪避障控制系统 - 系统服务卸载脚本
# ==============================================================
set -e

# 终端输出色彩定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

SERVICE_NAME="arm_project"
SYSTEMD_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

echo -e "${CYAN}==============================================================${NC}"
echo -e "${CYAN}   睿尔曼 RM65-6F 机械臂视觉控制系统 - 系统服务卸载向导       ${NC}"
echo -e "${CYAN}==============================================================${NC}"

# 1. 检查并请求 root / sudo 权限
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${YELLOW}[!] 卸载 systemd 系统服务需要管理员权限。${NC}"
    echo -e "${YELLOW}[!] 正在尝试使用 sudo 重新执行本脚本...${NC}"
    exec sudo bash "$0" "$@"
fi

# 2. 停止正在运行的服务
if systemctl is-active --quiet "${SERVICE_NAME}.service" 2>/dev/null; then
    echo -e "${BLUE}[1/4] 正在停止正在运行的 ${SERVICE_NAME}.service ...${NC}"
    systemctl stop "${SERVICE_NAME}.service"
    echo -e "${GREEN}[√] 服务已停止。${NC}"
else
    echo -e "${BLUE}[1/4] 服务当前未处于运行状态，跳过停止步骤。${NC}"
fi

# 3. 禁用开机自启
if systemctl is-enabled --quiet "${SERVICE_NAME}.service" 2>/dev/null; then
    echo -e "${BLUE}[2/4] 正在禁用开机自启...${NC}"
    systemctl disable "${SERVICE_NAME}.service"
    echo -e "${GREEN}[√] 开机自启已禁用。${NC}"
else
    echo -e "${BLUE}[2/4] 服务未配置开机自启，跳过禁用步骤。${NC}"
fi

# 4. 删除 service 配置文件
echo -e "${BLUE}[3/4] 正在移除 systemd 配置文件...${NC}"
if [ -f "${SYSTEMD_PATH}" ]; then
    rm -f "${SYSTEMD_PATH}"
    echo -e "${GREEN}[√] 配置文件已删除: ${SYSTEMD_PATH}${NC}"
else
    echo -e "${YELLOW}[*] 未发现配置文件 ${SYSTEMD_PATH}，跳过文件删除。${NC}"
fi

# 5. 重载 systemd 并重置状态
echo -e "${BLUE}[4/4] 正在重新加载 systemd 守护进程状态...${NC}"
systemctl daemon-reload
systemctl reset-failed "${SERVICE_NAME}.service" 2>/dev/null || true

echo -e "\n${CYAN}==============================================================${NC}"
echo -e "${GREEN}🎉 系统服务 [${SERVICE_NAME}.service] 已成功彻底卸载！${NC}"
echo -e "${BLUE}💡 说明: 项目本地源代码、配置及 logs/ 运行日志均完好保留。${NC}"
echo -e "${BLUE}   如需恢复服务，可随时运行 './install_service.sh' 重新安装。${NC}"
echo -e "${CYAN}==============================================================${NC}\n"
