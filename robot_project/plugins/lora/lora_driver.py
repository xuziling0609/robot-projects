import time
import json
import socket
import threading
from typing import Optional, Callable, Dict, Any, List
from core.logger_manager import get_logger
from core.tcp_manager import TCPManager

logger = get_logger("LoraDriver")

MODE_MAP = {"AUTO": "0", "MANU": "1"} 
LOCALIZATION_MAP = {"OK": "0", "FAILED": "1", "RUNNING": "2", "FINISH": "3"} 
TASK_STATUS_MAP = {
    "IDLE": "0", "RUNNING": "1", "PAUSED": "2", 
    "FINISH": "3", "FINISHED": "3",
    "FAILED": "4", "ERROR": "4", "ABORTED": "5"
}

class LoraProtocol:
    """
    LoRa 协议处理类 (对应参考 lora_server.py 中第5节 5. LoRa 核心业务)
    负责协议匹配校验、机器人状态列表解析转换与控制帧封装
    """
    @staticmethod
    def is_trigger_packet(data: bytes) -> bool:
        """
        校验收到 TCP 报文是否为触发状态上报的心跳报文(0x50)或转发报文(0x60)
        规则：第一个字节高4位为 0xA0，第二个字节高4位为 0x50 或 0x60
        遍历字节流，增强防止 TCP 粘包或拆包时的误漏断
        """
        if not data or len(data) < 2:
            return False
        for i in range(len(data) - 1):
            if (data[i] & 0xF0) == 0xA0 and (data[i+1] & 0xF0) in [0x50, 0x60]:
                return True
        return False

    @staticmethod
    def get_packet_type_str(data: bytes) -> str:
        """解析并返回捕获报文的类型名称"""
        if not data or len(data) < 2:
            return "UNKNOWN"
        for i in range(len(data) - 1):
            if (data[i] & 0xF0) == 0xA0:
                second_byte = data[i+1]
                if (second_byte & 0xF0) == 0x50:
                    return "HEARTBEAT(0x50)"
                elif (second_byte & 0xF0) == 0x60:
                    return "FORWARD(0x60)"
        return "OTHER"

    @staticmethod
    def parse_robot_status_to_list(
        status_json: Dict[str, Any], 
        task_json: Optional[Dict[str, Any]] = None,
        default_robot_id: str = "robot888"
    ) -> List[str]:
        """
        将导航插件状态与当前任务引擎状态，转换成 LoRa 协议要求的 7 元素列表：
        [robot_id, x_coord, y_coord, power, mode, loc_status, task_status]
        第7项任务状态映射：
        0: IDLE, 1: RUNNING, 2: PAUSED, 3: FINISH, 4: FAILED, 5: ABORTED
        """
        if not status_json or not isinstance(status_json, dict):
            status_json = {}

        mode_str = status_json.get("mode", "AUTO")
        localization = status_json.get("localization", {})
        battery = status_json.get("battery", {})

        # 获取设备 ID
        robot_id = str(status_json.get("robot_id") or status_json.get("device_sn") or default_robot_id)

        # 坐标格式化 (兼容大写 X 或小写 x)
        x_val = localization.get('x', localization.get('X', 0.0))
        y_val = localization.get('y', localization.get('Y', 0.0))
        try:
            x_coord = f"{float(x_val):.3f}"[:7]
        except (ValueError, TypeError):
            x_coord = "0.000"
        try:
            y_coord = f"{float(y_val):.3f}"[:7]
        except (ValueError, TypeError):
            y_coord = "0.000"

        # 电量转换
        power_val = battery.get("power", 0.0)
        try:
            power_float = float(power_val)
            # 兼容 0~1 的高精小数和 0~100 的数值
            if 0.0 < power_float <= 1.0:
                power_float *= 100.0
            power = f"{power_float:.2f}"
        except (ValueError, TypeError):
            power = "0.00"

        mode = MODE_MAP.get(str(mode_str).upper(), "0")
        loc_status = LOCALIZATION_MAP.get(str(localization.get("status", "FAILED")).upper(), "1")

        # 任务状态转换 (0: IDLE, 1: RUNNING, 2: PAUSED, 3: FINISH, 4: FAILED, 5: ABORTED)
        raw_task_status = "IDLE"
        if task_json and isinstance(task_json, dict) and "status" in task_json:
            raw_task_status = task_json.get("status", "IDLE")
        elif "task" in status_json and isinstance(status_json["task"], dict):
            raw_task_status = status_json["task"].get("status", "IDLE")
        elif "task_state" in status_json:
            raw_task_status = status_json.get("task_state", "IDLE")
        else:
            try:
                from core.context_manager import ContextManager
                raw_task_status = ContextManager.get_robot_task().get("status", "IDLE")
            except Exception:
                pass

        nav_status = TASK_STATUS_MAP.get(str(raw_task_status).upper(), "0")

        return [robot_id, x_coord, y_coord, power, mode, loc_status, nav_status]

    @staticmethod
    def format_status_packet(status_list: List[str]) -> bytes:
        """
        将 7 元素状态列表封装为 LoRa 协议发往网关的二进制报文：
        Header(0xC5, 0xC5) + JSON字符串 + End(0x0D, 0x0A)
        """
        header = bytes([0xC5, 0xC5])
        end = bytes([0x0D, 0x0A])
        json_content = json.dumps(status_list, separators=(',', ':'))
        return header + json_content.encode('utf-8') + end


class LoraTCPDriver:
    """
    LoRa 网关 TCP 客户端底座驱动
    基于工业级 TCPManager 维护与 LoRa 网关的连接通信，支持断线自愈与延迟上报锁控制
    """
    def __init__(self, host: str, port: int, on_trigger_callback: Callable[[float, str], None]):
        self.host = host
        self.port = int(port)
        self.on_trigger_callback = on_trigger_callback
        self.sock: Optional[socket.socket] = None
        self.running = False
        self.connected = False
        
        # 严格按照参考代码中的锁机制管理延迟发送生命周期
        self.report_is_locked = False
        self.lock_mutex = threading.Lock()
        self.pool = TCPManager()
        
        logger.debug(f"✨ 初始化 LoraTCPDriver -> 目标网关: [{self.host}:{self.port}]")

    def start(self):
        if not self.running:
            self.running = True
            threading.Thread(target=self._client_loop, daemon=True, name="LoraTCPClientLoop").start()
            logger.info("🚀 LoRa TCP 客户端监听驱动线程已启动...")

    def stop(self):
        self.running = False
        self.disconnect()

    def disconnect(self):
        self.connected = False
        if self.sock or self.pool:
            try:
                self.pool.release_connection(self.host, self.port)
            except Exception as e:
                logger.error('捕获到异常', exc_info=True)
            finally:
                self.sock = None

    def is_connected(self) -> bool:
        return self.connected and self.sock is not None

    def _client_loop(self):
        while self.running:
            try:
                logger.info(f"🔌 [LoRa驱动] 尝试通过 TCPManager 连接 LoRa 网关 {self.host}:{self.port}...")
                self.sock = self.pool.get_connection(self.host, self.port, timeout=5.0)
                if not self.sock:
                    raise socket.error("无法从 TCPManager 获取连接")
                self.connected = True
                logger.info(f"✅ [LoRa驱动] 成功连接至 LoRa 网关 {self.host}:{self.port}！正在监听网络数据流...")

                while self.running and self.connected:
                    try:
                        self.sock.settimeout(1.0)
                        data = self.sock.recv(1024)
                        if not data:
                            logger.warning("⚠️ [LoRa驱动] LoRa 网关对端断开连接")
                            break

                        if LoraProtocol.is_trigger_packet(data):
                            pkt_type = LoraProtocol.get_packet_type_str(data)
                            trigger_ts = time.time()
                            logger.debug(f"📥 [LoRa驱动] 捕获触发报文: {pkt_type} (Hex: {data.hex().upper()})")

                            with self.lock_mutex:
                                if not self.report_is_locked:
                                    self.report_is_locked = True
                                    can_trigger = True
                                else:
                                    can_trigger = False

                            if can_trigger:
                                if self.on_trigger_callback:
                                    # 异步派发上报任务，确保 Socket 接收线程永不阻塞
                                    threading.Thread(
                                        target=self.on_trigger_callback,
                                        args=(trigger_ts, pkt_type),
                                        daemon=True,
                                        name=f"LoraTrigger-{int(trigger_ts)}"
                                    ).start()
                            else:
                                logger.warning(f"⏸️ [LoRa驱动] 状态上报已锁定（正在等待 5s 上报期间），静默忽略本次重复触发")

                    except socket.timeout:
                        continue
                    except (socket.error, ConnectionResetError) as e:
                        logger.warning(f"⚠️ [LoRa驱动] Socket 通信异常: {e}")
                        self.pool.release_connection(self.host, self.port)
                        break
                    except Exception as e:
                        logger.error(f"❌ [LoRa驱动] 处理数据接收异常: {e}")
                        self.pool.release_connection(self.host, self.port)
                        break
            except (socket.timeout, socket.error, ConnectionRefusedError) as e:
                self.connected = False
                try:
                    self.pool.release_connection(self.host, self.port)
                except Exception as e:
                    logger.error('捕获到异常', exc_info=True)
                for _ in range(10):
                    if not self.running:
                        break
                    time.sleep(0.5)
            finally:
                self.disconnect()
                if self.running:
                    logger.info("⏳ [LoRa驱动] 链路中断，2秒后尝试重建连接...")
                    time.sleep(2.0)

    def schedule_send_report(self, status_list: List[str], trigger_timestamp: float, delay_seconds: float = 5.0) -> bool:
        """
        严格依据时间戳执行延迟发送 (参考 lora_server.py 第5节：距离捕获心跳刚好 5.00 秒射出报文)
        通过 TCPManager 动态复用或重建有效链路，并在完成后自动释放锁 report_is_locked
        """
        threading.current_thread().name = "LoraDelayedSendWorker"
        try:
            packet_to_send = LoraProtocol.format_status_packet(status_list)
            elapsed_time = time.time() - trigger_timestamp
            remaining_sleep = float(delay_seconds) - elapsed_time

            if remaining_sleep > 0 and self.running:
                logger.debug(f"⏳ [LoRa驱动] 等待 {remaining_sleep:.2f}s 后发往 LoRa 网关 (距离捕获心跳刚好 {delay_seconds:.2f}s)...")
                time.sleep(remaining_sleep)

            conn = self.pool.get_connection(self.host, self.port, timeout=3.0)
            if not conn:
                logger.error("❌ [LoRa发送] 无法从 TCP 连接池获取有效链路，报文下发失败")
                return False

            conn.sendall(packet_to_send)
            logger.debug(f"🚀 [LoRa发送] LoRa 报文通过 TCPManager 成功射出！(距离触发捕获约 {(time.time() - trigger_timestamp):.2f} 秒): {status_list}")
            return True
        except Exception as e:
            logger.error(f"❌ [LoRa发送] 报文传输异常: {e}")
            try:
                self.pool.release_connection(self.host, self.port)
            except Exception as e:
                logger.error('捕获到异常', exc_info=True)
            return False
        finally:
            with self.lock_mutex:
                self.report_is_locked = False
