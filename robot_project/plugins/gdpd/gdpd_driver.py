import time
import serial
from typing import Optional, Dict, Any
from core.tcp_manager import TCPManager
from core.logger_manager import get_logger

logger = get_logger("GdpdDriver")

# TEV协议 V1.1 常量定义 (基于 rs485_jf.h)
START_CMD    = b"\x02\x04\x55\x55\x00\x01\x30\x25"
START_RET    = b"\x02\x04\x02\x55\x55\x02\x5F"

STOP_CMD     = b"\x02\x04\xAA\xAA\x00\x01\x30\x01"
STOP_RET     = b"\x02\x04\x02\xAA\xAA\x03\xEF"

ACQUIRE_CMD  = b"\x02\x04\x00\x00\x00\x04\xF1\xFA"

FREQ_CLR_CMD = b"\x02\x06\x01\x0C\x00\x00\x48\x06"
FREQ_CLR_RET = b"\x02\x06\x01\x0C\x00\x00\x48\x06"


class GdpdProtocol:
    """
    GDPD-63-TEV-T-A 局部放电传感器协议处理类
    负责 Modbus CRC16 校验与报文解析转换
    """
    @staticmethod
    def calculate_modbus_crc16(data: bytes) -> bytes:
        """计算标准 Modbus RTU CRC16 校验码 (小端返回)"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return bytes([crc & 0xFF, (crc >> 8) & 0xFF])

    @staticmethod
    def verify_crc(frame: bytes) -> bool:
        """校验报文 CRC16 是否有效"""
        if not frame or len(frame) < 4:
            return False
        calc_crc = GdpdProtocol.calculate_modbus_crc16(frame[:-2])
        return frame[-2:] == calc_crc

    @staticmethod
    def parse_acquire_response(frame: bytes) -> Optional[Dict[str, Any]]:
        """
        解析局放数据采集返回报文：
        地址(0x02) + 功能码(0x04) + 字节数(0x08) + 4个寄存器(8字节) + CRC(2字节)
        寄存器0: 峰值 raw -> float(raw) - 80.0 dBm
        寄存器1: 平均值 raw -> float(raw) - 80.0 dBm
        寄存器2: 频次 count -> int(raw)
        寄存器3: 总频次 count -> int(raw)
        """
        if not frame or len(frame) < 5:
            logger.warning(f"⚠️ 响应报文长度不足: {len(frame) if frame else 0} 字节")
            return None

        if frame[0] != 0x02 or frame[1] != 0x04:
            logger.warning(f"⚠️ 报文地址或功能码异常: Addr=0x{frame[0]:02X}, Func=0x{frame[1]:02X}")
            return None

        if not GdpdProtocol.verify_crc(frame):
            logger.error(f"❌ 局放数据响应报文 CRC 校验失败! Hex: {frame.hex().upper()}")
            return None

        byte_count = frame[2]
        if len(frame) < 3 + byte_count + 2:
            logger.warning(f"⚠️ 数据帧不完整, 期望至少 {3 + byte_count + 2} 字节, 收到 {len(frame)} 字节")
            return None

        # 大端字节序解析寄存器
        peak_raw = (frame[3] << 8) | frame[4]
        avg_raw = (frame[5] << 8) | frame[6]
        freq_raw = (frame[7] << 8) | frame[8]
        total_freq = (frame[9] << 8) | frame[10] if len(frame) >= 13 else 0

        peak = float(peak_raw) - 80.0
        average = float(avg_raw) - 80.0
        frequency = int(freq_raw)

        logger.debug(f"📋 解析成功 -> 峰值: {peak:.2f} dBm, 平均值: {average:.2f} dBm, 频次: {frequency}")
        return {
            "peak": round(peak, 2),
            "average": round(average, 2),
            "frequency": frequency,
            "total_frequency": total_freq,
            "raw_hex": frame.hex().upper()
        }


class GdpdDriver:
    """
    GDPD 局放传感器底座驱动 (支持 RS485 串口连接 & 兼容 TCP 透传网关)
    严格对齐 rs485_jf.c 中的配置项（默认 9600 波特率, 8数据位, 1停止位, 无校验, 2秒超时）
    """
    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 9600,
        data_bits: int = 8,
        stop_bits: int = 1,
        parity: str = 'N',
        timeout: float = 2.0,
        conn_type: str = "serial",
        ip: str = "127.0.0.1"
    ):
        self.port = port
        self.baudrate = int(baudrate)
        self.data_bits = int(data_bits)
        self.stop_bits = int(stop_bits)
        self.parity = str(parity).upper()
        self.timeout = float(timeout)
        self.conn_type = str(conn_type).lower()
        self.ip = ip
        
        self.serial_conn = None
        self.pool = None
        
        # 自动识别通信模式：若参数指定 tcp 或 port 为数字端口，则启用 TCP 模式；否则默认采用 RS485 串口连接
        if self.conn_type == "tcp" or (isinstance(self.port, int) or (isinstance(self.port, str) and self.port.isdigit())):
            self.conn_type = "tcp"
            self.port = int(self.port)
            self.pool = TCPManager()
            logger.debug(f"✨ 初始化 GdpdDriver -> [TCP网关模式] 目标: [{self.ip}:{self.port}]")
        else:
            self.conn_type = "serial"
            logger.debug(f"✨ 初始化 GdpdDriver -> [RS485串口模式] 串口路径: [{self.port}] (Baud:{self.baudrate}, {self.data_bits}{self.parity}{self.stop_bits})")

    def _get_serial_connection(self) -> Optional[serial.Serial]:
        """获取或重建 RS485 串口长连接"""
        if self.serial_conn and self.serial_conn.is_open:
            return self.serial_conn
        
        try:
            parity_map = {
                'N': serial.PARITY_NONE,
                'E': serial.PARITY_EVEN,
                'O': serial.PARITY_ODD
            }
            p = parity_map.get(self.parity, serial.PARITY_NONE)
            
            self.serial_conn = serial.Serial(
                port=str(self.port),
                baudrate=self.baudrate,
                bytesize=self.data_bits,
                stopbits=self.stop_bits,
                parity=p,
                timeout=self.timeout
            )
            logger.info(f"✅ 成功打开 RS485 串口: {self.port} (波特率:{self.baudrate})")
            return self.serial_conn
        except Exception as e:
            logger.error(f"❌ 打开 RS485 串口失败 [{self.port}]: {e}")
            self.serial_conn = None
            return None

    def _send_and_receive(self, cmd_bytes: bytes, expected_length: int = 256) -> bytes:
        """底层通信收发分流控制 (RS485串口 / TCP网关)"""
        if self.conn_type == "tcp":
            return self._send_and_receive_tcp(cmd_bytes, expected_length)
        else:
            return self._send_and_receive_serial(cmd_bytes, expected_length)

    def _send_and_receive_serial(self, cmd_bytes: bytes, expected_length: int = 256) -> bytes:
        """通过 RS485 串口通信，包含 1 次断连自动恢复与重试机制"""
        try:
            conn = self._get_serial_connection()
            if not conn:
                return b''

            # 清除输入输出缓冲区中的残余脏数据 (对应于 tcflush)
            conn.reset_input_buffer()
            conn.reset_output_buffer()

            logger.debug(f"📤 [RS485串口] 发送局放指令 (Hex): {cmd_bytes.hex().upper()}")
            conn.write(cmd_bytes)
            conn.flush()  # 等待数据发送完毕 (对应于 tcdrain)
            time.sleep(0.05)

            resp = conn.read(expected_length)
            logger.debug(f"📥 [RS485串口] 收到局放响应 (Hex): {resp.hex().upper() if resp else 'EMPTY'}")
            return resp
        except Exception as e:
            logger.warning(f"⚠️ [RS485串口] 通信异常 [{self.port}] ({e})，触发 1 次自动重启串口与重连...")
            self.disconnect()
            
            try:
                conn = self._get_serial_connection()
                if conn:
                    conn.reset_input_buffer()
                    conn.write(cmd_bytes)
                    conn.flush()
                    time.sleep(0.05)
                    resp = conn.read(expected_length)
                    logger.debug(f"📥 [RS485串口] 重开后收到响应 (Hex): {resp.hex().upper() if resp else 'EMPTY'}")
                    return resp
            except Exception as retry_e:
                logger.error(f"❌ [RS485串口] 重传报文彻底失败 [{self.port}]: {retry_e}")
            return b''

    def _send_and_receive_tcp(self, cmd_bytes: bytes, expected_length: int = 256) -> bytes:
        """通过 TCP 连接池与网关通信"""
        target = f"{self.ip}:{self.port}"
        try:
            conn = self.pool.get_connection(self.ip, self.port, self.timeout)
            if not conn:
                logger.error(f"❌ 无法获取目标 [{target}] 的有效 TCP 链路")
                return b''

            logger.debug(f"📤 [TCP网关] 发送局放指令 (Hex): {cmd_bytes.hex().upper()}")
            conn.sendall(cmd_bytes)
            time.sleep(0.05)
            resp = conn.recv(expected_length)
            logger.debug(f"📥 [TCP网关] 收到局放响应 (Hex): {resp.hex().upper() if resp else 'EMPTY'}")
            return resp
        except Exception as e:
            logger.warning(f"⚠️ [TCP网关] 通信异常 [{target}] ({e})，触发 1 次自动重连...")
            try:
                self.pool.release_connection(self.ip, self.port)
                conn = self.pool.get_connection(self.ip, self.port, self.timeout)
                if conn:
                    conn.sendall(cmd_bytes)
                    time.sleep(0.05)
                    resp = conn.recv(expected_length)
                    logger.debug(f"📥 [TCP网关] 重连后收到响应 (Hex): {resp.hex().upper() if resp else 'EMPTY'}")
                    return resp
            except Exception as retry_e:
                logger.error(f"❌ [TCP网关] 重连并二次投递报文彻底失败 [{target}]: {retry_e}")
            return b''

    def start_acquisition(self) -> bool:
        """下发局放启动采集指令 (02 04 55 55 00 01 CRC)"""
        logger.info(f"🚀 [GdpdDriver] 下发启动局放采集指令...")
        resp = self._send_and_receive(START_CMD, expected_length=len(START_RET))
        if resp and (resp == START_RET or (len(resp) >= 5 and resp[0] == 0x02 and GdpdProtocol.verify_crc(resp))):
            logger.info("✅ 启动局放采集成功")
            return True
        logger.error(f"❌ 启动局放采集失败! 响应: {resp.hex().upper() if resp else 'NONE'}")
        return False

    def stop_acquisition(self) -> bool:
        """下发局放停止采集指令 (02 04 AA AA 00 01 CRC)"""
        logger.info(f"🛑 [GdpdDriver] 下发停止局放采集指令...")
        resp = self._send_and_receive(STOP_CMD, expected_length=len(STOP_RET))
        if resp and (resp == STOP_RET or (len(resp) >= 5 and resp[0] == 0x02 and GdpdProtocol.verify_crc(resp))):
            logger.info("✅ 停止局放采集成功")
            return True
        logger.error(f"❌ 停止局放采集失败! 响应: {resp.hex().upper() if resp else 'NONE'}")
        return False

    def clear_frequency(self) -> bool:
        """清零频次计数器"""
        logger.info(f"🔄 [GdpdDriver] 下发频次计数清零指令...")
        resp = self._send_and_receive(FREQ_CLR_CMD, expected_length=len(FREQ_CLR_RET))
        if resp and (resp == FREQ_CLR_RET or (len(resp) >= 5 and resp[0] == 0x02 and GdpdProtocol.verify_crc(resp))):
            logger.info("✅ 频次计数清零成功")
            return True
        logger.error(f"❌ 频次计数清零失败! 响应: {resp.hex().upper() if resp else 'NONE'}")
        return False

    def acquire_data(self) -> Optional[Dict[str, Any]]:
        """读取单次局放实时检测数据"""
        resp = self._send_and_receive(ACQUIRE_CMD, expected_length=64)
        if not resp:
            logger.warning("⚠️ 读取局放数据无响应")
            return None
        return GdpdProtocol.parse_acquire_response(resp)

    def disconnect(self):
        """安全关闭串口或释放网络链路资源"""
        if self.serial_conn:
            try:
                if self.serial_conn.is_open:
                    self.serial_conn.close()
                logger.info(f"🛑 已关闭 RS485 串口: {self.port}")
            except Exception as e:
                logger.debug(f"关闭串口异常: {e}")
            finally:
                self.serial_conn = None
        elif self.pool and self.conn_type == "tcp":
            try:
                self.pool.release_connection(self.ip, self.port)
            except Exception as e:
                logger.error('捕获到异常', exc_info=True)
