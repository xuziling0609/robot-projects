import builtins
import json
import time
import socket
from typing import Tuple
from plugins.base import BasePlugin
from core.tcp_manager import TCPManager
from core.logger_manager import get_logger

# 显式声明内置符号，消除部分 IDE 静态分析器 (如 Pylance) 的未定义误报
super = builtins.super
InterruptedError = builtins.InterruptedError

logger = get_logger("ArmPlugin")

class ArmPlugin(BasePlugin):
    """
    机械臂能力插件 (ArmPlugin)
    复用 TCPManager 与机械臂 TCP 控制服务通信。
    提供 goto, pause, goback 能力。
    
    交互流程:
    1. 触发动作时根据配置连接 TCP Socket (IP 与端口由配置文件指定，平台不下发)。
    2. 下发 TCP JSON 指令:
       - goto: {"action": "goto", "point": 0}
       - pause: {"action": "pause"}
       - goback: {"action": "goback"}
    3. 接收并校验 TCP 回复 {"result": "start"} (表示机械臂开始运动)。
    4. 阻塞/等待机械臂到达目标点，接收 TCP 回复 {"result": "success"}。
    5. 返回平台成功完成状态。
    6. 最后安全关闭与释放 TCP 连接。
    """
    def __init__(self, config: dict = None):
        super().__init__(config)
        self.plugin_name = self.__class__.__name__
        params = self.config.get("params", {}) if isinstance(self.config, dict) else {}
        if not isinstance(params, dict):
            params = {}
        self.ip = self.config.get("ip") or params.get("ip")
        if not self.ip:
            try:
                from core.config_manager import ConfigManager
                self.ip = ConfigManager.get("plugins.arm.params.ip", ConfigManager.get("plugins.arm.ip", "127.0.0.1"))
            except Exception:
                self.ip = "127.0.0.1"
        self.port = int(self.config.get("port") or params.get("port") or 10020)
        self.connect_timeout = float(self.config.get("connect_timeout") or params.get("connect_timeout") or 5.0)
        self.start_timeout = float(self.config.get("start_timeout") or params.get("start_timeout") or 5.0)
        self.exec_timeout = float(self.config.get("exec_timeout") or params.get("exec_timeout") or 60.0)
        self._is_paused: bool = False
        logger.info(f"🦾 机械臂插件初始化完成 (按需 TCP 目标: {self.ip}:{self.port})")

    def _read_json_message(self, sock: socket.socket, buffer: str, timeout: float, action_name: str = "") -> Tuple[dict, str]:
        """按行分隔从 TCP Socket 接收并解析 JSON 消息"""
        sock.settimeout(0.5)
        start_time = time.time()
        while time.time() - start_time < timeout:
            if action_name != "pause" and self._is_paused:
                raise InterruptedError("机械臂动作因暂停被中断")

            if '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                line = line.strip()
                if line:
                    try:
                        return json.loads(line), buffer
                    except json.JSONDecodeError:
                        pass

            try:
                chunk = sock.recv(1024)
                if not chunk:
                    raise ConnectionError("TCP 连接对端断开")
                buffer += chunk.decode('utf-8', errors='ignore')
            except socket.timeout:
                continue

        raise TimeoutError(f"等待机械臂响应超时 ({timeout}s)")

    def execute(self, action: str, params: dict) -> dict:
        params = params or {}
        action_name = action.lower()
        
        if action_name != "pause" and self._is_paused:
            logger.warning(f"⏸️ [{self.plugin_name}] 处于暂停状态，中断动作。")
            return {"status": "paused", "message": "机械臂动作因暂停被中断"}

        if action_name in ["status", "get_status"]:
            is_online = True
            return {
                "status": "success" if is_online else "error",
                "message": "机械臂在线" if is_online else "机械臂离线 (TCP 连接失败)",
                "data": {"online": is_online}
            }

        if action_name not in ["goto", "pause", "goback"]:
            msg = f"不支持的机械臂动作: {action} (仅支持 goto, pause, goback, status)"
            logger.error(f"[{self.plugin_name}] {msg}")
            return {"status": "error", "message": msg}

        # 机械臂 IP 和端口从配置文件读取，平台不下发
        target_ip = self.ip
        target_port = self.port

        # 构建下发的 TCP JSON 指令
        cmd_payload = {"action": action_name}

        if action_name == "goto":
            point = params.get("point", 0)
            try:
                if isinstance(point, str) and point.isdigit():
                    point = int(point)
            except Exception as e:
                logger.error('捕获到异常', exc_info=True)
            cmd_payload["point"] = point

        cmd_bytes = (json.dumps(cmd_payload, ensure_ascii=False) + "\n").encode('utf-8')

        logger.info(f"[{self.plugin_name}] 收到平台动作 -> [{action_name}], 下发指令: {cmd_payload}, 目标: {target_ip}:{target_port}")

        pool = TCPManager()
        sock = None
        buffer = ""

        try:
            # 1. 使用时连接 TCP
            logger.info(f"[{self.plugin_name}] 🔌 正在建立/获取 TCP 连接 [{target_ip}:{target_port}]...")
            sock = pool.get_connection(target_ip, target_port, timeout=self.connect_timeout)

            # 2. 下发 TCP 指令
            logger.info(f"[{self.plugin_name}] 📤 下发 TCP 指令: {cmd_payload}")
            sock.sendall(cmd_bytes)

            # 3. 等待 TCP 回复 {"result": "start"}
            res_start, buffer = self._read_json_message(sock, buffer, timeout=self.start_timeout, action_name=action_name)
            logger.info(f"[{self.plugin_name}] 📥 收到阶段 1 启动响应: {res_start}")
            
            result_val = res_start.get("result")
            if result_val != "start":
                msg = f"机械臂启动回应异常，期望 'start' 但收到: {res_start}"
                logger.error(f"[{self.plugin_name}] ❌ {msg}")
                return {"status": "error", "message": msg}

            # 4. 等待机械臂到达目标点，回复 {"result": "success"}
            res_success, buffer = self._read_json_message(sock, buffer, timeout=self.exec_timeout, action_name=action_name)
            logger.info(f"[{self.plugin_name}] 📥 收到阶段 2 完成响应: {res_success}")

            if res_success.get("result") == "success":
                logger.info(f"[{self.plugin_name}] ✅ 机械臂 [{action_name}] 动作成功完成！")
                return {
                    "status": "success", 
                    "message": f"机械臂 {action_name} 动作执行成功"
                }
            else:
                msg = f"机械臂到达阶段回应失败: {res_success}"
                logger.error(f"[{self.plugin_name}] ❌ {msg}")
                return {"status": "error", "message": msg}

        except InterruptedError as ie:
            logger.warning(f"⏸️ [{self.plugin_name}] {ie}")
            return {"status": "paused", "message": "机械臂动作因暂停被中断"}
        except Exception as e:
            if self._is_paused:
                logger.warning(f"⏸️ [{self.plugin_name}] 机械臂动作执行期间捕获暂停信号")
                return {"status": "paused", "message": "机械臂动作因暂停被中断"}
            err_msg = f"机械臂动作 [{action_name}] 执行异常: {e}"
            logger.error(f"[{self.plugin_name}] ❌ {err_msg}")
            return {"status": "error", "message": err_msg}

        finally:
            # 5. 最后关闭 TCP 连接
            logger.info(f"[{self.plugin_name}] 🔒 动作执行完毕，关闭并释放 TCP 连接 [{target_ip}:{target_port}]")
            pool.release_connection(target_ip, target_port)

    def pause(self) -> dict:
        """暂停机械臂动作 (TCP 下发 pause 指令)"""
        if self._is_paused:
            logger.warning(f"[{self.plugin_name}] 机械臂已处于暂停状态，忽略 pause 请求")
            return {"status": "success", "message": "机械臂已处于暂停状态"}
        self._is_paused = True
        logger.info(f"⏸️ [{self.plugin_name}] 触发 pause (暂停) 方法，下发 TCP 暂停指令...")
        try:
            return self.execute("pause", {})
        except Exception as e:
            logger.error(f"❌ [{self.plugin_name}] 机械臂下发 pause 指令异常: {e}")
            return {"status": "error", "message": str(e)}

    def resume(self) -> None:
        """恢复机械臂动作"""
        self._is_paused = False
        logger.info(f"▶️ [{self.plugin_name}] 触发 resume (恢复) 方法，恢复机械臂任务控制，暂停标志已清除。")

    def abort(self) -> None:
        """终止/打断机械臂动作 (tcp 发送 goback)"""
        self._is_paused = False
        logger.info(f"🛑 [{self.plugin_name}] 触发 abort (停止) 方法，清除暂停标志并发送复位指令")
        try:
            return self.execute("goback", {})
        except Exception as e:
            logger.error(f"❌ [{self.plugin_name}] 机械臂下发 goback 指令异常: {e}")

    def status(self) -> bool:
        """获取当前插件就绪状态 (按需连接架构，初始化完成即视为就绪)"""
        return bool(self.ip and self.port)

    def get_status(self) -> bool:
        """
        获取机械臂插件状态 (按需连接架构：未执行动作时不主动握手 TCP 链路，避免后台轮询产生高频建连与超时风暴)
        """
        return True

    def check_connection(self) -> bool:
        """按需探测机械臂 TCP 控制服务连通性，探测完毕立即关闭并释放 Socket 链路"""
        pool = TCPManager()
        try:
            logger.info(f"[{self.plugin_name}] 🔍 正在按需探测 TCP 连通性 [{self.ip}:{self.port}]...")
            sock = pool.get_connection(self.ip, self.port, timeout=self.connect_timeout)
            return sock is not None
        except Exception as e:
            logger.warning(f"[{self.plugin_name}] 机械臂 TCP 连通性探测失败 [{self.ip}:{self.port}]: {e}")
            return False
        finally:
            pool.release_connection(self.ip, self.port)

    def get_capabilities(self) -> dict:
        """获取机械臂插件标准能力清单元数据 (Schema)"""
        return {
            "plugin_type": self.plugin_name,
            "plugin_name": "机械臂插件",
            "description": "基于 TCP 闭环通讯协议的机械臂点位运动、暂停控制与复位归位能力",
            "version": "1.2.0",
            "supported_actions": [
                {
                    "action": "goto",
                    "action_name": "姿态移动",
                    "description": "控制机械臂轴组运动到位到达指定目标姿态点",
                    "scopes": ["task", "config"],
                    "params": [
                        {"name": "point", "label": "目标姿态点位ID", "type": "int", "required": True, "ui_component": "input_number"}
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
                    "action_name": "暂停动作",
                    "description": "控制机械臂轴组运动立即暂停锁轴",
                    "scopes": ["task"],
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
                    "action": "goback",
                    "action_name": "复位归位",
                    "description": "控制机械臂安全退回归位零点位置",
                    "scopes": ["task"],
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
                    "description": "查询机械臂控制器 TCP Socket 连接状态",
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
