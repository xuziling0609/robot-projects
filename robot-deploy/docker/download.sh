#!/bin/bash
set -euo pipefail

# ==============================================================================
# Docker & Docker Compose 离线安装包一键下载脚本
# 基于 SeaweedFS Filer 8888 接口动态获取文件列表
# 步骤 1: 选择目标系统架构（默认检测本机架构）
# 步骤 2: 仅列出所选架构文件供用户交互式勾选下载
# 默认源地址: http://192.168.3.36:8888/docker/
# ==============================================================================

# 颜色配置
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;36m'
GRAY='\033[0;90m'
PLAIN='\033[0m'

# 定位脚本所在目录（默认为 docker 目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${SCRIPT_DIR}"

DEFAULT_BASE_URL="http://192.168.3.36:8888/docker"
BASE_URL="${DEFAULT_BASE_URL}"
FORCE_DOWNLOAD=false
SELECT_ALL=false
CLI_ARCH=""

# 恢复终端状态清理函数
cleanup_terminal() {
    printf "\033[?25h" 2>/dev/null || true
    if [ -t 0 ]; then
        stty echo icanon 2>/dev/null || true
    fi
}
trap cleanup_terminal EXIT INT TERM

show_help() {
    echo "使用方式: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -A, --arch <arch> 指定架构: x86_64(amd64) | aarch64(arm64) | all (跳过架构选择)"
    echo "  -a, --all         全选所选架构文件并下载（跳过勾选）"
    echo "  -f, --force       强制重新下载（覆盖已存在的完整文件）"
    echo "  -u, --url <url>   自定义 SeaweedFS Filer 接口基础路径 (默认: ${DEFAULT_BASE_URL})"
    echo "  -d, --dir <path>  指定下载保存目录 (默认: 脚本所在目录 ${SCRIPT_DIR})"
    echo "  -h, --help        显示帮助信息"
    echo ""
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        -A|--arch)
            CLI_ARCH="$2"
            shift 2
            ;;
        -a|--all)
            SELECT_ALL=true
            shift
            ;;
        -f|--force)
            FORCE_DOWNLOAD=true
            shift
            ;;
        -u|--url)
            BASE_URL="$2"
            shift 2
            ;;
        -d|--dir)
            TARGET_DIR="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}[错误] 未知参数: $1${PLAIN}"
            show_help
            exit 1
            ;;
    esac
done

BASE_URL="${BASE_URL%/}"
mkdir -p "${TARGET_DIR}"

echo "================================================================="
echo -e "${BLUE}    Docker & Docker Compose 离线安装包一键下载工具 (SeaweedFS)${PLAIN}"
echo "================================================================="
echo -e "接口地址 : ${BLUE}${BASE_URL}/${PLAIN}"
echo -e "保存目录 : ${BLUE}${TARGET_DIR}${PLAIN}"
echo -e "强制覆盖 : $([ "${FORCE_DOWNLOAD}" = true ] && echo -e "${YELLOW}是${PLAIN}" || echo "否 (支持断点续传/跳过完整文件)")"
echo "-----------------------------------------------------------------"

# 检测必要工具
DOWNLOAD_TOOL=""
if command -v curl >/dev/null 2>&1; then
    DOWNLOAD_TOOL="curl"
elif command -v wget >/dev/null 2>&1; then
    DOWNLOAD_TOOL="wget"
else
    echo -e "${RED}[错误] 系统中未找到 curl 或 wget 工具，请先安装！${PLAIN}"
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${RED}[错误] 系统中未找到 python3，用于解析 SeaweedFS Filer JSON 数据，请先安装！${PLAIN}"
    exit 1
fi

# 格式化字节为易读大小
format_size() {
    local bytes=$1
    if [ -z "$bytes" ] || ! [[ "$bytes" =~ ^[0-9]+$ ]]; then
        echo "未知"
        return
    fi
    if [ "$bytes" -ge 1073741824 ]; then
        awk -v b="$bytes" 'BEGIN {printf "%.2f GB", b/1073741824}'
    elif [ "$bytes" -ge 1048576 ]; then
        awk -v b="$bytes" 'BEGIN {printf "%.2f MB", b/1048576}'
    elif [ "$bytes" -ge 1024 ]; then
        awk -v b="$bytes" 'BEGIN {printf "%.2f KB", b/1024}'
    else
        echo "${bytes} B"
    fi
}

# ==============================================================================
# 第一步：选择系统架构（默认检测本机架构）
# ==============================================================================
ARCH_RAW=$(uname -m)
case "${ARCH_RAW}" in
    x86_64|amd64)
        DETECTED_ARCH="x86_64"
        DEFAULT_ARCH_CHOICE="1"
        ;;
    aarch64|arm64)
        DETECTED_ARCH="aarch64"
        DEFAULT_ARCH_CHOICE="2"
        ;;
    *)
        DETECTED_ARCH="x86_64"
        DEFAULT_ARCH_CHOICE="1"
        ;;
esac

CHOSEN_ARCH=""
if [ -n "${CLI_ARCH}" ]; then
    case "${CLI_ARCH}" in
        1|x86_64|amd64|x86)
            CHOSEN_ARCH="x86_64"
            ;;
        2|aarch64|arm64|arm)
            CHOSEN_ARCH="aarch64"
            ;;
        3|all|ALL|全部)
            CHOSEN_ARCH="all"
            ;;
        *)
            echo -e "${RED}[错误] 未知架构参数: ${CLI_ARCH} (支持: x86_64, aarch64, all)${PLAIN}"
            exit 1
            ;;
    esac
fi

if [ -z "${CHOSEN_ARCH}" ]; then
    if [ -t 0 ]; then
        echo -e "${BLUE}【步骤 1/2】请选择目标系统架构 (检测到本机架构: ${GREEN}${DETECTED_ARCH}${BLUE})${PLAIN}"
        echo "-----------------------------------------------------------------"
        echo "  1) x86_64  / amd64   (Intel / AMD 64位架构$([ "${DETECTED_ARCH}" = "x86_64" ] && echo -e " - ${GREEN}本机推荐/默认${PLAIN}"))"
        echo "  2) aarch64 / arm64   (ARM 64位架构 / 鲲鹏 / 麒麟$([ "${DETECTED_ARCH}" = "aarch64" ] && echo -e " - ${GREEN}本机推荐/默认${PLAIN}"))"
        echo "  3) 全部架构 (All)    (下载全部架构文件)"
        echo "-----------------------------------------------------------------"
        read -r -p "请输入架构编号 [1-3] (直接回车默认: ${DEFAULT_ARCH_CHOICE}): " arch_input
        case "${arch_input:-$DEFAULT_ARCH_CHOICE}" in
            1|x86_64|amd64)
                CHOSEN_ARCH="x86_64"
                ;;
            2|aarch64|arm64)
                CHOSEN_ARCH="aarch64"
                ;;
            3|all|ALL)
                CHOSEN_ARCH="all"
                ;;
            *)
                echo -e "⚠️ 输入无效，采用本机架构默认: ${DETECTED_ARCH}"
                CHOSEN_ARCH="${DETECTED_ARCH}"
                ;;
        esac
    else
        CHOSEN_ARCH="${DETECTED_ARCH}"
    fi
fi

echo -e "✅ 已选定架构: ${GREEN}${CHOSEN_ARCH}${PLAIN}"

# 架构匹配判断函数
matches_arch() {
    local fname="$1"
    local arch="$2"

    if [ "$arch" = "all" ]; then
        return 0
    fi
    if [ "$arch" = "x86_64" ]; then
        if [[ "$fname" == *x86_64* ]] || [[ "$fname" == *amd64* ]]; then
            return 0
        fi
        if [[ "$fname" != *aarch64* ]] && [[ "$fname" != *arm64* ]]; then
            return 0
        fi
        return 1
    elif [ "$arch" = "aarch64" ]; then
        if [[ "$fname" == *aarch64* ]] || [[ "$fname" == *arm64* ]]; then
            return 0
        fi
        if [[ "$fname" != *x86_64* ]] && [[ "$fname" != *amd64* ]]; then
            return 0
        fi
        return 1
    fi
    return 0
}

# ==============================================================================
# 从 SeaweedFS Filer 获取文件列表并按架构筛选
# ==============================================================================
echo ""
echo -e "正在通过 SeaweedFS Filer 8888 接口获取文件列表..."
API_URL="${BASE_URL}/?limit=1000"

FETCHED_DATA=$(python3 -c "
import urllib.request, json, sys, os

url = '${API_URL}'
req = urllib.request.Request(url, headers={'Accept': 'application/json'})
try:
    with urllib.request.urlopen(req, timeout=12) as resp:
        data = json.loads(resp.read().decode('utf-8'))
except Exception as e:
    sys.stderr.write(f'连接 SeaweedFS 接口失败: {e}\n')
    sys.exit(1)

entries = data.get('Entries', [])
results = []
for e in entries:
    path = e.get('FullPath', '')
    name = path.rstrip('/').split('/')[-1]
    size = e.get('FileSize', 0)
    mode = e.get('Mode', 0)
    # 过滤目录 (os.ModeDir 标志位 1<<31)
    if not (mode & 2147483648) and name:
        results.append(f'{name}\t{size}')

if not results:
    sys.stderr.write('未在远程目录找到任何可用文件！\n')
    sys.exit(2)

for r in results:
    print(r)
" 2>&1) || {
    echo -e "${RED}[错误] 获取文件列表失败:${PLAIN} ${FETCHED_DATA}"
    exit 1
}

declare -a FILE_NAMES=()
declare -a FILE_SIZES=()
declare -a FILE_FORMATTED_SIZES=()
declare -a LOCAL_STATUS=()
declare -a LOCAL_STATUS_COLORED=()
declare -a SELECTED=()

HAS_MISSING=false
INDEX=0

while IFS=$'\t' read -r fname fsize; do
    [ -n "$fname" ] || continue
    # 过滤只保留所选架构的文件
    if ! matches_arch "$fname" "$CHOSEN_ARCH"; then
        continue
    fi

    FILE_NAMES+=("$fname")
    FILE_SIZES+=("$fsize")
    FILE_FORMATTED_SIZES+=("$(format_size "$fsize")")

    local_path="${TARGET_DIR}/${fname}"
    if [ -f "$local_path" ]; then
        local_sz=$(stat -c%s "$local_path" 2>/dev/null || stat -f%z "$local_path" 2>/dev/null || echo 0)
        if [ "$local_sz" -eq "$fsize" ]; then
            LOCAL_STATUS+=("已完整")
            LOCAL_STATUS_COLORED+=("${GREEN}[已完整]${PLAIN}")
            SELECTED+=(false)
        elif [ "$local_sz" -lt "$fsize" ]; then
            LOCAL_STATUS+=("未完成")
            LOCAL_STATUS_COLORED+=("${YELLOW}[未完成,可续传]${PLAIN}")
            SELECTED+=(true)
            HAS_MISSING=true
        else
            LOCAL_STATUS+=("异常大小")
            LOCAL_STATUS_COLORED+=("${RED}[大小不一致]${PLAIN}")
            SELECTED+=(true)
            HAS_MISSING=true
        fi
    else
        LOCAL_STATUS+=("未下载")
        LOCAL_STATUS_COLORED+=("${GRAY}[未下载]${PLAIN}")
        SELECTED+=(true)
        HAS_MISSING=true
    fi
    INDEX=$((INDEX + 1))
done <<< "${FETCHED_DATA}"

TOTAL_COUNT=${#FILE_NAMES[@]}
if [ "${TOTAL_COUNT}" -eq 0 ]; then
    echo -e "${RED}[错误] 未在远程目录找到匹配架构 [${CHOSEN_ARCH}] 的文件。${PLAIN}"
    exit 1
fi

echo -e "✅ 成功匹配到 [${GREEN}${CHOSEN_ARCH}${PLAIN}] 架构文件共 ${GREEN}${TOTAL_COUNT}${PLAIN} 个"

# 若本地所有文件均已完整存在，且未指定全选，则默认全选便于用户回车重新校验/下载
if [ "${HAS_MISSING}" = false ]; then
    for ((i=0; i<TOTAL_COUNT; i++)); do
        SELECTED[i]=true
    done
fi

# ==============================================================================
# 第二步：列出所选架构的文件供用户勾选
# ==============================================================================
choose_by_numbers() {
    echo ""
    echo "================================================================="
    echo -e "${BLUE}【步骤 2/2】勾选需要下载的 [${CHOSEN_ARCH}] 离线文件${PLAIN}"
    echo "-----------------------------------------------------------------"
    for ((i=0; i<TOTAL_COUNT; i++)); do
        local mark="[ ]"
        [ "${SELECTED[i]}" = true ] && mark="[✔]"
        printf "  %s %2d. %-35s %10s %b\n" \
            "$mark" "$((i+1))" "${FILE_NAMES[i]}" "${FILE_FORMATTED_SIZES[i]}" "${LOCAL_STATUS_COLORED[i]}"
    done
    echo "================================================================="
    echo "输入提示: 输入编号以空格或逗号分隔 (例如: 1 2 或 1-2)，输入 'a' 全选，回车使用默认勾选，'q' 退出。"
    read -r -p "请选择要下载的文件序号: " user_input

    if [[ "$user_input" =~ ^[qQ]$ ]]; then
        echo "用户取消下载。"
        exit 0
    fi

    if [ -n "$user_input" ]; then
        if [[ "$user_input" =~ ^(a|all|ALL)$ ]]; then
            for ((i=0; i<TOTAL_COUNT; i++)); do SELECTED[i]=true; done
        else
            for ((i=0; i<TOTAL_COUNT; i++)); do SELECTED[i]=false; done
            local clean="${user_input//,/ }"
            for token in $clean; do
                if [[ "$token" =~ ^([0-9]+)-([0-9]+)$ ]]; then
                    local s="${BASH_REMATCH[1]}"
                    local e="${BASH_REMATCH[2]}"
                    [ "$s" -gt "$e" ] && { local tmp="$s"; s="$e"; e="$tmp"; }
                    for ((idx=s; idx<=e; idx++)); do
                        if [ "$idx" -ge 1 ] && [ "$idx" -le "$TOTAL_COUNT" ]; then
                            SELECTED[$((idx-1))]=true
                        fi
                    done
                elif [[ "$token" =~ ^[0-9]+$ ]]; then
                    if [ "$token" -ge 1 ] && [ "$token" -le "$TOTAL_COUNT" ]; then
                        SELECTED[$((token-1))]=true
                    fi
                fi
            done
        fi
    fi
}

choose_interactive_tui() {
    local cursor=0
    local term_lines
    term_lines=$(tput lines 2>/dev/null || echo 24)

    # 若终端可视高度不足以容纳列表，则退化至数字选择模式
    if [ "$term_lines" -lt "$((TOTAL_COUNT + 5))" ]; then
        choose_by_numbers
        return
    fi

    # 隐藏光标并启用单键原始读取
    printf "\033[?25l"
    stty -echo -icanon min 1 time 0 2>/dev/null || true

    local first_render=true
    local menu_lines=$((TOTAL_COUNT + 3))

    render_ui() {
        if [ "$first_render" = false ]; then
            printf "\033[%dA\r" "$menu_lines"
        fi
        first_render=false

        local sel_n=0
        for s in "${SELECTED[@]}"; do [ "$s" = true ] && sel_n=$((sel_n + 1)); done

        printf "\033[K%b\n" "${BLUE}【步骤 2/2】勾选需要下载的 [${CHOSEN_ARCH}] 离线文件${PLAIN}"
        printf "\033[K%b\n" "${GRAY}快捷键: [↑/↓] 移动 | [空格] 勾选/取消 | [a] 全选 | [i] 反选 | [回车] 确认 | [q] 退出${PLAIN}"

        for ((i=0; i<TOTAL_COUNT; i++)); do
            local ptr="   "
            [ "$i" -eq "$cursor" ] && ptr="${YELLOW} > ${PLAIN}"

            local chk="${PLAIN}[ ]"
            [ "${SELECTED[i]}" = true ] && chk="${GREEN}[✔]${PLAIN}"

            printf "\033[K%b%b %2d. %-35s %10s %b\n" \
                "$ptr" "$chk" "$((i+1))" "${FILE_NAMES[i]}" "${FILE_FORMATTED_SIZES[i]}" "${LOCAL_STATUS_COLORED[i]}"
        done

        printf "\033[K%b\n" "当前已勾选: ${GREEN}${sel_n}/${TOTAL_COUNT}${PLAIN} 个文件  |  按 ${GREEN}[回车]${PLAIN} 确认并开始下载"
    }

    echo ""
    render_ui

    while true; do
        local key=""
        IFS= read -rsn1 key 2>/dev/null || key=""
        if [[ "$key" == $'\x1b' ]]; then
            local rest=""
            read -rsn2 -t 0.05 rest 2>/dev/null || rest=""
            key+="$rest"
        fi

        case "$key" in
            $'\x1b[A'|$'\x1bOA'|k|K) # 上移
                cursor=$(( (cursor - 1 + TOTAL_COUNT) % TOTAL_COUNT ))
                render_ui
                ;;
            $'\x1b[B'|$'\x1bOB'|j|J) # 下移
                cursor=$(( (cursor + 1) % TOTAL_COUNT ))
                render_ui
                ;;
            " ") # 空格切换当前勾选
                if [ "${SELECTED[cursor]}" = true ]; then
                    SELECTED[cursor]=false
                else
                    SELECTED[cursor]=true
                fi
                render_ui
                ;;
            a|A) # 全选 / 全不选切换
                local all_on=true
                for s in "${SELECTED[@]}"; do
                    if [ "$s" = false ]; then all_on=false; break; fi
                done
                local target_state=$([ "$all_on" = true ] && echo false || echo true)
                for ((i=0; i<TOTAL_COUNT; i++)); do SELECTED[i]=$target_state; done
                render_ui
                ;;
            i|I) # 反选
                for ((i=0; i<TOTAL_COUNT; i++)); do
                    if [ "${SELECTED[i]}" = true ]; then
                        SELECTED[i]=false
                    else
                        SELECTED[i]=true
                    fi
                done
                render_ui
                ;;
            "") # 回车确认
                local count=0
                for s in "${SELECTED[@]}"; do [ "$s" = true ] && count=$((count + 1)); done
                if [ "$count" -eq 0 ]; then
                    continue
                fi
                break
                ;;
            q|Q) # 退出
                cleanup_terminal
                echo ""
                echo "用户取消下载。"
                exit 0
                ;;
            n|N) # 切换至编号输入模式
                cleanup_terminal
                choose_by_numbers
                return
                ;;
        esac
    done

    cleanup_terminal
    echo ""
}

# 判断运行环境决定勾选方式
if [ "${SELECT_ALL}" = true ]; then
    for ((i=0; i<TOTAL_COUNT; i++)); do SELECTED[i]=true; done
    echo -e "参数指定 ${BLUE}--all${PLAIN}，全选所选架构所有文件开始下载。"
elif [ -t 0 ]; then
    choose_interactive_tui
else
    choose_by_numbers
fi

# 统计用户最终选择项
declare -a DOWNLOAD_QUEUE=()
for ((i=0; i<TOTAL_COUNT; i++)); do
    if [ "${SELECTED[i]}" = true ]; then
        DOWNLOAD_QUEUE+=("$i")
    fi
done

QUEUE_LEN=${#DOWNLOAD_QUEUE[@]}
if [ "${QUEUE_LEN}" -eq 0 ]; then
    echo -e "${YELLOW}未勾选任何文件，退出。${PLAIN}"
    exit 0
fi

echo "================================================================="
echo -e "准备开始下载勾选的 ${GREEN}${QUEUE_LEN}${PLAIN} 个文件..."
echo "================================================================="
echo ""

SUCCESS_COUNT=0
SKIP_COUNT=0
FAIL_COUNT=0
declare -a FINAL_SUMMARY=()

CURRENT_IDX=1
for idx in "${DOWNLOAD_QUEUE[@]}"; do
    fname="${FILE_NAMES[idx]}"
    fsize="${FILE_SIZES[idx]}"
    fsize_str="${FILE_FORMATTED_SIZES[idx]}"
    file_url="${BASE_URL}/${fname}"
    dest_path="${TARGET_DIR}/${fname}"

    echo -e "${BLUE}[${CURRENT_IDX}/${QUEUE_LEN}] 正在处理: ${fname}${PLAIN} (${fsize_str})"

    # 检查本地是否已有且完整
    if [ "${FORCE_DOWNLOAD}" = false ] && [ -f "${dest_path}" ]; then
        cur_sz=$(stat -c%s "${dest_path}" 2>/dev/null || stat -f%z "${dest_path}" 2>/dev/null || echo 0)
        if [ "$cur_sz" -eq "$fsize" ]; then
            echo -e "  -> ${GREEN}本地文件已存在且大小完整，跳过下载。${PLAIN}"
            if [[ "${fname}" == docker-compose* ]]; then
                chmod +x "${dest_path}" 2>/dev/null || true
            fi
            SKIP_COUNT=$((SKIP_COUNT + 1))
            FINAL_SUMMARY+=("${fname}|已存在 (完整)|${fsize}")
            CURRENT_IDX=$((CURRENT_IDX + 1))
            echo ""
            continue
        fi
    fi

    # 执行下载
    echo -e "  -> 下载地址: ${file_url}"
    DOWNLOAD_OK=false

    if [ "${DOWNLOAD_TOOL}" = "curl" ]; then
        if [ "${FORCE_DOWNLOAD}" = true ]; then
            if curl -fL --progress-bar -o "${dest_path}" "${file_url}"; then
                DOWNLOAD_OK=true
            fi
        else
            # 断点续传模式
            if curl -fL -C - --progress-bar -o "${dest_path}" "${file_url}"; then
                DOWNLOAD_OK=true
            fi
        fi
    elif [ "${DOWNLOAD_TOOL}" = "wget" ]; then
        if [ "${FORCE_DOWNLOAD}" = true ]; then
            if wget --show-progress -q -O "${dest_path}" "${file_url}"; then
                DOWNLOAD_OK=true
            fi
        else
            # 断点续传模式
            if wget -c --show-progress -q -O "${dest_path}" "${file_url}"; then
                DOWNLOAD_OK=true
            fi
        fi
    fi

    if [ "${DOWNLOAD_OK}" = true ] && [ -f "${dest_path}" ]; then
        actual_sz=$(stat -c%s "${dest_path}" 2>/dev/null || stat -f%z "${dest_path}" 2>/dev/null || echo 0)
        if [ "$fsize" -gt 0 ] && [ "$actual_sz" -ne "$fsize" ]; then
            echo -e "  -> ${RED}[错误] 文件大小不一致！预期: ${fsize}, 实际: ${actual_sz}${PLAIN}"
            FAIL_COUNT=$((FAIL_COUNT + 1))
            FINAL_SUMMARY+=("${fname}|校验失败|${actual_sz}")
        else
            echo -e "  -> ${GREEN}[成功] 下载完成: $(format_size "${actual_sz}")${PLAIN}"
            if [[ "${fname}" == docker-compose* ]]; then
                chmod +x "${dest_path}" 2>/dev/null || true
            fi
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
            FINAL_SUMMARY+=("${fname}|下载成功|${actual_sz}")
        fi
    else
        echo -e "  -> ${RED}[失败] 下载未成功，请检查网络或 SeaweedFS Filer 服务是否可达！${PLAIN}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        FINAL_SUMMARY+=("${fname}|下载失败|0")
    fi

    CURRENT_IDX=$((CURRENT_IDX + 1))
    echo ""
done

# ==============================================================================
# 下载结果汇总
# ==============================================================================
echo "================================================================="
echo -e "${BLUE}                        下载结果汇总${PLAIN}"
echo "================================================================="
printf "%-35s %-16s %-12s\n" "文件名" "状态" "文件大小"
echo "-----------------------------------------------------------------"
for item in "${FINAL_SUMMARY[@]}"; do
    IFS="|" read -r item_name item_status item_size <<< "${item}"
    readable_sz=$(format_size "${item_size}")
    if [[ "${item_status}" == *"成功"* ]] || [[ "${item_status}" == *"已存在"* ]]; then
        printf "%-35s ${GREEN}%-14s${PLAIN} %-12s\n" "${item_name}" "${item_status}" "${readable_sz}"
    else
        printf "%-35s ${RED}%-14s${PLAIN} %-12s\n" "${item_name}" "${item_status}" "${readable_sz}"
    fi
done
echo "-----------------------------------------------------------------"
echo -e "统计: 本次勾选 ${QUEUE_LEN} 个文件, 新下载: ${GREEN}${SUCCESS_COUNT}${PLAIN}, 跳过已存在: ${BLUE}${SKIP_COUNT}${PLAIN}, 失败: ${RED}${FAIL_COUNT}${PLAIN}"

if [ "${FAIL_COUNT}" -gt 0 ]; then
    echo -e "${RED}[警告] 部分文件下载失败，可再次运行脚本重新勾选下载！${PLAIN}"
    exit 1
else
    echo -e "${GREEN}[完成] 所选文件均已就绪！${PLAIN}"
fi
