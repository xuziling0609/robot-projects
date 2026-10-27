#!/usr/bin/env bash
# ==============================================================================
# 通用串口管理工具 (增强重构版)
# 支持: 增量固化 / 取消固化(单项&全部) / 多端口芯片适配 / 免root配置 / 拔插监听 / 状态诊断
# 兼容: Ubuntu 20.04 / 22.04 / 24.04 及 WSL2 (usbipd) / 嵌入式 Linux
# ==============================================================================

# 注意：不盲目使用 set -e，改用针对性退出与错误处理，保证交互式脚本稳定性
set -u

# 终端色彩定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

RULES_FILE="/etc/udev/rules.d/99-serial-devices.rules"
LINK_DIR="/dev/sensors"

# 1. 权限检查
if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo -e "${RED}[错误] 请使用 sudo 执行此脚本：sudo bash $0${NC}"
    exit 1
fi

# 获取执行 sudo 的实际普通用户名
REAL_USER="${SUDO_USER:-$USER}"

# 检查并在必要时启动 systemd-udevd (特别针对 WSL2 或精简容器环境)
ensure_udevd_running() {
    if command -v systemctl &>/dev/null && systemctl is-system-running &>/dev/null; then
        if ! systemctl is-active --quiet systemd-udevd 2>/dev/null; then
            echo -e "${YELLOW}[提示] 检测到 systemd-udevd 守护进程未运行，正在尝试启动...${NC}"
            systemctl start systemd-udevd 2>/dev/null || true
            sleep 1
        fi
    fi
}

# 屏蔽 brltty 冲突服务
disable_brltty_if_needed() {
    if command -v systemctl &>/dev/null; then
        if systemctl is-active --quiet brltty 2>/dev/null || systemctl is-enabled --quiet brltty 2>/dev/null; then
            echo -e "${YELLOW}[系统提示] 检测到 brltty 服务正在运行（可能抢占 CH340/FTDI 等串口设备）。${NC}"
            read -rp "是否立即禁用并停止 brltty 服务？(推荐 y) [y/N]: " DISABLE_BRLTTY
            if [[ "$DISABLE_BRLTTY" =~ ^[Yy]$ ]]; then
                systemctl stop brltty-udev.service brltty.service 2>/dev/null || true
                systemctl mask brltty-udev.service brltty.service 2>/dev/null || true
                echo -e "${GREEN}[OK] 已屏蔽 brltty 服务。${NC}\n"
            fi
        fi
    fi
}

# 扫描系统中现有的物理串口设备
scan_serial_devices() {
    find /dev -maxdepth 1 \( \
        -name "ttyUSB*" -o \
        -name "ttyACM*" -o \
        -name "ttyCH343USB*" -o \
        -name "ttyCH9344USB*" \
    \) 2>/dev/null | sort
}

# 触发并刷新 udev 规则
reload_udev() {
    ensure_udevd_running
    udevadm control --reload-rules 2>/dev/null || true
    udevadm trigger --subsystem-match=tty 2>/dev/null || true
    udevadm trigger --action=change 2>/dev/null || true
}

# ------------------------------------------------------------------------------
# 功能 1: 查看当前设备与映射状态
# ------------------------------------------------------------------------------
do_show_status() {
    echo -e "\n${CYAN}=========================== 串口设备与映射状态 ===========================${NC}"

    # 1. 软链接固化状态
    echo -e "${BOLD}【1. 已生效的 /dev/sensors/ 软链接】${NC}"
    if [ -d "$LINK_DIR" ] && [ -n "$(ls -A "$LINK_DIR" 2>/dev/null)" ]; then
        for link in "$LINK_DIR"/*; do
            [ -e "$link" ] || [ -L "$link" ] || continue
            alias_name=$(basename "$link")
            if [ -e "$link" ]; then
                real_target=$(readlink -f "$link")
                echo -e "  [在线] ${GREEN}$link${NC} -> ${BOLD}$real_target${NC}"
            else
                echo -e "  [离线] ${RED}$link${NC} -> (目标设备未插入)"
            fi
        done
    else
        echo -e "  ${YELLOW}暂无任何 /dev/sensors/ 软链接生效。${NC}"
    fi

    # 2. 当前在线的物理串口
    echo -e "\n${BOLD}【2. 当前系统检测到的物理串口】${NC}"
    mapfile -t DEV_LIST < <(scan_serial_devices)

    if [ ${#DEV_LIST[@]} -eq 0 ]; then
        echo -e "  ${YELLOW}当前无物理串口在线 (请检查硬件连接或 WSL usbipd 挂载)。${NC}"
    else
        printf "  %-14s %-20s %-12s %-10s %-12s %-8s\n" "设备节点" "硬件型号" "VID:PID" "devpath" "序列号" "权限"
        echo "  --------------------------------------------------------------------------------"
        for dev in "${DEV_LIST[@]}"; do
            id_vendor=$(udevadm info -q property -n "$dev" 2>/dev/null | grep -E "^ID_VENDOR_ID=" | cut -d'=' -f2 || true)
            id_product=$(udevadm info -q property -n "$dev" 2>/dev/null | grep -E "^ID_MODEL_ID=" | cut -d'=' -f2 || true)
            serial_num=$(udevadm info -q property -n "$dev" 2>/dev/null | grep -E "^ID_SERIAL_SHORT=" | cut -d'=' -f2 || true)
            devpath=$(udevadm info --name="$dev" --attribute-walk 2>/dev/null | grep -m1 'ATTRS{devpath}' | cut -d'"' -f2 || true)
            prod_name=$(udevadm info --query=property --name="$dev" 2>/dev/null | grep -E "^ID_MODEL_FROM_DATABASE=|^ID_MODEL=" | head -n1 | cut -d'=' -f2 || echo "通用串口")
            perm=$(stat -c "%a %G" "$dev" 2>/dev/null || echo "未知")

            printf "  ${GREEN}%-14s${NC} %-20.20s %-12s %-10s %-12.12s %-8s\n" \
                "$dev" "${prod_name:-通用串口}" "${id_vendor:-????}:${id_product:-????}" "${devpath:--}" "${serial_num:-(无)}" "$perm"
        done
    fi

    # 3. rules 文件中的规则数
    echo -e "\n${BOLD}【3. udev 规则文件配置】${NC}"
    if [ -f "$RULES_FILE" ]; then
        rule_count=$(grep -c 'SYMLINK+="sensors/' "$RULES_FILE" 2>/dev/null || echo "0")
        echo -e "  规则文件: ${CYAN}$RULES_FILE${NC} (共配置 $rule_count 条固化规则)"
    else
        echo -e "  规则文件: ${YELLOW}未创建 ($RULES_FILE)${NC}"
    fi
    echo -e "${CYAN}==========================================================================${NC}\n"
}

# ------------------------------------------------------------------------------
# 功能 2: 固化串口 (增量添加/覆盖)
# ------------------------------------------------------------------------------
do_bind_serial() {
    disable_brltty_if_needed
    ensure_udevd_running

    mapfile -t DEV_LIST < <(scan_serial_devices)

    if [ ${#DEV_LIST[@]} -eq 0 ]; then
        echo -e "${RED}[错误] 未检测到任何串口设备！${NC}"
        echo "请检查硬件接线或 Windows usbipd 挂载状态。"
        return
    fi

    # 确保规则文件所在目录及文件存在
    mkdir -p "/etc/udev/rules.d"
    touch "$RULES_FILE"

    echo -e "${BLUE}检测到以下串口设备，请为需要固化的设备输入别名:${NC}"
    echo -e "${YELLOW}说明: 规则支持【增量维护】，不会冲掉以往配置的其他设备。${NC}"
    echo -e "${YELLOW}提示: 别名只允许英文字母、数字、下划线及短横线；直接回车将跳过该设备。${NC}\n"

    declare -a ADDED_ALIASES=()

    for dev in "${DEV_LIST[@]}"; do
        devname=$(basename "$dev")
        k_prefix=$(echo "$devname" | sed 's/[0-9]*//g')

        # 硬件与接口信息精准提取 (使用内置属性，杜绝跨级误抓父总线控制器)
        id_vendor=$(udevadm info -q property -n "$dev" 2>/dev/null | grep -E "^ID_VENDOR_ID=" | cut -d'=' -f2 || true)
        id_product=$(udevadm info -q property -n "$dev" 2>/dev/null | grep -E "^ID_MODEL_ID=" | cut -d'=' -f2 || true)
        serial_num=$(udevadm info -q property -n "$dev" 2>/dev/null | grep -E "^ID_SERIAL_SHORT=" | cut -d'=' -f2 || true)
        interface_num=$(udevadm info -q property -n "$dev" 2>/dev/null | grep -E "^ID_USB_INTERFACE_NUM=" | cut -d'=' -f2 || true)
        dev_path=$(udevadm info --name="$dev" --attribute-walk 2>/dev/null | grep -m1 'ATTRS{devpath}' | cut -d'"' -f2 || true)
        prod_name=$(udevadm info --query=property --name="$dev" 2>/dev/null | grep -E "^ID_MODEL_FROM_DATABASE=|^ID_MODEL=" | head -n1 | cut -d'=' -f2 || echo "通用串口")

        # fallback 兜底
        [ -z "$id_vendor" ] && id_vendor=$(udevadm info -a -n "$dev" 2>/dev/null | grep -m1 '{idVendor}' | awk -F'==' '{print $2}' | tr -d '" ' || true)
        [ -z "$id_product" ] && id_product=$(udevadm info -a -n "$dev" 2>/dev/null | grep -m1 '{idProduct}' | awk -F'==' '{print $2}' | tr -d '" ' || true)

        # 序列号过滤：排除全0、纯空白以及虚拟驱动误报
        if [ "$serial_num" = "0" ] || [ "$serial_num" = "00000000" ] || [[ "$serial_num" =~ vhci_hcd ]]; then
            serial_num=""
        fi

        echo -e "${CYAN}----------------------------------------------------------------${NC}"
        echo -e "当前设备: ${BOLD}$dev${NC} (${prod_name} [${id_vendor}:${id_product}])"
        echo -e "物理插槽 devpath: ${BOLD}${dev_path:-未知}${NC} | 硬件序列号: ${BOLD}${serial_num:-(无独立SN)}${NC} | 接口编号: ${BOLD}${interface_num:-00}${NC}"

        while true; do
            read -rp "请输入固化别名 (生成至 /dev/sensors/ 下，回车跳过): " ALIAS_NAME
            if [ -z "$ALIAS_NAME" ]; then
                echo -e "${YELLOW}已跳过该设备。${NC}"
                break
            fi

            # 校验别名合法性
            if [[ ! "$ALIAS_NAME" =~ ^[a-zA-Z0-9_-]+$ ]]; then
                echo -e "${RED}[错误] 别名不合法！仅支持英文字母、数字、下划线(_)和短横线(-)，请重新输入：${NC}"
                continue
            fi
            break
        done

        [ -z "$ALIAS_NAME" ] && continue

        # 生成规则字符串 (严格保证同一条规则中的 ATTRS 处于同一父设备层，多接口采用 ENV 隔离匹配)
        RULE_STR=""
        if [ -n "$serial_num" ]; then
            echo -e "绑定策略: 【硬件序列号绑定】(支持插到任意 USB 物理口)"
            if [ -n "$interface_num" ]; then
                # 多端口芯片(如 FT4232H/CH344): ATTRS在设备层，ENV在当前节点，完全符合 udev 匹配规范
                RULE_STR="KERNEL==\"${k_prefix}*\", ATTRS{idVendor}==\"$id_vendor\", ATTRS{idProduct}==\"$id_product\", ATTRS{serial}==\"$serial_num\", ENV{ID_USB_INTERFACE_NUM}==\"$interface_num\", MODE:=\"0777\", GROUP:=\"dialout\", SYMLINK+=\"sensors/$ALIAS_NAME\""
            else
                RULE_STR="KERNEL==\"${k_prefix}*\", ATTRS{idVendor}==\"$id_vendor\", ATTRS{idProduct}==\"$id_product\", ATTRS{serial}==\"$serial_num\", MODE:=\"0777\", GROUP:=\"dialout\", SYMLINK+=\"sensors/$ALIAS_NAME\""
            fi
        else
            echo -e "绑定策略: 【物理插槽 devpath 绑定】(无独立SN芯片，devpath与VID/PID全同层，固定插孔生效)"
            if [ -n "$interface_num" ]; then
                RULE_STR="KERNEL==\"${k_prefix}*\", ATTRS{idVendor}==\"$id_vendor\", ATTRS{idProduct}==\"$id_product\", ATTRS{devpath}==\"$dev_path\", ENV{ID_USB_INTERFACE_NUM}==\"$interface_num\", MODE:=\"0777\", GROUP:=\"dialout\", SYMLINK+=\"sensors/$ALIAS_NAME\""
            else
                RULE_STR="KERNEL==\"${k_prefix}*\", ATTRS{idVendor}==\"$id_vendor\", ATTRS{idProduct}==\"$id_product\", ATTRS{devpath}==\"$dev_path\", MODE:=\"0777\", GROUP:=\"dialout\", SYMLINK+=\"sensors/$ALIAS_NAME\""
            fi
        fi

        # 增量更新：如果已存在相同别名的旧规则，先移除旧行
        if grep -q "SYMLINK+=\"sensors/$ALIAS_NAME\"" "$RULES_FILE" 2>/dev/null; then
            sed -i "/SYMLINK+=\"sensors\/$ALIAS_NAME\"/d" "$RULES_FILE"
            echo -e "${YELLOW}[更新] 已覆盖原有的别名 [$ALIAS_NAME] 规则。${NC}"
        fi

        # 写入新规则
        echo "$RULE_STR" >> "$RULES_FILE"
        ADDED_ALIASES+=("$ALIAS_NAME")
        echo -e "${GREEN}✓ 计划映射: $dev -> /dev/sensors/$ALIAS_NAME${NC}"
    done

    if [ ${#ADDED_ALIASES[@]} -eq 0 ]; then
        echo -e "\n${YELLOW}[提示] 本次未新增任何有效别名。${NC}"
        return
    fi

    echo -e "\n${GREEN}[OK] 规则已增量写入: $RULES_FILE${NC}"
    echo "正在重新加载 udev 规则..."
    reload_udev
    sleep 1

    # 显示结果
    echo -e "\n${CYAN}=========================== 生效检查 ===========================${NC}"
    for alias_item in "${ADDED_ALIASES[@]}"; do
        target_link="/dev/sensors/$alias_item"
        if [ -e "$target_link" ]; then
            real_node=$(readlink -f "$target_link")
            echo -e "  [成功] ${GREEN}/dev/sensors/$alias_item${NC} -> ${BOLD}$real_node${NC}"
        else
            echo -e "  [待刷新] ${RED}/dev/sensors/$alias_item${NC} (未立即生成软链接，请尝试重新插拔该硬件)"
        fi
    done
    echo -e "${CYAN}================================================================${NC}"
}

# ------------------------------------------------------------------------------
# 功能 3: 取消固化 / 管理已有规则
# ------------------------------------------------------------------------------
do_unbind_serial() {
    if [ ! -f "$RULES_FILE" ] || [ ! -s "$RULES_FILE" ]; then
        echo -e "${YELLOW}[提示] 未发现规则文件或文件为空 ($RULES_FILE)${NC}"
        return
    fi

    echo -e "\n${CYAN}=== 当前已配置的固化规则 ===${NC}"
    mapfile -t RULE_LINES < <(grep 'SYMLINK+="sensors/' "$RULES_FILE" || true)

    if [ ${#RULE_LINES[@]} -eq 0 ]; then
        echo -e "${YELLOW}规则文件中没有包含 /dev/sensors/ 的配置条目。${NC}"
        return
    fi

    declare -a ALIAS_LIST=()
    local idx=1
    for r in "${RULE_LINES[@]}"; do
        al=$(echo "$r" | sed -n 's/.*SYMLINK+="sensors\/\([^"]*\)".*/\1/p')
        ALIAS_LIST+=("$al")
        link_target="/dev/sensors/$al"
        status_str="${RED}离线${NC}"
        if [ -e "$link_target" ]; then
            status_str="${GREEN}在线 -> $(readlink -f "$link_target")${NC}"
        fi
        echo -e "  [$idx] 别名: ${BOLD}$al${NC} ($status_str)"
        ((idx++))
    done

    echo -e "  [A] 清空全部规则并删除 /dev/sensors 目录"
    echo -e "  [0] 返回上级菜单"
    echo -e "${CYAN}================================${NC}"

    read -rp "请选择要删除的规则序号 [1-${#ALIAS_LIST[@]} / A / 0]: " UNBIND_CHOICE

    if [ "$UNBIND_CHOICE" = "0" ] || [ -z "$UNBIND_CHOICE" ]; then
        return
    elif [ "$UNBIND_CHOICE" = "A" ] || [ "$UNBIND_CHOICE" = "a" ]; then
        read -rp "确定要清空全部固化规则吗？[y/N]: " CONFIRM_ALL
        if [[ "$CONFIRM_ALL" =~ ^[Yy]$ ]]; then
            rm -f "$RULES_FILE"
            rm -rf "$LINK_DIR"
            reload_udev
            echo -e "${GREEN}[OK] 已清空全部固化规则并清理软链接目录。${NC}"
        fi
    elif [[ "$UNBIND_CHOICE" =~ ^[0-9]+$ ]] && [ "$UNBIND_CHOICE" -ge 1 ] && [ "$UNBIND_CHOICE" -le "${#ALIAS_LIST[@]}" ]; then
        target_alias="${ALIAS_LIST[$((UNBIND_CHOICE-1))]}"
        # 删除特定行
        sed -i "/SYMLINK+=\"sensors\/$target_alias\"/d" "$RULES_FILE"
        rm -f "/dev/sensors/$target_alias"
        reload_udev
        echo -e "${GREEN}[OK] 已成功移除别名 [$target_alias] 的规则及软链接。${NC}"
    else
        echo -e "${RED}[错误] 输入无效。${NC}"
    fi
}

# ------------------------------------------------------------------------------
# 功能 4: Python 调用串口免 root
# ------------------------------------------------------------------------------
do_enable_no_root() {
    echo -e "\n${BLUE}=== 配置串口免 root 读写权限 ===${NC}"
    echo -e "当前检测的目标普通用户: ${BOLD}$REAL_USER${NC}"

    if [ "$REAL_USER" = "root" ]; then
        echo -e "${YELLOW}[提示] 检测到当前直接以 root 身份执行。${NC}"
        read -rp "请输入需要免 root 读写串口的普通用户名: " TARGET_INPUT_USER
        if [ -n "$TARGET_INPUT_USER" ]; then
            REAL_USER="$TARGET_INPUT_USER"
        else
            echo -e "${RED}[错误] 用户名不能为空。${NC}"
            return
        fi
    fi

    # 检查用户是否存在
    if ! id "$REAL_USER" &>/dev/null; then
        echo -e "${RED}[错误] 系统中不存在用户: $REAL_USER${NC}"
        return
    fi

    # 检查是否已在 dialout 组
    if id -nG "$REAL_USER" | grep -qw "dialout"; then
        echo -e "${GREEN}[OK] 用户 $REAL_USER 已经在 dialout 用户组中。${NC}"
    else
        usermod -aG dialout "$REAL_USER"
        echo -e "${GREEN}[OK] 成功将用户 $REAL_USER 添加到 dialout 组。${NC}"
    fi

    # 临时对已有串口赋权，方便无需重新登录即可做即时测试
    chmod 666 /dev/ttyUSB* /dev/ttyACM* /dev/ttyCH* 2>/dev/null || true
    if [ -d "$LINK_DIR" ]; then
        chmod -R 777 "$LINK_DIR" 2>/dev/null || true
    fi

    echo -e "\n${CYAN}================================================================${NC}"
    echo -e "${GREEN}✓ 免 root 配置完成！${NC}"
    echo -e "注意：Linux 用户组变更通常需要新开终端生效。"
    echo -e "  1. 若在当前终端立即生效，请执行: ${YELLOW}newgrp dialout${NC}"
    echo -e "  2. 随后即可使用普通权限直接运行 Python 串口代码:"
    echo -e "     ${CYAN}python3 -c \"import serial; ser = serial.Serial('/dev/sensors/xxx', 115200)\"${NC}"
    echo -e "${CYAN}================================================================${NC}"
}

# ------------------------------------------------------------------------------
# 功能 5: 实时监听串口插拔 (极其实用的现场调试工具)
# ------------------------------------------------------------------------------
do_monitor_serial() {
    echo -e "\n${BLUE}=== 实时监听串口设备插拔事件 ===${NC}"
    echo -e "${YELLOW}请拔出或插入 USB 串口硬件，下方将实时显示设备事件。${NC}"
    echo -e "${YELLOW}按 ${BOLD}Ctrl + C${NC}${YELLOW} 即可退出监听返回主菜单...${NC}\n"

    # 使用 udevadm monitor 实时过滤 tty 子系统事件
    udevadm monitor --subsystem-match=tty --udev
}

# ------------------------------------------------------------------------------
# 主循环菜单
# ------------------------------------------------------------------------------
while true; do
    echo -e "\n${CYAN}================================================================${NC}"
    echo -e "${CYAN}                 Linux 串口设备管理工具 (增强重构版)            ${NC}"
    echo -e "${CYAN}================================================================${NC}"
    echo -e "  ${BOLD}[1]${NC} 查看设备状态 (当前在线串口、/dev/sensors/ 映射关系与健康度)"
    echo -e "  ${BOLD}[2]${NC} 固化串口设备 (支持增量绑定、多端口芯片区分、防覆盖)"
    echo -e "  ${BOLD}[3]${NC} 取消固化管理 (支持单条别名解绑，或一键清空全部)"
    echo -e "  ${BOLD}[4]${NC} 免 root 配置  (加入 dialout 组，Python 免 sudo 读写)"
    echo -e "  ${BOLD}[5]${NC} 拔插动态监听 (实时监测插入/拔出的设备名，方便硬件排查)"
    echo -e "  ${BOLD}[0]${NC} 退出程序"
    echo -e "${CYAN}================================================================${NC}"

    read -rp "请输入操作编号 [0-5]: " CHOICE

    case "$CHOICE" in
        1)
            do_show_status
            ;;
        2)
            do_bind_serial
            ;;
        3)
            do_unbind_serial
            ;;
        4)
            do_enable_no_root
            ;;
        5)
            do_monitor_serial
            ;;
        0)
            echo -e "${BLUE}感谢使用，已退出。${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}[错误] 输入无效，请输入 0 到 5 之间的数字。${NC}"
            ;;
    esac

    read -rp "按回车键继续..." _
done