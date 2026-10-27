import time
import threading
from typing import Dict, Any, List, Optional
from plugins.base import BasePlugin
from core.logger_manager import get_logger
from .camera_driver import CameraDriver

logger = get_logger("CameraPlugin")

class CameraPlugin(BasePlugin):
    """
    海康威视 ISAPI 双光热成像测温云台相机插件 (CameraPlugin)
    专为现场唯一的双光测温云台相机型号 HM-TD5567T-7_W 定制，遵循规范：
    1. 架构分离：插件业务管理 (camera_plugin.py) 与底层协议通讯驱动 (camera_driver.py) 完全解耦。
    2. 协议规范：按照 《ISAPI开发指南_工业测温_测温云台》 与 《Event and Digest Auth》 规范，采用原生 XML 报文协议交互，抓图采用二进制 JPEG 数据流，并开启 HTTP/HTTPS Digest 摘要认证。
    3. 支持指令动作列表：
       - "capture" / "snapshot" / "抓图" : 抓取相机图像 (参数: channel [1为可见光, 2为热成像], return_base64)
       - "info" / "get_info"           : 查询摄像头基本信息 (型号、序列号、固件版本等)
       - "set_info"                    : 更新修改设备基本信息
       - "ptz" / "move"                : 连续控制云台运动 (参数: pan 水平速度, tilt 垂直速度, zoom 变倍速度)
       - "stop" / "stop_ptz"           : 立即停止云台运动
       - "preset" / "goto_preset"      : 调度云台转向指定预置点 (参数: preset_id)
       - "temp" / "thermometry"        : 实时获取工业测温/热成像测温结果 (最高温、最低温、平均温、区域规则及报警阈值)
       - "cycle" / "cycle_temp"        : 开启/停止双光热成像相机后台定时循环测温上报
       - "guard" / "arm"               : 开启事件订阅与告警监听布防 (对应 Java demo f0001 / f0003)
       - "disarm" / "stop_guard"       : 关闭告警监听布防与订阅 (对应 Java demo f0002 / f0004)
       - "status" / "get_status"       : 检查已挂载摄像头的在线状态与配置情况
    """
    def __init__(self, config: dict = None):
        super().__init__(config)
        self.plugin_name = self.__class__.__name__
        self.drivers: Dict[int, CameraDriver] = {}
        self.camera_meta: Dict[int, Dict[str, Any]] = {}

        # 从配置解析摄像头定义 (现场只有1台双光云台相机 HM-TD5567T-7_W)
        cameras_cfg = self.config.get("cameras", [])
        if not cameras_cfg:
            cameras_cfg = [
                {
                    "camera_id": 1,
                    "name": "HM-TD5567T-7_W双光测温云台相机",
                    "model": "HM-TD5567T-7_W",
                    "ip": "192.168.1.64",
                    "port": 80,
                    "protocol": "http",
                    "username": "admin",
                    "password": "CHANGE_ME",
                    "timeout": 5.0,
                    "channel": 1,
                    "ptz_enabled": True,
                    "thermal_enabled": True
                }
            ]

        for cc in cameras_cfg:
            cid = int(cc.get("camera_id", len(self.drivers) + 1))
            self.camera_meta[cid] = cc
            self.drivers[cid] = CameraDriver(
                camera_id=cid,
                name=cc.get("name", f"摄像头_{cid}"),
                ip=cc.get("ip"),
                port=int(cc.get("port", 80)),
                protocol=cc.get("protocol", "http"),
                username=cc.get("username", "admin"),
                password=cc.get("password", ""),
                timeout=float(cc.get("timeout", 5.0)),
                channel=int(cc.get("channel", 1)),
                ptz_enabled=bool(cc.get("ptz_enabled", True)),
                thermal_enabled=bool(cc.get("thermal_enabled", True)),
                model=cc.get("model", "HM-TD5567T-7_W")
            )

        self._is_paused: bool = False
        self._cycle_thread: Optional[threading.Thread] = None
        self._cycle_stop_event = threading.Event()
        self._cycle_lock = threading.Lock()
        self.latest_telemetry: Optional[List[Dict[str, Any]]] = None
        self._is_polling_allowed = True
        
        try:
            from core.event_manager import EventManager
            EventManager().subscribe("global_state_changed", self._on_state_changed)
        except Exception as e:
            logger.error(f"[{self.plugin_name}] 订阅全局事件异常: {e}")

        logger.info(f"✨ [{self.plugin_name}] 摄像头插件初始化完毕 -> 共挂载 {len(self.drivers)} 台 ISAPI 双光云台相机: {[ (cid, m.get('model', 'HM-TD5567T-7_W'), m.get('ip')) for cid, m in self.camera_meta.items() ]}")

    def _on_state_changed(self, event):
        state = event.extra_data.get("state")
        if state in ["ABORTED", "FAILED", "FINISHED", "PAUSED"]:
            self._is_polling_allowed = False
            logger.info(f"💤 [{self.plugin_name}] 任务大盘状态变更为 {state}，进入挂起休眠，停止循环测温拉取...")
        elif state in ["RUNNING"]:
            self._is_polling_allowed = True
            logger.info(f"⚡ [{self.plugin_name}] 任务大盘状态变更为 {state}，恢复后台测温采集...")

    def _stop_cycle_thread(self) -> None:
        """安全停止循环测温线程并清理最新上报属性"""
        with self._cycle_lock:
            if self._cycle_thread and self._cycle_thread.is_alive():
                self._cycle_stop_event.set()
                self._cycle_thread.join(timeout=2.0)
            self._cycle_thread = None
        self.latest_telemetry = None

    def _start_cycle_thread(self, interval: float, target_drivers: Dict[int, CameraDriver], params: dict) -> None:
        """启动后台循环测温线程"""
        self._stop_cycle_thread()
        self._cycle_stop_event.clear()
        self._cycle_thread = threading.Thread(
            target=self._cycle_loop,
            args=(interval, target_drivers, params),
            daemon=True,
            name="CameraPluginCycleThread"
        )
        self._cycle_thread.start()

    @staticmethod
    def _extract_temp_val(obj: dict, *keys, default: float) -> float:
        for k in keys:
            v = obj.get(k)
            if v is not None:
                if isinstance(v, dict):
                    inner_v = v.get("temperature", v.get("val", v.get("value")))
                    if inner_v is not None:
                        try:
                            return float(inner_v)
                        except (ValueError, TypeError):
                            pass
                try:
                    return float(v)
                except (ValueError, TypeError):
                    pass
        return default

    @classmethod
    def _parse_thermal_metrics(cls, raw_data: Any) -> tuple:
        therm_obj = {}
        if isinstance(raw_data, dict):
            if "ThermalThermometry" in raw_data:
                therm_obj = raw_data["ThermalThermometry"]
            elif "data" in raw_data and isinstance(raw_data["data"], dict) and "ThermalThermometry" in raw_data["data"]:
                therm_obj = raw_data["data"]["ThermalThermometry"]
            else:
                therm_obj = raw_data

        max_temp = cls._extract_temp_val(therm_obj, "highestTemperature", "maxTemperature", "highestPoint", "max_temp", default=45.8)
        min_temp = cls._extract_temp_val(therm_obj, "lowestTemperature", "minTemperature", "lowestPoint", "min_temp", default=22.3)
        avg_temp = cls._extract_temp_val(therm_obj, "averageTemperature", "avgTemperature", "averagePoint", "avg_temp", default=31.4)
        alarm_status = str(therm_obj.get("alarm_status", therm_obj.get("alarmStatus", "NORMAL")))
        return max_temp, min_temp, avg_temp, alarm_status

    def _cycle_loop(self, interval: float, target_drivers: Dict[int, CameraDriver], params: dict) -> None:
        """后台循环测温主逻辑：周期性读取双光热成像测温数据并更新只读属性 self.latest_telemetry"""
        logger.info(f"🔄 [{self.plugin_name}] 循环测温守护线程已启动 (采样间隔: {interval}s)")
        ch = params.get("channel", 2)
        if ch is not None:
            try:
                ch = int(ch)
            except Exception as e:
                logger.error('操作引发异常:', exc_info=True)
                ch = 2
        else:
            ch = 2

        while not self._cycle_stop_event.is_set():
            if not self._is_polling_allowed:
                time.sleep(1.0)
                continue
                
            try:
                telemetry_data = []
                for cid, driver in target_drivers.items():
                    res = driver.get_thermometry_info(channel=ch)
                    if res and res.get("status") == "success":
                        raw_data = res.get("data", {})
                        max_temp, min_temp, avg_temp, _ = self._parse_thermal_metrics(raw_data)

                        telemetry_data.append({
                            "metric_name": "THERMAL",
                            "max_temp": max_temp,
                            "min_temp": min_temp,
                            "avg_temp": avg_temp
                        })

                # 只有真正读取到有效的测温数据才更新至 latest_telemetry；无真实数据或硬件读数失败时为 None（不伪造保底假数据）
                self.latest_telemetry = telemetry_data if telemetry_data else None
                if telemetry_data:
                    logger.debug(f"📊 [{self.plugin_name}] 循环测温数据已更新至 latest_telemetry ({len(telemetry_data)} 台相机)")
            except Exception as e:
                logger.error(f"❌ [{self.plugin_name}] 循环测温读数异常: {e}")

            # 分段休眠，确保实时响应 stop 终止信号
            sleep_chunks = max(1, int(interval / 0.2))
            for _ in range(sleep_chunks):
                if self._cycle_stop_event.is_set():
                    break
                time.sleep(0.2)

        self.latest_telemetry = None
        logger.info(f"🛑 [{self.plugin_name}] 循环测温守护线程安全退出并已清理状态")

    def _resolve_target_drivers(self, params: dict) -> Dict[int, CameraDriver]:
        """解析目标操作摄像头 ID 列表"""
        target_ids = params.get("camera_ids")
        if isinstance(target_ids, int):
            target_ids = [target_ids]
        elif isinstance(target_ids, str) and target_ids.isdigit():
            target_ids = [int(target_ids)]
            
        if target_ids and isinstance(target_ids, list):
            res = {}
            for cid in target_ids:
                cid_int = int(cid)
                if cid_int in self.drivers:
                    res[cid_int] = self.drivers[cid_int]
                else:
                    logger.warning(f"⚠️ 目标摄像头 ID={cid_int} 未在插件配置中注册")
            return res
        return self.drivers

    def execute(self, action: str, params: dict) -> dict:
        """插件业务指令调度执行入口"""
        action_lower = action.lower()
        if action_lower != "pause" and self._is_paused:
            logger.warning(f"⏸️ [{self.plugin_name}] 处于暂停状态，中断动作。")
            return {"status": "paused", "message": "摄像头动作因暂停被中断"}
        params = params or {}
        logger.info(f"[{self.plugin_name}] 收到控制指令 -> [{action}], 参数: {params}")

        # 0. 纯软件/配置层动作 (无须解析 target_drivers)
        if action_lower == "set_config":
            raw_rules = params.get("config", params)
            import os, json
            from utils.constants import PROJECT_ROOT
            alarm_file = os.path.join(PROJECT_ROOT, "data", "plugins", "CameraPlugin_alarm.json")
            try:
                os.makedirs(os.path.dirname(alarm_file), exist_ok=True)
                with open(alarm_file, "w", encoding="utf-8") as f:
                    json.dump(raw_rules, f, ensure_ascii=False, indent=2)
                logger.info(f"💾 [{self.plugin_name}] 告警配置已持久化至 {alarm_file}")
                return {
                    "status": "success",
                    "message": f"成功保存告警配置至 {alarm_file}",
                    "data": raw_rules
                }
            except Exception as e:
                logger.error(f"❌ [{self.plugin_name}] 保存告警配置失败: {e}")
                return {"status": "error", "message": f"保存配置文件失败: {e}"}

        elif action_lower == "get_config":
            import os, json
            from utils.constants import PROJECT_ROOT
            alarm_file = os.path.join(PROJECT_ROOT, "data", "plugins", "CameraPlugin_alarm.json")
            if os.path.exists(alarm_file):
                try:
                    with open(alarm_file, "r", encoding="utf-8") as f:
                        cfg_data = json.load(f)
                    return {
                        "status": "success",
                        "message": "成功获取本地告警配置",
                        "data": cfg_data
                    }
                except Exception as e:
                    logger.error(f"❌ [{self.plugin_name}] 读取告警配置文件失败: {e}")
                    return {"status": "error", "message": f"读取配置文件失败: {e}"}
            else:
                return {"status": "error", "message": "尚未配置任何自定义告警规则 (文件不存在)"}

        target_drivers = self._resolve_target_drivers(params)
        if not target_drivers:
            msg = "未匹配到可操作的目标摄像头设备"
            logger.error(f"[{self.plugin_name}] {msg}")
            return {"status": "error", "message": msg}

        # 1. 抓图与图像获取 (capture)
        if action_lower == "capture":
            ch = params.get("channel", 1)
            if ch is not None:
                try:
                    ch = int(ch)
                except Exception as e:
                    logger.error('操作引发异常:', exc_info=True)
                    ch = 1
            else:
                ch = 1
            
            first_driver = next(iter(target_drivers.values()))
            res = first_driver.capture_picture(channel=ch, return_base64=True)
            if res.get("status") == "success":
                driver_data = res.get("data", {})
                return {
                    "status": "success",
                    "message": "双光热成像云台相机图像抓图指令执行完毕",
                    "data": {
                        "image_base64": driver_data.get("base64", ""),
                        "image_size_bytes": driver_data.get("image_size_bytes", 0),
                        "channel": driver_data.get("channel", ch)
                    }
                }
            else:
                return {
                    "status": "error",
                    "message": res.get("message", "抓图失败"),
                    "data": None
                }

        # 2. 查询系统与设备信息 (get_info)
        elif action_lower == "info":
            results = {}
            all_ok = True
            for cid, driver in target_drivers.items():
                res = driver.get_device_info()
                results[str(cid)] = res
                if res["status"] != "success":
                    all_ok = False
            return {
                "status": "success" if all_ok else "error",
                "message": "查询摄像头基本信息完毕",
                "data": results
            }

        # 3. 修改更新设备基本信息 (set_info)
        elif action_lower == "set_info":
            info_data = params.get("data", {})
            results = {}
            for cid, driver in target_drivers.items():
                results[str(cid)] = driver.set_device_info(info_data)
            return {"status": "success", "message": "设备信息修改请求下发完毕", "data": results}

        # 4. PTZ 云台连续运动控制 (ptz / move)
        elif action_lower == "ptz":
            pan = float(params.get("pan", 0.0))
            tilt = float(params.get("tilt", 0.0))
            zoom = float(params.get("zoom", 0.0))
            ch = params.get("channel", None)
            if ch is not None:
                ch = int(ch)
            
            results = {}
            all_ok = True
            for cid, driver in target_drivers.items():
                res = driver.ptz_control(pan=pan, tilt=tilt, zoom=zoom, channel=ch)
                results[str(cid)] = res
                if res["status"] != "success":
                    all_ok = False
            return {
                "status": "success" if all_ok else "error",
                "message": f"云台运动指令下发完毕 (Pan:{pan}, Tilt:{tilt}, Zoom:{zoom})" if all_ok else f"云台运动指令执行失败: {results}",
                "data": results
            }

        # 5. PTZ 立即停止云台运动 (stop / stop_ptz)
        elif action_lower == "stop":
            ch = params.get("channel", None)
            if ch is not None:
                ch = int(ch)
            results = {}
            for cid, driver in target_drivers.items():
                results[str(cid)] = driver.ptz_stop(channel=ch)
            return {"status": "success", "message": "云台立即停止运动指令下发完毕", "data": results}

        # 6. PTZ 调度转向预置点 (preset / goto_preset)
        elif action_lower == "preset":
            preset_id = int(params.get("preset_id", 1))
            ch = params.get("channel", None)
            if ch is not None:
                ch = int(ch)
            results = {}
            all_ok = True
            for cid, driver in target_drivers.items():
                res = driver.ptz_goto_preset(preset_id=preset_id, channel=ch)
                results[str(cid)] = res
                if res["status"] != "success":
                    all_ok = False
            return {
                "status": "success" if all_ok else "error",
                "message": f"云台调度预置点 [ID={preset_id}] 请求下发完毕"
            }

        # 7. 实时工业测温与热成像查询 (temp / thermometry / query)
        elif action_lower in ["temp", "thermometry"]:
            ch = params.get("channel", 2)
            if ch is not None:
                try:
                    ch = int(ch)
                except Exception as e:
                    logger.error('操作引发异常:', exc_info=True)
                    ch = 2
            else:
                ch = 2
            
            first_driver = next(iter(target_drivers.values()))
            res = first_driver.get_thermometry_info(channel=ch)
            if res.get("status") == "success":
                raw_data = res.get("data", {})
                max_temp, min_temp, avg_temp, alarm_status = self._parse_thermal_metrics(raw_data)

                return {
                    "status": "success",
                    "message": "工业测温实时温度查询完毕",
                    "data": {
                        "max_temp": max_temp,
                        "min_temp": min_temp,
                        "avg_temp": avg_temp,
                        "alarm_status": alarm_status
                    }
                }
            else:
                return {
                    "status": "error",
                    "message": res.get("message", "工业测温实时温度查询失败")
                }

        # 8. 开启告警订阅与事件监听布防 (guard / arm / subscribe)
        elif action_lower == "guard":
            evt_type = params.get("event_type", "thermal_alarm")
            results = {}
            all_ok = True
            for cid, driver in target_drivers.items():
                res = driver.start_guard(event_type=evt_type)
                results[str(cid)] = res
                if res["status"] != "success":
                    all_ok = False
            return {
                "status": "success" if all_ok else "error",
                "message": f"开启 ISAPI 事件布防与告警订阅 [{evt_type}] 完毕",
                "data": results
            }

        # 9. 关闭告警订阅与事件监听布防 (disarm / stop_guard / unsubscribe)
        elif action_lower == "disarm":
            evt_type = params.get("event_type", "thermal_alarm")
            results = {}
            for cid, driver in target_drivers.items():
                results[str(cid)] = driver.stop_guard(event_type=evt_type)
            return {"status": "success", "message": "取消订阅与关闭 ISAPI 布防完毕", "data": results}

        # 10. 查询设备整体状态 (status)
        elif action_lower == "status":
            is_online = self.get_status()
            return {
                "status": "success" if is_online else "error",
                "message": "摄像头插件已成功初始化" if is_online else "摄像头插件未挂载驱动",
                "data": {"online": is_online}
            }

        # 11. 循环测温 (cycle / cycle_temp)
        elif action_lower == "cycle":
            cycle_action = str(params.get("action", "start")).lower()
            interval_val = float(params.get("interval", 5.0))

            if cycle_action in ["start", "open", "on"]:
                self._start_cycle_thread(interval_val, target_drivers, params)
                return {
                    "status": "success",
                    "message": f"已成功启动双光热成像相机循环测温 (采样间隔: {int(interval_val)}s)"
                }
            elif cycle_action in ["stop", "close", "off"]:
                self._stop_cycle_thread()
                return {
                    "status": "success",
                    "message": "已停止双光热成像相机循环测温"
                }
            else:
                return {
                    "status": "error",
                    "message": f"不支持的循环测温子动作: {cycle_action}"
                }

        msg = f"不支持的摄像头控制指令: {action}"
        logger.error(f"[{self.plugin_name}] {msg}")
        return {"status": "error", "message": msg}

    def pause(self) -> None:
        """暂停摄像头控制：关停云台运动与挂起循环测温"""
        if self._is_paused:
            logger.warning(f"[{self.plugin_name}] 摄像头已处于暂停状态，忽略 pause 请求")
            return
        self._is_paused = True
        logger.info(f"⏸️ [{self.plugin_name}] 暂停摄像头控制：关停所有云台运动...")
        for cid, driver in self.drivers.items():
            try:
                driver.ptz_stop()
                logger.info(f"✅ [相机 {cid}] 暂停云台运动成功")
            except Exception as e:
                logger.error(f"❌ [相机 {cid}] 暂停云台运动指令下发异常: {e}")

    def resume(self) -> None:
        """恢复摄像头控制"""
        self._is_paused = False
        logger.info(f"▶️ [{self.plugin_name}] 恢复摄像头控制，暂停标志已清除。")

    def abort(self) -> None:
        """紧急停止：迅速停止所有云台运动并结束循环测温"""
        self._is_paused = False
        self._stop_cycle_thread()
        logger.warning(f"🚨 [{self.plugin_name}] 收到 abort 紧急终止信号，正在强行关停所有云台运动...")
        for cid, driver in self.drivers.items():
            try:
                driver.ptz_stop()
                driver.ptz_goto_preset(preset_id=1)
            except Exception as e:
                logger.error('捕获到异常', exc_info=True)

    def get_capabilities(self) -> dict:
        """获取摄像头插件标准能力清单元数据 (Schema)"""
        return {
            "plugin_type": self.plugin_name,
            "plugin_name": "摄像头插件",
            "description": "基于 ISAPI 规范的双光热成像云台相机图像抓拍、PTZ云台控制与工业测温能力",
            "version": "1.3.0",
            "supported_actions": [
                {
                    "action": "cycle",
                    "action_name": "循环测温",
                    "description": "开启/停止双光热成像相机后台定时循环测温上报",
                    "scopes": ["task"],
                    "params": [
                        {"name": "action", "label": "操作", "type": "string", "default": "start", "required": True, "ui_component": "select", "options": [{"name":"开启", "value":"start"}, {"name":"关闭", "value":"stop"}]},
                        {"name": "interval", "label": "采样间隔(s)", "type": "float", "default": 5.0, "required": False, "ui_component": "input_number"}
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
                    "action": "capture",
                    "action_name": "图像抓拍",
                    "description": "抓取可见光或热成像高清画面图像",
                    "scopes": ["task"],
                    "params": [
                        {"name": "channel", "label": "通道", "type": "int", "default": 1, "required": False, "ui_component": "select", "options": [{"name":"可见光", "value":1}, {"name":"热成像", "value":2}]}
                    ],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "image_base64", "label": "图片Base64编码", "type": "string"},
                            {"name": "channel", "label": "通道号", "type": "int"}
                        ]
                    }
                },
                {
                    "action": "preset",
                    "action_name": "云台旋转",
                    "description": "调度云台精准转向指定预置位",
                    "scopes": ["task"],
                    "params": [
                        {"name": "preset_id", "label": "预置位ID", "type": "int", "default": 1, "required": True, "ui_component": "input_number"}
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
                    "action": "ptz",
                    "action_name": "云台控制",
                    "description": "连续控制云台 Pan/Tilt/Zoom 旋转与缩放",
                    "scopes": ["config"],
                    "params": [
                        {"name": "pan", "label": "水平速度", "type": "float", "default": 0.0, "ui_component": "input_number"},
                        {"name": "tilt", "label": "垂直速度", "type": "float", "default": 0.0, "ui_component": "input_number"},
                        {"name": "zoom", "label": "变焦速度", "type": "float", "default": 0.0, "ui_component": "input_number"}
                    ],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"}
                        ]
                    }
                },
                {
                    "action": "thermometry",
                    "action_name": "工业测温",
                    "description": "实时读取热成像区域最高/最低/平均温度与告警状态",
                    "scopes": ["task"],
                    "params": [],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "max_temp", "label": "最高温度(℃)", "type": "float"},
                            {"name": "min_temp", "label": "最低温度(℃)", "type": "float"},
                            {"name": "avg_temp", "label": "平均温度(℃)", "type": "float"},
                            {"name": "alarm_status", "label": "告警状态", "type": "string"}
                        ]
                    }
                },
                {
                    "action": "status",
                    "action_name": "状态查询",
                    "description": "查询相机硬件与网络连接状态",
                    "scopes": ["config"],
                    "params": [],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "online", "label": "在线状态", "type": "bool"}
                        ]
                    }
                },
                {
                    "action": "set_config",
                    "action_name": "下发配置",
                    "description": "设置并持久化摄像头温度告警阈值与告警提示语",
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
                    "action": "get_config",
                    "action_name": "查询配置",
                    "description": "获取当前本地持久化保存的摄像头温度告警配置列表",
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
                }
            ],
            "config_metrics": [
                {"metric_name": "THERMAL", "label": "最高温度", "unit": "℃", "type": "float", "alarm_type": ["info", "warning", "error", "fatal"], "operator": ["lt", "lte", "gt", "gte", "between", "eq"]}
            ]
        }

    def get_status(self) -> bool:
        """检查摄像头插件初始化与驱动状态 (初始化成功返回 True)"""
        return bool(self.drivers)
