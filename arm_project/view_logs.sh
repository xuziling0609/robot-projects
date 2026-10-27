#!/usr/bin/env bash
# ==============================================================
# RM65-6F 机械臂三维视觉追踪避障控制系统 - 实时日志查看脚本
# ==============================================================

# 终端输出色彩定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

SERVICE_NAME="arm_project"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${PROJECT_ROOT}/logs"

# 默认参数
LINES=100
FOLLOW=true
MODE="auto" # auto | journal | file
ERROR_ONLY=false
RAW_OUTPUT=false

# 打印帮助信息
show_help() {
    echo -e "${CYAN}用法: $0 [选项]${NC}"
    echo -e "选项说明:"
    echo -e "  -n, --lines <N>   指定查看最近的 N 行日志 (默认: 100)"
    echo -e "  -f, --file        强制查看本地文件日志 (logs/arm_sys_*.log)"
    echo -e "  -j, --journal     强制查看 Systemd 服务 Journal 实时日志"
    echo -e "  -e, --error       仅过滤显示 ERROR 及以上严重级别的错误日志"
    echo -e "  -v, --verbose     显示系统级完整前缀 (时间戳、进程 PID)"
    echo -e "      --no-follow   查看完最近日志后立即退出，不持续追踪"
    echo -e "  -h, --help        显示本帮助信息"
    echo -e "\n示例:"
    echo -e "  $0                # 默认实时追踪最新日志 (按 Ctrl+C 退出)"
    echo -e "  $0 -n 50          # 显示最近 50 行并持续追踪"
    echo -e "  $0 -e             # 仅查看错误日志"
    echo -e "  $0 -f             # 强制追踪本地 logs/ 目录日志文件"
    exit 0
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        -n|--lines)
            LINES="$2"
            shift 2
            ;;
        -f|--file)
            MODE="file"
            shift
            ;;
        -j|--journal)
            MODE="journal"
            shift
            ;;
        -e|--error)
            ERROR_ONLY=true
            shift
            ;;
        -v|--verbose)
            RAW_OUTPUT=true
            shift
            ;;
        --no-follow)
            FOLLOW=false
            shift
            ;;
        -h|--help)
            show_help
            ;;
        *)
            echo -e "${RED}[未知参数]: $1${NC}"
            show_help
            ;;
    esac
done

echo -e "${CYAN}==============================================================${NC}"
echo -e "${CYAN}   睿尔曼 RM65-6F 机械臂视觉控制系统 - 实时日志监视器         ${NC}"
echo -e "${CYAN}==============================================================${NC}"
echo -e "${BLUE}提示: 按下 ${YELLOW}[ Ctrl + C ]${BLUE} 可随时退出日志监视。${NC}\n"

# 判断日志查看源
USE_JOURNAL=false
if [ "${MODE}" = "journal" ]; then
    USE_JOURNAL=true
elif [ "${MODE}" = "file" ]; then
    USE_JOURNAL=false
else
    # auto 模式：优先探测 systemd 服务是否已加载或处于运行中
    if systemctl is-active --quiet "${SERVICE_NAME}.service" 2>/dev/null; then
        USE_JOURNAL=true
    elif systemctl list-unit-files "${SERVICE_NAME}.service" 2>/dev/null | grep -q "${SERVICE_NAME}.service"; then
        USE_JOURNAL=true
    else
        USE_JOURNAL=false
    fi
fi

# 1. 采用 systemd journalctl 模式
if [ "${USE_JOURNAL}" = true ]; then
    echo -e "${BLUE}[模式] 来源: Systemd 服务 [${SERVICE_NAME}.service]${NC}"
    
    # 状态指示
    if systemctl is-active --quiet "${SERVICE_NAME}.service" 2>/dev/null; then
        echo -e "${GREEN}[状态] 服务正在运行中 (active)${NC}"
    else
        echo -e "${YELLOW}[状态] 服务当前未处于运行状态 (inactive/failed)${NC}"
        echo -e "${YELLOW}       正在输出最近产生的历史运行记录与崩溃排查日志...${NC}"
    fi

    JOURNAL_ARGS=("-u" "${SERVICE_NAME}" "-n" "${LINES}")
    
    # 是否持续跟随
    if [ "${FOLLOW}" = true ]; then
        JOURNAL_ARGS+=("-f")
    fi
    
    # 是否只看错误
    if [ "${ERROR_ONLY}" = true ]; then
        JOURNAL_ARGS+=("-p" "err..emerg")
    fi

    # 是否格式化输出 (保持 Loguru 原生色彩)
    if [ "${RAW_OUTPUT}" = false ]; then
        JOURNAL_ARGS+=("--output=cat")
    fi

    echo -e "${CYAN}------------------------- 日志流开始 -------------------------${NC}"
    exec journalctl "${JOURNAL_ARGS[@]}"

# 2. 采用 本地日志文件 模式
else
    # 查找 logs/ 目录下最新的 log 文件
    LATEST_LOG="$(ls -t "${LOG_DIR}"/arm_sys_*.log 2>/dev/null | head -n 1 || true)"

    if [ -n "${LATEST_LOG}" ] && [ -f "${LATEST_LOG}" ]; then
        echo -e "${BLUE}[模式] 来源: 本地日志文件 [${LATEST_LOG}]${NC}"
        echo -e "${CYAN}------------------------- 日志流开始 -------------------------${NC}"
        
        if [ "${ERROR_ONLY}" = true ]; then
            if [ "${FOLLOW}" = true ]; then
                exec tail -n "${LINES}" -f "${LATEST_LOG}" | grep --line-buffered -E "ERROR|CRITICAL"
            else
                exec tail -n "${LINES}" "${LATEST_LOG}" | grep -E "ERROR|CRITICAL"
            fi
        else
            if [ "${FOLLOW}" = true ]; then
                exec tail -n "${LINES}" -f "${LATEST_LOG}"
            else
                exec tail -n "${LINES}" "${LATEST_LOG}"
            fi
        fi
    else
        echo -e "${RED}[提示] 未检测到可用的运行日志！${NC}"
        echo -e "${YELLOW}  1. 系统服务尚未安装或启动: 可运行 './install_service.sh' 安装启动服务${NC}"
        echo -e "${YELLOW}  2. 本地尚未生成日志文件: 可通过 './run.sh' 手动启动系统${NC}"
        exit 1
    fi
fi
