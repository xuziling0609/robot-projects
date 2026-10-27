import time
from core.logger_manager import get_logger
from core.tcp_manager import TCPManager

logger = get_logger("Tasio211Driver")

# ==================== Tasio211 16进制控制协议 ====================
CMD_READ_STATE = bytes.fromhex("11 01 00 00 00 02 BF 5B")
EXPECTED_STATE_RESP = bytes.fromhex("11 01 01 00 55 48")

CMD_MULTI_CLOSE = bytes.fromhex("11 0F 00 00 00 02 01 00 DF 9B")
EXPECTED_MULTI_CLOSE_RESP = bytes.fromhex("11 0F 00 00 00 02 D6 9A")

CMD_DO1_JOG_OPEN = bytes.fromhex("11 10 96 04 00 03 06 02 00 00 FF 01 00 4A 0D")
EXPECTED_DO1_RESP = bytes.fromhex("11 10 96 04 00 03 EE D1")

CMD_DO2_JOG_CLOSE = bytes.fromhex("11 10 96 08 00 03 06 02 00 00 FF 01 00 8A 32")
EXPECTED_DO2_RESP = bytes.fromhex("11 10 96 08 00 03 2E D2")
# =================================================================

class Tasio211Driver:
    """
    Tasio211 多路继电器(DO)底层驱动 (流程结束统一释放连接版)
    """
    
    def __init__(self, port: int = 10022, timeout: float = 3.0):
        self.port = port
        self.timeout = timeout
        self.pool = TCPManager()
        logger.debug(f"✨ 初始化 Tasio211 硬件驱动实例 -> 默认端口: {self.port}")

    def _send_and_receive(self, ip: str, cmd_bytes: bytes, desc: str = "", expected_length: int = 1024) -> bytes:
        """通过连接池获取 TCP 链路并进行收发"""
        target = f"{ip}:{self.port}"
            
        try:
            conn = self.pool.get_connection(ip, self.port, timeout=self.timeout)
            
            if not conn:
                logger.error(f"❌ 无法获取到目标 [{target}] 的有效 TCP 链路实例。")
                return b''
            
            time.sleep(0.5) # 此款继电器需要连接成功后等待0.5s后才能发送数据
            
            logger.debug(f"📤 {desc} | 发送 HEX: {cmd_bytes.hex(' ').upper()}")
            conn.sendall(cmd_bytes)
            time.sleep(0.1) # 给予底层继电器 MCU 处理时间
            
            resp = conn.recv(expected_length)
            logger.debug(f"📥 {desc} | 收到 HEX: {resp.hex(' ').upper() if resp else 'EMPTY'}")
            return resp
            
        except Exception as e:
            logger.warning(f"⚠️ 链路异常 [{target}] ({e})，触发 1 次自动断线重连...")

            try:
                # 释放失效链路并强制重新建立
                self.pool.release_connection(ip, self.port)
                conn = self.pool.get_connection(ip, self.port, timeout=self.timeout)
                
                logger.debug(f"🔄 链路重连成功，正在向 [{target}] 重新投递报文...")
                time.sleep(0.5)
                conn.sendall(cmd_bytes)
                time.sleep(0.1)
                
                resp = conn.recv(expected_length)
                logger.debug(f"📥 {desc} | 重连后收到 HEX: {resp.hex(' ').upper() if resp else 'EMPTY'}")
                return resp
            except Exception as retry_e:
                logger.error(f"❌ 重连后二次投递报文依然失败 [{target}]: {retry_e}")
                
            return b''

    def execute_door_action(self, ip: str, action: str) -> tuple[bool, str]:
        """对单个 IP 执行物理控制，包含状态前置校验，并在流程结束时统一释放连接"""
        action_name = "开门(DO1)" if action == "open" else "关门(DO2)"
        logger.info(f"[{ip}] --- 开始执行 [{action_name}] 硬件流程 ---")

        try:
            # 1. 读取 DO 状态
            state_resp = self._send_and_receive(ip, CMD_READ_STATE, desc=f"[{ip}] 读取状态")
            if not state_resp:
                return False, "Failed to read DO state (Timeout or offline)"

            # 2. 状态判定与安全复位
            if state_resp == EXPECTED_STATE_RESP:
                logger.info(f"[{ip}] 状态匹配，直接调用点动指令。")
            else:
                logger.info(f"[{ip}] 状态不匹配，先执行多路关闭 (复位)...")
                close_resp = self._send_and_receive(ip, CMD_MULTI_CLOSE, desc=f"[{ip}] 多路关闭")
                if close_resp != EXPECTED_MULTI_CLOSE_RESP:
                    return False, "Multi-close reset failed (Invalid hardware response)"
                time.sleep(0.3)

            # 3. 执行具体开/关动作
            if action == "open":
                resp = self._send_and_receive(ip, CMD_DO1_JOG_OPEN, desc=f"[{ip}] DO1点动开门")
                if resp == EXPECTED_DO1_RESP:
                    return True, ""
                else:
                    return False, "Invalid confirmation for DO1 open"
                    
            elif action == "close":
                resp = self._send_and_receive(ip, CMD_DO2_JOG_CLOSE, desc=f"[{ip}] DO2点动关门")
                if resp == EXPECTED_DO2_RESP:
                    return True, ""
                else:
                    return False, "Invalid confirmation for DO2 close"
                    
            return False, "Unknown action error"

        finally:
            # 4. 【核心改动】：无论整个动作流程成功、异常还是提前返回，在结束时显式释放该 IP 的 TCP 连接
            self.pool.release_connection(ip, self.port)
            logger.info(f"[{ip}] --- [{action_name}] 硬件流程结束，已显式释放 TCP 链路 ---")