import os
import json
import threading
import socket
import numpy as np
import cv2
import av
import base64
from typing import Optional, List, Dict, Any

from plugins.base import BasePlugin
from .acoustic_driver import AcousticDriver
from core.logger_manager import get_logger
from core.alarm_manager import AlarmManager
from core.config_manager import ConfigManager
from utils.constants import PROJECT_ROOT
from utils import get_timestamp_ms

logger = get_logger("AcousticPlugin")

class AcousticPlugin(BasePlugin):
    def __init__(self, config: dict = None):
        super().__init__(config)
        cfg_mgr = ConfigManager()
        
        cfg_params = self.config.get("params", {}) if isinstance(self.config, dict) else {}
        self.ip = (
            (self.config.get("ip") if isinstance(self.config, dict) else None)
            or cfg_params.get("ip")
            or cfg_mgr.get("plugins.acoustic.params.ip")
            or "192.168.123.102"
        )
        self.http_port = int(
            (self.config.get("http_port") if isinstance(self.config, dict) else None)
            or cfg_params.get("http_port")
            or cfg_mgr.get("plugins.acoustic.params.http_port", 80)
        )
        self.tcp_port = int(
            (self.config.get("tcp_port") if isinstance(self.config, dict) else None)
            or cfg_params.get("tcp_port")
            or cfg_mgr.get("plugins.acoustic.params.tcp_port", 13052)
        )
        
        # 告警规则从独立 JSON 管理，不硬编码在 yaml
        self.alarm_config_path = os.path.join(PROJECT_ROOT, "data", "plugins", "AcousticPlugin_alarm.json")
        self.alarm_rules = []
        self.alarm_spl_threshold = 80.0  # 默认抓图底线，稍后会被 JSON 覆盖
        self.alarm_cooldown = 60.0
        self.recovery_hysteresis = 5.0
        self._load_alarm_config()
        
        # 标志位与状态机：控制 TCP 流循环检测是否开启及防抖
        self.cycle_enabled = False
        self._last_alarm_time = 0.0
        self._in_alarm_state = False
        self._latest_frame_bgr: Optional[np.ndarray] = None
        self._h264_codec = None
        
        self.driver = AcousticDriver(self.ip, self.http_port, self.tcp_port)
        self._is_running = True
        self.latest_telemetry: Optional[List[Dict[str, Any]]] = None
        self._is_polling_allowed = True
        
        try:
            from core.event_manager import EventManager
            EventManager().subscribe("global_state_changed", self._on_state_changed)
        except Exception as e:
            logger.error(f"[AcousticPlugin] 订阅全局事件异常: {e}")
            
        # 启动驱动底层的 TCP 长连接，通过回调接收解析好的帧数据
        self.driver.start_tcp_stream(self._on_tcp_frame)
        
    def _on_state_changed(self, event):
        state = event.extra_data.get("state")
        if state in ["ABORTED", "FAILED", "FINISHED", "PAUSED"]:
            self._is_polling_allowed = False
            self.driver.stop_tcp_stream()
            logger.info(f"💤 [AcousticPlugin] 任务大盘状态变更为 {state}，进入挂起休眠，断开 TCP 流...")
        elif state in ["RUNNING"]:
            if not self._is_polling_allowed:
                self._is_polling_allowed = True
                self.driver.start_tcp_stream(self._on_tcp_frame)
                logger.info(f"⚡ [AcousticPlugin] 任务大盘状态变更为 {state}，恢复 TCP 拉流采集...")
        
    def _load_alarm_config(self):
        """从 JSON 加载分级告警配置，并自动提取最小有效触发门限作为抓图底线"""
        try:
            if os.path.exists(self.alarm_config_path):
                with open(self.alarm_config_path, "r", encoding="utf-8") as f:
                    self.alarm_rules = json.load(f)

                min_threshold = None
                for rule in self.alarm_rules:
                    if rule.get("metric_name") == "SPL" or rule.get("type") == "SPL":
                        thresholds = rule.get("thresholds", {})
                        for level in ["info", "warning", "error", "fatal"]:
                            cfg = thresholds.get(level, {})
                            val = cfg.get("value")
                            op = cfg.get("operator")
                            if op == "between" and isinstance(val, list) and len(val) == 2:
                                lvl_min = float(val[0])
                                min_threshold = lvl_min if min_threshold is None else min(min_threshold, lvl_min)
                            elif op in ["gte", "gt"] and val is not None:
                                lvl_min = float(val)
                                min_threshold = lvl_min if min_threshold is None else min(min_threshold, lvl_min)
                if min_threshold is not None:
                    self.alarm_spl_threshold = min_threshold
                    logger.info(f"🎯 [AcousticPlugin] 提取到声纹告警最低触发门限: {self.alarm_spl_threshold} dB")
        except Exception as e:
            logger.error(f"❌ 加载声纹分级告警配置失败: {e}")

    def _determine_alarm_level(self, spl: float) -> tuple:
        """根据分级配置动态判定当前 SPL 所属的告警级别及对应 Message"""
        try:
            for rule in self.alarm_rules:
                if rule.get("metric_name") == "SPL" or rule.get("type") == "SPL":
                    thresholds = rule.get("thresholds", {})
                    # 优先级：fatal > error > warning > info
                    for level in ["fatal", "error", "warning", "info"]:
                        cfg = thresholds.get(level, {})
                        op = cfg.get("operator")
                        val = cfg.get("value")
                        msg = cfg.get("message", f"声压异常: {spl} dB")
                        
                        if op == "gte" and spl >= float(val):
                            return level, msg
                        elif op == "gt" and spl > float(val):
                            return level, msg
                        elif op == "between" and isinstance(val, list) and len(val) == 2:
                            if float(val[0]) <= spl < float(val[1]):
                                return level, msg
        except Exception as e:
            logger.error('捕获到异常', exc_info=True)
        return "warning", f"声纹探头检测到异常声压 ({spl:.2f} dB)"

    def _decode_video_frame(self, video_data: bytes, v_type: int = 1) -> Optional[np.ndarray]:
        """多重容错解码视频帧 (优先快速 JPEG，随后 H.264 流式解析及缓冲区冲刷)"""
        if not video_data or len(video_data) < 4:
            return None

        # 1. 优先尝试直接作为 JPEG / PNG 解码
        if video_data.startswith(b'\xff\xd8') or video_data.startswith(b'\x89PNG'):
            try:
                img = cv2.imdecode(np.frombuffer(video_data, np.uint8), cv2.IMREAD_COLOR)
                if img is not None and img.size > 0:
                    return img
            except Exception:
                pass

        # 2. 尝试使用 PyAV 解码 H.264 单帧或裸流
        try:
            # 当收到关键帧 (v_type == 1) 或首次启动时，创建或重置 Codec 以确保干净解析 SPS/PPS
            if v_type == 1 or self._h264_codec is None:
                self._h264_codec = av.CodecContext.create('h264', 'r')

            # 确保 Annex B 边界定界符，使 parser 能够立即判定 NAL 结束并输出 Packet
            feed_data = video_data
            if not feed_data.endswith(b'\x00\x00\x00\x01\x09\x10'):
                feed_data = feed_data + b'\x00\x00\x00\x01\x09\x10'

            packets = self._h264_codec.parse(feed_data)
            for packet in packets:
                frames = self._h264_codec.decode(packet)
                if frames:
                    return frames[0].to_ndarray(format='bgr24')

            # 冲刷解码器内部延迟队列 (flush delay frames)
            frames = self._h264_codec.decode()
            if frames:
                return frames[0].to_ndarray(format='bgr24')
        except Exception as e:
            # logger.debug(f"[AcousticPlugin] 持久化 H.264 解码器解析异常: {e}")
            try:
                # 重新创建独立解码器单次尝试
                single_codec = av.CodecContext.create('h264', 'r')
                feed_data = video_data + b'\x00\x00\x00\x01\x09\x10'
                packets = single_codec.parse(feed_data)
                for packet in packets:
                    frames = single_codec.decode(packet)
                    if frames:
                        return frames[0].to_ndarray(format='bgr24')
                frames = single_codec.decode()
                if frames:
                    return frames[0].to_ndarray(format='bgr24')
            except Exception:
                pass

        # 3. 兜底尝试 OpenCV decode
        try:
            img = cv2.imdecode(np.frombuffer(video_data, np.uint8), cv2.IMREAD_COLOR)
            if img is not None and img.size > 0:
                return img
        except Exception:
            pass

        return None

    def _on_tcp_frame(self, spl: float, grid_data: tuple, prpd_len: int, video_data: bytes, v_type: int):
        """来自驱动层的 TCP 帧数据回调"""
        if not self._is_polling_allowed:
            return

        # 后台静默尝试解析并刷新最新有效视频底图
        if video_data and len(video_data) > 0:
            frame = self._decode_video_frame(video_data, v_type)
            if frame is not None:
                self._latest_frame_bgr = frame

        if self.cycle_enabled:
            self.latest_telemetry = [
                {
                    "metric_name": "SPL_TELEMETRY",
                    "value": float(spl),
                    "unit": "dB"
                }
            ]
        else:
            self.latest_telemetry = None

        # 状态机：迟滞恢复判断
        if self._in_alarm_state and spl < (self.alarm_spl_threshold - self.recovery_hysteresis):
            self._in_alarm_state = False

        # 若 SPL 超过阈值且开启了循环检测
        if self.cycle_enabled and spl >= self.alarm_spl_threshold:

            import time
            now = time.time()
            if not self._in_alarm_state and (now - self._last_alarm_time >= self.alarm_cooldown):

                self._in_alarm_state = True
                self._last_alarm_time = now

                # 异步触发告警以免阻塞 TCP 读取 (因为底层 tcp thread 是同步调用的回调)
                threading.Thread(
                    target=self._trigger_spl_alarm,
                    args=(spl, grid_data, prpd_len, video_data, v_type),
                    daemon=True
                ).start()

    def _generate_fallback_canvas(self, spl: float) -> np.ndarray:
        """当硬件未提供有效视频帧时，依据工业规范生成深色声学成像监控底图"""
        img_w, img_h = 1280, 720
        canvas = np.full((img_h, img_w, 3), (28, 32, 38), dtype=np.uint8)

        # 绘制声学成像网格参考刻度线
        for x in range(0, img_w, 64):
            cv2.line(canvas, (x, 0), (x, img_h), (40, 46, 54), 1)
        for y in range(0, img_h, 64):
            cv2.line(canvas, (0, y), (img_w, y), (40, 46, 54), 1)

        # 边框与工业指示标题栏
        cv2.rectangle(canvas, (20, 20), (img_w - 20, img_h - 20), (70, 80, 95), 2)
        cv2.rectangle(canvas, (20, 20), (img_w - 20, 70), (45, 52, 62), -1)

        title = f"ACOUSTIC IMAGING MONITOR [DES-T168TPT] - IP: {self.ip}"
        cv2.putText(canvas, title, (35, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (220, 220, 220), 2)

        spl_text = f"PEAK SPL: {spl:.1f} dB"
        cv2.putText(canvas, spl_text, (img_w - 320, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)

        return canvas

    def _render_acoustic_heatmap(self, frame_bgr: np.ndarray, grid_data: tuple, spl: float) -> str:
        """将 32x24 声成像数据渲染为伪彩色热力图并与底图融合，生成 Base64 JPEG"""
        img_h, img_w = frame_bgr.shape[:2]

        # 1. 解析 grid 声成像矩阵 (32 列 x 24 行)
        if grid_data and len(grid_data) >= 768:
            grid_arr = np.array(grid_data[:768], dtype=np.float32).reshape((24, 32))
        else:
            grid_arr = np.zeros((24, 32), dtype=np.float32)

        # 2. 归一化并生成伪彩色 JET 热力图
        grid_norm = cv2.normalize(grid_arr, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
        heatmap = cv2.applyColorMap(grid_norm, cv2.COLORMAP_JET)
        heatmap_resized = cv2.resize(heatmap, (img_w, img_h), interpolation=cv2.INTER_CUBIC)

        # 3. 计算透明度 Mask，强化高能量声源聚焦
        mask = cv2.resize(grid_norm, (img_w, img_h), interpolation=cv2.INTER_CUBIC).astype(np.float32) / 255.0
        alpha = np.clip((mask - 0.25) / 0.75, 0.0, 0.85)
        alpha = np.expand_dims(alpha, axis=-1)

        # 4. 图像叠加融合 (Alpha Blending)
        overlayed = (heatmap_resized * alpha + frame_bgr * (1.0 - alpha)).astype(np.uint8)

        # 5. 右上角绘制声压 OSD 标识
        osd_text = f"SPL: {spl:.1f} dB"
        cv2.putText(overlayed, osd_text, (img_w - 220, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

        # 6. JPEG 内存编码并生成 base64 字符串
        _, buffer = cv2.imencode('.jpg', overlayed, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return "data:image/jpeg;base64," + base64.b64encode(buffer).decode('utf-8')

    def capture_current_image(self) -> str:
        """主动截取当前声纹定位探头融合成像图 (返回 Base64 编码，无需 RTSP 拉流)"""
        current_spl = self.driver.get_spl()
        frame = None
        if self._latest_frame_bgr is not None:
            frame = self._latest_frame_bgr.copy()
        if frame is None:
            frame = self._generate_fallback_canvas(current_spl)
        return self._render_acoustic_heatmap(frame, (), current_spl)

    def _trigger_spl_alarm(self, spl: float, grid_data: tuple, prpd_len: int, video_data: bytes, v_type: int):
        """解码 H.264/JPEG 视频帧，渲染 grid 为色彩热力图进行融合，生成 Base64 图片，并抓取 PRPD 数据发起告警"""
        try:
            # 1. 优先尝试从当前 TCP 视频帧解码 (协议 4.1 节 TCP 13052 流)
            frame_bgr = self._decode_video_frame(video_data, v_type)
            if frame_bgr is not None:
                self._latest_frame_bgr = frame_bgr

            # 2. 若当前帧未解出，尝试使用最近缓存成功的 TCP 视频底图
            if frame_bgr is None and self._latest_frame_bgr is not None:
                frame_bgr = self._latest_frame_bgr.copy()

            # 3. 若无视频底图，生成标准工业监测背景，确保告警图 100% 存在且有效 (不通过 RTSP 拉流)
            if frame_bgr is None:
                frame_bgr = self._generate_fallback_canvas(spl)

            # 5. 渲染伪彩色声像热力图并完成融合，获取 Base64 图片
            base64_img = self._render_acoustic_heatmap(frame_bgr, grid_data, spl)

            # 6. 智能节流：仅在发现 prpd_xy 有数据时，才拉取 HTTP PRPD 深度诊断数据
            prpd_res = {}
            if prpd_len > 0:
                prpd_res = self.driver.get_prpd()

            # 7. 拼装平铺的 MQTT 告警结构 (同时兼容 image_base64 与 image 字段)
            alarm_data = {
                "spl": spl,
                "image_base64": base64_img,
                "discharge_acceptance": prpd_res.get("discharge_acceptance", 0.0),
                "discharge_malfunction_grade": prpd_res.get("discharge_malfunction_grade", 0),
                "discharge_type": prpd_res.get("discharge_type", 0)
            }

            # 8. 根据配置动态定级
            level, msg = self._determine_alarm_level(spl)

            AlarmManager.report_alarm(
                level=level,
                code=6001,
                message=msg,
                data=alarm_data,
                source_plugin="AcousticPlugin"
            )
            logger.info(f"🚨 瞬态捕捉完成！带 Base64 融合图与 PRPD 数据的 [{level}] 级告警已上报 (图像长度: {len(base64_img)})")

        except Exception as e:
            logger.error(f"❌ 声纹热力图解码与融合异常: {e}", exc_info=True)

    def status(self) -> bool:
        # 只要驱动实体存在即认为在线，不强制绑定 TCP 循环采集状态
        return bool(self.driver)

    def _get_hardware_status(self) -> dict:
        return self.driver.get_status()

    def execute(self, action: str, params: dict) -> dict:
        """接收云端 MQTT 动作调用 (实现要求的物模型操作)"""
        try:
            action_lower = action.lower()
            if action_lower == "query_spl": # 查询声压
                return {"status": "success", "data": {"spl": self.driver.get_spl()}}
                
            elif action_lower == "cycle": # 循环检测开关
                if "action" in params:
                    cycle_action = str(params.get("action", "start")).lower()
                    enable = cycle_action in ["start", "open", "on", "true"]
                else:
                    enable = params.get("enable", True)
                
                self.cycle_enabled = enable
                return {"status": "success", "message": f"循环检测已{'开启' if enable else '关闭'}"}
                
            elif action_lower == "enable_channel": # 使能通道
                enable = params.get("enable", True)
                res = self.driver.set_rms_enable(enable)
                return {"status": "success", "data": res}
                
            elif action_lower == "get_config" or action_lower == "query_alarm_config": # 查询分级告警配置
                return {"status": "success", "data": self.alarm_rules}
                
            elif action_lower == "set_config" or action_lower == "set_alarm_config": # 下发设置分级告警配置
                new_cfg = params.get("config", [])
                with open(self.alarm_config_path, "w", encoding="utf-8") as f:
                    json.dump(new_cfg, f, ensure_ascii=False, indent=2)
                self._load_alarm_config() # 热生效
                return {"status": "success", "message": "声纹告警规则更新成功"}
                
            elif action_lower == "query_fault": # 查询故障 (PRPD接口)
                return {"status": "success", "data": self.driver.get_prpd()}
                
            elif action_lower == "get_status": # 查询设备状态
                return {"status": "success", "data": self._get_hardware_status()}
                
            elif action_lower == "status": # 状态查询 (返回 bool)
                return {"status": "success", "data": {"online": self.status()}}
                
            elif action_lower == "reboot":
                self.driver.reboot()
                return {"status": "success", "message": "重启指令已发送"}
            elif action_lower == "capture": # 抓取当前声学融合成像图
                img_b64 = self.capture_current_image()
                return {
                    "status": "success",
                    "message": "抓取当前声学热力融合成像图成功",
                    "data": {
                        "image_base64": img_b64
                    }
                }
            else:
                return {"status": "error", "message": f"不支持的动作: {action}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def abort(self) -> None:
        self._is_running = False
        self.driver.stop_tcp_stream()

    def get_capabilities(self) -> dict:
        return {
            "plugin_type": self.__class__.__name__,
            "plugin_name": "声纹插件",
            "version": "1.0.0",
            "description": "声纹插件",
            "supported_actions": [
                {
                    "action": "query_spl",
                    "action_name": "查询声压",
                    "description": "查询当前声压值",
                    "scopes": ["config"],
                    "params": [],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态(success/error)", "type": "string"},
                            {"name": "data", "label": "数据", "type": "object", "fields": [
                                {"name": "spl", "label": "声压级", "type": "float"}
                            ]}
                        ]
                    }
                },
                {
                    "action": "cycle",
                    "action_name": "循环采集",
                    "description": "开启或关闭自动截取报警合并上报功能",
                    "scopes": ["task"],
                    "params": [
                        {
                            "name": "action",
                            "label": "操作动作",
                            "type": "string",
                            "default": "start",
                            "required": True,
                            "ui_component": "select",
                            "options": [{"name": "开启", "value": "start"}, {"name": "关闭", "value": "stop"}]
                        },
                        {
                            "name": "interval",
                            "label": "上报间隔(秒)",
                            "type": "int",
                            "default": 5,
                            "required": False,
                            "ui_component": "input_number"
                        }
                    ],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态(success/error)", "type": "string"},
                            {"name": "message", "label": "执行描述", "type": "string"}
                        ]
                    }
                },
                {
                    "action": "capture",
                    "action_name": "截取声像图",
                    "description": "抓取当前声学热力融合成像图 (Base64)",
                    "scopes": ["task", "config"],
                    "params": [],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "message", "label": "执行描述", "type": "string"},
                            {"name": "data", "label": "数据", "type": "object", "fields": [
                                {"name": "base64", "label": "图片Base64编码", "type": "string"},
                                {"name": "image_base64", "label": "图片Base64编码", "type": "string"}
                            ]}
                        ]
                    }
                },
                # {
                #     "action": "enable_channel",
                #     "action_name": "使能通道",
                #     "description": "启用或关闭声纹分析通道",
                #     "scopes": ["config"],
                #     "params": [
                #         {
                #             "name": "enable",
                #             "label": "使能",
                #             "type": "bool",
                #             "default": False,
                #             "required": True,
                #             "ui_component": "select",
                #             "options": [{"name": "开启", "value": True}, {"name": "关闭", "value": False}]
                #         }
                #     ],
                #     "returns": {
                #         "type": "object",
                #         "fields": [
                #             {"name": "status", "label": "执行状态", "type": "string"},
                #             {"name": "message", "label": "执行描述", "type": "string"}
                #         ]
                #     }
                # },
                {
                    "action": "query_fault",
                    "action_name": "查询PRPD故障",
                    "description": "拉取深度诊断分析PRPD结果",
                    "scopes": ["config"],
                    "params": [],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "data", "label": "数据", "type": "object", "fields": [
                                {"name": "discharge_acceptance", "label": "故障置信度", "type": "float"},
                                {"name": "discharge_malfunction_grade", "label": "故障严重程度", "type": "int"},
                                {"name": "discharge_type", "label": "故障类型", "type": "int"}
                            ]}
                        ]
                    }
                },
                {
                    "action": "get_config",
                    "action_name": "获取告警配置",
                    "description": "获取当前本地持久化保存的声纹告警配置列表",
                    "scopes": ["config"],
                    "params": [],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "message", "label": "执行描述", "type": "string"},
                            {"name": "data", "label": "配置数据", "type": "array"}
                        ]
                    }
                },
                {
                    "action": "set_config",
                    "action_name": "设置告警配置",
                    "description": "动态设置分级告警规则",
                    "scopes": ["config"],
                    "params": [
                        {"name": "config", "label": "告警配置规则列表", "type": "array", "required": True, "ui_component": "json_editor"}
                    ],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "message", "label": "描述", "type": "string"}
                        ]
                    }
                },
                {
                    "action": "get_status",
                    "action_name": "查询设备状态",
                    "description": "调用/status获取硬件级健康状态",
                    "scopes": ["config"],
                    "params": [],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "data", "label": "数据", "type": "object", "fields": [
                                {"name": "app", "label": "App", "type": "string"},
                                {"name": "cam_heihgt", "label": "摄像机高度", "type": "int"},
                                {"name": "cam_width", "label": "摄像机宽度", "type": "int"},
                                {"name": "complie_time", "label": "编译时间", "type": "string"},
                                {"name": "cpu_temp", "label": "CPU温度", "type": "float"},
                                {"name": "device_no", "label": "设备编号", "type": "string"},
                                {"name": "fs", "label": "采样率", "type": "int"},
                                {"name": "gpu_temp", "label": "GPU温度", "type": "float"},
                                {"name": "httpflv_port", "label": "HTTP FLV端口", "type": "int"},
                                {"name": "npu_temp", "label": "NPU温度", "type": "float"},
                                {"name": "rtmp_port", "label": "RTMP端口", "type": "int"},
                                {"name": "rtsp_port", "label": "RTSP端口", "type": "int"},
                                {"name": "sn_fpga", "label": "FPGA序列号", "type": "string"},
                                {"name": "time", "label": "时间", "type": "string"},
                                {"name": "version", "label": "版本号", "type": "string"},
                                {"name": "version_fpga", "label": "FPGA版本号", "type": "string"},
                                {"name": "rms_enable", "label": "RMS使能", "type": "bool"}
                            ]}
                        ]
                    }
                },
                {
                    "action": "reboot",
                    "action_name": "重启设备",
                    "description": "设备热重启",
                    "scopes": ["config"],
                    "params": [],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "message", "label": "描述", "type": "string"}
                        ]
                    }
                },
                {
                    "action": "status",
                    "action_name": "状态查询",
                    "description": "查询网络连通状态",
                    "scopes": ["config"],
                    "params": [],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "data", "label": "数据", "type": "object", "fields": [
                                {"name": "online", "label": "在线状态", "type": "bool"}
                            ]}
                        ]
                    }
                }
            ],
            "config_metrics": [
                {"metric_name": "SPL", "label": "声压", "unit": "dB", "type": "float", "alarm_type": ["info", "warning", "error", "fatal"], "operator": ["lt", "lte", "gt", "gte", "between", "eq"]}
            ]
        }
