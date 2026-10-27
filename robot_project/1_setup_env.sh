#!/usr/bin/env bash
# ==============================================================================
# 边缘机器人智能网关 - 环境检测与依赖安装脚本 (setup_env.sh)
# 职责：
# 1. 检查 Python 版本 (>=3.10) 与系统基础构建工具；
# 2. 检查并自动安装 PDM (支持国内清华/阿里源高速下载)；
# 3. 自动绑定虚拟环境并执行 pdm install (依据 pdm.lock 锁定依赖)；
# 4. 自动化核心库导入自检，确保环境 100% 可用。
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

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${PROJECT_DIR}"

echo -e "${CYAN}${BOLD}==============================================================${NC}"
echo -e "${CYAN}${BOLD} 🤖 边缘机器人智能网关 - 环境自检与依赖拉取程序${NC}"
echo -e "${CYAN}${BOLD}==============================================================${NC}"
echo -e "📁 工作目录: ${BLUE}${PROJECT_DIR}${NC}"
echo -e "👤 当前用户: ${BLUE}$(whoami)${NC}\n"

# 国内常用 PyPI 镜像源
TSINGHUA_MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"
ALIYUN_MIRROR="https://mirrors.aliyun.com/pypi/simple/"
DEFAULT_MIRROR="${TSINGHUA_MIRROR}"

# 1. 检测系统 Python 3
echo -e "${YELLOW}[1/5] 🔍 检查 Python 运行环境...${NC}"
PYTHON_CMD=""
for cmd in python3.10 python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        VER=$($cmd -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)
        if [ "$VER" = "3.10" ]; then
            PYTHON_CMD="$cmd"
            break
        elif [ -z "$PYTHON_CMD" ]; then
            # 记录兜底命令
            PYTHON_CMD="$cmd"
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}❌ 未检测到 Python 解释器！请先安装 Python 3.10：${NC}"
    echo -e "   Ubuntu/Debian: sudo apt update && sudo apt install -y python3.10 python3.10-venv python3-pip"
    exit 1
fi

PY_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')
PY_MAJOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info.minor)')

echo -e "   检测到 Python 可执行文件: ${GREEN}$(which $PYTHON_CMD)${NC} (版本: ${GREEN}v${PY_VERSION}${NC})"

if [ "$PY_MAJOR" -ne 3 ] || [ "$PY_MINOR" -lt 10 ]; then
    echo -e "${RED}❌ Python 版本过低 (当前: v${PY_VERSION})！本项目严格要求 Python >= 3.10 (推荐 3.10.x)。${NC}"
    echo -e "   请安装 Python 3.10: sudo apt install -y python3.10 python3.10-venv python3-pip"
    exit 1
fi

# 检查系统 pip
if ! command -v pip3 >/dev/null 2>&1 && ! $PYTHON_CMD -m pip --version >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️ 未检测到 pip 工具，正在尝试通过 ensurepip 安装...${NC}"
    $PYTHON_CMD -m ensurepip --upgrade || {
        echo -e "${RED}❌ 安装 pip 失败，请执行: sudo apt install -y python3-pip${NC}"
        exit 1
    }
fi

# 2. 检测并安装 PDM
echo -e "\n${YELLOW}[2/5] 🔍 检查 PDM (Python Dependency Manager)...${NC}"
# 将用户本地 bin 追加至当前 PATH (防止 --user 安装后找不到命令)
export PATH="${HOME}/.local/bin:${PATH}"

if command -v pdm >/dev/null 2>&1; then
    PDM_VER=$(pdm --version 2>/dev/null || echo "已安装")
    echo -e "   ${GREEN}✅ PDM 已就绪: ${PDM_VER}${NC} (${BLUE}$(which pdm)${NC})"
else
    echo -e "   ${YELLOW}⚠️ 未检测到 PDM，正在通过 pip 自动安装 (使用国内清华源加速)...${NC}"
    $PYTHON_CMD -m pip install --user --upgrade pip -i "${DEFAULT_MIRROR}" || true
    $PYTHON_CMD -m pip install --user pdm -i "${DEFAULT_MIRROR}" --break-system-packages

    if command -v pdm >/dev/null 2>&1; then
        echo -e "   ${GREEN}✅ PDM 自动安装成功: $(pdm --version)${NC}"
    else
        echo -e "${RED}❌ PDM 安装后无法识别，请确保 ~/.local/bin 位于您的 PATH 环境变量中。${NC}"
        exit 1
    fi
fi

# 解析命令行参数
FORCE_INSTALL=false
for arg in "$@"; do
    case "$arg" in
        --force|-f)
            FORCE_INSTALL=true
            ;;
    esac
done

# 3. 智能检查现有虚拟环境与依赖完整性
echo -e "\n${YELLOW}[3/5] 🔍 检查本地虚拟环境与依赖就绪状态...${NC}"
VENV_PYTHON="${PROJECT_DIR}/.venv/bin/python"
NEED_INSTALL=true

if [ "$FORCE_INSTALL" = false ] && [ -f "${VENV_PYTHON}" ]; then
    # 极速校验核心依赖是否均已成功安装 (耗时 < 0.2s)
    FAST_CHECK_CODE='
import sys
try:
    import paho.mqtt, yaml, requests, serial, av, cv2, numpy, colorlog, pytest
    sys.exit(0)
except Exception:
    sys.exit(1)
'
    if "${VENV_PYTHON}" -c "${FAST_CHECK_CODE}" 2>/dev/null; then
        NEED_INSTALL=false
        echo -e "   ${GREEN}✅ 检测到本地虚拟环境完整，所有核心依赖均已就绪，跳过重复拉取安装！${NC}"
        echo -e "   ${CYAN}💡 提示：如需强制更新或重新拉取依赖，可附加参数: ./1_setup_env.sh --force${NC}"
    else
        echo -e "   ${YELLOW}⚠️ 检测到虚拟环境存在但部分依赖缺失，准备执行增量同步...${NC}"
    fi
elif [ "$FORCE_INSTALL" = true ]; then
    echo -e "   ${YELLOW}⚡ 用户指定了 --force 强制参数，将重新执行环境绑定与依赖同步...${NC}"
fi

# 4. 若依赖未就绪或强制刷新，执行 PDM 配置与拉取
if [ "$NEED_INSTALL" = true ]; then
    echo -e "\n${YELLOW}[4/5] ⚙️ 配置 PDM 虚拟环境解释器并拉取依赖...${NC}"
    pdm config python.use_pyenv false >/dev/null 2>&1 || true
    pdm use -f "$(which $PYTHON_CMD)" || {
        echo -e "${YELLOW}⚠️ pdm use 指定解释器返回非零，尝试默认初始化...${NC}"
    }

    echo -e "   📦 正在拉取并同步项目依赖包 (依据 pdm.lock)..."
    # 自动配置 PDM 使用国内清华源加速下载
    pdm config pypi.url "${DEFAULT_MIRROR}" >/dev/null 2>&1 || true

    echo -e "   正在执行 pdm install (包含业务依赖与开发测试组件)..."
    pdm install --dev || {
        echo -e "${RED}❌ pdm install 依赖拉取失败，请检查网络连接或尝试手动执行 pdm install。${NC}"
        exit 1
    }
else
    echo -e "\n${GREEN}[4/5] 📦 依赖同步已跳过 (已满足运行要求)${NC}"
fi

# 5. 环境健康自检
echo -e "\n${YELLOW}[5/5] 🧪 执行核心模块导入与环境健康自检...${NC}"

if [ ! -f "${VENV_PYTHON}" ]; then
    echo -e "${RED}❌ 未检测到虚拟环境解析器: ${VENV_PYTHON}${NC}"
    exit 1
fi

echo -e "   虚拟环境解释器: ${GREEN}${VENV_PYTHON}${NC}"

# 测试核心库导入
CHECK_CODE='
import sys
modules = [
    ("Paho-MQTT 通信", "paho.mqtt"),
    ("PyYAML 配置解析", "yaml"),
    ("Requests HTTP客户端", "requests"),
    ("PySerial 串口驱动", "serial"),
    ("PyAV 音视频流编解码", "av"),
    ("OpenCV 视觉计算", "cv2"),
    ("NumPy 科学计算", "numpy"),
    ("ColorLog 日志着色", "colorlog"),
    ("Pytest 自动化测试套件", "pytest"),
]

failed = []
for name, mod in modules:
    try:
        __import__(mod)
        print(f"   ✅ {name} [{mod}] -> 正常")
    except Exception as e:
        print(f"   ❌ {name} [{mod}] -> 加载失败: {e}")
        failed.append(mod)

if failed:
    sys.exit(1)
'

if "${VENV_PYTHON}" -c "${CHECK_CODE}"; then
    echo -e "   ${GREEN}🎉 所有关键依赖库全部加载成功！${NC}"
else
    echo -e "   ${RED}❌ 部分关键依赖库导入失败，请检查上方报错！${NC}"
    exit 1
fi

# 检查 FFmpeg 探测器
echo -e "\n   🔍 检查 FFmpeg 多平台二进制库..."
FFMPEG_RESOLVE_CODE='
from plugins.record.video_recorder import FFmpegResolver
path = FFmpegResolver.get_binary_path()
if path:
    print(f"   ✅ FFmpeg 智能寻址成功: {path}")
else:
    print("   ⚠️ 未检测到 FFmpeg 二进制库，可在系统安装 ffmpeg 或使用 plugins/record/lib 自包含版本。")
'
"${VENV_PYTHON}" -c "${FFMPEG_RESOLVE_CODE}" 2>/dev/null || true

echo -e "\n${GREEN}${BOLD}==============================================================${NC}"
echo -e "${GREEN}${BOLD} 🚀 环境检测与依赖安装已全部顺利完成！${NC}"
echo -e "${GREEN}${BOLD}==============================================================${NC}"
echo -e "接下来您可以选择："
echo -e "  1. 本地前台直接运行:  ${CYAN}pdm run main.py${NC}"
echo -e "  2. 启动硬件模拟器:    ${CYAN}pdm run simulator/start_all_simulators.py${NC}"
echo -e "  3. 部署为系统自启服务: ${CYAN}sudo ./2_install_service.sh${NC}\n"
