import time
import threading
import concurrent.futures
from plugins.base import BasePlugin
from core.logger_manager import get_logger

# 引入底层硬件驱动
from .tasio211_driver import Tasio211Driver

logger = get_logger("StationPlugin")

class StationPlugin(BasePlugin):
    """狗窝基站(Station)并发控制插件 (业务层)"""

    def __init__(self, config: dict = None):
        super().__init__(config)
        
        # 提取配置 (兼容 params 嵌套与顶层平铺)
        params = self.config.get("params", {}) if isinstance(self.config, dict) else {}
        if not isinstance(params, dict):
            params = {}
        self.default_ip = self.config.get("ip") or params.get("ip") or "127.0.0.1"
        self.port = int(self.config.get("port") or params.get("port") or 10022)
        self.timeout = float(self.config.get("timeout") or params.get("timeout") or 3.0)
        self.uptime_success = float(self.config.get("uptime_success") or params.get("uptime_success") or 5.0)
        
        self.plugin_name = self.__class__.__name__
        self.driver = Tasio211Driver(port=self.port, timeout=self.timeout)
        self.cancel_event = threading.Event()
        self._is_paused: bool = False
        
        logger.info(f"✅ StationPlugin 挂载成功 (按需 TCP 模式, DO 端口: {self.port})")

    def execute(self, action: str, params: dict) -> dict:
        """插件标准执行入口，负责并发调度与结果聚合"""
        action_lower = action.lower()
        if action_lower != "pause" and self._is_paused:
            logger.warning(f"⏸️ [{self.plugin_name}] 处于暂停状态，中断动作。")
            return {"status": "paused", "message": "基站动作因暂停被中断"}
        self.cancel_event.clear()

        if action_lower == "status":
            return {
                "status": "success",
                "message": "充电站插件在线",
                "data": {"online": True}
            }

        if action_lower not in ["open", "close"]:
            return {"status": "error", "message": f"不支持的动作: {action}"}
            
        ip_list = params.get("ips") or []
        if isinstance(ip_list, str):
            ip_list = [ip_list]

        if not ip_list:
            return {"status": "error", "message": "ips 列表为空"}

        logger.info(f"==> 启动并发控制，目标设备数: {len(ip_list)}，动作: {action}")
        results = {}
        
        # 利用 ThreadPoolExecutor 并发调用底层驱动
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(ip_list)) as executor:
            future_to_ip = {executor.submit(self.driver.execute_door_action, ip, action): ip for ip in ip_list}
            for future in concurrent.futures.as_completed(future_to_ip):
                ip = future_to_ip[future]
                try:
                    success, reason = future.result()
                    results[ip] = {"success": success, "reason": reason}
                except Exception as e:
                    logger.error(f"[{ip}] 并发执行任务崩溃: {e}")
                    results[ip] = {"success": False, "reason": f"Thread crashed: {str(e)}"}

        success_ips = [ip for ip, res in results.items() if res["success"]]
        fail_details = {ip: res["reason"] for ip, res in results.items() if not res["success"]}
        
        # 判断强一致性结果
        if len(success_ips) == len(ip_list):
            logger.info(f"并发控制【全部成功】！目标列表: {success_ips}")
            success_reason = "开门成功" if action == "open" else "关门成功"
            
            # 维持动作后的状态时序 (可打断的 Event 阻塞等待)
            wait_time = self.uptime_success if action == "open" else 1.0
            if self.cancel_event.wait(wait_time):
                logger.warning(f"⚠️ [StationPlugin] 等待保持期间收到紧急停止 (Abort/Pause) 信号，提前唤醒退出。")
                if self._is_paused:
                    return {"status": "paused", "message": "基站等待过程因暂停被中断"}
                return {"status": "error", "message": "基站等待过程被急停打断"}
            
            return {"status": "success", "message": success_reason}
        else:
            reason_strings = [f"[{ip}] {reason}" for ip, reason in fail_details.items()]
            final_reason = " | ".join(reason_strings)
            logger.critical(f"【控制告警】强一致联动失败！失败详情: {final_reason}")
            
            return {"status": "error", "message": final_reason}

    def pause(self) -> None:
        """暂停充电站基站控制：设置 cancel_event 打断当前保持等待"""
        if self._is_paused:
            logger.warning(f"[{self.plugin_name}] 充电站插件已处于暂停状态，忽略 pause 请求")
            return
        self._is_paused = True
        logger.warning(f"⏸️ [{self.plugin_name}] 收到暂停信号，触发 cancel_event 打断等待...")
        self.cancel_event.set()

    def resume(self) -> None:
        """恢复充电站基站控制"""
        self.cancel_event.clear()
        self._is_paused = False
        logger.info(f"▶️ [{self.plugin_name}] 恢复充电站控制，暂停标志已清除。")

    def abort(self) -> dict:
        """【接口契约】强制中止当前动作 (全局急停)"""
        self._is_paused = False
        logger.warning("🚨 StationPlugin 收到紧急停止 (Abort) 信号！")
        self.cancel_event.set()
        return {"status": "success", "message": "多路站控基站已进入安全急停状态"}

    def status(self) -> bool:
        """获取当前插件就绪状态 (按需连接架构，初始化完成即视为就绪)"""
        return bool(self.port)

    def get_status(self) -> bool:
        """
        获取充电站插件状态 (按需连接架构：未执行动作时不主动握手 TCP 链路，避免后台轮询产生高频建连与超时风暴)
        """
        return True

    def check_connection(self, ip: str = None) -> bool:
        """按需探测充电站继电器 TCP 连通性，探测完毕立即关闭并释放 Socket 链路"""
        target_ip = ip or self.default_ip
        from core.tcp_manager import TCPManager
        pool = TCPManager()
        try:
            logger.info(f"[{self.plugin_name}] 🔍 正在按需探测 TCP 连通性 [{target_ip}:{self.port}]...")
            sock = pool.get_connection(target_ip, self.port, timeout=self.timeout)
            return sock is not None
        except Exception as e:
            logger.warning(f"[{self.plugin_name}] 充电站 TCP 连通性探测失败 [{target_ip}:{self.port}]: {e}")
            return False
        finally:
            pool.release_connection(target_ip, self.port)

    def get_capabilities(self) -> dict:
        """获取充电站插件标准能力清单元数据 (Schema)"""
        return {
            "plugin_type": self.__class__.__name__,
            "plugin_name": "充电站插件",
            "description": "基于 Tasio211 多路继电器的狗窝充电基站舱门控制与状态管理",
            "version": "1.2.0",
            "supported_actions": [
                {
                    "action": "open",
                    "action_name": "基站开门",
                    "description": "控制多路继电器开启充电站舱门",
                    "scopes": ["task"],
                    "params": [
                        {"name": "ips", "label": "继电器控制器IP列表", "type": "array", "required": False, "ui_component": "input_text"}
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
                    "action": "close",
                    "action_name": "基站关门",
                    "description": "控制多路继电器关闭充电站舱门",
                    "scopes": ["task"],
                    "params": [
                        {"name": "ips", "label": "继电器控制器IP列表", "type": "array", "required": False, "ui_component": "input_text"}
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
                    "action": "status",
                    "action_name": "状态查询",
                    "description": "查询充电基站继电器通讯与到位状态",
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