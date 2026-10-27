#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Intel RealSense D435 / D435i 工业级综合可视化与测量诊断工具
(D435 Multi-Stream Visualizer & 3D Spatial Inspector)

功能特性:
1. 多流与多模式显示:
   - 并排模式 (Side-by-Side): 彩色图与伪彩色深度图并排对齐展示
   - 单流模式: 纯彩色图 (Color Only)、纯深度图 (Depth Only)
   - 叠加融合模式 (Overlay / Alpha Blend): 彩色图与半透明深度图空间融合
   - 四分屏模式 (Quad Grid): 同时显示 RGB、深度、红外 IR1、IR2 流
2. 实时 3D 空间测量与点位检测 (Interactive 3D Inspector):
   - 鼠标悬停/移动: 实时探测光标处像素 (u, v)、深度距离 (m/mm)、相机 3D 物理坐标 (X_c, Y_c, Z_c)
   - 手眼标定联动: 自动结合 config/settings.yaml 中的手眼变换矩阵，实时计算末端坐标系坐标 (X_end, Y_end, Z_end)
   - 3D 空间测距: 左键单击标记点 A，再次单击标记点 B，自动计算并渲染两点间三维欧式空间直线距离 (ΔL mm)
   - 右键清除标记点
3. 实时滤镜与伪彩色变换:
   - 支持 TURBO, JET, INFERNO, VIRIDIS, BONE, OCEAN 等多种伪彩色谱
   - 动态深度范围裁剪: 支持实时调整 [min_depth, max_depth] 显示阈值，附带高精度右侧标尺 (Colorbar Legend)
   - 支持硬件级滤波链 (Decimation, Spatial, Temporal, Hole Filling 空间/时间/空洞滤波)
4. AI 目标识别联动:
   - 快捷键 'd' 启动/关闭 YOLO 目标检测 (自动集成 models/cable.engine 或 models/cable.pt)
   - 实时渲染目标包围盒、置信度以及目标中心 3D 空间位置
5. 一键三维快照与点云导出:
   - 快捷键 's' 保存全套数据至 data/captures/:
     * RGB 彩色原图 (.png)
     * 16 位毫米级无损深度图 (.png)
     * 伪彩色深度渲染图 (.png)
     * 空间融合叠加图 (.png)
     * 3D 彩色点云文件 (.ply，原生兼容 CloudCompare, MeshLab, Open3D)
     * 详细相机内参及手眼矩阵元数据 (.json)
6. 双模运行引擎 (Local Desktop GUI + Headless Web Streamer):
   - 本地桌面 GUI 模式: OpenCV 高性能交互窗口，支持快捷键与鼠标事件
   - 远程 Web 流媒体模式 (--web): 内置轻量级多线程 HTTP MJPEG 实时流服务器与现代暗黑风格 Web 交互前端，
     无需安装额外依赖，无缝支持远程 SSH、平板或浏览器远程调试与点位点击测距！
"""

import os
import sys
import time
import json
import glob
import math
import argparse
import threading
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, Dict, List, Any
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# 抑制 Qt/xcb 无关警告信息
os.environ["QT_LOGGING_RULES"] = "qt.qpa.*=false;*.warning=false"

# 自动处理 Linux DISPLAY 与 XAUTHORITY 环境变量 (适配 SSH / IDE 终端启动 GUI)
if "DISPLAY" not in os.environ and os.path.exists("/tmp/.X11-unix/X0"):
    os.environ["DISPLAY"] = ":0"
if "XAUTHORITY" not in os.environ:
    for auth_candidate in ["/run/user/1000/gdm/Xauthority", os.path.expanduser("~/.Xauthority")]:
        if os.path.exists(auth_candidate):
            os.environ["XAUTHORITY"] = auth_candidate
            break

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np

try:
    import pyrealsense2 as rs
except ImportError:
    rs = None

# 加载项目核心配置与日志
try:
    from src.core.config_loader import get_config
    SYSTEM_CONFIG = get_config()
except Exception:
    SYSTEM_CONFIG = {}

try:
    from src.core.logger import logger
except Exception:
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logger = logging.getLogger("visualize_d435")


# ==============================================================================
# 伪彩色映射表定义
# ==============================================================================
COLORMAP_DICT = {
    "turbo": (cv2.COLORMAP_TURBO, "TURBO (Perceptual Uniform)"),
    "jet": (cv2.COLORMAP_JET, "JET (Classic Rainbow)"),
    "inferno": (cv2.COLORMAP_INFERNO, "INFERNO (High Contrast Thermal)"),
    "viridis": (cv2.COLORMAP_VIRIDIS, "VIRIDIS (Natural Gradient)"),
    "bone": (cv2.COLORMAP_BONE, "BONE (Medical X-Ray)"),
    "ocean": (cv2.COLORMAP_OCEAN, "OCEAN (Blue-Cyan Depth)"),
}
COLORMAP_KEYS = list(COLORMAP_DICT.keys())


# ==============================================================================
# D435 核心驱动与可视化控制器
# ==============================================================================
class D435Visualizer:
    def __init__(
        self,
        color_res: Tuple[int, int] = (1280, 720),
        depth_res: Tuple[int, int] = (848, 480),
        fps: int = 30,
        enable_ir: bool = False,
        align_to_color: bool = True,
        enable_filter: bool = False,
        min_depth: float = 0.15,
        max_depth: float = 3.0,
        colormap: str = "turbo",
        display_mode: str = "side-by-side",
        detect_model: Optional[str] = None,
        save_dir: str = "data/captures"
    ):
        self.color_width, self.color_height = color_res
        self.depth_width, self.depth_height = depth_res
        self.fps = fps
        self.enable_ir = enable_ir
        self.align_to_color = align_to_color
        self.enable_filter = enable_filter
        self.min_depth = max(0.05, float(min_depth))
        self.max_depth = max(self.min_depth + 0.1, float(max_depth))
        self.colormap_idx = COLORMAP_KEYS.index(colormap) if colormap in COLORMAP_KEYS else 0
        self.display_mode = display_mode  # 'side-by-side', 'color', 'depth', 'overlay', 'quad'
        self.overlay_alpha = 0.5
        self.show_hud = True
        self.show_help = True
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # RealSense 状态
        self.pipeline: Optional[rs.pipeline] = None
        self.profile: Optional[rs.pipeline_profile] = None
        self.align: Optional[rs.align] = None
        self.color_intrinsics = None
        self.depth_intrinsics = None
        self.depth_scale = 0.001
        self.device_name = "Unknown RealSense"
        self.serial_number = "Unknown"
        self.usb_type = "Unknown"
        self.is_running = False

        # 滤波链 (RealSense Post-Processing Filters)
        self.spatial_filter = None
        self.temporal_filter = None
        self.hole_filling_filter = None
        self.decimation_filter = None
        self.pointcloud = None

        # 帧缓存与锁
        self.lock = threading.Lock()
        self.latest_color: Optional[np.ndarray] = None
        self.latest_depth_raw: Optional[np.ndarray] = None
        self.latest_depth_colored: Optional[np.ndarray] = None
        self.latest_ir1: Optional[np.ndarray] = None
        self.latest_ir2: Optional[np.ndarray] = None
        self.latest_depth_frame: Optional[Any] = None
        self.latest_color_frame: Optional[Any] = None
        self.latest_display_frame: Optional[np.ndarray] = None
        self.latest_detections: List[Dict[str, Any]] = []

        # 性能统计
        self.fps_counter = 0
        self.fps_calc_time = time.time()
        self.current_fps = 0.0
        self.frame_count = 0

        # 交互测量状态 (光标与标记点)
        self.mouse_x = -1
        self.mouse_y = -1
        self.hover_info: Optional[Dict[str, Any]] = None
        self.point_a: Optional[Dict[str, Any]] = None  # {'pixel': (u, v), 'cam_3d': (x,y,z), 'end_3d': (x,y,z)}
        self.point_b: Optional[Dict[str, Any]] = None
        self.notification_text = ""
        self.notification_time = 0.0

        # 手眼标定变换矩阵 (T_end_to_camera, 单位 mm)
        self.T_end_to_camera: Optional[np.ndarray] = None
        self._load_calibration_matrix()

        # AI 目标检测模型
        self.enable_detection = False
        self.detector_model = None
        self.detect_model_path = detect_model
        if detect_model:
            self._init_detector(detect_model)

    def _load_calibration_matrix(self):
        """从 settings.yaml 加载手眼标定齐次变换矩阵"""
        try:
            calib_cfg = SYSTEM_CONFIG.get("calibration", {})
            mat_raw = calib_cfg.get("T_end_to_camera")
            if mat_raw and len(mat_raw) == 4:
                self.T_end_to_camera = np.array(mat_raw, dtype=np.float64)
                logger.info(f"已成功加载手眼标定矩阵 T_end_to_camera (单位: {calib_cfg.get('unit', 'mm')})")
        except Exception as e:
            logger.debug(f"加载手眼标定矩阵跳过: {e}")

    def _init_detector(self, model_path: str):
        """初始化 YOLO 目标检测模型"""
        try:
            from ultralytics import YOLO
            if os.path.exists(model_path):
                logger.info(f"正在加载 YOLO 检测模型: {model_path} ...")
                self.detector_model = YOLO(model_path)
                self.enable_detection = True
                logger.info("YOLO 检测模型加载成功！")
            else:
                logger.warning(f"模型文件不存在: {model_path}")
        except Exception as e:
            logger.error(f"初始化 YOLO 模型失败: {e}")

    def reset_hardware(self) -> bool:
        """调用硬件总线级复位与链路重建"""
        logger.warning("正在执行 D435 相机硬件链路自愈复位...")
        reset_done = False
        if rs is not None:
            try:
                ctx = rs.context()
                for dev in ctx.query_devices():
                    dev.hardware_reset()
                    reset_done = True
                    break
            except Exception as e:
                logger.debug(f"librealsense hardware_reset: {e}")

        if not reset_done:
            try:
                import subprocess
                res = subprocess.run(["usbreset", "8086:0b3a"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
                if res.returncode == 0:
                    reset_done = True
            except Exception:
                pass

        time.sleep(2.0)
        return reset_done

    def start_camera(self) -> bool:
        """初始化并启动 RealSense 硬件视频流管线"""
        if rs is None:
            logger.error("系统未检测到 pyrealsense2 库，无法驱动 D435 相机！")
            return False

        for attempt in range(2):
            try:
                self.pipeline = rs.pipeline()
                config = rs.config()

                # 启用深度流
                config.enable_stream(
                    rs.stream.depth,
                    self.depth_width,
                    self.depth_height,
                    rs.format.z16,
                    self.fps
                )

                # 启用彩色流
                config.enable_stream(
                    rs.stream.color,
                    self.color_width,
                    self.color_height,
                    rs.format.bgr8,
                    self.fps
                )

                # 如果开启红外流
                if self.enable_ir:
                    config.enable_stream(
                        rs.stream.infrared, 1,
                        self.depth_width, self.depth_height,
                        rs.format.y8, self.fps
                    )
                    config.enable_stream(
                        rs.stream.infrared, 2,
                        self.depth_width, self.depth_height,
                        rs.format.y8, self.fps
                    )

                self.profile = self.pipeline.start(config)

                # 获取硬件设备信息
                dev = self.profile.get_device()
                self.device_name = dev.get_info(rs.camera_info.name) if dev.supports(rs.camera_info.name) else "Intel RealSense"
                self.serial_number = dev.get_info(rs.camera_info.serial_number) if dev.supports(rs.camera_info.serial_number) else "Unknown"
                if dev.supports(rs.camera_info.usb_type_descriptor):
                    self.usb_type = dev.get_info(rs.camera_info.usb_type_descriptor)

                # 获取深度尺度
                depth_sensor = dev.first_depth_sensor()
                self.depth_scale = depth_sensor.get_depth_scale()

                # 获取流内参
                color_stream = self.profile.get_stream(rs.stream.color).as_video_stream_profile()
                depth_stream = self.profile.get_stream(rs.stream.depth).as_video_stream_profile()
                self.color_intrinsics = color_stream.get_intrinsics()
                self.depth_intrinsics = depth_stream.get_intrinsics()

                # 对齐对象
                self.align = rs.align(rs.stream.color)

                # 初始化滤波链与点云模块
                self.spatial_filter = rs.spatial_filter()
                self.temporal_filter = rs.temporal_filter()
                self.hole_filling_filter = rs.hole_filling_filter()
                self.pointcloud = rs.pointcloud()

                # 预热并等待曝光稳定
                for _ in range(8):
                    self.pipeline.wait_for_frames(timeout_ms=3000)

                self.is_running = True
                logger.info(f"D435 相机就绪: {self.device_name} (SN: {self.serial_number}, USB: {self.usb_type})")
                logger.info(f"深度比例尺: {self.depth_scale:.6f} m/LSB, 彩色分辨率: {self.color_width}x{self.color_height}@{self.fps}fps")
                return True

            except Exception as e:
                logger.warning(f"启动 RealSense 尝试 [{attempt+1}/2] 异常: {e}")
                if self.pipeline:
                    try:
                        self.pipeline.stop()
                    except Exception:
                        pass
                    self.pipeline = None
                if attempt == 0:
                    self.reset_hardware()
                else:
                    return False
        return False

    def stop_camera(self):
        """安全停止相机管线"""
        self.is_running = False
        if self.pipeline:
            try:
                self.pipeline.stop()
                logger.info("RealSense 数据流已安全关闭。")
            except Exception:
                pass
            self.pipeline = None

    def set_notification(self, text: str, duration: float = 3.0):
        """设置屏幕悬浮弹窗提示文本"""
        self.notification_text = text
        self.notification_time = time.time() + duration

    def deproject_to_3d(self, pixel_xy: Tuple[int, int], depth_val_m: float) -> Optional[np.ndarray]:
        """将 2D 像素坐标反投影为 3D 相机物理坐标 [X, Y, Z] (单位: 米)"""
        if depth_val_m <= 0.0 or rs is None:
            return None
        # 使用对应的内参 (若对齐至彩色图，则使用彩色图内参)
        intrinsics = self.color_intrinsics if self.align_to_color else self.depth_intrinsics
        if intrinsics is None:
            return None
        pt_3d = rs.rs2_deproject_pixel_to_point(intrinsics, [float(pixel_xy[0]), float(pixel_xy[1])], depth_val_m)
        return np.array(pt_3d, dtype=np.float64)

    def transform_to_end(self, pt_cam_m: np.ndarray) -> Optional[np.ndarray]:
        """将相机坐标系下的点 (米) 转换为机械臂末端坐标系坐标 (mm)"""
        if self.T_end_to_camera is None or pt_cam_m is None:
            return None
        # 转为 mm
        pt_cam_mm = pt_cam_m * 1000.0
        homo_cam = np.array([pt_cam_mm[0], pt_cam_mm[1], pt_cam_mm[2], 1.0], dtype=np.float64)
        homo_end = self.T_end_to_camera @ homo_cam
        return homo_end[:3]

    def process_frames(self) -> bool:
        """从硬件管线抓取一帧并完成滤波、对齐与色彩映射"""
        if not self.is_running or self.pipeline is None:
            return False

        try:
            frames = self.pipeline.wait_for_frames(timeout_ms=2000)

            # 是否执行滤波处理
            raw_depth = frames.get_depth_frame()
            if not raw_depth:
                return False

            if self.enable_filter and self.spatial_filter is not None:
                filtered_depth = self.spatial_filter.process(raw_depth)
                filtered_depth = self.temporal_filter.process(filtered_depth)
                filtered_depth = self.hole_filling_filter.process(filtered_depth)
                target_depth_frame = filtered_depth
            else:
                target_depth_frame = raw_depth

            # 是否执行色彩空间对齐
            if self.align_to_color and self.align is not None:
                aligned_frames = self.align.process(frames)
                color_frame = aligned_frames.get_color_frame()
                depth_frame = aligned_frames.get_depth_frame()
            else:
                color_frame = frames.get_color_frame()
                depth_frame = target_depth_frame

            if not color_frame or not depth_frame:
                return False

            color_np = np.asanyarray(color_frame.get_data())
            depth_np = np.asanyarray(depth_frame.get_data())

            # 获取红外图像 (如果启用)
            ir1_np, ir2_np = None, None
            if self.enable_ir:
                ir1_frame = frames.get_infrared_frame(1)
                ir2_frame = frames.get_infrared_frame(2)
                if ir1_frame:
                    ir1_np = cv2.cvtColor(np.asanyarray(ir1_frame.get_data()), cv2.COLOR_GRAY2BGR)
                if ir2_frame:
                    ir2_np = cv2.cvtColor(np.asanyarray(ir2_frame.get_data()), cv2.COLOR_GRAY2BGR)

            # 生成伪彩色深度图
            depth_colored_np = self.colorize_depth(depth_np)

            # AI 检测 (如果启用)
            detections = []
            if self.enable_detection and self.detector_model is not None:
                detections = self.run_object_detection(color_np, depth_np)

            with self.lock:
                self.latest_color = color_np
                self.latest_depth_raw = depth_np
                self.latest_depth_colored = depth_colored_np
                self.latest_ir1 = ir1_np
                self.latest_ir2 = ir2_np
                self.latest_depth_frame = depth_frame
                self.latest_color_frame = color_frame
                self.latest_detections = detections
                self.frame_count += 1

                # 刷新 FPS
                now = time.time()
                self.fps_counter += 1
                if now - self.fps_calc_time >= 1.0:
                    self.current_fps = self.fps_counter / (now - self.fps_calc_time)
                    self.fps_counter = 0
                    self.fps_calc_time = now

            return True

        except Exception as e:
            logger.debug(f"获取帧异常: {e}")
            return False

    def colorize_depth(self, depth_raw_np: np.ndarray) -> np.ndarray:
        """
        深度数据线性归一化并渲染为高级伪彩色。
        严格区分有效测距区与无回波黑洞 (无效像素标为纯黑灰)。
        """
        depth_m = depth_raw_np * self.depth_scale
        valid_mask = (depth_m >= self.min_depth) & (depth_m <= self.max_depth)

        # 线性映射到 [0, 255]
        clipped = np.clip(depth_m, self.min_depth, self.max_depth)
        norm_8u = ((clipped - self.min_depth) / (self.max_depth - self.min_depth) * 255.0).astype(np.uint8)

        # 获取选定的 colormap
        cmap_id = COLORMAP_DICT[COLORMAP_KEYS[self.colormap_idx]][0]
        colorized = cv2.applyColorMap(norm_8u, cmap_id)

        # 将盲区或黑洞像素重设为深黑炭灰色 (区分于真实测距)
        colorized[~valid_mask] = [20, 20, 20]

        return colorized

    def run_object_detection(self, color_img: np.ndarray, depth_img: np.ndarray) -> List[Dict[str, Any]]:
        """执行 YOLO 推理，并关联 3D 深度测距"""
        results_list = []
        try:
            preds = self.detector_model(color_img, verbose=False)
            for res in preds:
                if not hasattr(res, "boxes") or res.boxes is None:
                    continue
                for box in res.boxes:
                    xyxy = box.xyxy[0].cpu().numpy().tolist()
                    conf = float(box.conf[0].cpu().numpy())
                    cls_id = int(box.cls[0].cpu().numpy())
                    cls_name = res.names[cls_id] if hasattr(res, "names") else f"Class_{cls_id}"

                    x1, y1, x2, y2 = map(int, xyxy)
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

                    # 提取中心 ROI 抗黑洞深度
                    h, w = depth_img.shape
                    ry1, ry2 = max(0, cy - 5), min(h, cy + 5)
                    rx1, rx2 = max(0, cx - 5), min(w, cx + 5)
                    roi = depth_img[ry1:ry2, rx1:rx2]
                    valid = roi[roi > 0]
                    d_m = float(np.median(valid)) * self.depth_scale if len(valid) > 0 else 0.0
                    pt_3d = self.deproject_to_3d((cx, cy), d_m) if d_m > 0 else None

                    results_list.append({
                        "bbox": [x1, y1, x2, y2],
                        "center": (cx, cy),
                        "conf": conf,
                        "class_name": cls_name,
                        "depth_m": d_m,
                        "cam_3d": pt_3d
                    })
        except Exception as e:
            logger.debug(f"YOLO 推理异常: {e}")
        return results_list

    def add_vertical_colorbar(self, img: np.ndarray, width: int = 40) -> np.ndarray:
        """在图像右侧添加垂直标尺渐变 Colorbar 图例"""
        h, w = img.shape[:2]
        bar = np.zeros((h, width, 3), dtype=np.uint8)

        # 生成从顶部 (近) 到低部 (远) 的渐变
        # 0 在顶部代表 min_depth，255 在底部代表 max_depth
        gradient = np.linspace(0, 255, h, dtype=np.uint8).reshape(h, 1)
        gradient = np.repeat(gradient, width, axis=1)

        cmap_id = COLORMAP_DICT[COLORMAP_KEYS[self.colormap_idx]][0]
        bar_color = cv2.applyColorMap(gradient, cmap_id)

        # 绘制刻度线与刻度值
        cv2.rectangle(bar_color, (0, 0), (width - 1, h - 1), (100, 100, 100), 1)
        num_ticks = 5
        for i in range(num_ticks):
            y_tick = int(i * (h - 20) / (num_ticks - 1)) + 10
            val_m = self.min_depth + i * (self.max_depth - self.min_depth) / (num_ticks - 1)
            cv2.line(bar_color, (0, y_tick), (6, y_tick), (255, 255, 255), 1)
            cv2.putText(bar_color, f"{val_m:.1f}", (8, y_tick + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (255, 255, 255), 1)

        return np.hstack([img, bar_color])

    def render_hud(self, canvas: np.ndarray) -> np.ndarray:
        """渲染顶部半透明 HUD 状态看板与底部帮助提示栏"""
        if not self.show_hud:
            return canvas

        h, w = canvas.shape[:2]

        # 1. 顶部半透明状态 Banner
        top_bar_h = 36
        overlay = canvas.copy()
        cv2.rectangle(overlay, (0, 0), (w, top_bar_h), (18, 18, 22), -1)
        cv2.addWeighted(overlay, 0.75, canvas, 0.25, 0, canvas)
        cv2.line(canvas, (0, top_bar_h), (w, top_bar_h), (60, 60, 70), 1)

        # 状态徽章文本
        cmap_name = COLORMAP_DICT[COLORMAP_KEYS[self.colormap_idx]][1].split()[0]
        align_str = "ON" if self.align_to_color else "OFF"
        filt_str = "ON" if self.enable_filter else "OFF"
        det_str = "ON" if self.enable_detection else "OFF"
        mode_str = self.display_mode.upper()

        stats_items = [
            f"FPS: {self.current_fps:.1f}",
            f"DEV: {self.device_name} ({self.usb_type})",
            f"MODE: {mode_str}",
            f"CMAP: {cmap_name}",
            f"RANGE: [{self.min_depth:.2f}m - {self.max_depth:.2f}m]",
            f"ALIGN: {align_str}",
            f"FILT: {filt_str}",
            f"YOLO: {det_str}",
        ]

        text_x = 12
        for item in stats_items:
            cv2.putText(canvas, item, (text_x, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 230, 255), 1, cv2.LINE_AA)
            text_x += len(item) * 9 + 18
            if text_x > w - 100:
                break

        # 2. 悬浮弹窗提示 (如 "Snapshot Saved!")
        if time.time() < self.notification_time and self.notification_text:
            notif_w = min(len(self.notification_text) * 11 + 30, w - 40)
            cv2.rectangle(canvas, (w // 2 - notif_w // 2, 45), (w // 2 + notif_w // 2, 85), (0, 160, 80), -1)
            cv2.rectangle(canvas, (w // 2 - notif_w // 2, 45), (w // 2 + notif_w // 2, 85), (255, 255, 255), 1)
            cv2.putText(
                canvas, self.notification_text,
                (w // 2 - notif_w // 2 + 15, 71),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA
            )

        # 3. 底部快捷键指南栏 (如果开启)
        if self.show_help:
            bot_bar_h = 28
            overlay = canvas.copy()
            cv2.rectangle(overlay, (0, h - bot_bar_h), (w, h), (15, 15, 20), -1)
            cv2.addWeighted(overlay, 0.8, canvas, 0.2, 0, canvas)
            cv2.line(canvas, (0, h - bot_bar_h), (w, h - bot_bar_h), (50, 50, 60), 1)

            help_msg = (
                "[M] Mode  |  [C] Colormap  |  [A] Align  |  [F] Filter  |  [D] Detect  |  "
                "[S] Snapshot & 3D PLY  |  [+/-] Range  |  [L-Click] Pick/Measure  |  [R-Click] Clear  |  [Q] Quit"
            )
            cv2.putText(canvas, help_msg, (12, h - 9), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (190, 200, 210), 1, cv2.LINE_AA)

        return canvas

    def render_inspection(self, canvas: np.ndarray, coord_mapper: Optional[callable] = None) -> np.ndarray:
        """渲染光标交互十字准星、3D 测量线段与点位详情 Badge"""
        # 1. 绘制已固定的标记点 A 和 B
        pts = [("Pt A", self.point_a, (0, 255, 0)), ("Pt B", self.point_b, (255, 165, 0))]
        pt_coords_render = []

        for label, pt_data, color in pts:
            if pt_data is None:
                continue
            u, v = pt_data["pixel"]
            render_u, render_v = coord_mapper(u, v) if coord_mapper else (u, v)
            pt_coords_render.append((render_u, render_v, pt_data))

            # 绘制同心圆与中心十字
            cv2.circle(canvas, (render_u, render_v), 8, color, 2, cv2.LINE_AA)
            cv2.circle(canvas, (render_u, render_v), 2, (255, 255, 255), -1, cv2.LINE_AA)

            # 信息框
            d_mm = pt_data["depth_m"] * 1000.0
            cam_3d = pt_data["cam_3d"]
            cam_str = f"{label}: {d_mm:.0f}mm (X:{cam_3d[0]*1000:.0f}, Y:{cam_3d[1]*1000:.0f}, Z:{cam_3d[2]*1000:.0f})"
            cv2.putText(canvas, cam_str, (render_u + 12, render_v - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)

        # 2. 如果存在 A 和 B 两点，计算并绘制 3D 空间测距连线
        if len(pt_coords_render) == 2:
            p1_r, p2_r = pt_coords_render[0], pt_coords_render[1]
            u1, v1 = p1_r[0], p1_r[1]
            u2, v2 = p2_r[0], p2_r[1]

            # 连线
            cv2.line(canvas, (u1, v1), (u2, v2), (0, 255, 255), 2, cv2.LINE_AA)

            # 3D 欧式距离计算
            c1 = p1_r[2]["cam_3d"]
            c2 = p2_r[2]["cam_3d"]
            dist_3d_mm = np.linalg.norm(c1 - c2) * 1000.0
            dist_text = f"3D Distance: {dist_3d_mm:.1f} mm"

            # 居中显示距离标签
            mid_u, mid_v = (u1 + u2) // 2, (v1 + v2) // 2
            tw = len(dist_text) * 8 + 14
            cv2.rectangle(canvas, (mid_u - tw // 2, mid_v - 18), (mid_u + tw // 2, mid_v + 6), (0, 0, 0), -1)
            cv2.rectangle(canvas, (mid_u - tw // 2, mid_v - 18), (mid_u + tw // 2, mid_v + 6), (0, 255, 255), 1)
            cv2.putText(canvas, dist_text, (mid_u - tw // 2 + 7, mid_v - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1, cv2.LINE_AA)

        # 3. 鼠标悬停实时探测 Crosshair 与 HUD Tooltip
        if self.hover_info and self.mouse_x >= 0 and self.mouse_y >= 0:
            mx, my = self.mouse_x, self.mouse_y
            h, w = canvas.shape[:2]

            # 仅在画面有效范围内绘制
            if 0 <= mx < w and 0 <= my < h:
                # 动态十字准星
                cv2.line(canvas, (mx - 12, my), (mx + 12, my), (0, 255, 0), 1, cv2.LINE_AA)
                cv2.line(canvas, (mx, my - 12), (mx, my + 12), (0, 255, 0), 1, cv2.LINE_AA)
                cv2.circle(canvas, (mx, my), 4, (0, 255, 0), 1, cv2.LINE_AA)

                # Tooltip 内容构建
                u, v = self.hover_info["pixel"]
                d_m = self.hover_info["depth_m"]
                cam_3d = self.hover_info["cam_3d"]
                end_3d = self.hover_info.get("end_3d")

                tip_lines = [
                    f"Pixel: ({u}, {v})",
                    f"Depth: {d_m:.3f} m ({d_m*1000.0:.0f} mm)" if d_m > 0 else "Depth: Invalid / Hole",
                ]
                if cam_3d is not None:
                    tip_lines.append(f"Cam: [{cam_3d[0]*1000:.1f}, {cam_3d[1]*1000:.1f}, {cam_3d[2]*1000:.1f}] mm")
                if end_3d is not None:
                    tip_lines.append(f"End: [{end_3d[0]:.1f}, {end_3d[1]:.1f}, {end_3d[2]:.1f}] mm")

                # 计算 Tooltip 弹出位置，避免超出边界
                box_w = 230
                box_h = len(tip_lines) * 18 + 14
                bx = mx + 16 if mx + box_w + 20 < w else mx - box_w - 16
                by = my - box_h - 10 if my - box_h - 10 > 40 else my + 20

                # 绘制半透明 Tooltip 背景
                overlay = canvas.copy()
                cv2.rectangle(overlay, (bx, by), (bx + box_w, by + box_h), (20, 22, 28), -1)
                cv2.addWeighted(overlay, 0.85, canvas, 0.15, 0, canvas)
                cv2.rectangle(canvas, (bx, by), (bx + box_w, by + box_h), (0, 255, 200), 1)

                for idx, line in enumerate(tip_lines):
                    color = (0, 255, 255) if "Depth" in line else ((0, 255, 120) if "Cam" in line else (240, 240, 240))
                    cv2.putText(canvas, line, (bx + 8, by + 16 + idx * 18), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1, cv2.LINE_AA)

        return canvas

    def render_detections(self, img: np.ndarray, detections: List[Dict[str, Any]]) -> np.ndarray:
        """在画面上渲染目标检测识别框与空间三维向量"""
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            conf = det["conf"]
            name = det["class_name"]
            d_m = det["depth_m"]
            pt_3d = det.get("cam_3d")

            # 边框与标签
            cv2.rectangle(img, (x1, y1), (x2, y2), (255, 100, 0), 2, cv2.LINE_AA)
            label = f"{name} {conf:.2f}"
            if d_m > 0:
                label += f" | {d_m*1000:.0f}mm"

            cv2.rectangle(img, (x1, y1 - 20), (x1 + len(label) * 9 + 10, y1), (255, 100, 0), -1)
            cv2.putText(img, label, (x1 + 4, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)

            # 中心点
            cx, cy = det["center"]
            cv2.circle(img, (cx, cy), 4, (0, 0, 255), -1)

            if pt_3d is not None:
                pt_str = f"({pt_3d[0]*1000:.0f}, {pt_3d[1]*1000:.0f}, {pt_3d[2]*1000:.0f})mm"
                cv2.putText(img, pt_str, (cx - 40, cy + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 255), 1, cv2.LINE_AA)
        return img

    def compose_frame(self) -> Optional[np.ndarray]:
        """按当前 display_mode 拼装可视化渲染画布"""
        with self.lock:
            if self.latest_color is None or self.latest_depth_colored is None:
                return None
            color = self.latest_color.copy()
            depth_color = self.latest_depth_colored.copy()
            ir1 = self.latest_ir1.copy() if self.latest_ir1 is not None else None
            ir2 = self.latest_ir2.copy() if self.latest_ir2 is not None else None
            detections = list(self.latest_detections)

        # 叠加 YOLO 检测
        if self.enable_detection and detections:
            color = self.render_detections(color, detections)

        mode = self.display_mode.lower()
        canvas = None

        if mode == "color":
            # 纯彩色
            canvas = color
            canvas = self.render_inspection(canvas)

        elif mode == "depth":
            # 纯深度 (带垂直标尺)
            canvas = self.add_vertical_colorbar(depth_color)
            canvas = self.render_inspection(canvas)

        elif mode == "overlay":
            # 空间融合模式
            # 确保尺寸一致
            if depth_color.shape[:2] != color.shape[:2]:
                depth_resized = cv2.resize(depth_color, (color.shape[1], color.shape[0]))
            else:
                depth_resized = depth_color
            canvas = cv2.addWeighted(color, 1.0 - self.overlay_alpha, depth_resized, self.overlay_alpha, 0)
            canvas = self.render_inspection(canvas)

        elif mode == "quad" and self.enable_ir and ir1 is not None and ir2 is not None:
            # 四分屏网格
            target_w, target_h = 640, 360
            c_r = cv2.resize(color, (target_w, target_h))
            d_r = cv2.resize(depth_color, (target_w, target_h))
            i1_r = cv2.resize(ir1, (target_w, target_h))
            i2_r = cv2.resize(ir2, (target_w, target_h))

            # 添加标签
            cv2.putText(c_r, "RGB Stream", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.putText(d_r, "Depth Colormap", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.putText(i1_r, "Infrared 1 (Left)", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
            cv2.putText(i2_r, "Infrared 2 (Right)", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)

            top_row = np.hstack([c_r, d_r])
            bot_row = np.hstack([i1_r, i2_r])
            canvas = np.vstack([top_row, bot_row])

        else:
            # 默认: Side-by-Side 并排模式
            # 统一高度，按比例平铺展示
            h_c, w_c = color.shape[:2]
            h_d, w_d = depth_color.shape[:2]

            # 目标统一为高度 540 或 720
            target_h = 540
            scale_c = target_h / h_c
            scale_d = target_h / h_d

            target_w_c = int(w_c * scale_c)
            target_w_d = int(w_d * scale_d)

            color_scaled = cv2.resize(color, (target_w_c, target_h), interpolation=cv2.INTER_LINEAR)
            depth_scaled = cv2.resize(depth_color, (target_w_d, target_h), interpolation=cv2.INTER_NEAREST)

            # 在深度图右侧附加上色带 Colorbar
            depth_with_bar = self.add_vertical_colorbar(depth_scaled, width=32)

            # 标题标头
            cv2.putText(color_scaled, "RGB Color Stream", (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)
            cv2.putText(depth_with_bar, "Depth Colormap Stream", (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2, cv2.LINE_AA)

            canvas = np.hstack([color_scaled, depth_with_bar])

            # 映射坐标函数 (Side-by-Side 左侧为 Color，右侧为 Depth)
            def mapper(u, v):
                # 如果点击在左侧 (Color 区域)
                return int(u * scale_c), int(v * scale_c)

            canvas = self.render_inspection(canvas, coord_mapper=mapper)

        # 叠加全局 HUD
        canvas = self.render_hud(canvas)
        return canvas

    def handle_mouse_event(self, event: int, x: int, y: int, flags: int, param: Any):
        """处理 OpenCV 本地窗口鼠标事件"""
        self.mouse_x = x
        self.mouse_y = y

        # 将窗口像素坐标反算回原始图像像素坐标
        with self.lock:
            if self.latest_depth_raw is None:
                return
            h_raw, w_raw = self.latest_depth_raw.shape[:2]

        orig_u, orig_v = self._map_window_to_raw_pixel(x, y, w_raw, h_raw)
        if 0 <= orig_u < w_raw and 0 <= orig_v < h_raw:
            with self.lock:
                d_val = float(self.latest_depth_raw[orig_v, orig_u]) * self.depth_scale
            cam_3d = self.deproject_to_3d((orig_u, orig_v), d_val) if d_val > 0 else None
            end_3d = self.transform_to_end(cam_3d) if cam_3d is not None else None

            self.hover_info = {
                "pixel": (orig_u, orig_v),
                "depth_m": d_val,
                "cam_3d": cam_3d,
                "end_3d": end_3d
            }
        else:
            self.hover_info = None

        # 鼠标左键点击: 标记点 A / 点 B
        if event == cv2.EVENT_LBUTTONDOWN:
            if self.hover_info and self.hover_info["depth_m"] > 0:
                if self.point_a is None:
                    self.point_a = dict(self.hover_info)
                    self.set_notification("已设置标记点 Point A")
                elif self.point_b is None:
                    self.point_b = dict(self.hover_info)
                    dist = np.linalg.norm(self.point_a["cam_3d"] - self.point_b["cam_3d"]) * 1000.0
                    self.set_notification(f"已设置 Point B | 3D距离: {dist:.1f} mm")
                else:
                    # 重置并从 A 开始
                    self.point_a = dict(self.hover_info)
                    self.point_b = None
                    self.set_notification("重新设置标记点 Point A")

        # 鼠标右键点击: 清除标记
        elif event == cv2.EVENT_RBUTTONDOWN:
            self.point_a = None
            self.point_b = None
            self.set_notification("已清空所有 3D 测量标记点")

    def _map_window_to_raw_pixel(self, win_x: int, win_y: int, raw_w: int, raw_h: int) -> Tuple[int, int]:
        """将绘制窗口上的坐标反算回原始相机流像素 (u, v)"""
        mode = self.display_mode.lower()
        if mode == "side-by-side":
            target_h = 540
            scale_c = target_h / self.color_height
            scale_d = target_h / self.depth_height
            w_c_disp = int(self.color_width * scale_c)

            if win_x < w_c_disp:
                # 点击在彩色区域
                u = int(win_x / scale_c)
                v = int(win_y / scale_c)
            else:
                # 点击在深度区域
                u = int((win_x - w_c_disp) / scale_d)
                v = int(win_y / scale_d)
            return u, v
        elif mode in ["color", "overlay"]:
            scale = raw_h / self.color_height
            return win_x, win_y
        elif mode == "depth":
            return win_x, win_y
        return win_x, win_y

    def save_snapshot(self) -> Optional[str]:
        """捕获完整无损快照并导出三维彩色点云 (.ply) 与元数据"""
        with self.lock:
            if self.latest_color is None or self.latest_depth_raw is None or self.latest_depth_frame is None:
                self.set_notification("快照失败: 未接收到有效图像帧")
                return None
            color_img = self.latest_color.copy()
            depth_raw = self.latest_depth_raw.copy()
            depth_color = self.latest_depth_colored.copy() if self.latest_depth_colored is not None else None
            depth_frame = self.latest_depth_frame
            color_frame = self.latest_color_frame

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        snap_dir = self.save_dir / f"capture_{ts}"
        snap_dir.mkdir(parents=True, exist_ok=True)

        # 1. 保存彩色图
        color_path = snap_dir / "color.png"
        cv2.imwrite(str(color_path), color_img)

        # 2. 保存 16 位无损毫米深度图 (uint16)
        depth_path = snap_dir / "depth_raw16.png"
        cv2.imwrite(str(depth_path), depth_raw)

        # 3. 保存伪彩色深度图
        if depth_color is not None:
            cv2.imwrite(str(snap_dir / "depth_colored.png"), depth_color)

        # 4. 保存当前合成的屏幕截图
        if self.latest_display_frame is not None:
            cv2.imwrite(str(snap_dir / "display_hud.png"), self.latest_display_frame)

        # 5. 生成并导出 3D 彩色点云 PLY 文件
        ply_path = snap_dir / "pointcloud.ply"
        try:
            if self.pointcloud is not None and depth_frame and color_frame:
                self.pointcloud.map_to(color_frame)
                points = self.pointcloud.calculate(depth_frame)
                points.export_to_ply(str(ply_path), color_frame)
                logger.info(f"成功导出彩色 3D 点云文件: {ply_path}")
        except Exception as e:
            logger.warning(f"导出点云 PLY 异常: {e}")

        # 6. 保存内参与相机标定元数据 JSON
        meta = {
            "timestamp": ts,
            "device_name": self.device_name,
            "serial_number": self.serial_number,
            "usb_type": self.usb_type,
            "color_resolution": [self.color_width, self.color_height],
            "depth_resolution": [self.depth_width, self.depth_height],
            "fps": self.fps,
            "depth_scale_meter": self.depth_scale,
            "min_depth_meter": self.min_depth,
            "max_depth_meter": self.max_depth,
            "aligned_to_color": self.align_to_color,
            "color_intrinsics": {
                "fx": self.color_intrinsics.fx if self.color_intrinsics else None,
                "fy": self.color_intrinsics.fy if self.color_intrinsics else None,
                "ppx": self.color_intrinsics.ppx if self.color_intrinsics else None,
                "ppy": self.color_intrinsics.ppy if self.color_intrinsics else None,
                "model": str(self.color_intrinsics.model) if self.color_intrinsics else None,
                "coeffs": list(self.color_intrinsics.coeffs) if self.color_intrinsics else None,
            } if self.color_intrinsics else {},
            "hand_eye_matrix_T_end_to_cam": self.T_end_to_camera.tolist() if self.T_end_to_camera is not None else None
        }
        with open(snap_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        msg = f"快照与 3D 点云已保存至: {snap_dir.name}"
        logger.info(f"快照保存成功: {snap_dir}")
        self.set_notification(msg)
        return str(snap_dir)


# ==============================================================================
# 轻量级多线程 HTTP Web 流媒体服务器 (支持远程浏览器实时预览与点位测量)
# ==============================================================================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Intel RealSense D435 远程实时可视化监控台</title>
    <style>
        :root {
            --bg-primary: #0f1117;
            --bg-secondary: #1a1d24;
            --bg-card: #232732;
            --accent-cyan: #00d2ff;
            --accent-blue: #3a7bd5;
            --accent-green: #00e676;
            --accent-warn: #ffab00;
            --text-main: #f0f4f8;
            --text-sub: #94a3b8;
            --border-color: #2e3442;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background-color: var(--bg-primary);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            display: flex;
            flex-direction: column;
            min-height: 100vh;
        }
        header {
            background: linear-gradient(135deg, var(--bg-secondary), var(--bg-card));
            padding: 14px 24px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
        }
        .logo-area { display: flex; align-items: center; gap: 12px; }
        .logo-title { font-size: 1.25rem; font-weight: 700; color: #fff; letter-spacing: 0.5px; }
        .logo-badge {
            background: linear-gradient(90deg, var(--accent-cyan), var(--accent-blue));
            color: #000;
            font-size: 0.72rem;
            font-weight: 800;
            padding: 3px 8px;
            border-radius: 4px;
            text-transform: uppercase;
        }
        .header-stats { display: flex; gap: 16px; font-size: 0.85rem; color: var(--text-sub); }
        .stat-item span { color: var(--accent-cyan); font-weight: 600; margin-left: 4px; }
        
        main {
            display: flex;
            flex: 1;
            padding: 20px;
            gap: 20px;
            max-width: 1800px;
            margin: 0 auto;
            width: 100%;
        }
        .viewport-section {
            flex: 3;
            display: flex;
            flex-direction: column;
            background: var(--bg-secondary);
            border-radius: 12px;
            border: 1px solid var(--border-color);
            padding: 16px;
            position: relative;
        }
        .stream-container {
            position: relative;
            background: #000;
            border-radius: 8px;
            overflow: hidden;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 520px;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.8);
        }
        #stream-img {
            max-width: 100%;
            height: auto;
            display: block;
            cursor: crosshair;
            user-select: none;
        }
        .stream-overlay {
            position: absolute;
            top: 12px;
            left: 12px;
            background: rgba(15, 17, 23, 0.75);
            backdrop-filter: blur(8px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 8px 14px;
            border-radius: 6px;
            font-size: 0.8rem;
            line-height: 1.5;
            pointer-events: none;
        }
        .control-panel {
            flex: 1;
            min-width: 320px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        .card {
            background: var(--bg-secondary);
            border-radius: 12px;
            border: 1px solid var(--border-color);
            padding: 18px;
        }
        .card-title {
            font-size: 0.95rem;
            font-weight: 700;
            color: var(--accent-cyan);
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .btn-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }
        button {
            background: var(--bg-card);
            color: var(--text-main);
            border: 1px solid var(--border-color);
            padding: 10px 14px;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
        }
        button:hover {
            background: #2e3445;
            border-color: var(--accent-cyan);
            color: #fff;
            transform: translateY(-1px);
        }
        button.active {
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
            color: #000;
            border-color: transparent;
            font-weight: 700;
        }
        .btn-primary {
            grid-column: span 2;
            background: linear-gradient(135deg, #00b0ff, #0081cb);
            color: #fff;
            font-size: 0.9rem;
            padding: 12px;
            border: none;
        }
        .btn-primary:hover { background: linear-gradient(135deg, #40c4ff, #0091ea); }
        .btn-danger {
            background: #d32f2f;
            color: #fff;
            border: none;
        }
        .btn-danger:hover { background: #f44336; }
        
        .param-group { margin-bottom: 12px; }
        .param-label {
            display: flex;
            justify-content: space-between;
            font-size: 0.8rem;
            color: var(--text-sub);
            margin-bottom: 6px;
        }
        .range-slider {
            width: 100%;
            accent-color: var(--accent-cyan);
            cursor: pointer;
        }
        .inspect-box {
            background: #141720;
            border: 1px solid #282e3d;
            border-radius: 8px;
            padding: 12px;
            font-family: monospace;
            font-size: 0.82rem;
            line-height: 1.6;
        }
        .inspect-box span { color: var(--accent-green); }
        #toast {
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: var(--accent-green);
            color: #000;
            font-weight: 700;
            padding: 12px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.4);
            transform: translateY(100px);
            opacity: 0;
            transition: all 0.3s ease;
            z-index: 999;
        }
        #toast.show { transform: translateY(0); opacity: 1; }
    </style>
</head>
<body>
    <header>
        <div class="logo-area">
            <div class="logo-title">Intel RealSense D435</div>
            <div class="logo-badge">Remote Inspector</div>
        </div>
        <div class="header-stats">
            <div class="stat-item">FPS: <span id="val-fps">--</span></div>
            <div class="stat-item">Device: <span id="val-dev">D435i</span></div>
            <div class="stat-item">USB: <span id="val-usb">3.2</span></div>
            <div class="stat-item">Status: <span id="val-status" style="color: var(--accent-green);">STREAMING</span></div>
        </div>
    </header>

    <main>
        <section class="viewport-section">
            <div class="stream-container">
                <img id="stream-img" src="/stream.mjpg" alt="RealSense Live Stream">
                <div class="stream-overlay" id="stream-hud">
                    Mode: <span id="hud-mode">Side-by-Side</span> | Cmap: <span id="hud-cmap">Turbo</span><br>
                    Range: <span id="hud-range">0.15m - 3.00m</span>
                </div>
            </div>
        </section>

        <aside class="control-panel">
            <div class="card">
                <div class="card-title">📺 视角布局切换</div>
                <div class="btn-grid">
                    <button class="active" onclick="setMode('side-by-side')">并排对比</button>
                    <button onclick="setMode('color')">纯彩色</button>
                    <button onclick="setMode('depth')">纯深度</button>
                    <button onclick="setMode('overlay')">空间融合</button>
                </div>
            </div>

            <div class="card">
                <div class="card-title">🎨 深度伪彩色谱</div>
                <div class="btn-grid">
                    <button class="active" onclick="setCmap('turbo')">Turbo</button>
                    <button onclick="setCmap('jet')">Jet</button>
                    <button onclick="setCmap('inferno')">Inferno</button>
                    <button onclick="setCmap('viridis')">Viridis</button>
                    <button onclick="setCmap('bone')">Bone</button>
                    <button onclick="setCmap('ocean')">Ocean</button>
                </div>
            </div>

            <div class="card">
                <div class="card-title">⚙️ 深度范围截断</div>
                <div class="param-group">
                    <div class="param-label"><span>近景阈值 (Min Depth)</span><span id="txt-min-depth">0.15 m</span></div>
                    <input type="range" class="range-slider" min="0.05" max="1.5" step="0.05" value="0.15" onchange="setRange('min', this.value)">
                </div>
                <div class="param-group">
                    <div class="param-label"><span>远景阈值 (Max Depth)</span><span id="txt-max-depth">3.00 m</span></div>
                    <input type="range" class="range-slider" min="1.0" max="6.0" step="0.2" value="3.0" onchange="setRange('max', this.value)">
                </div>
            </div>

            <div class="card">
                <div class="card-title">🎯 交互功能开关</div>
                <div class="btn-grid">
                    <button id="btn-align" onclick="toggleOption('align')">对齐: 开</button>
                    <button id="btn-filter" onclick="toggleOption('filter')">滤波: 关</button>
                    <button id="btn-detect" onclick="toggleOption('detect')">YOLO: 关</button>
                    <button class="btn-danger" onclick="clearPoints()">清空测量点</button>
                    <button class="btn-primary" onclick="takeSnapshot()">📸 一键保存快照与 3D 点云</button>
                </div>
            </div>

            <div class="card">
                <div class="card-title">📍 3D 点位测量探测 (点击视频画面)</div>
                <div class="inspect-box" id="inspect-result">
                    点击画面任意位置获取深度与 3D 坐标<br>
                    Pixel: <span>(---, ---)</span><br>
                    Distance: <span>--- mm</span><br>
                    Camera 3D: <span>[X: ---, Y: ---, Z: ---]</span><br>
                    End Flange: <span>[X: ---, Y: ---, Z: ---]</span>
                </div>
            </div>
        </aside>
    </main>

    <div id="toast">快照已成功导出！</div>

    <script>
        function showToast(msg) {
            const t = document.getElementById('toast');
            t.innerText = msg;
            t.classList.add('show');
            setTimeout(() => t.classList.remove('show'), 3000);
        }

        function sendControl(data) {
            fetch('/api/control', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            }).then(r => r.json()).then(res => {
                if (res.msg) showToast(res.msg);
                updateStatus();
            });
        }

        function setMode(mode) { sendControl({mode: mode}); }
        function setCmap(cmap) { sendControl({colormap: cmap}); }
        function setRange(type, val) {
            if(type === 'min') {
                document.getElementById('txt-min-depth').innerText = parseFloat(val).toFixed(2) + ' m';
                sendControl({min_depth: parseFloat(val)});
            } else {
                document.getElementById('txt-max-depth').innerText = parseFloat(val).toFixed(2) + ' m';
                sendControl({max_depth: parseFloat(val)});
            }
        }
        function toggleOption(opt) { sendControl({toggle: opt}); }
        function clearPoints() { sendControl({action: 'clear_points'}); }
        function takeSnapshot() { sendControl({action: 'snapshot'}); }

        // 监听画面点击获取 3D 坐标
        const img = document.getElementById('stream-img');
        img.addEventListener('click', function(e) {
            const rect = img.getBoundingClientRect();
            const normX = (e.clientX - rect.left) / rect.width;
            const normY = (e.clientY - rect.top) / rect.height;
            fetch(`/api/inspect?nx=${normX}&ny=${normY}`)
                .then(r => r.json())
                .then(d => {
                    if (d.success) {
                        let html = `Pixel: <span>(${d.pixel[0]}, ${d.pixel[1]})</span><br>`;
                        html += `Distance: <span>${(d.depth_m * 1000).toFixed(0)} mm (${d.depth_m.toFixed(3)} m)</span><br>`;
                        if (d.cam_3d) {
                            html += `Camera 3D: <span>[X: ${(d.cam_3d[0]*1000).toFixed(1)}, Y: ${(d.cam_3d[1]*1000).toFixed(1)}, Z: ${(d.cam_3d[2]*1000).toFixed(1)}] mm</span><br>`;
                        }
                        if (d.end_3d) {
                            html += `End Flange: <span>[X: ${d.end_3d[0].toFixed(1)}, Y: ${d.end_3d[1].toFixed(1)}, Z: ${d.end_3d[2].toFixed(1)}] mm</span>`;
                        }
                        document.getElementById('inspect-result').innerHTML = html;
                    }
                });
        });

        // 轮询状态
        function updateStatus() {
            fetch('/api/status').then(r => r.json()).then(s => {
                document.getElementById('val-fps').innerText = s.fps.toFixed(1);
                document.getElementById('val-dev').innerText = s.device;
                document.getElementById('val-usb').innerText = s.usb;
                document.getElementById('hud-mode').innerText = s.mode;
                document.getElementById('hud-cmap').innerText = s.colormap;
                document.getElementById('hud-range').innerText = `${s.min_depth.toFixed(2)}m - ${s.max_depth.toFixed(2)}m`;
                document.getElementById('btn-align').innerText = '对齐: ' + (s.align ? '开' : '关');
                document.getElementById('btn-filter').innerText = '滤波: ' + (s.filter ? '开' : '关');
                document.getElementById('btn-detect').innerText = 'YOLO: ' + (s.detect ? '开' : '关');
            }).catch(() => {});
        }
        setInterval(updateStatus, 1500);
        updateStatus();
    </script>
</body>
</html>
"""

class WebStreamHandler(BaseHTTPRequestHandler):
    visualizer: Optional[D435Visualizer] = None

    def log_message(self, format, *args):
        # 静默常规 HTTP 请求日志，保持终端清爽
        return

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ["/", "/index.html"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))

        elif path == "/stream.mjpg":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()

            while self.visualizer and self.visualizer.is_running:
                frame = self.visualizer.compose_frame()
                if frame is not None:
                    # 编码为 JPEG
                    ret, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if ret:
                        data = jpeg.tobytes()
                        self.wfile.write(b"--frame\r\n")
                        self.send_header("Content-Type", "image/jpeg")
                        self.send_header("Content-Length", str(len(data)))
                        self.end_headers()
                        self.wfile.write(data)
                        self.wfile.write(b"\r\n")
                time.sleep(0.033)  # ~30 FPS

        elif path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            vis = self.visualizer
            status = {
                "fps": vis.current_fps if vis else 0.0,
                "device": vis.device_name if vis else "RealSense",
                "usb": vis.usb_type if vis else "USB 3.x",
                "mode": vis.display_mode if vis else "side-by-side",
                "colormap": COLORMAP_KEYS[vis.colormap_idx] if vis else "turbo",
                "min_depth": vis.min_depth if vis else 0.15,
                "max_depth": vis.max_depth if vis else 3.0,
                "align": vis.align_to_color if vis else True,
                "filter": vis.enable_filter if vis else False,
                "detect": vis.enable_detection if vis else False
            }
            self.wfile.write(json.dumps(status).encode("utf-8"))

        elif path == "/api/inspect":
            qs = parse_qs(parsed.query)
            vis = self.visualizer
            if vis and "nx" in qs and "ny" in qs:
                nx = float(qs["nx"][0])
                ny = float(qs["ny"][0])
                with vis.lock:
                    if vis.latest_depth_raw is not None:
                        h, w = vis.latest_depth_raw.shape[:2]
                        px = int(np.clip(nx * w, 0, w - 1))
                        py = int(np.clip(ny * h, 0, h - 1))
                        d_val = float(vis.latest_depth_raw[py, px]) * vis.depth_scale
                        cam_3d = vis.deproject_to_3d((px, py), d_val) if d_val > 0 else None
                        end_3d = vis.transform_to_end(cam_3d) if cam_3d is not None else None

                        res = {
                            "success": True,
                            "pixel": [px, py],
                            "depth_m": d_val,
                            "cam_3d": cam_3d.tolist() if cam_3d is not None else None,
                            "end_3d": end_3d.tolist() if end_3d is not None else None
                        }
                    else:
                        res = {"success": False}
            else:
                res = {"success": False}

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/control":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body)
            vis = self.visualizer
            res = {"success": True}

            if vis:
                if "mode" in data:
                    vis.display_mode = data["mode"]
                if "colormap" in data and data["colormap"] in COLORMAP_KEYS:
                    vis.colormap_idx = COLORMAP_KEYS.index(data["colormap"])
                if "min_depth" in data:
                    vis.min_depth = max(0.05, float(data["min_depth"]))
                if "max_depth" in data:
                    vis.max_depth = max(vis.min_depth + 0.1, float(data["max_depth"]))
                if "toggle" in data:
                    t = data["toggle"]
                    if t == "align":
                        vis.align_to_color = not vis.align_to_color
                        vis.align = rs.align(rs.stream.color) if vis.align_to_color else None
                    elif t == "filter":
                        vis.enable_filter = not vis.enable_filter
                    elif t == "detect":
                        vis.enable_detection = not vis.enable_detection
                        if vis.enable_detection and vis.detector_model is None:
                            # 尝试加载默认模型
                            m_path = vis.detect_model_path or "models/cable.pt"
                            vis._init_detector(m_path)
                if "action" in data:
                    act = data["action"]
                    if act == "clear_points":
                        vis.point_a = None
                        vis.point_b = None
                        res["msg"] = "测量点位已清空"
                    elif act == "snapshot":
                        saved_path = vis.save_snapshot()
                        res["msg"] = f"快照已保存: {Path(saved_path).name}" if saved_path else "快照保存失败"

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))


# ==============================================================================
# 主循环与 CLI 命令行解析入口
# ==============================================================================
def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Intel RealSense D435 / D435i 工业级综合可视化与 3D 测量诊断工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
快捷键说明 (Local GUI 模式):
  [Q] / [ESC]  : 退出程序
  [S]          : 保存当前快照 (RGB原图, 16位深度图, 伪彩色深度图, 3D点云 .ply, 内参元数据 .json)
  [M]          : 切换显示模式 (side-by-side -> color -> depth -> overlay -> quad)
  [C]          : 切换深度伪彩色谱 (turbo -> jet -> inferno -> viridis -> bone -> ocean)
  [A]          : 开启/关闭深度到彩色硬件对齐 (Align to Color)
  [F]          : 开启/关闭 RealSense 空间/时间/空洞滤波链 (Post-Processing Filters)
  [D]          : 开启/关闭 YOLO 目标检测模型联动
  [+] / [-]    : 调节最大截断深度 (Max Depth)
  [[] / []]    : 调节最小截断深度 (Min Depth)
  [H]          : 显示/隐藏底部帮助提示栏
  [鼠标左键]    : 设置测距点 A / 点 B (自动计算两点间三维欧式空间距离)
  [鼠标右键]    : 清除测距点 A / B

示例:
  python tools/visualize_d435.py                      # 启动默认 GUI 桌面窗口并排显示
  python tools/visualize_d435.py --web --port 8088     # 启动远程 Web 交互可视化服务器
  python tools/visualize_d435.py --detect              # 启动并开启 YOLO 线缆识别叠加
  python tools/visualize_d435.py --ir                  # 启用红外双目视频流 (Quad 模式)
        """
    )

    # 视频流分辨率与帧率
    cam_cfg = SYSTEM_CONFIG.get("vision", {}).get("camera", {})
    parser.add_argument("--width", type=int, default=cam_cfg.get("color_width", 1280), help="彩色流宽度 (默认: 1280)")
    parser.add_argument("--height", type=int, default=cam_cfg.get("color_height", 720), help="彩色流高度 (默认: 720)")
    parser.add_argument("--depth-width", type=int, default=cam_cfg.get("depth_width", 848), help="深度流宽度 (默认: 848)")
    parser.add_argument("--depth-height", type=int, default=cam_cfg.get("depth_height", 480), help="深度流高度 (默认: 480)")
    parser.add_argument("--fps", type=int, default=cam_cfg.get("fps", 30), help="视频流帧率 (默认: 30)")

    # 模式与参数
    parser.add_argument("--mode", type=str, default="side-by-side", choices=["side-by-side", "color", "depth", "overlay", "quad"], help="初始显示模式")
    parser.add_argument("--colormap", type=str, default="turbo", choices=COLORMAP_KEYS, help="初始深度伪彩色 (默认: turbo)")
    parser.add_argument("--min-depth", type=float, default=0.15, help="最小有效截断深度 (米, 默认: 0.15)")
    parser.add_argument("--max-depth", type=float, default=3.0, help="最大有效截断深度 (米, 默认: 3.0)")
    parser.add_argument("--no-align", action="store_true", help="禁用深度到彩色对齐")
    parser.add_argument("--filter", action="store_true", help="默认开启后处理硬件滤波 (Spatial + Temporal + Hole-filling)")
    parser.add_argument("--ir", action="store_true", help="启用红外 IR1 / IR2 视频流")

    # AI 目标检测
    default_model = SYSTEM_CONFIG.get("vision", {}).get("model_path", "models/cable.pt")
    if not os.path.exists(default_model) and os.path.exists("models/cable.pt"):
        default_model = "models/cable.pt"
    parser.add_argument("--detect", action="store_true", help="启用 YOLO 目标识别联动")
    parser.add_argument("--model", type=str, default=default_model, help="YOLO 模型权重路径")

    # 存储与 Web
    parser.add_argument("--output", type=str, default="data/captures", help="快照与点云存储路径 (默认: data/captures)")
    parser.add_argument("--web", action="store_true", help="启动多线程 Web 实时流服务器")
    parser.add_argument("--port", type=int, default=8088, help="Web 服务器端口 (默认: 8088)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Web 监听主机地址 (默认: 0.0.0.0)")
    parser.add_argument("--headless", action="store_true", help="无头模式运行 (不打开本地 GUI 窗口)")

    return parser.parse_args()


def main():
    args = parse_arguments()

    visualizer = D435Visualizer(
        color_res=(args.width, args.height),
        depth_res=(args.depth_width, args.depth_height),
        fps=args.fps,
        enable_ir=args.ir,
        align_to_color=not args.no_align,
        enable_filter=args.filter,
        min_depth=args.min_depth,
        max_depth=args.max_depth,
        colormap=args.colormap,
        display_mode=args.mode,
        detect_model=args.model if args.detect else None,
        save_dir=args.output
    )

    if not visualizer.start_camera():
        logger.error("无法启动 RealSense D435 相机，请检查 USB3.0 线缆连接或占用状态。")
        sys.exit(1)

    # 检查是否需要启动 Web 服务端
    web_server = None
    if args.web or args.headless or not os.environ.get("DISPLAY"):
        WebStreamHandler.visualizer = visualizer
        try:
            web_server = ThreadingHTTPServer((args.host, args.port), WebStreamHandler)
            web_thread = threading.Thread(target=web_server.serve_forever, daemon=True)
            web_thread.start()
            logger.info("================================================================")
            logger.info(f"🌐 远程 Web 可视化服务器已启动: http://{args.host}:{args.port}")
            logger.info(f"   在浏览器中打开该地址即可远程查看实时流并点击测距！")
            logger.info("================================================================")
        except Exception as e:
            logger.error(f"启动 Web 服务器失败: {e}")

    # 是否可启动本地桌面 GUI
    use_gui = not args.headless and bool(os.environ.get("DISPLAY"))
    win_name = "RealSense D435 Visualizer (Press 'H' for Help, 'Q' to Quit)"

    if use_gui:
        try:
            cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(win_name, 1280, 580)
            cv2.setMouseCallback(win_name, visualizer.handle_mouse_event)
            logger.info("本地 OpenCV GUI 窗口已启动。")
        except Exception as e:
            logger.warning(f"无法初始化本地桌面 GUI ({e})，将回退到无头/Web流模式。")
            use_gui = False

    logger.info("可视化主循环启动。按 'q' 键或 Ctrl+C 退出。")

    try:
        while visualizer.is_running:
            success = visualizer.process_frames()
            if not success:
                time.sleep(0.01)
                continue

            frame_to_show = visualizer.compose_frame()
            if frame_to_show is not None:
                with visualizer.lock:
                    visualizer.latest_display_frame = frame_to_show

                if use_gui:
                    cv2.imshow(win_name, frame_to_show)
                    key = cv2.waitKey(1) & 0xFF

                    if key in [ord('q'), 27]:  # 'q' 或 ESC
                        logger.info("收到退出指令，正在退出...")
                        break
                    elif key == ord('s'):      # 快照
                        visualizer.save_snapshot()
                    elif key == ord('m'):      # 模式循环
                        modes = ["side-by-side", "color", "depth", "overlay"]
                        if visualizer.enable_ir:
                            modes.append("quad")
                        curr_i = modes.index(visualizer.display_mode) if visualizer.display_mode in modes else 0
                        visualizer.display_mode = modes[(curr_i + 1) % len(modes)]
                        visualizer.set_notification(f"切换显示模式: {visualizer.display_mode.upper()}")
                    elif key == ord('c'):      # 色彩循环
                        visualizer.colormap_idx = (visualizer.colormap_idx + 1) % len(COLORMAP_KEYS)
                        c_name = COLORMAP_DICT[COLORMAP_KEYS[visualizer.colormap_idx]][1].split()[0]
                        visualizer.set_notification(f"切换色谱: {c_name}")
                    elif key == ord('a'):      # 对齐开关
                        visualizer.align_to_color = not visualizer.align_to_color
                        visualizer.align = rs.align(rs.stream.color) if visualizer.align_to_color else None
                        visualizer.set_notification(f"深度对齐 (Align): {'ON' if visualizer.align_to_color else 'OFF'}")
                    elif key == ord('f'):      # 滤波开关
                        visualizer.enable_filter = not visualizer.enable_filter
                        visualizer.set_notification(f"硬件滤波 (Filter): {'ON' if visualizer.enable_filter else 'OFF'}")
                    elif key == ord('d'):      # 目标检测
                        visualizer.enable_detection = not visualizer.enable_detection
                        if visualizer.enable_detection and visualizer.detector_model is None:
                            visualizer._init_detector(args.model)
                        visualizer.set_notification(f"YOLO 目标检测: {'ON' if visualizer.enable_detection else 'OFF'}")
                    elif key in [ord('+'), ord('=')]:
                        visualizer.max_depth = min(10.0, visualizer.max_depth + 0.2)
                        visualizer.set_notification(f"最大深度: {visualizer.max_depth:.2f} m")
                    elif key in [ord('-'), ord('_')]:
                        visualizer.max_depth = max(visualizer.min_depth + 0.2, visualizer.max_depth - 0.2)
                        visualizer.set_notification(f"最大深度: {visualizer.max_depth:.2f} m")
                    elif key == ord(']'):
                        visualizer.min_depth = min(visualizer.max_depth - 0.2, visualizer.min_depth + 0.05)
                        visualizer.set_notification(f"最小深度: {visualizer.min_depth:.2f} m")
                    elif key == ord('['):
                        visualizer.min_depth = max(0.05, visualizer.min_depth - 0.05)
                        visualizer.set_notification(f"最小深度: {visualizer.min_depth:.2f} m")
                    elif key == ord('r'):      # 清空标记
                        visualizer.point_a = None
                        visualizer.point_b = None
                        visualizer.set_notification("清空所有测量点")
                    elif key == ord('h'):      # 帮助栏
                        visualizer.show_help = not visualizer.show_help

            if not use_gui:
                time.sleep(0.01)

    except KeyboardInterrupt:
        logger.info("收到 Ctrl+C 中断信号，正在退出...")

    finally:
        visualizer.stop_camera()
        if use_gui:
            cv2.destroyAllWindows()
        if web_server:
            web_server.shutdown()
        logger.info("程序正常退出。")


if __name__ == "__main__":
    main()
