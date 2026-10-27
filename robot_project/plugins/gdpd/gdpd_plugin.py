import os
import json
import time
from typing import Dict, Any, List, Optional
from plugins.base import BasePlugin
from core.logger_manager import get_logger
from utils.constants import PROJECT_ROOT
from .gdpd_driver import GdpdDriver

logger = get_logger("GdpdPlugin")

class GdpdPlugin(BasePlugin):
    """
    GDPD 局放数据采集与业务控制插件 (GdpdPlugin)
    严格执行业务规范：
    1. 默认基于 485串口 连接（对齐 rs485_jf.c 配置规范），同时支持可选的 TCP 网关模式。
    2. 启动 (Start) -> 连续采集 (Acquire) -> 停止 (Stop) 的标准化全自动闭环流程。
    3. 启动后间隔 1s 连续采集 10 次。
    4. 指标统计原则：
       - 局部放电峰值 (Peak Value) 取最大值 (Max)
       - 局部放电平均值 (Average Value) 取算术平均值 (Average)
       - 局部放电频次 (Discharge Count / Frequency) 取累加和 (Sum)
    5. 插件层与下层驱动 (GdpdDriver) 完全分离。
    6. 告警规则配置：支持动态 get_config / set_config 热重载局放峰值 (PEAK) 告警规则。
    """
    def __init__(self, config: dict = None):
        super().__init__(config)
        self.plugin_name = self.__class__.__name__

        # 读取插件串口与通信基础配置
        self.conn_type = self.config.get("conn_type", "serial")
        self.port = self.config.get("port", "/dev/ttyUSB0")
        self.baudrate = int(self.config.get("baudrate", 9600))
        self.data_bits = int(self.config.get("data_bits", 8))
        self.stop_bits = int(self.config.get("stop_bits", 1))
        self.parity = self.config.get("parity", "N")
        self.timeout = float(self.config.get("timeout", 2.0))
        self.ip = self.config.get("ip", "127.0.0.1")
        self.sample_count = int(self.config.get("sample_count", 10))
        self.sample_interval = float(self.config.get("sample_interval", 1.0))

        # 告警规则配置文件路径 (对齐 data/plugins/ 目录规范)
        self.alarm_config_path = os.path.join(PROJECT_ROOT, "data", "plugins", "GdpdPlugin_alarm.json")

        # 实例化默认底层硬件驱动
        self.driver = GdpdDriver(
            port=self.port,
            baudrate=self.baudrate,
            data_bits=self.data_bits,
            stop_bits=self.stop_bits,
            parity=self.parity,
            timeout=self.timeout,
            conn_type=self.conn_type,
            ip=self.ip
        )

        # 缓存最后一次检测统计报告
        self.latest_report: Dict[str, Any] = {}
        self._is_paused: bool = False

        logger.info(f"✨ [{self.plugin_name}] 初始化完毕 -> 模式: [{self.conn_type}], 目标: [{self.port}] (Baud:{self.baudrate}), 自动流程: 间隔 {self.sample_interval}s 采集 {self.sample_count} 次")

    def execute(self, action: str, params: dict) -> dict:
        """插件业务控制执行入口"""
        action_lower = action.lower()
        if action_lower != "pause" and self._is_paused:
            logger.warning(f"⏸️ [{self.plugin_name}] 处于暂停状态，中断动作。")
            return {"status": "paused", "message": "局放全闭环采集任务因暂停被中断"}
        params = params or {}
        logger.info(f"[{self.plugin_name}] 收到动作 -> [{action}], 参数: {params}")

        # 0. 阈值配置热重载能力 (set_config / get_config，无需硬件驱动参与)
        if action_lower == "set_config":
            raw_rules = params.get("config", params)
            try:
                os.makedirs(os.path.dirname(self.alarm_config_path), exist_ok=True)
                with open(self.alarm_config_path, "w", encoding="utf-8") as f:
                    json.dump(raw_rules, f, ensure_ascii=False, indent=2)
                logger.info(f"💾 [{self.plugin_name}] 局放告警配置已持久化至 {self.alarm_config_path}")
                return {
                    "status": "success",
                    "message": f"成功保存局放告警配置至 {self.alarm_config_path}",
                    "data": raw_rules
                }
            except Exception as e:
                logger.error(f"❌ [{self.plugin_name}] 保存局放告警配置失败: {e}")
                return {"status": "error", "message": f"保存配置文件失败: {e}"}

        elif action_lower == "get_config":
            if os.path.exists(self.alarm_config_path):
                try:
                    with open(self.alarm_config_path, "r", encoding="utf-8") as f:
                        cfg_data = json.load(f)
                    return {
                        "status": "success",
                        "message": "成功获取局放告警配置",
                        "data": cfg_data
                    }
                except Exception as e:
                    logger.error(f"❌ [{self.plugin_name}] 读取局放告警配置文件失败: {e}")
                    return {"status": "error", "message": f"读取配置文件失败: {e}"}
            else:
                return {
                    "status": "success",
                    "message": "尚未配置自定义局放告警规则，当前无本地配置文件",
                    "data": []
                }

        # 动态参数支持重载驱动通信链路目标 (支持切到临时串口或仿真 TCP 端口)
        conn_type = params.get("conn_type", self.conn_type)
        port = params.get("port", self.port)
        baudrate = int(params.get("baudrate", self.baudrate))
        ip = params.get("ip", self.ip)

        if conn_type == self.conn_type and port == self.port and baudrate == self.baudrate and ip == self.ip:
            driver = self.driver
        else:
            driver = GdpdDriver(
                port=port,
                baudrate=baudrate,
                data_bits=self.data_bits,
                stop_bits=self.stop_bits,
                parity=self.parity,
                timeout=self.timeout,
                conn_type=conn_type,
                ip=ip
            )

        # 1. 核心自动全闭环业务：启动 -> 连续采集10次并算统计值 -> 停止
        if action_lower == "monitor":
            count = int(params.get("sample_count", self.sample_count))
            interval = float(params.get("sample_interval", self.sample_interval))
            return self._execute_auto_monitor_sequence(driver, count, interval)

        # 2. 单独启动指令
        elif action_lower == "start":
            success = driver.start_acquisition()
            return {
                "status": "success" if success else "error",
                "message": "启动局放采集成功" if success else "启动局放采集指令下发失败"
            }

        # 3. 单次采集指令
        elif action_lower == "acquire":
            raw_data = driver.acquire_data()
            if raw_data:
                data = {
                    "peak": raw_data.get("peak", 0.0),
                    "mean": raw_data.get("average", 0.0),
                    "frequency": raw_data.get("frequency", 0)
                }
                return {"status": "success", "message": "单次数据读取成功", "data": data}
            return {"status": "error", "message": "单次读取无响应或校验失败"}

        # 4. 单独停止指令
        elif action_lower == "stop":
            success = driver.stop_acquisition()
            return {
                "status": "success" if success else "error",
                "message": "停止局放采集成功" if success else "停止局放采集指令下发失败"
            }

        # 5. 清频次计数指令
        elif action_lower == "clear":
            success = driver.clear_frequency()
            return {
                "status": "success" if success else "error",
                "message": "频次计数清零成功" if success else "清频指令下发失败"
            }

        # 6. 查询缓存状态/报告
        elif action_lower == "status":
            is_online = self.get_status()
            return {
                "status": "success" if is_online else "error",
                "message": "局放检测仪在线" if is_online else "局放检测仪离线",
                "data": {"online": is_online}
            }

        msg = f"不支持的局放动作指令: {action}"
        logger.error(f"[{self.plugin_name}] {msg}")
        return {"status": "error", "message": msg}

    def _execute_auto_monitor_sequence(self, driver: GdpdDriver, count: int, interval: float) -> dict:
        """
        执行核心业务流程：
        启动 -> 间隔 interval 秒连续采集 count 次 -> 停止
        计算指标：峰值取最大值(Max)，平均值取算术平均值(Average)，频次取累加和(Sum)
        """
        logger.info(f"🚀 [{self.plugin_name}] 启动全闭环局放采集任务 (共 {count} 次, 间隔 {interval}s)...")

        # 步骤 1：启动局放检测
        if not driver.start_acquisition():
            msg = "启动局放检测流程失败：底层硬件指令返回错误或超时"
            logger.error(f"[{self.plugin_name}] {msg}")
            return {"status": "error", "message": msg}

        peaks: List[float] = []
        averages: List[float] = []
        frequencies: List[int] = []

        # 步骤 2：间隔 1s 连续采集 10 次
        for i in range(1, count + 1):
            logger.debug(f"[{self.plugin_name}] 正在执行第 {i}/{count} 次局放数据抓取...")
            res = driver.acquire_data()
            if res:
                p = res["peak"]
                a = res["average"]
                f = res["frequency"]
                peaks.append(p)
                averages.append(a)
                frequencies.append(f)
                logger.info(f"📊 [{self.plugin_name}] 抓取第 {i}/{count} 次 -> 峰值: {p:.2f} dBm, 平均: {a:.2f} dBm, 频次: {f}")
            else:
                logger.warning(f"⚠️ [{self.plugin_name}] 第 {i}/{count} 次数据抓取失败或报文损坏，将继续下一次")

            if self._is_paused:
                logger.warning(f"⏸️ [{self.plugin_name}] 采样循环中检测到暂停信号，终止采集并返回暂停状态。")
                driver.stop_acquisition()
                return {"status": "paused", "message": "局放全闭环采集任务因暂停被中断"}

            if i < count and interval > 0:
                start_sleep = time.time()
                while time.time() - start_sleep < interval:
                    if self._is_paused:
                        logger.warning(f"⏸️ [{self.plugin_name}] 采样间隔等待检测到暂停信号，终止采集。")
                        driver.stop_acquisition()
                        return {"status": "paused", "message": "局放全闭环采集任务因暂停被中断"}
                    time.sleep(0.1)

        # 步骤 3：停止局放检测 (无论中间是否有丢包，均需安全发送停止指令)
        logger.info(f"🛑 [{self.plugin_name}] 连续采样结束，正在下发停止采集指令...")
        stop_ok = driver.stop_acquisition()
        if not stop_ok:
            logger.warning(f"⚠️ [{self.plugin_name}] 停止指令下发异常，可能硬件已离线或超时")

        # 步骤 4：指标计算与校验
        if not peaks:
            msg = f"连续 {count} 次局放采集均未获取到有效数据，无法生成报告"
            logger.error(f"[{self.plugin_name}] {msg}")
            return {"status": "error", "message": msg}

        # 1. 局部放电峰值取最大值 (Max)
        max_peak = round(max(peaks), 2)
        # 2. 局部放电平均值取算术平均值 (Average)
        avg_val = round(sum(averages) / len(averages), 2)
        # 3. 局部放电频次取累加和 (Sum)
        sum_freq = int(sum(frequencies))

        self.latest_report = {
            "peak": max_peak,
            "mean": avg_val,
            "frequency": sum_freq
        }

        logger.info(f"🎉 [{self.plugin_name}] 统计报表生成成功 -> Peak峰值={max_peak} dBm, Mean平均值={avg_val} dBm, Frequency总频次={sum_freq} (有效样本数={len(peaks)}/{count})")
        return {
            "status": "success",
            "message": "局放全闭环采集与数据统计成功",
            "data": self.latest_report
        }

    def pause(self) -> None:
        """暂停局放采集：下发停止采集指令，置暂停标志"""
        if self._is_paused:
            logger.warning(f"[{self.plugin_name}] 局放插件已处于暂停状态，忽略 pause 请求")
            return
        self._is_paused = True
        logger.warning(f"⏸️ [{self.plugin_name}] 收到 pause 暂停信号，下发 stop 采集指令...")
        try:
            self.driver.stop_acquisition()
            logger.info(f"✅ [{self.plugin_name}] 局放停止采集指令下发成功")
        except Exception as e:
            logger.error(f"❌ [{self.plugin_name}] 下发 stop 指令异常: {e}")

    def resume(self) -> None:
        """恢复局放检测"""
        self._is_paused = False
        logger.info(f"▶️ [{self.plugin_name}] 恢复局放检测，暂停标志已清除。")

    def abort(self) -> None:
        """紧急终止：向设备下发停止采集报文"""
        self._is_paused = False
        logger.warning(f"🚨 [{self.plugin_name}] 收到 abort 紧急终止信号，下发 stop 指令...")
        try:
            self.driver.stop_acquisition()
        except Exception as e:
            logger.error('捕获到异常', exc_info=True)

    def get_capabilities(self) -> dict:
        """获取局放检测插件标准能力清单元数据 (Schema)"""
        return {
            "plugin_type": self.plugin_name,
            "plugin_name": "局放插件",
            "description": "基于 TEV 地电波局放检测仪的自动采样、峰值/均值/频次统计分析能力",
            "version": "1.3.0",
            "supported_actions": [
                {
                    "action": "monitor",
                    "action_name": "局放检测",
                    "description": "闭环局放采样流程：启动检测 -> 连续多次采样 -> 自动统计峰值与频次 -> 发送停止",
                    "scopes": ["task"],
                    "params": [
                        {"name": "sample_count", "label": "采样次数", "type": "int", "default": 10, "required": False, "ui_component": "input_number"},
                        {"name": "sample_interval", "label": "采样间隔(s)", "type": "float", "default": 1.0, "required": False, "ui_component": "input_number"}
                    ],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "peak", "label": "局放峰值(dBm)", "type": "float"},
                            {"name": "mean", "label": "局放均值(dBm)", "type": "float"},
                            {"name": "frequency", "label": "局放放电频次", "type": "int"}
                        ]
                    }
                },
                {
                    "action": "start",
                    "action_name": "启动采集",
                    "description": "单独向 TEV 硬件下发开始监测采样指令",
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
                    "action": "acquire",
                    "action_name": "读取局放",
                    "description": "单次读取当前实时局放幅值与频次数据",
                    "scopes": ["config"],
                    "params": [],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "peak", "label": "局放峰值(dBm)", "type": "float"},
                            {"name": "mean", "label": "局放均值(dBm)", "type": "float"},
                            {"name": "frequency", "label": "局放放电频次", "type": "int"}
                        ]
                    }
                },
                {
                    "action": "stop",
                    "action_name": "停止采集",
                    "description": "向 TEV 硬件下发停止监测采样指令",
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
                    "action": "clear",
                    "action_name": "数据清空",
                    "description": "清空局放检测仪内部缓存数据",
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
                    "action": "set_config",
                    "action_name": "设置局放告警配置",
                    "description": "配置局放检测峰值阈值告警规则",
                    "scopes": ["config"],
                    "params": [
                        {"name": "config", "label": "告警规则配置", "type": "array", "required": True, "ui_component": "json_editor"}
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
                    "action_name": "获取局放告警配置",
                    "description": "获取当前本地持久化保存的局放峰值告警配置",
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
                    "description": "查询局放检测仪串口或 TCP 通讯在线状态",
                    "scopes": ["config"],
                    "params": [],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "online", "label": "在线状态", "type": "bool"}
                        ]
                    }
                }
            ],
            "config_metrics": [
                {
                    "metric_name": "PEAK",
                    "label": "局放峰值",
                    "unit": "dBm",
                    "type": "float",
                    "alarm_type": ["info", "warning", "error", "fatal"],
                    "operator": ["lt", "lte", "gt", "gte", "between", "eq"]
                }
            ]
        }

    def get_status(self) -> bool:
        """检查局放通道连接状态 (TCP 则测试 TCP 连接池，串口则判断串口状态)"""
        try:
            if self.conn_type.lower() == "tcp":
                from core.tcp_manager import TCPManager
                pool = TCPManager()
                target_port = int(self.config.get("port", 8080)) if str(self.config.get("port", "8080")).isdigit() else 8080
                sock = pool.get_connection(self.ip, target_port, timeout=2.0)
                return sock is not None
            else:
                ser = self.driver._get_serial_connection()
                return ser is not None and ser.is_open
        except Exception as e:
            logger.error('操作引发异常:', exc_info=True)
            return False
