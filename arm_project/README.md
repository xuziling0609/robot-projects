# 睿尔曼 RM65-6F 机械臂三维视觉追踪避障控制系统

基于 **睿尔曼 RM65-6F 协作机械臂** 与 **Intel RealSense D435i 深度相机** 构建的工业级三维视觉引导控制系统。

---

## 🌟 核心特性与架构

- **RGB-D 标准融合视觉架构**：基于 YOLOv8 提取 RGB 彩色图特征精准分割电缆，100% 排除金属固定夹具/构件干扰；结合对齐深度图（`rs.align`）提取 3D 物理空间坐标。
- **多段碎片容错与动态聚类**：内置 Y 轴中心动态聚类算法（Row-level Clustering），能够完美容忍支架遮挡导致的“一缆多框”现象，在任意视角下精准归纳 4 层线缆。
- **主动扫描机制 (Active Scanning)**：当镜头偏离或近景特写捕获层数不足 4 层时，自动判定为 `INCOMPLETE` 并触发机械臂 Z 轴沿线平移微调扫描。
- **人工势场局部避障 (APF)**：实时提取近场点云并执行算力降采样，构建引力与斥力复合场，实现 20Hz 高频柔顺避障。
- **Python 3.8 原生轻量构建**：采用标准 `venv` + `pip` 体系，彻底剥离复杂依赖管理器，原生兼容 Python 3.8 工业环境与各类边缘计算主板。

---

## 📂 项目目录结构

```text
arm_project/
├── requirements.txt        # 核心生产环境依赖配置 (Python 3.8 兼容)
├── requirements-dev.txt    # 单元测试与开发依赖配置
├── pyproject.toml          # 项目基础元数据声明
├── pytest.ini              # Pytest 自动化测试配置 (含 pythonpath)
├── run.sh                  # 主程序一键运行脚本
├── README.md               # 项目自述文件
├── config/                 # 配置文件目录
│   └── settings.yaml       # 系统全局配置 (机械臂 IP、相机、算法参数)
├── docs/                   # 项目技术文档
│   ├── environment_setup.md# 环境部署与依赖适配指南
│   ├── yolov8_training_guide.md # YOLOv8 训练与训练脚手架教程
│   ├── plan/               # 架构方案与开发蓝图
│   └── sdk/                # 现场实测识别效果截图
├── libs/                   # 本地预编译/补丁 Wheel 库 (含 pyrealsense2, Robotic_Arm, torch)
├── src/                    # 源代码目录
│   ├── main.py             # 主程序入口 (TCP 服务端 & 主循环)
│   ├── core/               # 基础配置与日志单例
│   ├── communication/      # 上位机 TCP 协议通信服务
│   ├── vision/             # YOLO 检测、动态聚类与深度采样
│   ├── control/            # 睿尔曼 RM65 SDK 封装与 APF 轨迹避障
│   └── calibration/        # 手眼标定齐次变换矩阵计算
└── tests/                  # 单元测试矩阵
```

---

## 🚀 快速启动指南

### 1. 激活虚拟环境 (推荐 Conda robot 环境)

```bash
# 方式 A (推荐)：激活已配置的 conda robot 虚拟环境 (Python 3.8.20 + Robotic-Arm 1.0.6)
conda activate robot

# 方式 B：创建全新 Python 3.8 隔离环境
python3.8 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
```

### 2. 安装项目依赖

详细部署流程可参考 [环境部署指南](docs/environment_setup.md)。

- **安装基础依赖**：
  ```bash
  pip install -r requirements.txt
  ```

- **机械臂驱动 SDK (`Robotic-Arm`)**：
  conda `robot` 环境已预装 `Robotic-Arm 1.0.6`。代码已原生兼容 1.0.6 API。
  若在其他环境部署，可安装本地轮子或通过 pip 安装：
  ```bash
  pip install libs/robotic_arm-1.0.6-py38-none-any.whl
  # 或直接 pip
  pip install Robotic-Arm==1.0.6
  ```

- **开发与测试模式 (可选)**：
  ```bash
  pip install -r requirements-dev.txt
  ```

### 3. 运行自动化测试矩阵
```bash
pytest
```

### 4. 启动主程序
- **方式一 (推荐，脚本自动激活环境与路径)**：
  ```bash
  ./run.sh
  ```
- **方式二 (标准命令)**：
  ```bash
  python3 -m src.main
  ```

### 5. 系统后台服务化部署 (Systemd 守护进程)
系统提供了一键安装、卸载与日志追踪脚本，支持开机自启、崩溃自动拉起与优雅停机：

- **一键安装并启动系统服务** (含自动开机自启)：
  ```bash
  ./install_service.sh
  # 或通过 sudo 执行
  sudo ./install_service.sh
  ```

- **查看实时日志流** (自动支持彩色高亮与错误过滤)：
  ```bash
  ./view_logs.sh            # 实时追踪运行日志 (Ctrl+C 退出)
  ./view_logs.sh -n 50      # 显示最近 50 行并追踪
  ./view_logs.sh -e         # 仅过滤 ERROR 严重级别日志
  ./view_logs.sh -f         # 强制追踪本地 logs/ 目录日志文件
  ```

- **一键卸载系统服务**：
  ```bash
  ./uninstall_service.sh
  ```

- **常用 systemctl 快捷控制**：
  ```bash
  sudo systemctl status arm_project     # 查看服务运行状态
  sudo systemctl restart arm_project    # 重启服务
  sudo systemctl stop arm_project       # 停止服务
  sudo systemctl start arm_project      # 启动服务
  ```

---


## 🛠️ 实用工具集 (Tools)

项目在 `tools/` 目录下提供了完备的独立调试与生产辅助脚本：

### 1. D435 深度相机实时可视化与 3D 空间测距 (`tools/visualize_d435.py`)
用于 RealSense D435/D435i 相机流调试、手眼坐标验证、伪彩色深度分析、YOLO 识别叠加及点云导出。
- **本地桌面 GUI 模式**：
  ```bash
  python tools/visualize_d435.py
  ```
  * 鼠标移动实时探测任意像素 `(u, v)`、深度与相机 3D 坐标；
  * 鼠标左键点击 A/B 两点可直接计算三维空间直线欧氏距离；
  * 快捷键：`M` 切换模式 (并排/纯彩色/纯深度/融合/四分屏)，`C` 切换色谱，`S` 保存无损快照与 `.ply` 彩色点云，`D` 开启 YOLO 检测，`A` 切换对齐。
- **远程 Web 交互可视化模式 (支持远程浏览器免桌面调试)**：
  ```bash
  python tools/visualize_d435.py --web --port 8088
  ```
  在浏览器访问 `http://<IP>:8088`，即可流畅查看实时流并在网页上直接点击测距！

### 2. YOLO 训练样本图片采集工具 (`tools/collect_training_images.py`)
专门用于快速采集模型训练所需的 RGB 样本图片并自动保存至 `images/` 目录：
- **本地桌面 GUI 模式**：
  ```bash
  python tools/collect_training_images.py --target 300
  ```
  * `[Space / Enter / S]`：单张拍照；
  * `[A]`：开启/暂停每秒 1 张的连续自动采集；
  * `[Backspace / D]`：一键撤销并删除上一张拍摄的样本图片；
  * 自动在 `images/` 下生成 `classes.txt`（包含 `cable`），无缝兼容 X-AnyLabeling 标注软件。
- **远程 Web 移动端采集模式**：
  ```bash
  python tools/collect_training_images.py --web --port 8089
  ```
  可在手机或平板浏览器上打开 `http://<IP>:8089`，边在机械臂周围调整视角边轻触屏幕点击拍照与连采。

### 3. 机械臂手眼标定工具 (`tools/calibrate_hand_eye.py`)
```bash
python tools/calibrate_hand_eye.py --mode auto
```

### 4. TensorRT 引擎编译工具 (`tools/export_engine.py`)
```bash
python tools/export_engine.py --weights models/cable.pt --half
```

---

## 📄 协议与授权
本项目遵循 [MIT License](LICENSE)。
