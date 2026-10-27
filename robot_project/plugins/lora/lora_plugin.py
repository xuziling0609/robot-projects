import time
import threading
from typing import Dict, Any, Optional
from plugins.base import BasePlugin
from core.logger_manager import get_logger
from core.context_manager import ContextManager
from .lora_driver import LoraTCPDriver, LoraProtocol

logger = get_logger("LoraPlugin")

class LoraPlugin(BasePlugin):
    """
    LoRa 核心通讯与网关交互插件 (LoraPlugin)
    严格规范：
    1. 底层通信与协议封装独立拆解至 lora_driver.py，插件层专注于事件协调与生命周期管理。
    2. 监听 TCP 心跳报文(0x50)或转发报文(0x60)。
    3. 机器人实时状态不通过 HTTP 轮询，而是直接绑定获取导航插件(如 NavPlugin)的主动推送状态数据。
    4. 延时 5 秒进行 LoRa 报文射出，支持互斥锁防止抖动重投。
    """
    def __init__(self, config: dict = None):
        super().__init__(config)
        self.plugin_name = self.__class__.__name__

        # 解析插件配置
        self.host = self.config.get("host")
        self.port = int(self.config.get("port", 1030))
        self.robot_id = str(self.config.get("robot_id", "robot888"))
        self.delay_seconds = float(self.config.get("delay_seconds", 5.0))
        self.nav_plugin_name = self.config.get("nav_plugin_name", "NavPlugin")

        # 状态字典由 ContextManager 接管，此处仅保留基础通信属性
        self.last_report_time: float = 0.0
        self.last_heartbeat_time: float = 0.0
        self.last_packet_type: str = "NONE"

        # 1. 实例化底层 LoRa TCP 驱动
        self.driver = LoraTCPDriver(
            host=self.host,
            port=self.port,
            on_trigger_callback=self._on_tcp_trigger
        )

        # 2. 启动驱动长连接监听
        self.driver.start()

        # 3. 无需再启动多余的后台解耦绑定线程，完全依赖 ContextManager

        self._is_paused: bool = False
        logger.info(f"✨ [{self.plugin_name}] 初始化完毕 -> 绑定网关 [{self.host}:{self.port}], 状态来源: [{self.nav_plugin_name}] 主动推送")

    def _on_tcp_trigger(self, trigger_ts: float, pkt_type: str):
        """
        响应底层驱动的 TCP 心跳或转发报文触发事件
        在独立的后台触发线程中运行，绝不阻塞网络流接收
        """
        self.last_heartbeat_time = trigger_ts
        self.last_packet_type = pkt_type
        logger.debug(f"⚡ [{self.plugin_name}] 响应 LoRa 触发报文 [{pkt_type}] -> 获取主动推送状态并调度延时 {self.delay_seconds}s 上报...")

        # 1. 直接获取公共内存池中最新机器人状态与任务引擎状态 (0 延迟)
        current_status = ContextManager.get_robot_status()
        current_task = ContextManager.get_robot_task()
        if not current_status:
            # 容错降级：若内存池尚未收到首次状态推送，尝试主动拉取一次导航插件最新状态
            try:
                from core.plugin_manager import PluginManager
                pm = PluginManager()
                nav_plugin = pm.get_plugin(self.nav_plugin_name)
                if nav_plugin and hasattr(nav_plugin, "get_status"):
                    current_status = nav_plugin.get_status()
            except Exception as e:
                logger.error(f"❌ 降级获取 [{self.nav_plugin_name}] 状态异常: {e}")
        
        # 2. 转换成 LoRa 协议规范的 7 元素列表 (包含任务引擎状态映射)
        status_list = LoraProtocol.parse_robot_status_to_list(
            status_json=current_status,
            task_json=current_task,
            default_robot_id=self.robot_id
        )
        logger.debug(f"📋 [{self.plugin_name}] 构建上报数据包状态内容: {status_list}")

        # 3. 调度延迟发送 (精准保障 5 秒后射出)
        success = self.driver.schedule_send_report(status_list, trigger_ts, delay_seconds=self.delay_seconds)
        if success:
            self.last_report_time = time.time()

    def execute(self, action: str, params: dict) -> dict:
        """插件统一执行控制入口"""
        params = params or {}
        action_lower = action.lower()
        logger.info(f"[{self.plugin_name}] 收到动作 -> [{action}], 参数: {params}")

        if action_lower in ["status", "get_status"]:
            is_online = self.get_status()
            return {
                "status": "success" if is_online else "error",
                "message": "LoRa TCP 网关连接正常" if is_online else "LoRa TCP 网关连接断开",
                "data": {"online": is_online}
            }

        elif action_lower in ["reconnect", "reset_connection"]:
            try:
                if hasattr(self.driver, "stop") and callable(self.driver.stop):
                    self.driver.stop()
                if hasattr(self.driver, "start") and callable(self.driver.start):
                    self.driver.start()
                return {"status": "success", "message": "LoRa TCP 重连成功"}
            except Exception as e:
                return {"status": "error", "message": f"LoRa 重连失败: {e}"}

        msg = f"不支持的 LoRa 动作: {action}"
        logger.error(f"[{self.plugin_name}] {msg}")
        return {"status": "error", "message": msg}

    def pause(self) -> None:
        pass

    def resume(self) -> None:
        pass

    def abort(self) -> None:
        pass

    def get_capabilities(self) -> dict:
        """获取 LoRa 插件标准能力清单元数据 (Schema)"""
        return {
            "plugin_type": self.plugin_name,
            "plugin_name": "LoRa插件",
            "description": "基于 433MHz/868MHz 广播监听、TCP心跳守护与离线状态延时上报能力",
            "version": "1.2.0",
            "supported_actions": [
                {
                    "action": "status",
                    "action_name": "状态查询",
                    "description": "查询 LoRa 通讯网关链路连接与心跳状态",
                    "scopes": ["config"],
                    "params": [],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "online", "label": "在线状态", "type": "bool"}
                        ]
                    }
                }
            ]
        }

    def get_status(self) -> bool:
        """检查 LoRa TCP 网关通道连接状态 (复用 TCP 连接池)"""
        try:
            from core.tcp_manager import TCPManager
            pool = TCPManager()
            sock = pool.get_connection(self.host, self.port, timeout=2.0)
            return sock is not None
        except Exception as e:
            logger.error('操作引发异常:', exc_info=True)
            return False
