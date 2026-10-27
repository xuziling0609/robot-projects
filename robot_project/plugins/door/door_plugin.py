import time
import concurrent.futures
from plugins.base import BasePlugin
from .fmk02_driver import FMK02Driver
from core.logger_manager import get_logger

logger = get_logger("DoorPlugin")

class DoorPlugin(BasePlugin):
    def __init__(self, config: dict = None):
        super().__init__(config)
        # 提取类名作为日志前缀
        self.plugin_name = self.__class__.__name__
        self.current_drivers = [] 
        self.port = self.config.get("port", 1030)
        self.timeout = float(self.config.get("timeout", 3.0))
        self._is_paused: bool = False
        self._action_counter = 0
        logger.info(f"🚪 开门机插件初始化完毕 (端口: {self.port}, 超时: {self.timeout}s)")

    def execute(self, action: str, params: dict) -> dict:
        params = params or {}
        action_lower = action.lower()
        self._action_counter += 1
        my_action_id = self._action_counter

        if action_lower != "pause" and self._is_paused:
            logger.warning(f"⏸️ [{self.plugin_name}] 处于暂停状态，中断动作。")
            return {"status": "paused", "message": "开门机动作因暂停被中断"}

        if action_lower == "status":
            is_online = self.get_status()
            return {
                "status": "success" if is_online else "error",
                "message": "开门机插件运行正常" if is_online else "开门机插件未就绪",
                "data": {"online": is_online}
            }

        ips = params.get("ips") or []
        if isinstance(ips, str):
            ips = [ips]
        
        logger.info(f"[{self.plugin_name}] 收到动作 -> [{action}], 目标: {ips}")

        if not ips:
            msg = "未提取到门控 IPs (请提供 ips 数组或 ip 字符串)"
            logger.error(f"[{self.plugin_name}] {msg}")
            return {"status": "error", "message": msg}

        cmd_map = {"open": "OPEN", "close": "CLOSE", "pause": "PAUSE"}
        hw_cmd = cmd_map.get(action_lower)
        
        if not hw_cmd:
            msg = f"不支持的动作: {action}"
            logger.error(f"[{self.plugin_name}] {msg}")
            return {"status": "error", "message": msg}

        self.current_drivers = [FMK02Driver(ip, self.port, self.timeout) for ip in ips]

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(ips)) as executor:
            send_results = list(executor.map(lambda d: d.send_command(hw_cmd), self.current_drivers))
            
        if not all(send_results):
            logger.error(f"[{self.plugin_name}] ❌ 网络指令下发失败。")
            return {"status": "error", "message": "部分门控机指令失败"}

        if hw_cmd == "PAUSE":
            return {"status": "success", "message": f"{len(ips)} 部开门机已成功下发暂停"}

        if hw_cmd == "CLOSE":
            time.sleep(0.5)
            return {"status": "success", "message": f"{len(ips)} 部开门机已成功下发关门指令"}

        logger.info(f"[{self.plugin_name}] 进入状态轮询...")
        target_status = "FULLY_OPENED" if hw_cmd == "OPEN" else "FULLY_CLOSED"
        start_time = time.time()
        default_timeout = 30
        consecutive_net_errors = 0
        
        while time.time() - start_time < default_timeout:
            if self._is_paused:
                logger.warning(f"⏸️ [{self.plugin_name}] 状态轮询过程中检测到 pause 暂停信号，终止轮询。")
                return {"status": "paused", "message": "开门机动作因暂停被中断"}
            
            if self._action_counter != my_action_id:
                logger.warning(f"🚨 [{self.plugin_name}] 状态轮询过程中检测到动作 ID 变更 (可能被 abort 或被新指令覆盖)，立即终止原轮询。")
                return {"status": "error", "message": "开门机动作因全局急停或新指令被中断"}

            with concurrent.futures.ThreadPoolExecutor(max_workers=len(ips)) as executor:
                statuses = list(executor.map(lambda d: d.get_sensor_status(), self.current_drivers))

            if "NETWORK_ERROR" in statuses:
                consecutive_net_errors += 1
                logger.warning(f"⚠️ 状态轮询出现网络抖动/超时 ({consecutive_net_errors}/3 次)")
                if consecutive_net_errors >= 3:
                    return {"status": "error", "message": "状态轮询链路断开 (连续 3 次网络错误)"}
            else:
                consecutive_net_errors = 0

            if all(s == target_status for s in statuses):
                return {"status": "success", "message": f"开门机 {action} 完成"}
                
            time.sleep(0.5)

        return {"status": "error", "message": "动作超时"}

    def abort(self) -> dict:
        """全局急停与打断：中断当前轮询等待，并下发暂停防止门机继续运动"""
        logger.warning(f"🚨 [{self.plugin_name}] 收到全局打断指令，准备中断轮询并下发停止...")
        self._action_counter += 1
        self._is_paused = False  # 清除暂停标志，以免影响后续撤回动作(如强制关门)
        
        # 为了物理安全，打断时让门机立即停在原地
        if self.current_drivers:
            try:
                for d in self.current_drivers:
                    d.send_command("PAUSE")
            except Exception as e:
                logger.error(f"门控机打断异常: {e}")
                
        return {"status": "success", "message": "门机任务已安全打断"}

    def pause(self) -> None:
        """暂停开门机控制：下发 PAUSE 指令至所有门控机"""
        if self._is_paused:
            logger.warning(f"[{self.plugin_name}] 开门机插件已处于暂停状态，忽略 pause 请求")
            return
        self._is_paused = True
        logger.info(f"⏸️ [{self.plugin_name}] 暂停开门机：下发 PAUSE 指令...")
        if self.current_drivers:
            try:
                for d in self.current_drivers:
                    d.send_command("PAUSE")
                logger.info(f"✅ [{self.plugin_name}] 门控机暂停指令下发完毕")
            except Exception as e:
                logger.error(f"❌ [{self.plugin_name}] 门控机下发 pause 异常: {e}")

    def resume(self) -> None:
        """恢复开门机控制"""
        self._is_paused = False
        logger.info(f"▶️ [{self.plugin_name}] 恢复开门机控制，暂停标志已清除。")

    def abort(self) -> None:
        """终止/打断门控机控制：下发 PAUSE 指令至所有门控机并清除暂停标志"""
        self._is_paused = False
        logger.info(f"🛑 [{self.plugin_name}] 触发 abort 方法，清除暂停标志并下发 PAUSE 指令...")
        if self.current_drivers:
            try:
                for d in self.current_drivers:
                    d.send_command("PAUSE")
                logger.info(f"✅ [{self.plugin_name}] 门控机 abort 指令下发完毕")
            except Exception as e:
                logger.error(f"❌ [{self.plugin_name}] 门控机下发 abort 异常: {e}")

    def get_status(self) -> bool:
        """开门机插件状态（规范定义直接返回 True）"""
        return True

    def get_capabilities(self) -> dict:
        """获取开门机插件标准能力清单元数据 (Schema)"""
        return {
            "plugin_type": self.plugin_name,
            "plugin_name": "开门机插件",
            "description": "提供电动推拉门控机的开门、关门与急停控制能力",
            "version": "1.2.0",
            "supported_actions": [
                {
                    "action": "open",
                    "action_name": "自动开门",
                    "description": "控制开门机机构打开门体",
                    "scopes": ["task"],
                    "params": [
                        {"name": "ips", "label": "门控机IP列表", "type": "array", "required": False, "ui_component": "input_text"}
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
                    "action_name": "自动关门",
                    "description": "控制开门机机构关闭门体",
                    "scopes": ["task"],
                    "params": [
                        {"name": "ips", "label": "门控机IP列表", "type": "array", "required": False, "ui_component": "input_text"}
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
                    "action": "pause",
                    "action_name": "停止动作",
                    "description": "控制门体运动立即停止",
                    "scopes": ["task"],
                    "params": [
                        {"name": "ips", "label": "门控机IP列表", "type": "array", "required": False, "ui_component": "input_text"}
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
                    "description": "查询开门机网络与联动状态",
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