#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YOLOv8 模型训练样本图片采集工具
(Training Images Collector for Intel RealSense D435 / D435i)

主要功能:
1. 样本采集输出:
   - 默认采集并保存至项目根目录 `images/` 目录下 (支持通过 --output 自定义)
   - 自动扫描目录中已存在的图像编号，支持增量续采 (如已有 cable_0050.jpg，则自动从 0051 开始计数)
   - 自动生成 `images/classes.txt` (默认写入 'cable' 类别标签)，原生兼容 X-AnyLabeling / LabelImg 标注流程
2. 多种采集触发模式:
   - 手动单帧采集: 按空格键 [Space]、回车 [Enter] 或 [S] 键手动抓取单帧 (适合不同姿态、光照调整)
   - 定时连续自动采集: 按 [A] 键开启/暂停自动连续采集 (默认每隔 1.0 秒自动记录一张，附带倒计时与进度条)
   - 撤销防呆机制: 若刚拍的图像存在模糊或遮挡，按 [Backspace] 或 [D] 键立即撤销/删除上一张采集的图片并回退计数
3. 辅助取景与 HUD 看板:
   - 实时显示采集进度条与目标完成度 (例如 45 / 300 张，15.0%)
   - 辅助九宫格构图线与中心十字线 (按 [G] 键切换)，方便对齐电缆视野与主体居中
   - 快门闪烁视觉反馈动画 (Capture Flash)，拍摄瞬间屏幕亮绿框反馈
4. 双模运行支持 (桌面 GUI + 远程 Web 端):
   - 本地桌面 GUI 模式: OpenCV 实时窗口交互，支持键盘快捷键与鼠标操作
   - 远程 Web 交互模式 (--web): 内置轻量级 HTTP 实时流与控制台，手机/平板/电脑浏览器访问即可远程点击拍照与连拍！
"""

import os
import sys
import time
import glob
import json
import argparse
import threading
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, Dict, List, Any
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# 抑制 Qt/xcb 无关警告信息
os.environ["QT_LOGGING_RULES"] = "qt.qpa.*=false;*.warning=false"

# 自动处理 Linux DISPLAY 与 XAUTHORITY 环境变量
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

# 加载配置与日志
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
    logger = logging.getLogger("collect_training_images")


class TrainingImageCollector:
    """训练样本图像采集管理器"""
    def __init__(
        self,
        output_dir: str = "images",
        prefix: str = "cable",
        img_format: str = "jpg",
        target_count: int = 300,
        interval_sec: float = 1.0,
        color_res: Tuple[int, int] = (1280, 720),
        fps: int = 30,
        save_depth: bool = False
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.prefix = prefix
        self.img_format = img_format.lower().lstrip(".")
        self.target_count = target_count
        self.interval_sec = max(0.2, float(interval_sec))
        self.color_width, self.color_height = color_res
        self.fps = fps
        self.save_depth = save_depth

        # 相机句柄
        self.pipeline: Optional[rs.pipeline] = None
        self.profile: Optional[rs.pipeline_profile] = None
        self.align: Optional[rs.align] = None
        self.device_name = "Intel RealSense"
        self.serial_number = "Unknown"
        self.is_running = False

        # 帧缓存与线程锁
        self.lock = threading.Lock()
        self.latest_color: Optional[np.ndarray] = None
        self.latest_depth_raw: Optional[np.ndarray] = None
        self.latest_display_frame: Optional[np.ndarray] = None

        # 采集状态管理
        self.auto_capture = False
        self.last_auto_capture_time = 0.0
        self.show_grid = True
        self.show_help = True
        self.flash_until = 0.0
        self.notification_text = ""
        self.notification_time = 0.0

        # 扫描现有文件，自动延续编号
        self.saved_history: List[str] = []
        self.current_index = self._scan_existing_index()

        # 生成标注标签类目文件 classes.txt
        self._ensure_classes_file()

        # FPS 计算
        self.fps_counter = 0
        self.fps_calc_time = time.time()
        self.current_fps = 0.0

    def _ensure_classes_file(self):
        """确保 images/ 目录下存在 classes.txt 供 X-AnyLabeling 等工具自动读取"""
        classes_path = self.output_dir / "classes.txt"
        if not classes_path.exists():
            try:
                with open(classes_path, "w", encoding="utf-8") as f:
                    f.write("cable\n")
                logger.info(f"已自动生成标注类别定义文件: {classes_path}")
            except Exception as e:
                logger.debug(f"写入 classes.txt 跳过: {e}")

    def _scan_existing_index(self) -> int:
        """扫描输出目录下已有文件，获取当前最大序列号以支持增量采集"""
        pattern = str(self.output_dir / f"{self.prefix}_*.*")
        existing_files = glob.glob(pattern)
        max_idx = 0
        for fpath in existing_files:
            fname = Path(fpath).stem
            # 尝试提取前缀后的数字部分
            parts = fname.split("_")
            if len(parts) >= 2 and parts[-1].isdigit():
                idx = int(parts[-1])
                if idx > max_idx:
                    max_idx = idx
        if max_idx > 0:
            logger.info(f"检测到目录 [{self.output_dir}] 已有 {len(existing_files)} 张历史样本，最大编号 #{max_idx}，将从 #{max_idx + 1} 续采。")
        else:
            logger.info(f"样本保存目录: [{self.output_dir}]，起始编号: #1")
        return max_idx

    def start_camera(self) -> bool:
        """启动 D435 相机色彩流"""
        if rs is None:
            logger.error("未检测到 pyrealsense2 库，无法驱动 D435 相机！")
            return False

        try:
            self.pipeline = rs.pipeline()
            config = rs.config()

            # 启用彩色流
            config.enable_stream(
                rs.stream.color,
                self.color_width,
                self.color_height,
                rs.format.bgr8,
                self.fps
            )

            # 若需要对齐保存深度
            if self.save_depth:
                config.enable_stream(
                    rs.stream.depth,
                    848, 480,
                    rs.format.z16,
                    self.fps
                )
                self.align = rs.align(rs.stream.color)

            self.profile = self.pipeline.start(config)

            dev = self.profile.get_device()
            self.device_name = dev.get_info(rs.camera_info.name) if dev.supports(rs.camera_info.name) else "RealSense"
            self.serial_number = dev.get_info(rs.camera_info.serial_number) if dev.supports(rs.camera_info.serial_number) else "Unknown"

            # 预热并等待曝光稳定
            for _ in range(10):
                self.pipeline.wait_for_frames(timeout_ms=3000)

            self.is_running = True
            logger.info(f"D435 相机已启动: {self.device_name} (SN: {self.serial_number})")
            logger.info(f"采集分辨率: {self.color_width}x{self.color_height}@{self.fps}fps, 目标样本量: {self.target_count} 张")
            return True

        except Exception as e:
            logger.error(f"启动 D435 相机失败: {e}")
            if self.pipeline:
                try:
                    self.pipeline.stop()
                except Exception:
                    pass
                self.pipeline = None
            return False

    def stop_camera(self):
        """关闭相机管线"""
        self.is_running = False
        if self.pipeline:
            try:
                self.pipeline.stop()
                logger.info("RealSense 数据流已关闭。")
            except Exception:
                pass
            self.pipeline = None

    def set_notification(self, text: str, duration: float = 2.5):
        """设置屏幕悬浮弹窗提示"""
        self.notification_text = text
        self.notification_time = time.time() + duration

    def process_frames(self) -> bool:
        """从硬件管线拉取最新帧"""
        if not self.is_running or self.pipeline is None:
            return False

        try:
            frames = self.pipeline.wait_for_frames(timeout_ms=2000)
            if self.save_depth and self.align:
                aligned = self.align.process(frames)
                color_frame = aligned.get_color_frame()
                depth_frame = aligned.get_depth_frame()
                depth_np = np.asanyarray(depth_frame.get_data()) if depth_frame else None
            else:
                color_frame = frames.get_color_frame()
                depth_np = None

            if not color_frame:
                return False

            color_np = np.asanyarray(color_frame.get_data())

            with self.lock:
                self.latest_color = color_np
                self.latest_depth_raw = depth_np

                # 刷新 FPS
                now = time.time()
                self.fps_counter += 1
                if now - self.fps_calc_time >= 1.0:
                    self.current_fps = self.fps_counter / (now - self.fps_calc_time)
                    self.fps_counter = 0
                    self.fps_calc_time = now

            # 自动采集定时器检测
            if self.auto_capture:
                if now - self.last_auto_capture_time >= self.interval_sec:
                    self.capture_current_frame()
                    self.last_auto_capture_time = now

            return True

        except Exception as e:
            logger.debug(f"获取视频帧异常: {e}")
            return False

    def capture_current_frame(self) -> Optional[str]:
        """抓取并保存当前帧图片"""
        with self.lock:
            if self.latest_color is None:
                self.set_notification("采集失败: 无有效图像帧")
                return None
            color_to_save = self.latest_color.copy()
            depth_to_save = self.latest_depth_raw.copy() if self.latest_depth_raw is not None else None

        self.current_index += 1
        filename = f"{self.prefix}_{self.current_index:04d}.{self.img_format}"
        filepath = self.output_dir / filename

        # 写入图像文件
        if self.img_format in ["jpg", "jpeg"]:
            cv2.imwrite(str(filepath), color_to_save, [cv2.IMWRITE_JPEG_QUALITY, 95])
        else:
            cv2.imwrite(str(filepath), color_to_save)

        # 若开启保存深度图，同时保存同名 16 位深度
        if self.save_depth and depth_to_save is not None:
            depth_path = self.output_dir / f"{self.prefix}_{self.current_index:04d}_depth.png"
            cv2.imwrite(str(depth_path), depth_to_save)

        # 录入历史队列以便支持快捷键撤销
        self.saved_history.append(str(filepath))

        # 触发快门闪烁动画
        self.flash_until = time.time() + 0.18
        progress_pct = (self.current_index / self.target_count) * 100.0 if self.target_count > 0 else 0.0
        msg = f"已捕获 #{self.current_index:04d} ({self.current_index}/{self.target_count}, {progress_pct:.1f}%)"
        logger.info(f"保存样本 [{filepath.name}] - 累计采集: {self.current_index} 张")
        self.set_notification(msg)

        # 达到目标量自动暂停连采
        if self.current_index >= self.target_count and self.auto_capture:
            self.auto_capture = False
            self.set_notification(f"🎉 目标数量已达成 ({self.target_count} 张)！自动采集已停止。")
            logger.info(f"已达到预设样本采集目标 ({self.target_count} 张)！")

        return str(filepath)

    def undo_last_capture(self) -> bool:
        """撤销/删除最新采集的一张图片"""
        if not self.saved_history:
            self.set_notification("无可用历史记录可撤销")
            return False

        last_path = Path(self.saved_history.pop())
        try:
            if last_path.exists():
                last_path.unlink()
                # 同时删除伴随的深度图 (若存在)
                depth_pair = last_path.parent / f"{last_path.stem}_depth.png"
                if depth_pair.exists():
                    depth_pair.unlink()

                self.current_index = max(0, self.current_index - 1)
                msg = f"已撤销并删除: {last_path.name} (回退至 #{self.current_index})"
                logger.info(msg)
                self.set_notification(msg)
                return True
        except Exception as e:
            logger.error(f"删除样本异常: {e}")
            self.set_notification(f"撤销失败: {e}")
        return False

    def render_overlay(self) -> Optional[np.ndarray]:
        """组装画面渲染 (含构图网格、HUD 看板、进度条与快门动画)"""
        with self.lock:
            if self.latest_color is None:
                return None
            canvas = self.latest_color.copy()

        h, w = canvas.shape[:2]

        # 1. 九宫格构图辅助线与中心十字 (可按 G 键开关)
        if self.show_grid:
            grid_color = (60, 60, 65)
            # 水平三等分线
            cv2.line(canvas, (0, h // 3), (w, h // 3), grid_color, 1, cv2.LINE_AA)
            cv2.line(canvas, (0, 2 * h // 3), (w, 2 * h // 3), grid_color, 1, cv2.LINE_AA)
            # 垂直三等分线
            cv2.line(canvas, (w // 3, 0), (w // 3, h), grid_color, 1, cv2.LINE_AA)
            cv2.line(canvas, (2 * w // 3, 0), (2 * w // 3, h), grid_color, 1, cv2.LINE_AA)
            # 画面中心准星
            cx, cy = w // 2, h // 2
            cv2.line(canvas, (cx - 15, cy), (cx + 15, cy), (0, 255, 255), 1, cv2.LINE_AA)
            cv2.line(canvas, (cx, cy - 15), (cx, cy + 15), (0, 255, 255), 1, cv2.LINE_AA)

        # 2. 顶部 HUD 状态看板
        top_h = 42
        overlay = canvas.copy()
        cv2.rectangle(overlay, (0, 0), (w, top_h), (18, 20, 26), -1)
        cv2.addWeighted(overlay, 0.78, canvas, 0.22, 0, canvas)
        cv2.line(canvas, (0, top_h), (w, top_h), (60, 65, 75), 1)

        # 状态文本
        auto_str = f"AUTO: ON ({self.interval_sec:.1f}s)" if self.auto_capture else "AUTO: OFF (Manual)"
        auto_color = (0, 255, 120) if self.auto_capture else (180, 180, 180)

        pct = (self.current_index / self.target_count) * 100.0 if self.target_count > 0 else 0.0
        count_str = f"COLLECTED: {self.current_index} / {self.target_count} ({pct:.1f}%)"

        cv2.putText(canvas, count_str, (16, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 230, 255), 2, cv2.LINE_AA)
        cv2.putText(canvas, auto_str, (w - 240, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.48, auto_color, 1, cv2.LINE_AA)

        # 顶部进度条
        bar_x1 = 360
        bar_x2 = w - 260
        if bar_x2 > bar_x1 + 60:
            bar_w = bar_x2 - bar_x1
            bar_fill = int(bar_w * min(1.0, self.current_index / max(1, self.target_count)))
            cv2.rectangle(canvas, (bar_x1, 14), (bar_x2, 28), (40, 45, 55), -1)
            if bar_fill > 0:
                cv2.rectangle(canvas, (bar_x1, 14), (bar_x1 + bar_fill, 28), (0, 200, 100), -1)
            cv2.rectangle(canvas, (bar_x1, 14), (bar_x2, 28), (80, 85, 95), 1)

        # 3. 快门拍照高亮闪烁效果
        if time.time() < self.flash_until:
            cv2.rectangle(canvas, (0, 0), (w - 1, h - 1), (0, 255, 0), 8)
            cv2.putText(canvas, "CAPTURE OK", (w // 2 - 80, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2, cv2.LINE_AA)

        # 4. 悬浮弹窗提示
        if time.time() < self.notification_time and self.notification_text:
            notif_w = min(len(self.notification_text) * 11 + 30, w - 40)
            cv2.rectangle(canvas, (w // 2 - notif_w // 2, 54), (w // 2 + notif_w // 2, 92), (0, 160, 80), -1)
            cv2.rectangle(canvas, (w // 2 - notif_w // 2, 54), (w // 2 + notif_w // 2, 92), (255, 255, 255), 1)
            cv2.putText(
                canvas, self.notification_text,
                (w // 2 - notif_w // 2 + 15, 78),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA
            )

        # 5. 底部快捷键指南栏
        if self.show_help:
            bot_h = 30
            overlay = canvas.copy()
            cv2.rectangle(overlay, (0, h - bot_h), (w, h), (15, 18, 22), -1)
            cv2.addWeighted(overlay, 0.82, canvas, 0.18, 0, canvas)
            cv2.line(canvas, (0, h - bot_h), (w, h - bot_h), (50, 55, 65), 1)

            help_msg = (
                "[Space / Enter / S] 单张采集  |  [A] 自动连采开关  |  "
                "[Backspace / D] 撤销删除上一张  |  [G] 构图网格  |  [Q] 退出完成"
            )
            cv2.putText(canvas, help_msg, (16, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 210, 225), 1, cv2.LINE_AA)

        return canvas


# ==============================================================================
# Web 远程交互服务器 (手机/平板/电脑浏览器远程点按拍照)
# ==============================================================================
WEB_COLLECTOR_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YOLO 训练样本图片采集控制台</title>
    <style>
        :root {
            --bg-dark: #0f1117;
            --bg-card: #1c1f28;
            --accent-cyan: #00d2ff;
            --accent-green: #00e676;
            --accent-red: #ff3d00;
            --text-main: #f0f4f8;
            --text-sub: #94a3b8;
            --border-line: #2e3442;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background-color: var(--bg-dark);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            flex-direction: column;
            min-height: 100vh;
        }
        header {
            background: var(--bg-card);
            padding: 14px 24px;
            border-bottom: 1px solid var(--border-line);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .title { font-size: 1.2rem; font-weight: 700; color: #fff; }
        .badge {
            background: linear-gradient(90deg, var(--accent-cyan), #3a7bd5);
            color: #000;
            font-size: 0.72rem;
            font-weight: 800;
            padding: 3px 8px;
            border-radius: 4px;
        }
        main {
            display: flex;
            flex: 1;
            padding: 20px;
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
            width: 100%;
        }
        .stream-view {
            flex: 3;
            background: #000;
            border-radius: 12px;
            overflow: hidden;
            display: flex;
            justify-content: center;
            align-items: center;
            box-shadow: 0 4px 20px rgba(0,0,0,0.6);
            border: 1px solid var(--border-line);
        }
        #stream-img { max-width: 100%; height: auto; display: block; }
        .control-panel {
            flex: 1;
            min-width: 320px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        .card {
            background: var(--bg-card);
            border-radius: 12px;
            border: 1px solid var(--border-line);
            padding: 18px;
        }
        .stat-val { font-size: 1.8rem; font-weight: 800; color: var(--accent-cyan); }
        .progress-bar-bg {
            background: #11141a;
            border-radius: 6px;
            height: 12px;
            overflow: hidden;
            margin: 10px 0 16px 0;
            border: 1px solid #2d3342;
        }
        .progress-bar-fill {
            background: linear-gradient(90deg, var(--accent-cyan), var(--accent-green));
            height: 100%;
            width: 0%;
            transition: width 0.3s ease;
        }
        button {
            width: 100%;
            padding: 14px;
            border-radius: 10px;
            font-size: 1rem;
            font-weight: 700;
            cursor: pointer;
            margin-bottom: 12px;
            border: none;
            transition: all 0.2s ease;
        }
        .btn-capture {
            background: linear-gradient(135deg, #00e676, #00b0ff);
            color: #000;
        }
        .btn-capture:hover { transform: scale(1.02); filter: brightness(1.1); }
        .btn-auto {
            background: #2b3242;
            color: #fff;
            border: 1px solid var(--border-line);
        }
        .btn-auto.active {
            background: linear-gradient(135deg, #ff9100, #ff3d00);
            color: #fff;
        }
        .btn-undo {
            background: #2b3242;
            color: #ff5252;
            border: 1px solid #ff5252;
        }
        .btn-undo:hover { background: #3d1c1c; }
        #toast {
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: var(--accent-green);
            color: #000;
            font-weight: 700;
            padding: 12px 20px;
            border-radius: 8px;
            transform: translateY(100px);
            opacity: 0;
            transition: all 0.3s ease;
        }
        #toast.show { transform: translateY(0); opacity: 1; }
    </style>
</head>
<body>
    <header>
        <div style="display: flex; align-items: center; gap: 10px;">
            <div class="title">RealSense 样本图片采集终端</div>
            <div class="badge">YOLOv8 Dataset</div>
        </div>
        <div style="color: var(--text-sub); font-size: 0.85rem;">
            目标目录: <span style="color: #fff;" id="txt-dir">images/</span>
        </div>
    </header>

    <main>
        <div class="stream-view">
            <img id="stream-img" src="/stream.mjpg" alt="Camera Stream">
        </div>

        <div class="control-panel">
            <div class="card">
                <div style="color: var(--text-sub); font-size: 0.85rem;">已采集样本总量</div>
                <div class="stat-val" id="txt-count">0 / 300</div>
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" id="bar-fill"></div>
                </div>
                <div style="font-size: 0.82rem; color: var(--text-sub); display: flex; justify-content: space-between;">
                    <span>完成进度: <span id="txt-pct" style="color: var(--accent-cyan);">0%</span></span>
                    <span>帧率: <span id="txt-fps">--</span> FPS</span>
                </div>
            </div>

            <div class="card">
                <button class="btn-capture" onclick="doAction('capture')">📸 单张拍照采集 [Space]</button>
                <button class="btn-auto" id="btn-auto" onclick="doAction('toggle_auto')">⏱️ 开启自动连续采集 (1.0s)</button>
                <button class="btn-undo" onclick="doAction('undo')">🗑️ 撤销上一张 [Backspace]</button>
            </div>
        </div>
    </main>

    <div id="toast">操作成功</div>

    <script>
        function showToast(msg) {
            const t = document.getElementById('toast');
            t.innerText = msg;
            t.classList.add('show');
            setTimeout(() => t.classList.remove('show'), 2500);
        }

        function doAction(act) {
            fetch('/api/action', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action: act})
            }).then(r => r.json()).then(res => {
                if (res.msg) showToast(res.msg);
                updateStatus();
            });
        }

        function updateStatus() {
            fetch('/api/status').then(r => r.json()).then(s => {
                document.getElementById('txt-count').innerText = `${s.count} / ${s.target}`;
                const pct = s.target > 0 ? (s.count / s.target * 100).toFixed(1) : 0;
                document.getElementById('txt-pct').innerText = pct + '%';
                document.getElementById('bar-fill').style.width = Math.min(100, pct) + '%';
                document.getElementById('txt-fps').innerText = s.fps.toFixed(1);
                document.getElementById('txt-dir').innerText = s.output_dir;

                const autoBtn = document.getElementById('btn-auto');
                if (s.auto) {
                    autoBtn.classList.add('active');
                    autoBtn.innerText = '⏸️ 暂停自动连采';
                } else {
                    autoBtn.classList.remove('active');
                    autoBtn.innerText = `⏱️ 开启自动连续采集 (${s.interval}s)`;
                }
            }).catch(() => {});
        }

        setInterval(updateStatus, 1200);
        updateStatus();
    </script>
</body>
</html>
"""

class WebCollectorHandler(BaseHTTPRequestHandler):
    collector: Optional[TrainingImageCollector] = None

    def log_message(self, format, *args):
        return

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ["/", "/index.html"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(WEB_COLLECTOR_HTML.encode("utf-8"))

        elif path == "/stream.mjpg":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            while self.collector and self.collector.is_running:
                frame = self.collector.render_overlay()
                if frame is not None:
                    ret, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if ret:
                        data = jpeg.tobytes()
                        self.wfile.write(b"--frame\r\n")
                        self.send_header("Content-Type", "image/jpeg")
                        self.send_header("Content-Length", str(len(data)))
                        self.end_headers()
                        self.wfile.write(data)
                        self.wfile.write(b"\r\n")
                time.sleep(0.033)

        elif path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            col = self.collector
            st = {
                "count": col.current_index if col else 0,
                "target": col.target_count if col else 300,
                "auto": col.auto_capture if col else False,
                "interval": col.interval_sec if col else 1.0,
                "fps": col.current_fps if col else 0.0,
                "output_dir": str(col.output_dir) if col else "images/"
            }
            self.wfile.write(json.dumps(st).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/action":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body)
            col = self.collector
            res = {"success": True}

            if col:
                act = data.get("action")
                if act == "capture":
                    saved = col.capture_current_frame()
                    res["msg"] = f"已捕获 #{col.current_index}" if saved else "采集失败"
                elif act == "toggle_auto":
                    col.auto_capture = not col.auto_capture
                    res["msg"] = f"自动连采已{'开启' if col.auto_capture else '暂停'}"
                elif act == "undo":
                    ok = col.undo_last_capture()
                    res["msg"] = "已撤销删除上一张" if ok else "无可用文件撤销"

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))


# ==============================================================================
# CLI 解析与主入口
# ==============================================================================
def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="YOLOv8 模型训练图片采集工具 (默认保存至 images/ 目录)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
快捷键说明 (Local GUI 模式):
  [Space] / [Enter] / [S] : 手动单张拍照采集
  [A]                     : 开启 / 暂停自动连续采集 (默认每隔 1.0 秒拍摄一张)
  [Backspace] / [D]       : 撤销 / 删除上一张拍摄的样本图片并回退序号
  [G]                     : 显示 / 隐藏九宫格构图线与中心十字准星
  [Q] / [ESC]             : 退出程序并输出数据集汇总信息

示例:
  python tools/collect_training_images.py                      # 启动默认采集窗口 (保存至 images/)
  python tools/collect_training_images.py --target 500         # 设定采集目标为 500 张
  python tools/collect_training_images.py --interval 0.5       # 设置自动连采间隔为 0.5 秒
  python tools/collect_training_images.py --web --port 8089    # 启动 Web 远程手机/平板控制台
        """
    )

    cam_cfg = SYSTEM_CONFIG.get("vision", {}).get("camera", {})
    parser.add_argument("--output", "-o", type=str, default="images", help="图像样本输出目录 (默认: images)")
    parser.add_argument("--prefix", type=str, default="cable", help="图像文件名前缀 (默认: cable)")
    parser.add_argument("--format", type=str, default="jpg", choices=["jpg", "png", "jpeg"], help="图像存储格式 (默认: jpg)")
    parser.add_argument("--target", type=int, default=300, help="预设采集目标样本数量 (默认: 300)")
    parser.add_argument("--interval", type=float, default=1.0, help="自动连续采集时间间隔 (秒, 默认: 1.0)")
    parser.add_argument("--auto", action="store_true", help="启动时立即开启自动连采")
    parser.add_argument("--save-depth", action="store_true", help="同时保存对齐的 16 位深度图")
    parser.add_argument("--width", type=int, default=cam_cfg.get("color_width", 1280), help="彩色流宽度 (默认: 1280)")
    parser.add_argument("--height", type=int, default=cam_cfg.get("color_height", 720), help="彩色流高度 (默认: 720)")
    parser.add_argument("--fps", type=int, default=cam_cfg.get("fps", 30), help="视频流帧率 (默认: 30)")
    parser.add_argument("--web", action="store_true", help="启动 Web 远程可视化与交互采集控制台")
    parser.add_argument("--port", type=int, default=8089, help="Web 服务器端口 (默认: 8089)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Web 监听主机地址 (默认: 0.0.0.0)")
    parser.add_argument("--headless", action="store_true", help="无头模式运行 (不打开本地 GUI 窗口)")

    return parser.parse_args()


def main():
    args = parse_arguments()

    collector = TrainingImageCollector(
        output_dir=args.output,
        prefix=args.prefix,
        img_format=args.format,
        target_count=args.target,
        interval_sec=args.interval,
        color_res=(args.width, args.height),
        fps=args.fps,
        save_depth=args.save_depth
    )

    if args.auto:
        collector.auto_capture = True

    if not collector.start_camera():
        logger.error("无法启动 RealSense D435 相机，请检查 USB 线缆连接！")
        sys.exit(1)

    # 检查是否启动 Web 控制台
    web_server = None
    if args.web or args.headless or not os.environ.get("DISPLAY"):
        WebCollectorHandler.collector = collector
        try:
            web_server = ThreadingHTTPServer((args.host, args.port), WebCollectorHandler)
            web_thread = threading.Thread(target=web_server.serve_forever, daemon=True)
            web_thread.start()
            logger.info("================================================================")
            logger.info(f"🌐 远程 Web 图像采集控制台已启动: http://{args.host}:{args.port}")
            logger.info(f"   可在手机/平板/电脑浏览器上远程实时取景并点击采集样本！")
            logger.info("================================================================")
        except Exception as e:
            logger.error(f"启动 Web 服务器失败: {e}")

    # 是否开启本地 GUI 窗口
    use_gui = not args.headless and bool(os.environ.get("DISPLAY"))
    win_name = "YOLO Dataset Image Collector (Space: Capture | A: Auto | D: Undo | Q: Quit)"

    if use_gui:
        try:
            cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(win_name, 1280, 720)
            logger.info("本地桌面 GUI 窗口已启动。聚焦该窗口后即可按空格采集。")
        except Exception as e:
            logger.warning(f"无法打开桌面 GUI 窗口 ({e})，回退到无头/Web流模式。")
            use_gui = False

    logger.info("================================================================")
    logger.info("📷 采集工具已就绪！")
    logger.info(f"   输出路径: {collector.output_dir.resolve()}")
    logger.info("   快捷键: [空格/回车/S] 拍照  |  [A] 自动连采  |  [D/Backspace] 撤销  |  [Q] 退出")
    logger.info("================================================================")

    try:
        while collector.is_running:
            success = collector.process_frames()
            if not success:
                time.sleep(0.01)
                continue

            frame_to_show = collector.render_overlay()
            if frame_to_show is not None:
                with collector.lock:
                    collector.latest_display_frame = frame_to_show

                if use_gui:
                    cv2.imshow(win_name, frame_to_show)
                    key = cv2.waitKey(1) & 0xFF

                    if key in [ord('q'), 27]:  # 退出
                        logger.info("收到退出指令...")
                        break
                    elif key in [32, 13, ord('s')]:  # 空格 (32), 回车 (13), 's' 单张采集
                        collector.capture_current_frame()
                    elif key == ord('a'):  # 开启/暂停自动连采
                        collector.auto_capture = not collector.auto_capture
                        status_str = "开启" if collector.auto_capture else "暂停"
                        collector.set_notification(f"自动连续采集: {status_str}")
                    elif key in [8, ord('d')]:  # Backspace (8) 或 'd' 撤销删除
                        collector.undo_last_capture()
                    elif key == ord('g'):  # 构图网格
                        collector.show_grid = not collector.show_grid
                        collector.set_notification(f"构图辅助线: {'开' if collector.show_grid else '关'}")
                    elif key == ord('h'):  # 帮助栏
                        collector.show_help = not collector.show_help

            if not use_gui:
                time.sleep(0.01)

    except KeyboardInterrupt:
        logger.info("收到中断信号，正在退出...")

    finally:
        collector.stop_camera()
        if use_gui:
            cv2.destroyAllWindows()
        if web_server:
            web_server.shutdown()

        # 输出采集统计总结
        total_files = len(glob.glob(str(collector.output_dir / f"{collector.prefix}_*.*")))
        logger.info("================================================================")
        logger.info(f"🎉 采集任务结束！样本统计:")
        logger.info(f"   保存目录: {collector.output_dir.resolve()}")
        logger.info(f"   有效样本: {total_files} 张图像")
        logger.info(f"   标注定义: {collector.output_dir.resolve() / 'classes.txt'}")
        logger.info(f"   下一步推荐: 使用 X-AnyLabeling 打开该目录直接框选标注 (Rectangle / 快捷键 R)")
        logger.info("================================================================")


if __name__ == "__main__":
    main()
