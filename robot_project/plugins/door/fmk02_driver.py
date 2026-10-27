import time
from core.tcp_manager import TCPManager  # 依赖核心层的单例连接池
from core.logger_manager import get_logger

# 初始化当前模块专属 Logger
logger = get_logger("FMK02Driver")

class FMK02Driver:
    """
    FMK02 开门机 TCP 透传底层驱动
    负责协议封装、解析以及底层长连接断线重试，集成统一彩色日志。
    """
    def __init__(self, ip: str, port: int, timeout: float = 3.0):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.pool = TCPManager()
        logger.debug(f"✨ 初始化 FMK02 硬件驱动实例 -> 目标: [{self.ip}:{self.port}]")

    def _send_and_receive(self, cmd_bytes: bytes, expected_length: int) -> bytes:
        """通过连接池复用 TCP 长连接，包含 1 次网络闪断重试机制"""
        target = f"{self.ip}:{self.port}"
            
        try:
            conn = self.pool.get_connection(self.ip, self.port, self.timeout)
            if not conn:
                logger.error(f"❌ 无法获取到目标 [{target}] 的有效 TCP 链路实例。")
                return b''
            
            logger.debug(f"📤 向 [{target}] 发送底层 Modbus 报文 (Hex): {cmd_bytes.hex().upper()}")
            conn.sendall(cmd_bytes)
            time.sleep(0.1) # 等待 Modbus RTU 从机及串口服务器处理
            
            resp = conn.recv(expected_length)
            logger.debug(f"📥 从 [{target}] 收到响应报文 (Hex): {resp.hex().upper() if resp else 'EMPTY'}")
            return resp
            
        except Exception as e:
            logger.warning(f"⚠️ 链路异常 [{target}] ({e})，触发 1 次自动断线重连...")
            
            # 确保重试逻辑也在异常保护之内
            try:
                self.pool.release_connection(self.ip, self.port)
                # 重新尝试获取连接
                conn = self.pool.get_connection(self.ip, self.port)
                
                if conn:
                    logger.debug(f"🔄 链路重连成功，正在向 [{target}] 重新投递报文...")
                    conn.sendall(cmd_bytes)
                    time.sleep(0.1)
                    resp = conn.recv(expected_length)
                    logger.debug(f"📥 重连后收到响应报文 (Hex): {resp.hex().upper() if resp else 'EMPTY'}")
                    return resp
                else:
                    logger.error(f"❌ 链路重连失败，无法建立与 [{target}] 的连接。")
                    return b''
                    
            except Exception as retry_e:
                # 🚀 核心修复：捕获重连时的 ConnectionRefusedError 或 Timeout
                logger.error(f"❌ 重连并二次投递报文彻底失败 [{target}]: {retry_e}")
                return b''

    def get_sensor_status(self) -> str:
        """查询门限位状态"""
        # 主机发送: 01 03 00 00 00 01 84 0A
        cmd = bytes.fromhex('01 03 00 00 00 01 84 0A')
        resp = self._send_and_receive(cmd, expected_length=7)
        
        target = f"{self.ip}:{self.port}"
        if not resp:
            logger.warning(f"⚠️ 轮询硬件 [{target}] 传感器状态超时或无应答 -> 标记为 NETWORK_ERROR")
            return "NETWORK_ERROR"

        # 解析控制板返回报文
        if resp == bytes.fromhex('01 03 02 00 00 B8 44'): 
            logger.debug(f"🔍 硬件 [{target}] 状态解析: FULLY_CLOSED (全关)")
            return "FULLY_CLOSED" 
        if resp == bytes.fromhex('01 03 02 00 01 79 84'): 
            logger.debug(f"🔍 硬件 [{target}] 状态解析: MIDDLE (运行中/中间态)")
            return "MIDDLE"      
        if resp == bytes.fromhex('01 03 02 00 02 39 85'): 
            logger.debug(f"🔍 硬件 [{target}] 状态解析: FULLY_OPENED (全开)")
            return "FULLY_OPENED" 
            
        logger.warning(f"⚠️ 硬件 [{target}] 返回了未知状态报文 (Hex): {resp.hex().upper()}")
        return "UNKNOWN_STATE"

    def send_command(self, action: str) -> bool:
        """发送控制指令并校验设备回读确认"""
        target = f"{self.ip}:{self.port}"
        
        if action == "OPEN":   
            cmd = bytes.fromhex('01 06 00 00 00 01 48 0A') 
        elif action == "CLOSE": 
            cmd = bytes.fromhex('01 06 00 00 00 02 08 0B') 
        elif action == "PAUSE": 
            cmd = bytes.fromhex('01 06 00 00 00 03 C9 CB') 
        else: 
            logger.error(f"❌ 不支持的底层指令动作: '{action}'")
            return False

        logger.info(f"📤 准备向硬件 [{target}] 发送控制指令: [{action}]")
        resp = self._send_and_receive(cmd, expected_length=8)
        
        # 成功执行的报文反馈: 01 06 00 00 00 00 89 CA
        success_resp = bytes.fromhex('01 06 00 00 00 00 89 CA') 
        
        is_success = (resp == success_resp)
        if is_success:
            logger.info(f"✅ 硬件 [{target}] 成功执行指令 [{action}] 并返回 ACK 确认。")
        else:
            logger.error(f"❌ 硬件 [{target}] 对指令 [{action}] 的应答校验失败！收到报文 (Hex): {resp.hex().upper() if resp else 'EMPTY'}")
            
        return is_success