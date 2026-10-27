import os
import json
import time
import threading
from typing import Dict, Any, List, Optional
from plugins.base import BasePlugin
from core.logger_manager import get_logger
from .gas_driver import GasDriver

logger = get_logger("GasPlugin")

class GasPlugin(BasePlugin):
    """
    气体传感器控制与采集插件 (GasPlugin)
    遵循规范：
    1. 插件和驱动完全分离（驱动在 gas_driver.py，插件业务管理在 gas_plugin.py）。
    2. 硬件与通道结构：2个传感器模组（1个6合一 ID=1，1个1合一 ID=2）。
       上报数据统一采用拍平列表 (`List[dict]`) 结构，显式包含 `sensor_id` (1, 2) 与标准 `channel_code` (1~6, 1)。
    3. 硬件上电行为规范：传感器上电默认自动启动，需要在初始化完毕后主动下发命令关闭气泵。
    4. 气体采集业务规范：当执行采集流程 (acquire / monitor / startMonitor) 时，自动打开气泵 -> 等待30s预热 -> 采集读取数据 -> 关闭气泵。
    5. 支持指令动作库：
       - "acquire" / "monitor"  : 触发完整采集流程（开泵 -> 默认等30s -> 读浓度 -> 关泵）
       - "start" / "open"       : 单独启动采样气泵
       - "stop"  / "close"      : 单独关闭采样气泵
       - "query" / "value"      : 实时即时读取当前浓度数据
       - "channel"              : 读取设备通道完整参数信息 (量程、放大倍数、单位、报警点等 80 byte结构)
       - "level" / "speed"      : 动态设置内置气泵流量级别 / 流速
       - "base"  / "base_info"  : 读取设备基础信息 (UID、软硬件版本、厂商及出厂时间)
       - "calibrate"            : 触发通道标定校准
       - "reset"                : 触发恢复出厂设置
    """
    def __init__(self, config: dict = None):
        super().__init__(config)
        self.plugin_name = self.__class__.__name__
        self.drivers: Dict[int, GasDriver] = {}
        self.sensor_meta: Dict[int, Dict[str, Any]] = {}

        # 从配置中解析传感器定义（包含 sensor_id 1与2，标准通道编号 1~6 与 1）
        sensors_cfg = self.config.get("sensors", [])
        if not sensors_cfg:
            sensors_cfg = [
                {
                    "sensor_id": 1,
                    "name": "6合一气体检测模组",
                    "port": "/tmp/tty_gas_sim0",
                    "baudrate": 9600,
                    "short_addr": 0x1236,
                    "channel_count": 6,
                    "channels": [
                        {"channel_code": 1, "name": "CO",  "unit": "PPM",  "magnification": 1},
                        {"channel_code": 2, "name": "H2S", "unit": "PPM",  "magnification": 1},
                        {"channel_code": 3, "name": "O2",  "unit": "%VOL", "magnification": 2},
                        {"channel_code": 4, "name": "EX",  "unit": "%LEL", "magnification": 1},
                        {"channel_code": 5, "name": "CO2", "unit": "PPM",  "magnification": 1},
                        {"channel_code": 6, "name": "NOX", "unit": "PPM",  "magnification": 1}
                    ]
                },
                {
                    "sensor_id": 2,
                    "name": "1合一气体传感器",
                    "port": "/tmp/tty_gas_sim1",
                    "baudrate": 9600,
                    "short_addr": 0x1235,
                    "channel_count": 1,
                    "channels": [
                        {"channel_code": 1, "name": "SF6", "unit": "PPM",  "magnification": 1}
                    ]
                }
            ]

        for sc in sensors_cfg:
            sid = int(sc.get("sensor_id", len(self.drivers) + 1))
            self.sensor_meta[sid] = sc
            self.drivers[sid] = GasDriver(
                sensor_id=sid,
                port=sc.get("port", "/dev/ttyUSB0"),
                baudrate=int(sc.get("baudrate", 9600)),
                data_bits=int(sc.get("data_bits", 8)),
                stop_bits=int(sc.get("stop_bits", 1)),
                parity=sc.get("parity", "N"),
                short_addr=int(sc.get("short_addr", 0x1236)),
                timeout=float(sc.get("timeout", 2.0)),
                channel_configs=sc.get("channels", [])
            )

        logger.info(f"✨ [{self.plugin_name}] 驱动加载完毕 -> 共挂载 {len(self.drivers)} 个气体传感器: {[ (sid, m.get('name'), m.get('port')) for sid, m in self.sensor_meta.items() ]}")
        
        self._is_paused: bool = False  # 暂停标志
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

        # 传感器上电默认启动，初始化后主动下发关泵指令
        self._init_shutdown_pumps()

    def _on_state_changed(self, event):
        state = event.extra_data.get("state")
        if state in ["ABORTED", "FAILED", "FINISHED", "PAUSED"]:
            self._is_polling_allowed = False
            logger.info(f"💤 [{self.plugin_name}] 任务大盘状态变更为 {state}，进入挂起休眠，停止串口拉取...")
        elif state in ["RUNNING"]:
            self._is_polling_allowed = True
            logger.info(f"⚡ [{self.plugin_name}] 任务大盘状态变更为 {state}，恢复后台采集...")

    def _stop_cycle_thread(self) -> None:
        """安全停止循环采集线程并清空最新上报属性"""
        with self._cycle_lock:
            if self._cycle_thread and self._cycle_thread.is_alive():
                self._cycle_stop_event.set()
                self._cycle_thread.join(timeout=2.0)
            self._cycle_thread = None
        self.latest_telemetry = None

    def _start_cycle_thread(self, interval: float) -> None:
        """启动后台循环采集与定时上报线程"""
        self._stop_cycle_thread()
        self._cycle_stop_event.clear()
        self._cycle_thread = threading.Thread(
            target=self._cycle_loop,
            args=(interval,),
            daemon=True,
            name="GasPluginCycleThread"
        )
        self._cycle_thread.start()

    def _cycle_loop(self, interval: float) -> None:
        """后台循环采集主逻辑：周期性读取通道数据并更新只读属性 self.latest_telemetry"""
        logger.info(f"🔄 [{self.plugin_name}] 循环采集守护线程已启动 (采样间隔: {interval}s)")
        while not self._cycle_stop_event.is_set():
            if not self._is_polling_allowed:
                time.sleep(1.0)
                continue
                
            try:
                flattened_channels = []
                for sid, driver in self.drivers.items():
                    res = driver.read_concentration()
                    if res and isinstance(res, dict) and "channels" in res:
                        channels = res.get("channels", [])
                        for ch in channels:
                            conc_val = ch.get("value")
                            if conc_val is None:
                                conc_val = ch.get("concentration", 0.0)

                            st_val = ch.get("status")
                            if not st_val or not isinstance(st_val, str):
                                alarm_st = ch.get("alarm_status", 0)
                                st_val = "NORMAL" if alarm_st == 0 else "ALARM"

                            flattened_channels.append({
                                "sensor_id": ch.get("sensor_id", sid),
                                "channel_code": ch.get("channel_code", 1),
                                "name": ch.get("name", f"GAS_{ch.get('channel_code', 1)}"),
                                "value": float(conc_val),
                                "unit": ch.get("unit", "PPM"),
                                "status": st_val
                            })
                # 只有真实读取到有效传感器通道数据才更新至 latest_telemetry；无真实数据或硬件无响应时为 None（无需伪造保底数据）
                self.latest_telemetry = flattened_channels if flattened_channels else None
                if flattened_channels:
                    logger.debug(f"📊 [{self.plugin_name}] 循环采集数据已更新至 latest_telemetry ({len(flattened_channels)} 个通道)")
            except Exception as e:
                logger.error(f"❌ [{self.plugin_name}] 循环采集读数异常: {e}")

            # 分段休眠，确保响应 stop 信号
            sleep_chunks = max(1, int(interval / 0.2))
            for _ in range(sleep_chunks):
                if self._cycle_stop_event.is_set():
                    break
                time.sleep(0.2)

        self.latest_telemetry = None
        logger.info(f"🛑 [{self.plugin_name}] 循环采集守护线程安全退出并已清理状态")

    def _init_shutdown_pumps(self) -> None:
        """初始化后主动关闭气泵规范"""
        logger.info(f"🛑 [{self.plugin_name}] 硬件初始化后规范执行: 传感器上电默认启动气泵，现已主动下发关泵指令复位状态...")
        for sid, driver in self.drivers.items():
            try:
                driver.control_pump(on_off=0x00, flow_level=0)
                logger.debug(f"✅ [传感器 {sid}] 初始化关闭气泵完成")
            except Exception as e:
                logger.warning(f"⚠️ [传感器 {sid}] 初始化关闭气泵尝试失败 (可能当前硬件未接通): {e}")

    def _resolve_target_drivers(self, params: dict) -> Dict[int, GasDriver]:
        """解析指令目标传感器列表（优先根据 sensor_id 解析）"""
        sid = params.get("sensor_id")
        if sid is not None:
            try:
                sid_int = int(sid)
                if sid_int in self.drivers:
                    return {sid_int: self.drivers[sid_int]}
            except Exception as e:
                logger.error('捕获到异常', exc_info=True)

        target_ids = params.get("sensor_ids", [])
        if isinstance(target_ids, int):
            target_ids = [target_ids]
        elif isinstance(target_ids, str) and target_ids.isdigit():
            target_ids = [int(target_ids)]

        if target_ids and isinstance(target_ids, list):
            res = {}
            for s_id in target_ids:
                sid_int = int(s_id)
                if sid_int in self.drivers:
                    res[sid_int] = self.drivers[sid_int]
                else:
                    logger.warning(f"⚠️ 目标传感器 ID={sid_int} 未在插件中注册")
            return res
        return self.drivers

    def _do_acquisition_flow(self, target_drivers: Dict[int, GasDriver], params: dict) -> dict:
        """
        执行标准气体浓度采集流程:
        1. 下发启动指令打开气泵 (start)
        2. 等待启动后 30s 在采集 (默认 30s)
        3. 采集读取实时浓度数值信息 (query)
        4. 采集完毕后下发关泵指令关闭气泵 (stop)
        上报格式：返回拍平通道列表，每个对象显式包含 sensor_id 与 channel_code
        """
        wait_seconds = float(params.get("wait_time", 30.0))
        flow_level = int(params.get("flow_level", 10))

        logger.info(f"🚀 [气体采集流程] 步骤 1/4: 正在启动指定气泵 (等级:{flow_level})...")
        for sid, driver in target_drivers.items():
            driver.control_pump(on_off=0x01, flow_level=flow_level)

        if wait_seconds > 0:
            logger.info(f"⏳ [气体采集流程] 步骤 2/4: 气泵已启动，等待 {wait_seconds} 秒使气流与传感器预热稳定后进行采样...")
            start_wait = time.time()
            while time.time() - start_wait < wait_seconds:
                if self._is_paused:
                    logger.warning(f"⏸️ [{self.plugin_name}] 气体采样等待期间检测到 pause 暂停信号，终止关泵并退出。")
                    for sid, driver in target_drivers.items():
                        try:
                            driver.control_pump(on_off=0x00, flow_level=0)
                        except Exception as e:
                            logger.error('捕获到异常', exc_info=True)
                    return {"status": "paused", "message": "气体采样动作因暂停被中断"}
                time.sleep(0.1)
        else:
            logger.debug(f"⚡ [气体采集流程] 步骤 2/4: wait_time={wait_seconds}s，即时开始采样...")

        logger.info(f"📊 [气体采集流程] 步骤 3/4: {wait_seconds}s 等待稳定完毕，开始轮询读取气体浓度数据...")
        result_data = []
        all_ok = True
        for sid, driver in target_drivers.items():
            if self._is_paused:
                logger.warning(f"⏸️ [{self.plugin_name}] 气体采样数据读取期间检测到 pause 暂停信号")
                driver.control_pump(on_off=0x00, flow_level=0)
                return {"status": "paused", "message": "气体采样动作因暂停被中断"}
            res = driver.read_concentration()
            if res and "channels" in res:
                for ch in res["channels"]:
                    result_data.append({
                        "sensor_id": ch.get("sensor_id", sid),
                        "channel_code": ch.get("channel_code"),
                        "name": ch["name"],
                        "value": ch["concentration"],
                        "unit": ch["unit"]
                    })
                logger.info(f"✅ [传感器 {sid}] 成功读取 {len(res['channels'])} 个气体通道数据")
            else:
                all_ok = False
                logger.warning(f"⚠️ [传感器 {sid}] 采集读取数据失败或无响应")

        logger.info(f"🛑 [气体采集流程] 步骤 4/4: 采集流程结束，下发关泵指令以保护模组...")
        for sid, driver in target_drivers.items():
            driver.control_pump(on_off=0x00, flow_level=0)

        return {
            "status": "success" if all_ok else "error",
            "message": f"气体采样采集完毕（已完成 {wait_seconds}s 稳定等待与关泵动作）" if all_ok else "采集结束但部分传感器无有效响应",
            "data": result_data
        }

    def execute(self, action: str, params: dict) -> dict:
        """插件业务控制执行入口"""
        action_lower = action.lower()
        if action_lower != "pause" and self._is_paused:
            logger.warning(f"⏸️ [{self.plugin_name}] 处于暂停状态，中断动作。")
            return {"status": "paused", "message": "气体采样动作因暂停被中断"}
        params = params or {}
        logger.info(f"[{self.plugin_name}] 收到指令 -> [{action}], 参数: {params}")

        # 0. 纯软件/配置层动作 (无须强依赖硬件传感器驱动对象)
        if action_lower == "set_config":
            raw_rules = params.get("config", params)
            from utils.constants import PROJECT_ROOT
            alarm_file = os.path.join(PROJECT_ROOT, "data", "plugins", "GasPlugin_alarm.json")
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
            from utils.constants import PROJECT_ROOT
            alarm_file = os.path.join(PROJECT_ROOT, "data", "plugins", "GasPlugin_alarm.json")
            if os.path.exists(alarm_file):
                try:
                    with open(alarm_file, "r", encoding="utf-8") as f:
                        cfg_data = json.load(f)
                    return {
                        "status": "success",
                        "message": "获取气体告警配置成功",
                        "data": cfg_data
                    }
                except Exception as e:
                    return {"status": "error", "message": f"读取配置文件失败: {e}"}
            else:
                return {
                    "status": "success",
                    "message": "暂无已保存的气体告警配置",
                    "data": {}
                }

        target_drivers = self._resolve_target_drivers(params)
        if not target_drivers:
            msg = "没有可用的目标气体传感器"
            logger.error(f"[{self.plugin_name}] {msg}")
            return {"status": "error", "message": msg}

        # 1. 触发完整采集流程 (开启气泵 -> 等待启动后30s在采集 -> 读浓度 -> 关闭气泵)
        if action_lower == "acquire":
            return self._do_acquisition_flow(target_drivers, params)

        # 2. 单独打开采样气泵
        elif action_lower == "start":
            flow_level = int(params.get("flow_level", 10))
            all_ok = True
            for sid, driver in target_drivers.items():
                ok = driver.control_pump(on_off=0x01, flow_level=flow_level)
                if not ok:
                    all_ok = False
            return {
                "status": "success" if all_ok else "error",
                "message": "指定气体传感器气泵启动成功" if all_ok else "气泵启动下发异常"
            }

        # 3. 单独关闭采样气泵
        elif action_lower == "stop":
            all_ok = True
            for sid, driver in target_drivers.items():
                ok = driver.control_pump(on_off=0x00, flow_level=0)
                if not ok:
                    all_ok = False
            return {
                "status": "success" if all_ok else "error",
                "message": "指定气体传感器气泵关闭成功" if all_ok else "气泵关闭下发异常"
            }

        # 4. 即时查询当前气体浓度 (拍平列表上报，显式包含 sensor_id 与 channel_code)
        elif action_lower == "query":
            if params.get("with_pump", False) or "wait_time" in params or "wait_s" in params:
                return self._do_acquisition_flow(target_drivers, params)

            result_data = []
            all_ok = True
            for sid, driver in target_drivers.items():
                res = driver.read_concentration()
                if res and "channels" in res:
                    for ch in res["channels"]:
                        result_data.append({
                            "sensor_id": ch.get("sensor_id", sid),
                            "channel_code": ch.get("channel_code"),
                            "name": ch["name"],
                            "value": ch["concentration"],
                            "unit": ch["unit"]
                        })
                else:
                    all_ok = False

            return {
                "status": "success" if all_ok else "error",
                "message": "读取当前气体浓度成功" if all_ok else "读取浓度报文超时或失败",
                "data": result_data
            }

        # 5. 读取设备通道完整参数信息 (80 bytes/channel 协议，拍平列表上报)
        elif action_lower == "channel":
            result_data = []
            all_ok = True
            for sid, driver in target_drivers.items():
                res = driver.read_channel_info()
                if res and "channels" in res:
                    for ch in res["channels"]:
                        ch_info = dict(ch)
                        ch_info["sensor_id"] = ch.get("sensor_id", sid)
                        result_data.append(ch_info)
                else:
                    all_ok = False
            return {
                "status": "success" if all_ok else "error",
                "message": "读取通道完整信息成功" if all_ok else "读取通道参数异常",
                "data": result_data
            }

        # 6. 设置气泵流量等级
        elif action_lower == "level":
            level_val = int(params.get("level", 10))
            all_ok = True
            for sid, driver in target_drivers.items():
                ok = driver.control_pump(on_off=0x01, flow_level=level_val)
                if not ok:
                    all_ok = False
            return {"status": "success" if all_ok else "error", "message": f"气泵流量等级设置为 {level_val}"}

        # 7. 设置气泵流速
        elif action_lower == "speed":
            speed_val = int(params.get("speed", 500))
            all_ok = True
            for sid, driver in target_drivers.items():
                ok = driver.control_pump(on_off=0x01, flow_level=255, flow_rate=speed_val)
                if not ok:
                    all_ok = False
            return {"status": "success" if all_ok else "error", "message": f"气泵流速设置为 {speed_val}"}

        # 8. 查询基本信息 (UID、厂商、软硬件版本)
        elif action_lower == "base":
            result_data = []
            for sid, driver in target_drivers.items():
                info = driver.read_base_info()
                if info:
                    filtered_info = {
                        "channel_count": info.get("channel_count", 6),
                        "device_uid": info.get("device_uid", ""),
                        "manufacturer": info.get("manufacturer", ""),
                        "hardware_version": info.get("hardware_version", ""),
                        "software_version": info.get("software_version", ""),
                        "build_time": info.get("build_time", ""),
                        "sensor_id": sid
                    }
                    result_data.append(filtered_info)
            return {"status": "success", "message": "获取基本信息完毕", "data": result_data}

        # 9. 标定校准
        elif action_lower == "calibrate":
            sid_target = params.get("sensor_id")
            ch_code = int(params.get("channel_code", 1))
            level = int(params.get("level", 0))
            cal_data = float(params.get("calibration_data", 0.0))
            cal_ad = int(params.get("calibration_ad", 0))
            all_ok = True
            for sid, driver in target_drivers.items():
                ok = driver.calibrate_channel(ch_code, level, cal_data, cal_ad)
                if not ok:
                    all_ok = False
            return {
                "status": "success" if all_ok else "error",
                "message": f"传感器 {sid_target or '所有'} 通道 {ch_code} 校准操作下发完毕",
                "data": {"sensor_id": sid_target, "channel_code": ch_code, "success": all_ok}
            }

        # 10. 恢复出厂设置
        elif action_lower == "reset":
            ch_code = int(params.get("channel_code", 0xFF))
            flag = int(params.get("restore_flag", 0xFF))
            all_ok = True
            for sid, driver in target_drivers.items():
                ok = driver.factory_reset(ch_code, flag)
                if not ok:
                    all_ok = False
            return {"status": "success" if all_ok else "error", "message": "恢复出厂设置指令下发完毕"}

        # 11. 循环采集 (cycle)
        elif action_lower == "cycle":
            cycle_action = str(params.get("action", "start")).lower()
            interval_val = float(params.get("interval", 5.0))

            if cycle_action in ["start", "open", "on"]:
                # 1. 开启采样气泵
                for sid, driver in target_drivers.items():
                    try:
                        driver.control_pump(on_off=0x01, flow_level=5)
                    except Exception as e:
                        logger.error(f"❌ [传感器 {sid}] 开启气泵异常: {e}")

                # 2. 启动后台循环采集与定时上报线程
                self._start_cycle_thread(interval_val)
                return {
                    "status": "success",
                    "message": f"已开启气泵并启动气体循环采集 (上报间隔: {int(interval_val)}s)"
                }

            elif cycle_action in ["stop", "close", "off"]:
                # 1. 终止后台循环采集线程
                self._stop_cycle_thread()

                # 2. 关闭采样气泵
                for sid, driver in target_drivers.items():
                    try:
                        driver.control_pump(on_off=0x00, flow_level=0)
                    except Exception as e:
                        logger.error(f"❌ [传感器 {sid}] 关闭气泵异常: {e}")

                return {
                    "status": "success",
                    "message": "已停止气体循环采集并关停采样气泵"
                }
            else:
                msg = f"不支持的循环采集动作参数: {cycle_action} (仅支持 start / stop)"
                logger.error(f"[{self.plugin_name}] {msg}")
                return {"status": "error", "message": msg}

        # 12. 查询插件整体状态
        elif action_lower == "status":
            is_online = self.get_status()
            return {
                "status": "success" if is_online else "error",
                "message": "气体检测串口连接正常" if is_online else "气体检测串口未连接或关闭",
                "data": {"online": is_online}
            }

        msg = f"不支持的气体动作指令: {action}"
        logger.error(f"[{self.plugin_name}] {msg}")
        return {"status": "error", "message": msg}

    def pause(self) -> None:
        """暂停气体检测任务"""
        if self._is_paused:
            logger.warning(f"[{self.plugin_name}] 气体插件已处于暂停状态，忽略 pause 请求")
            return
        self._is_paused = True
        self._stop_cycle_thread()
        logger.info(f"⏸️ [{self.plugin_name}] 暂停气体检测：已置暂停标志，下发关泵指令...")
        for sid, driver in self.drivers.items():
            try:
                driver.control_pump(on_off=0x00, flow_level=0)
                logger.info(f"✅ [传感器 {sid}] 暂停关泵成功")
            except Exception as e:
                logger.error(f"❌ [传感器 {sid}] 暂停关泵指令下发异常: {e}")

    def resume(self) -> None:
        """恢复气体检测任务"""
        logger.info(f"▶️ [{self.plugin_name}] 恢复气体检测：重新下发开泵指令...")
        try:
            for sid, driver in self.drivers.items():
                driver.control_pump(on_off=0x01, flow_level=5)
                logger.info(f"✅ [传感器 {sid}] 恢复开泵成功")
        except Exception as e:
            logger.error(f"❌ [传感器 {sid}] 恢复开泵指令下发异常: {e}")
        finally:
            self._is_paused = False
            logger.info(f"[{self.plugin_name}] 气体插件暂停标志已清除")

    def abort(self) -> None:
        """紧急停止：立刻关闭所有气泵与循环采集线程"""
        self._is_paused = False
        self._stop_cycle_thread()
        logger.warning(f"🚨 [{self.plugin_name}] 收到 abort 紧急终止信号，正在强行关泵...")
        for sid, driver in self.drivers.items():
            try:
                driver.control_pump(on_off=0x00, flow_level=0)
            except Exception as e:
                logger.error('捕获到异常', exc_info=True)

    def get_capabilities(self) -> dict:
        """
        获取气体插件的标准能力清单元数据 (Schema)
        符合平台统一规范：params 输入元数据 + scopes 场景作用域 + returns 响应结构定义
        """
        return {
            "plugin_type": self.plugin_name,
            "plugin_name": "气体插件",
            "description": "基于 6合一(ID=1) 与 1合一(ID=2) 双模组的多通道气体浓度采集、气泵调速、传感器标定与诊断能力",
            "version": "1.2.0",
            "supported_actions": [
                {
                    "action": "acquire",
                    "action_name": "气体采集",
                    "description": "标准巡检流程：开泵 -> 自动预热等待(默认30s) -> 读多通道浓度 -> 自动关泵",
                    "scopes": ["task"],  # 巡检任务编排专用
                    "params": [
                        {
                            "name": "wait_time",
                            "label": "稳定等待时间(s)",
                            "type": "float",
                            "default": 30.0,
                            "required": False,
                            "ui_component": "input_number"
                        },
                        {
                            "name": "flow_level",
                            "label": "气泵流量等级(1-10级)",
                            "type": "int",
                            "default": 10,
                            "min": 1,
                            "max": 10,
                            "step": 1,
                            "required": False,
                            "ui_component": "slider"
                        }
                    ],
                    "returns": {
                        "type": "array",
                        "description": "拍平的气体通道实时浓度列表",
                        "fields": [
                            {"name": "sensor_id", "label": "传感器模组ID", "type": "int"},
                            {"name": "channel_code", "label": "通道编号(1-6)", "type": "int"},
                            {"name": "name", "label": "气体名称(CO/H2S/O2/EX/CO2/NOX/SF6)", "type": "string"},
                            {"name": "value", "label": "气体浓度值", "type": "float"},
                            {"name": "unit", "label": "浓度单位(PPM/%VOL/%LEL)", "type": "string"}
                        ]
                    }
                },
                {
                    "action": "query",
                    "action_name": "即时读取",
                    "description": "不触发气泵预热与开关，直接即时读取当前气体传感器数据",
                    "scopes": ["task"],
                    "params": [],  # 默认即时查询所有挂载模组浓度
                    "returns": {
                        "type": "array",
                        "description": "拍平的气体通道实时浓度列表",
                        "fields": [
                            {"name": "sensor_id", "label": "传感器模组ID", "type": "int"},
                            {"name": "channel_code", "label": "通道编号", "type": "int"},
                            {"name": "name", "label": "气体名称", "type": "string"},
                            {"name": "value", "label": "气体浓度值", "type": "float"},
                            {"name": "unit", "label": "浓度单位", "type": "string"}
                        ]
                    }
                },
                {
                    "action": "level",
                    "action_name": "流量调节",
                    "description": "动态调整气泵抽气流量档位",
                    "scopes": ["config"],
                    "params": [
                        {
                            "name": "flow_level",
                            "label": "流量档位(1-10级)",
                            "type": "int",
                            "default": 10,
                            "min": 1,
                            "max": 10,
                            "step": 1,
                            "required": True,
                            "ui_component": "slider"
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
                    "action": "start",
                    "action_name": "开启气泵",
                    "description": "开启指定传感器的抽气气泵",
                    "scopes": ["config"],
                    "params": [
                        {
                            "name": "flow_level",
                            "label": "启动流量档位(1-10级)",
                            "type": "int",
                            "default": 10,
                            "min": 1,
                            "max": 10,
                            "ui_component": "slider"
                        }
                    ],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"}
                        ]
                    }
                },
                {
                    "action": "stop",
                    "action_name": "关闭气泵",
                    "description": "关闭指定传感器的抽气气泵",
                    "scopes": ["config"],
                    "params": [],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"}
                        ]
                    }
                },
                {
                    "action": "channel",
                    "action_name": "通道查询",
                    "description": "读取 80-byte 完整的通道配置参数（量程、放大倍数、报警点等）",
                    "scopes": ["config"],
                    "params": [],  # 默认读取所有挂载模组的通道配置参数
                    "returns": {
                        "type": "array",
                        "fields": [
                            {"name": "sensor_id", "label": "模组ID", "type": "int"},
                            {"name": "channel_code", "label": "通道编号", "type": "int"},
                            {"name": "gas_name", "label": "气体名称", "type": "string"},
                            {"name": "range_max", "label": "满量程上限", "type": "float"},
                            {"name": "unit", "label": "单位", "type": "string"},
                            {"name": "alarm_low", "label": "低报数值", "type": "float"},
                            {"name": "alarm_high", "label": "高报数值", "type": "float"}
                        ]
                    }
                },
                {
                    "action": "base",
                    "action_name": "信息查询",
                    "description": "读取设备的 UID 硬件唯一识别码、软硬件版本号与厂商信息",
                    "scopes": ["config"],
                    "params": [],
                    "returns": {
                        "type": "array",
                        "fields": [
                            {"name": "channel_count", "label": "通道数量", "type": "int"},
                            {"name": "device_uid", "label": "设备UID", "type": "string"},
                            {"name": "manufacturer", "label": "厂商名称", "type": "string"},
                            {"name": "hardware_version", "label": "硬件版本", "type": "string"},
                            {"name": "software_version", "label": "软件版本", "type": "string"},
                            {"name": "build_time", "label": "出厂/构建时间", "type": "string"},
                            {"name": "sensor_id", "label": "传感器ID", "type": "int"}
                        ]
                    }
                },
                {
                    "action": "calibrate",
                    "action_name": "通道校准",
                    "description": "下发指定通道的零点/标气校准，保存校准数据至 Flash",
                    "scopes": ["config"],
                    "danger_level": "warning",
                    "confirm_msg": "确定要对该气体通道下发校准命令吗？这会覆盖硬件 Flash 中的基准校准点！",
                    "params": [
                        {
                            "name": "sensor_id",
                            "label": "目标传感器模组",
                            "type": "int",
                            "required": True,
                            "ui_component": "select",
                            "options": [{"name": "模组1", "value": 1}, {"name": "模组2", "value": 2}]
                        },
                        {
                            "name": "channel_code",
                            "label": "通道编号",
                            "type": "int",
                            "required": True,
                            "ui_component": "select",
                            "options": [{"name": "通道1", "value": 1}, {"name": "通道2", "value": 2}, {"name": "通道3", "value": 3}, {"name": "通道4", "value": 4}, {"name": "通道5", "value": 5}, {"name": "通道6", "value": 6}]
                        },
                        {
                            "name": "level",
                            "label": "校准类型",
                            "type": "int",
                            "required": True,
                            "ui_component": "select",
                            "options": [{"name": "零点校准", "value": 0}, {"name": "一级校准", "value": 1}]
                        },
                        {
                            "name": "calibration_data",
                            "label": "标气标准值(PPM)",
                            "type": "float",
                            "default": 0.0,
                            "ui_component": "input_number"
                        },
                        {
                            "name": "calibration_ad",
                            "label": "校准AD值",
                            "type": "int",
                            "default": 0,
                            "ui_component": "input_number"
                        }
                    ],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "sensor_id", "label": "目标模组ID", "type": "int"},
                            {"name": "channel_code", "label": "通道编号", "type": "int"},
                            {"name": "success", "label": "校准结果", "type": "bool"}
                        ]
                    }
                },
                {
                    "action": "reset",
                    "action_name": "恢复出厂",
                    "description": "复位指定通道或全模组出厂校准参数",
                    "scopes": ["config"],
                    "danger_level": "warning",
                    "confirm_msg": "高危操作警告：恢复出厂设置将清除硬件中的自定义校准点，无法撤销！",
                    "params": [
                        {
                            "name": "channel_code",
                            "label": "目标通道(255表示全部)",
                            "type": "int",
                            "default": 255,
                            "ui_component": "input_number"
                        }
                    ],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "状态", "type": "string"},
                            {"name": "message", "label": "描述", "type": "string"}
                        ]
                    }
                },
                {
                    "action": "cycle",
                    "action_name": "循环采集",
                    "description": "控制气泵开启/关闭，并进行周期的气体数据循环采集与 status/up 主题定时上报",
                    "scopes": ["task"],
                    "params": [
                        {
                            "name": "action",
                            "label": "操作动作",
                            "type": "string",
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
                    "action": "set_config",
                    "action_name": "下发配置",
                    "description": "设置并持久化各气体通道浓度告警阈值与告警提示语",
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
                    "description": "获取当前本地持久化保存的气体告警配置列表",
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
                    "action": "status",
                    "action_name": "状态查询",
                    "description": "检查串口在线状态",
                    "scopes": ["config"],  # 纯底层诊断动作
                    "params": [],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "online", "label": "串口在线状态", "type": "bool"}
                        ]
                    }
                }
            ],
            "config_metrics": [
                {"metric_name": "CO2", "label": "二氧化碳", "unit": "PPM", "type": "float", "alarm_type": ["info", "warning", "error", "fatal"], "operator": ["lt", "lte", "gt", "gte", "between", "eq"]},
                {"metric_name": "CO", "label": "一氧化碳", "unit": "PPM", "type": "float", "alarm_type": ["info", "warning", "error", "fatal"], "operator": ["lt", "lte", "gt", "gte", "between", "eq"]},
                {"metric_name": "H2S", "label": "硫化氢", "unit": "PPM", "type": "float", "alarm_type": ["info", "warning", "error", "fatal"], "operator": ["lt", "lte", "gt", "gte", "between", "eq"]},
                {"metric_name": "O2", "label": "氧气浓度", "unit": "%VOL", "type": "float", "alarm_type": ["info", "warning", "error", "fatal"], "operator": ["lt", "lte", "gt", "gte", "between", "eq"]},
                {"metric_name": "EX", "label": "可燃气体", "unit": "%LEL", "type": "float", "alarm_type": ["info", "warning", "error", "fatal"], "operator": ["lt", "lte", "gt", "gte", "between", "eq"]},
                {"metric_name": "SF6", "label": "六氟化硫", "unit": "PPM", "type": "float", "alarm_type": ["info", "warning", "error", "fatal"], "operator": ["lt", "lte", "gt", "gte", "between", "eq"]},
                {"metric_name": "NOX", "label": "氮氧化物", "unit": "PPM", "type": "float", "alarm_type": ["info", "warning", "error", "fatal"], "operator": ["lt", "lte", "gt", "gte", "between", "eq"]}
            ]
        }

    def get_status(self) -> bool:
        """根据串口状态返回连接状态"""
        if not self.drivers:
            return False
        for driver in self.drivers.values():
            try:
                ser = driver._get_serial_connection()
                if ser is not None and ser.is_open:
                    return True
            except Exception as e:
                logger.error('捕获到异常', exc_info=True)
        return False
