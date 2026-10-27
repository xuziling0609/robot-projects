import os
import sys
import time
import signal
import threading
import subprocess
from plugins.base import BasePlugin
from core.logger_manager import get_logger
from core.context_manager import ContextManager

logger = get_logger("SystemPlugin")

class SystemPlugin(BasePlugin):
    def __init__(self, config: dict = None):
        super().__init__(config)
        self.plugin_name = self.__class__.__name__
        self._is_paused: bool = False
        self._delay_event = None
        logger.info(f"✨ 初始化系统级核心能力插件: [{self.plugin_name}]")

    def _check_safety_interlock(self, force: bool = False) -> tuple[bool, str]:
        """
        检查当前系统/机器人任务状态安全互锁。
        若有动态任务处于 running 或 paused 状态，且未指定 force=True，则予以拦截保护。
        """
        try:
            task_info = ContextManager.get_robot_task()
            task_status = (task_info.get("status") or "idle").lower()
            task_id = task_info.get("task_id") or "UNKNOWN"
            if task_status in ["running", "paused"] and not force:
                return False, f"当前机器人正在执行或挂起任务[{task_id}]，已拒绝执行重启。如需紧急强制执行请指定 force=True"
        except Exception as e:
            logger.warning(f"[{self.plugin_name}] 安全互锁检测异常: {e}")
        return True, ""

    def _schedule_restart_service(self, delay_s: float = 1.0) -> None:
        """异步延时触发网关服务重启（确保 ACK_EXECUTE 报文先行发送完毕）"""
        def _do_restart():
            logger.info(f"[{self.plugin_name}] 重启守护线程启动，等待 {delay_s} 秒安全窗口...")
            time.sleep(max(0.1, delay_s))
            logger.warning(f"[{self.plugin_name}] 正在执行网关服务重启...")

            # 1. 尝试检测是否在 systemd 托管下运行
            is_systemd = False
            try:
                res = subprocess.run(["sudo", "-n", "systemctl", "is-active", "robot-gateway"],
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=2, text=True)
                if res.stdout.strip() == "active":
                    is_systemd = True
            except Exception:
                is_systemd = False

            # 2. 如果是 systemd 托管，通知 systemctl restart
            if is_systemd:
                try:
                    logger.info(f"[{self.plugin_name}] 检测到 systemd 托管运行，通知 systemctl restart...")
                    subprocess.run(["sudo", "-n", "systemctl", "restart", "robot-gateway"], timeout=3)
                    return
                except Exception as e:
                    logger.warning(f"[{self.plugin_name}] systemctl restart 触发异常: {e}")

            # 3. 如果是 pdm run main.py 或直接运行，执行优雅的 execv 原地拉起
            try:
                logger.info(f"[{self.plugin_name}] 开发/非systemd环境 (如 pdm run)，通过 execv 原地重拉主进程...")
                
                # 优雅关闭 MQTT 连接，释放网络会话
                try:
                    from core.mqtt_manager import MQTTManager
                    if MQTTManager._instance:
                        MQTTManager._instance.stop()
                except Exception as e:
                    logger.debug(f"[{self.plugin_name}] 停止 MQTTManager 异常: {e}")

                # 刷新标准输出
                sys.stdout.flush()
                sys.stderr.flush()
                time.sleep(0.5)

                # 原地替换当前 Python 进程
                os.execv(sys.executable, [sys.executable] + sys.argv)
            except Exception as ex:
                logger.critical(f"[{self.plugin_name}] 进程重新拉起失败: {ex}")

        t = threading.Thread(target=_do_restart, daemon=True, name="ServiceRestartThread")
        t.start()

    def _schedule_reboot_system(self, delay_s: float = 2.0) -> None:
        """异步延时触发操作系统整机重启（确保 ACK_EXECUTE 报文先行发送完毕）"""
        def _do_reboot():
            logger.info(f"[{self.plugin_name}] 系统重启守护线程启动，等待 {delay_s} 秒安全窗口...")
            time.sleep(max(0.1, delay_s))
            logger.critical(f"[{self.plugin_name}] 正在执行工控机整机重启 (sudo reboot)...")
            try:
                subprocess.run(["sudo", "-n", "reboot"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            except Exception as e:
                logger.critical(f"[{self.plugin_name}] 执行 sudo reboot 失败: {e}")

        t = threading.Thread(target=_do_reboot, daemon=True, name="SystemRebootThread")
        t.start()

    def execute(self, action: str, params: dict) -> dict:
        action_lower = action.lower()
        if action_lower != "pause" and self._is_paused:
            logger.warning(f"⏸️ [{self.plugin_name}] 处于暂停状态，中断动作。")
            return {"status": "paused", "message": "系统动作因暂停被中断"}
        params = params or {}
        logger.info(f"[{self.plugin_name}] 收到动作 -> [{action}], 参数: {params}")

        if action_lower == "status":
            return {"status": "success", "message": "系统基础插件在线", "data": {"online": True}}

        if action_lower == "delay":
            delay_s = float(params.get("seconds", 0))
            logger.info(f"⏳ [System] 执行工作流阻塞，延时 {delay_s} 秒...")
            
            # 使用 Event.wait 实现可被及时唤醒的非阻塞延时
            self._delay_event = threading.Event()
            
            start_t = time.time()
            while time.time() - start_t < delay_s:
                if self._is_paused:
                    logger.warning(f"⏸️ [{self.plugin_name}] 延时过程中检测到 pause 暂停信号，终止延时。")
                    return {"status": "paused", "message": "系统延时动作因暂停被中断"}
                
                # 每次最多 wait 0.1秒，响应 _is_paused 的轮询
                self._delay_event.wait(0.1)
                if self._delay_event.is_set():
                    # 收到 abort 强制打断
                    logger.warning(f"🛑 [{self.plugin_name}] 延时被 abort 打断！")
                    return {"status": "error", "message": "系统延时被紧急中断"}
                    
            return {"status": "success", "message": f"延时 {delay_s} 秒完成"}

        if action_lower == "restart_service":
            force = bool(params.get("force", False))
            delay_s = float(params.get("delay_s", 1.0))
            safe, err_msg = self._check_safety_interlock(force=force)
            if not safe:
                logger.warning(f"[{self.plugin_name}] restart_service 被安全互锁拦截: {err_msg}")
                return {"status": "error", "message": err_msg}

            self._schedule_restart_service(delay_s=delay_s)
            return {
                "status": "success",
                "message": f"网关服务正在重启中，将在 {delay_s} 秒后触发优雅退出并重新拉起",
                "data": {"target": "service", "delay_s": delay_s}
            }

        if action_lower == "reboot_system":
            force = bool(params.get("force", False))
            delay_s = float(params.get("delay_s", 2.0))
            safe, err_msg = self._check_safety_interlock(force=force)
            if not safe:
                logger.warning(f"[{self.plugin_name}] reboot_system 被安全互锁拦截: {err_msg}")
                return {"status": "error", "message": err_msg}

            self._schedule_reboot_system(delay_s=delay_s)
            return {
                "status": "success",
                "message": f"工控机操作系统正在重启中，将在 {delay_s} 秒后切断物理系统并重新启动",
                "data": {"target": "system", "delay_s": delay_s}
            }

        msg = f"不支持的系统动作: {action}"
        logger.error(f"[{self.plugin_name}] {msg}")
        return {"status": "error", "message": msg}

    def pause(self) -> None:
        """暂停系统基础插件"""
        if self._is_paused:
            logger.warning(f"[{self.plugin_name}] 系统插件已处于暂停状态，忽略 pause 请求")
            return
        self._is_paused = True
        logger.info(f"⏸️ [{self.plugin_name}] 暂停系统插件...")

    def resume(self) -> None:
        """恢复系统基础插件"""
        self._is_paused = False
        logger.info(f"▶️ [{self.plugin_name}] 恢复系统插件，暂停标志已清除。")

    def abort(self) -> None:
        """终止/打断系统基础插件"""
        self._is_paused = False
        if hasattr(self, "_delay_event") and self._delay_event:
            self._delay_event.set()
        logger.info(f"🛑 [{self.plugin_name}] 打断系统插件，暂停标志已清除。")

    def get_status(self) -> bool:
        """系统基础插件状态（规范定义直接返回 True）"""
        return True

    def get_capabilities(self) -> dict:
        """获取系统基础插件标准能力清单元数据 (Schema)"""
        return {
            "plugin_type": self.plugin_name,
            "plugin_name": "基础插件",
            "description": "提供网关本地系统级延时等待、服务重启与整机重启自愈控制能力",
            "version": "1.3.0",
            "supported_actions": [
                {
                    "action": "delay",
                    "action_name": "延时等待",
                    "description": "阻塞式系统延时等待指定的秒数",
                    "scopes": ["task"],
                    "params": [
                        {"name": "seconds", "label": "延时秒数(s)", "type": "float", "default": 1.0, "required": True, "ui_component": "input_number"}
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
                    "description": "查询系统基本运行状态",
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
                    "action": "restart_service",
                    "action_name": "重启服务",
                    "description": "安全重启边缘网关中间件服务进程 (带安全互锁与先ACK后重启保护)",
                    "scopes": ["config"],
                    "params": [
                        {"name": "delay_s", "label": "延时秒数(s)", "type": "float", "default": 1.0, "required": False, "ui_component": "input_number"},
                        {"name": "force", "label": "强制重启", "type": "bool", "default": False, "required": False, "ui_component": "switch"}
                    ],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "message", "label": "描述", "type": "string"},
                            {"name": "data", "label": "数据", "type": "object"}
                        ]
                    }
                },
                {
                    "action": "reboot_system",
                    "action_name": "重启系统",
                    "description": "安全重启边缘工控机操作系统 (带安全互锁与先ACK后重启保护)",
                    "scopes": ["config"],
                    "params": [
                        {"name": "delay_s", "label": "延时秒数(s)", "type": "float", "default": 2.0, "required": False, "ui_component": "input_number"},
                        {"name": "force", "label": "强制重启", "type": "bool", "default": False, "required": False, "ui_component": "switch"}
                    ],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "message", "label": "描述", "type": "string"},
                            {"name": "data", "label": "数据", "type": "object"}
                        ]
                    }
                }
            ]
        }