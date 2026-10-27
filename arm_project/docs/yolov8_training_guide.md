# YOLOv8 电缆目标检测 - 训练与导出指南 (RGB-D 融合版)

本项目已升级采用 **“RGB-D 标准融合架构”**。为了彻底解决深度图无法通过纹理和颜色区分“电缆”与“金属固定夹具 (Clamp)”的痛点，我们将使用 RealSense 的**原生 RGB 彩色图**作为 YOLO 模型的输入进行语义识别，再通过代码底层的坐标对齐 (`rs.align`) 从深度图中提取 3D 距离。

即使在工业环境的不理想光照下，只要通过合理的数据增强，YOLOv8 依然能敏锐捕捉电缆与夹具在材质和光泽上的差异。

本文档详细介绍了如何从零开始采集数据、标注、训练 YOLOv8 模型，并最终将其导出为 Jetson 专属的 TensorRT 引擎加速格式。

---

## 1. 数据采集 (Data Collection)

为了让模型适应现场，您必须在真实的机械臂工作区域内采集数据。

1. **一键采集工具 (`tools/collect_training_images.py`)**：
   运行项目内置的数据采集脚本，自动将 RGB 彩色图保存至 `images/` 目录：
   ```bash
   # 本地桌面 GUI 模式 (按空格单拍，按 A 自动连拍，按 D 撤销删除，按 Q 退出)
   python tools/collect_training_images.py --target 300

   # 或启动远程 Web 交互控制台 (手机/平板/电脑浏览器远程点击拍照)
   python tools/collect_training_images.py --web --port 8089
   ```
   * 脚本会自动在 `images/` 下生成 `classes.txt`（写入 `cable`），方便直接导入标注软件。
   * 支持断点续采，自动延续现有最大编号。
2. **场景覆盖**：
   * 不同的机械臂视角（远、近、俯视、平视）。
   * 背景中应包含可能造成干扰的线束、金属支架。
   * 电缆的不同重叠、遮挡状态。
   * 建议采集总数：**300 ~ 500 张**。

---

## 2. 数据标注 (Annotation)

推荐使用 **[X-AnyLabeling](https://github.com/CVHub520/X-AnyLabeling)**（推荐 **v4.0.0** 版本，支持自动标注与多格式导出）、在线平台 **[Roboflow](https://roboflow.com/)** 或本地工具 **[CVAT](https://cvat.ai/)**、**LabelImg**。

### 使用 X-AnyLabeling-v4.0.0 标注与导出流程：
1. **加载图像文件夹**：打开 X-AnyLabeling，点击 `Open Dir` 选择采集好的彩色图像目录，设置输出 `.json` 标注保存目录。
2. **类别定义与标注**：新建类别标签（本项目统一使用 `cable`），使用矩形框工具 (`Rectangle` / 快捷键 `R`) 进行框选（也可载入自带 AI 模型辅助自动标注）。
3. **导出为 YOLO 格式 TXT**：
   - X-AnyLabeling 默认保存为 **JSON 格式**文件。
   - **方式一（内置导出菜单 - 推荐）**：
     点击顶部菜单栏 **`File`（文件） -> `Export Annotations`（导出标注） -> 选择 `Export YOLO-Hbb Annotations`**（如果是矩形框目标检测）或 **`Export YOLO Annotations`**。
     > **注意**：导出时软件可能会提示你导入/确认一个 `classes.txt` 文件（里面按行填写 `cable`），导出后会在指定目录下生成与每张图片对应的同名 `.txt` 文件（归一化的 `class_id cx cy w h`）。
   - **方式二（脚本一键转换）**：如果直接保存了 `.json` 标签，可直接使用官方/第三方 JSON 转 YOLO 转换脚本（或运行 `json_to_yolo.py`）将 `JSON` 转换为 YOLOv8 所需的 `images/`、`labels/` 目录及 `data.yaml` 文件。

---

## 3. 模型训练 (Training)

我们不建议在计算资源较弱的 Jetson 上进行训练。**强烈建议在带 Nvidia 独立显卡的个人电脑或云服务器（如 AutoDL）上进行。**

### 方式一：直接在 X-AnyLabeling 界面内训练（可视化图形界面）
根据 [X-AnyLabeling 官方文档](https://github.com/CVHub520/X-AnyLabeling)，软件内置了 **Ultralytics Training 训练模块**，支持“标注-训练-自动再标注”闭环：

1. **进入训练界面**：在 X-AnyLabeling 主界面顶部菜单或工具栏中点击 **`Ultralytics Training` / `Model Training`** 图标。
2. **配置参数**：
   - 标注任务 / 数据集路径：自动加载或手动选择已标注的数据集。
   - 训练/验证集比例 (Split Ratio)：推荐 8:2。
   - 基础模型：选择 `yolov8n.pt`。
   - 训练轮次 (Epochs)：100。
   - 图像尺寸 (Image Size)：640。
3. **启动训练**：点击 `Start Training`，软件底层将直接调用内置的 Ultralytics 引擎进行训练。
4. **反哺自动标注 (可选)**：训练完成后，将生成的 `best.onnx` 或权重模型加载回 X-AnyLabeling 的自定义模型库中，即可一键对后续未标注的电缆图片进行**自动标注**（Auto Labeling）。

---

### 方式二：使用独立 Python 脚本训练（推荐 / 更灵活）

若通过源码/环境安装了 `ultralytics` 库：
```bash
pip install ultralytics
```

在含有 `data.yaml` 的目录下，新建并运行 `train.py`：

```python
from ultralytics import YOLO

# 1. 加载官方预训练的 nano 模型 (模型极小，适合 Jetson 边缘端)
model = YOLO("yolov8n.pt") 

# 2. 启动训练
results = model.train(
    data="data.yaml",   # 你的数据集配置路径
    epochs=100,         # 迭代次数
    imgsz=640,          # 图像缩放尺寸 (D435i 深度图一般为 640x480)
    batch=16,           # 显存够的话可以开 32
    device="0",         # 使用 GPU 0
    project="cable_detection",
    name="run_v1"
)
```
运行脚本，耐心等待 1~2 小时。训练完成后，最佳的权重文件将会保存在：
`cable_detection/run_v1/weights/best.pt`。

---

## 4. TensorRT 加速导出 (Jetson 独享)

您拿到 `best.pt` 后，如果直接在 Jetson 上用 PyTorch 推理，大概只能跑 10~15 帧。为了匹配我们的 `20Hz` 极速控制闭环，**必须将其转换为 TensorRT (`.engine`) 格式**。

**注意：此步骤必须且只能在目标运行机器 (您的 Jetson 板卡) 上执行！**
因为 TensorRT 会根据当前的 GPU 硬件微架构进行极度特化的指令集编译。

### 4.1 在 Jetson 上执行导出
将 `best.pt` 拷贝到 Jetson 上的 `models/` 目录下，并重命名为 `cable_yolov8.pt`。
在 Jetson 的项目环境 (PDM) 中，执行以下 Python 代码：

```python
from ultralytics import YOLO

# 加载我们在 PC 上训练好的 pt 模型
model = YOLO("models/cable_yolov8.pt")

# 指定转换为 engine 格式 (fp16 半精度加速，画质几乎无损，速度翻倍)
model.export(
    format="engine",
    device="0",
    half=True,      # 开启 FP16 半精度推理
    workspace=4     # 允许 TRT 使用 4GB 显存用于编译优化
)
```

### 4.2 漫长的编译等待
执行上述代码后，Jetson 需要花费 5~15 分钟来暴力穷举搜索最优算子（终端会输出大量 TensorRT 的编译日志）。
完成后，您将在同目录下得到一个 `cable_yolov8.engine` 文件。

### 4.3 零代码修改，直接起飞
得益于 Ultralytics 库的强大封装，我们在 `src/vision/detector.py` 中的代码无需做任何修改：
```python
# 当模型路径指向 .engine 文件时，YOLO 底层会自动调用 TensorRT 运行时！
self.model = YOLO("models/cable_yolov8.engine")
```
现在，您的边缘视觉推理速度将突破 30 帧甚至 50 帧，足以完美支撑我们的人工势场法柔顺避障！
