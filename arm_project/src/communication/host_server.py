import json
import threading
import socketserver
from queue import Queue
from typing import Any, Dict, Optional
from src.core.logger import logger

# 全局队列，用于主线程与 TCP 线程间的指令通信
# 存放解析后的指令字典，例如: {"action": "goto", "point": 0, "handler": <HostRequestHandler_instance>}
command_queue = Queue()

# 全局紧急停机钩子，允许在 TCP 线程接收到 pause 时立即触发底层硬件缓停，无需等待主事件循环
_emergency_pause_hook = None

def register_emergency_pause_hook(hook):
    global _emergency_pause_hook
    _emergency_pause_hook = hook

class HostRequestHandler(socketserver.StreamRequestHandler):
    """
    处理上位机客户端连接请求。
    继承 StreamRequestHandler，支持按行读取与下发 JSON 报文。
    严格对齐上位机 ArmPlugin 协议：
      1. 下发 goto/pause/goback 后，立即响应阶段 1 启动确认: {"result": "start"}
      2. 任务执行完成后，响应阶段 2 结果: {"result": "success"} 或 {"result": "error", "message": "..."}
      3. 支持按需连接探测与状态查询 (status/get_status)
    """
    def handle(self):
        client_ip, client_port = self.client_address
        logger.info(f"上位机已连接: {client_ip}:{client_port}")
        
        try:
            # 持续按行读取数据
            while True:
                # readline() 阻塞读取，直到遇到换行符 \n
                raw_line = self.rfile.readline()
                if not raw_line:
                    logger.info(f"上位机 {client_ip}:{client_port} 连接断开 (对端关闭链路)")
                    break
                
                line = raw_line.strip()
                if not line:
                    continue
                
                try:
                    msg = json.loads(line.decode('utf-8'))
                    logger.info(f"收到上位机指令: {msg}")
                    
                    action = msg.get("action")
                    if not action or not isinstance(action, str):
                        self.send_fail("缺少 action 字段或 action 格式非法")
                        continue
                        
                    action_name = action.strip().lower()
                    
                    # 1. 查询类指令 (无需进入底层运动队列)
                    if action_name in ["status", "get_status"]:
                        self.send_response({
                            "result": "success",
                            "status": "success",
                            "message": "机械臂在线",
                            "data": {"online": True}
                        })
                        continue
                    
                    # 2. 运动控制类指令 (goto, pause, goback)
                    if action_name not in ["goto", "pause", "goback"]:
                        err_msg = f"不支持的机械臂动作: {action} (仅支持 goto, pause, goback, status)"
                        logger.warning(f"[{client_ip}] {err_msg}")
                        self.send_fail(err_msg)
                        continue
                    
                    # 若为 pause 指令，在进入队列之前立即触发紧急缓停钩子，实现毫秒级物理停机
                    if action_name == "pause" and _emergency_pause_hook:
                        try:
                            logger.info("TCP 线程检测到 pause 指令，立即触发紧急停机钩子...")
                            _emergency_pause_hook()
                        except Exception as e:
                            logger.error(f"触发 emergency_pause_hook 异常: {e}")

                    # 开始执行回复: {"result": "start"}
                    self.send_start()
                    
                    # 点位解析 (goto 动作专用，支持 int 或字符串数字)
                    point = msg.get("point", 0)
                    try:
                        if isinstance(point, str) and point.strip().isdigit():
                            point = int(point.strip())
                        elif not isinstance(point, int):
                            point = int(point)
                    except Exception:
                        point = 0
                        
                    cmd_task = {
                        "action": action_name,
                        "point": point,
                        "handler": self
                    }
                    command_queue.put(cmd_task)
                    logger.debug(f"指令已放入主控队列: {cmd_task['action']} (point={cmd_task.get('point')})")
                    
                except json.JSONDecodeError:
                    err_msg = f"非法的 JSON 报文格式: {line.decode('utf-8', errors='ignore')}"
                    logger.error(err_msg)
                    self.send_fail(err_msg)
                    
        except (ConnectionResetError, BrokenPipeError):
            logger.info(f"上位机 {client_ip} 连接断开 (Connection reset/Broken pipe)")
        except Exception as e:
            logger.error(f"TCP 连接处理异常 [{client_ip}]: {e}")

    def send_response(self, data: Dict[str, Any]) -> bool:
        """
        向客户端发送异步响应报文，强制附加 \\n 换行符以匹配上位机按行读取协议。
        """
        try:
            resp_str = json.dumps(data, ensure_ascii=False) + "\n"
            self.wfile.write(resp_str.encode('utf-8'))
            self.wfile.flush()
            logger.info(f"📤 发送 TCP 响应: {data}")
            return True
        except Exception as e:
            logger.warning(f"向客户端发送响应失败 (客户端可能已断开连接): {e}")
            return False

    def send_start(self, message: str = "") -> bool:
        """开始执行回复: {"result": "start"}"""
        payload: Dict[str, Any] = {"result": "start"}
        if message:
            payload["message"] = message
        return self.send_response(payload)

    def send_success(self, message: str = "") -> bool:
        """执行完成回复: {"result": "success"}"""
        payload: Dict[str, Any] = {"result": "success"}
        if message:
            payload["message"] = message
        return self.send_response(payload)

    def send_fail(self, message: str = "") -> bool:
        """执行时失败回复: {"result": "fail"}"""
        payload: Dict[str, Any] = {"result": "fail"}
        if message:
            payload["message"] = message
        return self.send_response(payload)

    def send_error(self, message: str = "") -> bool:
        """兼容别名方法，调用 send_fail"""
        return self.send_fail(message)


class TCPServerThread(threading.Thread):
    """
    将 TCP Server 封装为后台守护线程，解耦主事件循环。
    """
    def __init__(self, host: str, port: int):
        super().__init__(daemon=True)
        self.host = host
        self.port = int(port)
        self.server: Optional[socketserver.ThreadingTCPServer] = None

    def run(self):
        socketserver.TCPServer.allow_reuse_address = True
        try:
            self.server = socketserver.ThreadingTCPServer(
                (self.host, self.port),
                HostRequestHandler
            )
            self.server.daemon_threads = True
            logger.info(f"🚀 TCP 控制服务启动成功，监听地址: {self.host}:{self.port}")
            self.server.serve_forever()
        except Exception as e:
            logger.error(f"TCP 控制服务启动异常: {e}")

    def stop(self):
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
                logger.info("TCP 控制服务已安全关闭")
            except Exception as e:
                logger.warning(f"关闭 TCP 服务时出现异常: {e}")

