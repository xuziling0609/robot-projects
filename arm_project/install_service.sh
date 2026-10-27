#!/usr/bin/env bash
# ==============================================================
# RM65-6F 机械臂三维视觉追踪避障控制系统 - 系统服务一键安装脚本
# ==============================================================
set -e

# 终端输出色彩定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 服务配置
SERVICE_NAME="arm_project"
SERVICE_DESC="RM65-6F 机械臂三维视觉追踪避障控制系统 (Arm Project)"
SYSTEMD_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

# 定位项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${CYAN}==============================================================${NC}"
echo -e "${CYAN}   睿尔曼 RM65-6F 机械臂视觉控制系统 - 系统服务安装向导       ${NC}"
echo -e "${CYAN}==============================================================${NC}"

# 1. 检查并请求 root / sudo 权限
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${YELLOW}[!] 安装 systemd 系统服务需要管理员权限。${NC}"
    echo -e "${YELLOW}[!] 正在尝试使用 sudo 重新执行本脚本...${NC}"
    exec sudo bash "$0" "$@"
fi

# 2. 识别实际登录用户与用户组 (防止以 root 权限运行造成普通用户权限混乱)
if [ -n "${SUDO_USER}" ]; then
    REAL_USER="${SUDO_USER}"
else
    REAL_USER="$(id -un)"
fi
REAL_GROUP="$(id -gn "${REAL_USER}")"
USER_HOME="$(getent passwd "${REAL_USER}" | cut -d: -f6)"

echo -e "${BLUE}[*] 项目运行根目录 :${NC} ${PROJECT_ROOT}"
echo -e "${BLUE}[*] 服务执行用户   :${NC} ${REAL_USER} (群组: ${REAL_GROUP})"
echo -e "${BLUE}[*] 目标服务名称   :${NC} ${SERVICE_NAME}.service"

# 3. 环境与关键文件检查
echo -e "\n${BLUE}[1/4] 正在检查项目执行环境...${NC}"

# 检查启动脚本
if [ ! -f "${PROJECT_ROOT}/run.sh" ]; then
    echo -e "${RED}[错误] 未在 ${PROJECT_ROOT} 找到 run.sh 启动脚本！${NC}"
    exit 1
fi
chmod +x "${PROJECT_ROOT}/run.sh"

# 检查主程序
if [ ! -f "${PROJECT_ROOT}/src/main.py" ]; then
    echo -e "${RED}[错误] 未在 ${PROJECT_ROOT}/src 找到 main.py 入口文件！${NC}"
    exit 1
fi

# 确保本地日志目录存在且所有者正确
mkdir -p "${PROJECT_ROOT}/logs"
chown -R "${REAL_USER}:${REAL_GROUP}" "${PROJECT_ROOT}/logs"

# 探测 Python 环境路径
CONDA_BIN_DIR="${USER_HOME}/miniforge3/envs/robot/bin"
BASE_CONDA_DIR="${USER_HOME}/miniforge3/bin"
SYSTEM_PATH_ENV="${CONDA_BIN_DIR}:${BASE_CONDA_DIR}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

echo -e "${GREEN}[√] 项目文件完整，执行权限配置就绪。${NC}"

# 4. 生成 systemd service 文件
echo -e "\n${BLUE}[2/4] 正在生成 Systemd 服务配置文件...${NC}"

cat <<EOF > "${SYSTEMD_PATH}"
[Unit]
Description=${SERVICE_DESC}
After=network.target network-online.target time-sync.target
Wants=network-online.target

[Service]
Type=simple
User=${REAL_USER}
Group=${REAL_GROUP}
WorkingDirectory=${PROJECT_ROOT}

# 环境变量设置
Environment="PYTHONUNBUFFERED=1"
Environment="PROJECT_ROOT=${PROJECT_ROOT}"
Environment="PATH=${SYSTEM_PATH_ENV}"
Environment="HOME=${USER_HOME}"

# 启动脚本
ExecStart=/bin/bash ${PROJECT_ROOT}/run.sh

# 进程异常重启策略
Restart=always
RestartSec=5s
StartLimitIntervalSec=60s
StartLimitBurst=5

# 优雅停机信号处理 (配合 Python signal/atexit 安全停止机械臂与相机)
KillMode=mixed
KillSignal=SIGINT
TimeoutStopSec=10s

# 系统日志输出
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

# 针对机器人控制设置较高进程优先级
Nice=-5

[Install]
WantedBy=multi-user.target
EOF

chmod 644 "${SYSTEMD_PATH}"
echo -e "${GREEN}[√] 服务文件已成功写入: ${SYSTEMD_PATH}${NC}"

# 5. 重新加载并设置开机自启
echo -e "\n${BLUE}[3/4] 正在配置系统服务并启用开机自启...${NC}"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"
echo -e "${GREEN}[√] 已成功设置开机自启: ${SERVICE_NAME}.service${NC}"

# 6. 启动或重启服务
echo -e "\n${BLUE}[4/4] 正在启动系统服务...${NC}"
systemctl restart "${SERVICE_NAME}.service"
sleep 2

# 7. 检查服务运行状态
echo -e "\n${CYAN}==============================================================${NC}"
if systemctl is-active --quiet "${SERVICE_NAME}.service"; then
    echo -e "${GREEN}🎉 系统服务安装并启动成功！当前运行状态: ACTIVE (RUNNING)${NC}"
else
    echo -e "${YELLOW}⚠️ 服务已安装，但当前状态可能未完全启动或处于自检阶段。${NC}"
    echo -e "${YELLOW}   请运行 './view_logs.sh' 或 'systemctl status ${SERVICE_NAME}' 排查硬件/网络连接。${NC}"
fi
echo -e "${CYAN}==============================================================${NC}"

# 打印常用运维命令清单
echo -e "\n${CYAN}常用服务管理命令清单：${NC}"
echo -e "  • ${GREEN}查看实时日志${NC} : ./view_logs.sh  或  journalctl -u ${SERVICE_NAME} -f"
echo -e "  • ${GREEN}查看运行状态${NC} : systemctl status ${SERVICE_NAME}"
echo -e "  • ${GREEN}启动服务${NC}     : sudo systemctl start ${SERVICE_NAME}"
echo -e "  • ${GREEN}停止服务${NC}     : sudo systemctl stop ${SERVICE_NAME}"
echo -e "  • ${GREEN}重启服务${NC}     : sudo systemctl restart ${SERVICE_NAME}"
echo -e "  • ${GREEN}卸载服务${NC}     : ./uninstall_service.sh"
echo -e "${CYAN}==============================================================${NC}\n"
