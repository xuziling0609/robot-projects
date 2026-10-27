import struct
from core.logger_manager import get_logger
from core.tcp_manager import TCPManager

logger = get_logger("YunjiLoraDriver")

class YunjiLoraDriver:
    """云迹机器人本地 LoRa 梯控 TCP 透传底层驱动 (协议 V1.4)"""
    
    def __init__(self, config: dict):
        self.ip = config.get("local_ip")
        self.port = config.get("local_port", 1030)
        self.timeout = config.get("timeout", 1.0)
        
        # 唯一码(12byte)与机器人 MAC(6byte)
        self.unique_code = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x10, 0x11, 0x12])
        self.local_mac = bytes([0x11, 0x22, 0x33, 0x44, 0x55, 0x66])
        self.pool = TCPManager()

    def _calc_xor(self, data_bytes: bytes) -> int:
        """CheckSum 校验算法：除 Header 外所有字节的 XOR 异或计算"""
        res = 0
        for b in data_bytes: 
            res ^= b
        return res

    def _build_frame(self, cmd: int, addr: int, data_payload: bytes) -> bytes:
        """
        组装控制报文:
        Header (0x7F 0xF7) | Length | Flag (0x29) | Addr | MAC | Payload Len | Cmd | Data | CheckSum
        """
        header = b'\x7F\xF7'
        flag = b'\x29'
        # 通信采用小端传输模式，先发低8位，再发高8位
        addr_bytes = struct.pack('<H', addr) 
        
        payload_len = bytes([len(data_payload)])
        cmd_byte = bytes([cmd])
        
        # 总长度计算 = 长度位(1) + Flag(1) + Addr(2) + MAC(6) + 载荷长度位(1) + Cmd(1) + 载荷真实长度
        total_len = 1 + 1 + 2 + 6 + 1 + 1 + len(data_payload)
        
        frame_no_header = bytes([total_len]) + flag + addr_bytes + self.local_mac + payload_len + cmd_byte + data_payload
        checksum = bytes([self._calc_xor(frame_no_header)])
        
        return header + frame_no_header + checksum

    def _send_and_receive(self, frame: bytes) -> bytes:
        """复用 TCP 连接池发送指令 (含获取连接异常保护)"""
        try:
            # 🚀 修复点：将 get_connection 放入 try 代码块
            # 这样 TCP 池抛出的 ConnectionRefusedError 就会被安全捕获
            conn = self.pool.get_connection(self.ip, self.port, timeout=self.timeout)
            if not conn: 
                return b''
            
            conn.sendall(frame)
            return conn.recv(1024)
            
        except Exception as e:
            logger.warning(f"⚠️ 本地 LoRa 模块通信异常 (可能已离线): {e}")
            # 如果是链路异常断开，通知连接池释放这个死链接
            self.pool.release_connection(self.ip, self.port)
            # 返回空字节，告知上层插件本地链路不通，触发双模转云端逻辑
            return b''

    def query_local_floor(self, addr: int) -> int:
        """
        查询电梯轿厢所在楼层 (Cmd: 0x61)
        请求: 唯一码(12byte)
        响应: 楼层(1byte) + 电梯状态(1byte) + 预留(2byte) ...
        """
        resp = self._send_and_receive(self._build_frame(0x61, addr, self.unique_code))
        if resp and len(resp) > 14 and resp[13] == 0x61:
            return resp[14] 
        return None

    def call_lift(self, addr: int, floor: int) -> bool:
        """
        点亮目标楼层 (Cmd: 0x60)
        请求: 目标楼层(1byte) + 唯一码(12byte)
        地下楼层映射: 201表示地下一层，202表示地下二层
        """
        mapped_floor = (200 + abs(floor)) if floor < 0 else floor
        logger.info(f"📡 开始本地 LoRa 模块呼梯 (Addr: {addr}, Floor: {mapped_floor})")
        resp = self._send_and_receive(self._build_frame(0x60, addr, bytes([mapped_floor]) + self.unique_code))
        return resp is not None and len(resp) > 0

    def delay_close(self, addr: int, delay_sec: int = 5) -> bool:
        """
        延时关门 (Cmd: 0x62)
        请求: 时间(1byte, 单位秒) + 唯一码(12byte)
        时间可用范围 1-9s
        """
        delay_sec = max(1, min(9, delay_sec)) # 严格限制在 1-9s 范围内
        resp = self._send_and_receive(self._build_frame(0x62, addr, bytes([delay_sec]) + self.unique_code))
        return resp is not None and len(resp) > 0
        
    def ping(self, addr: int) -> bool:
        """
        Ping 指令 (Cmd: 0x65)
        探测梯控板是否在线
        """
        resp = self._send_and_receive(self._build_frame(0x65, addr, self.unique_code))
        return resp is not None and len(resp) > 0