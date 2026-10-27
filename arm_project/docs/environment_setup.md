# 机械臂视觉追踪避障系统 - 环境依赖与部署指南 (Python 3.8 / 原生 pip)

本文档旨在指导开发者使用标准 Python 工具链（`venv` + `pip`）搭建并运行本项目的运行环境。

---

## 1. 系统要求与环境底座
- **Python 版本**: Python 3.8 (或 >=3.8, <3.9)
- **依赖管理**: 标准 `pip` 与原生虚拟环境 `venv`（已彻底去除 PDM 依赖）
- **机械臂硬件**: 睿尔曼 (RealMan) RM65-6F (需配置固定的局域网 IP)
- **视觉传感器**: Intel RealSense D435i (提供 RGB 与 Depth 对齐数据)

---

## 2. 部署流程

### 2.1 激活虚拟环境

推荐使用本机已配置的 **Conda `robot` 虚拟环境**（已内置 Python 3.8.20、PyTorch、Ultralytics、pyrealsense2 以及 `Robotic-Arm 1.0.6`）：

```bash
# 方式 A (推荐)：激活已就绪的 conda robot 环境
conda activate robot

# 方式 B：手动创建全新 Python 3.8 隔离环境
python3.8 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
```

---

### 2.2 安装项目基础依赖

```bash
# 一键安装通用生产环境依赖 (NumPy 1.x, OpenCV, SciPy, Ultralytics 等)
pip install -r requirements.txt
```

---

### 2.3 硬件驱动与 SDK (`Robotic-Arm` & `pyrealsense2`)

1. **睿尔曼机械臂 SDK (`Robotic-Arm`)**：
   在 conda `robot` 环境中已预装 `Robotic-Arm 1.0.6`，项目底层代码已对 1.0.6 版本中的接口（如 `rm_set_collision_state`、`rm_set_arm_continue`、`rm_set_manual_tool_frame`）进行了原生兼容适配。
   若在其他全新环境中安装，可执行：
   ```bash
   pip install libs/robotic_arm-1.0.6-py38-none-any.whl
   # 或直接从 PyPI 安装
   pip install Robotic-Arm==1.0.6
   ```

2. **Intel RealSense 相机驱动 (`pyrealsense2`)**：
   如在 x86_64 PC 开发机，可直接通过 pip 安装官方轮子：
   ```bash
   pip install pyrealsense2
   ```
   如在 ARM64 边缘计算平台上，需挂载匹配 Python 3.8 的 aarch64 编译轮子（或在实机上执行源码编译生成的 wheel）：
   ```bash
   pip install libs/pyrealsense2*cp38*.whl
   ```

3. **CUDA 加速版 PyTorch (嵌入式设备 / Jetson 环境可选)**：
   如在支持 CUDA 11.4 的 JetPack 5.1 实机上部署，可直接安装本地归档的官方硬件加速包：
   ```bash
   pip install libs/torch-2.0.0+nv23.05-cp38-cp38-linux_aarch64.whl
   ```

---

### 2.4 安装开发与测试依赖 (可选)

```bash
pip install -r requirements-dev.txt
```

---

## 3. 配置文件修改

在启动系统前，请根据实机网络环境，修改 `config/settings.yaml`：

```yaml
robot:
  controller_ip: "192.168.1.18"  # 替换为睿尔曼机械臂的真实IP
  controller_port: 8080          # 默认端口

vision:
  camera:
    fps: 30
    depth_width: 848
    depth_height: 480
    color_width: 1280
    color_height: 720
```

---

## 4. 验证与启动

### 4.1 运行单元测试
```bash
# 直接运行 pytest (已通过 pytest.ini 配置模块搜索路径)
pytest
```

### 4.2 启动主系统
```bash
# 推荐使用封装脚本 (自动设置 PYTHONPATH 并激活环境)
./run.sh

# 或者使用 Python 模块化启动
python3 -m src.main
```
如果看到 `=== 机械臂视觉系统启动 ===` 和 `TCP Server 开始监听 0.0.0.0:9000` 且无报错，即代表部署成功！
