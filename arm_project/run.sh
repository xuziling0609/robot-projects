#!/usr/bin/env bash
# ==============================================================
# RM65-6F 机械臂三维视觉追踪避障控制系统 - 启动脚本
# ==============================================================
set -e

# 定位脚本所在根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${PROJECT_ROOT}"

# 优先激活 conda robot 虚拟环境，若无则尝试本地 .venv
if [ -f "/home/unitree/miniforge3/bin/activate" ]; then
    source "/home/unitree/miniforge3/bin/activate" robot
elif command -v conda &> /dev/null; then
    eval "$(conda shell.bash hook)"
    conda activate robot 2>/dev/null || true
elif [ -d "${PROJECT_ROOT}/.venv" ]; then
    source "${PROJECT_ROOT}/.venv/bin/activate"
fi

# 确保项目根路径进入 Python 模块检索路径
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH}"

echo "=== 正在启动机械臂视觉追踪避障控制系统 ==="
exec python src/main.py "$@"
