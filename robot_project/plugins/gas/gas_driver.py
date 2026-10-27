import time
import struct
import threading
import serial
from typing import Optional, Dict, Any, List, Tuple, Union
from core.logger_manager import get_logger

logger = get_logger("GasDriver")

# ============================================================================
# 协议常量定义 (严格基于: 传感器模组数据读取用户协议V1.00-20250427 & gas_controller.h/c)
# ============================================================================

GAS_FRAME_HEADER          = 0x5A    # 协议帧头
GAS_FRAME_TAIL            = 0x5B    # 协议帧尾

# 功能码定义
GAS_FUNC_CODE_READ        = 0x01    # 读参数数据
GAS_FUNC_CODE_WRITE       = 0x03    # 写数据
GAS_FUNC_CODE_CONTROL     = 0x05    # 设备控制
GAS_FUNC_CODE_OPERATE     = 0x06    # 设备操作

# 读数据命令字
GAS_CMD_READ_BASE_INFO    = 0x01    # 读取设备基本信息
GAS_CMD_READ_CHANNEL_INFO = 0x02    # 读取设备通道信息
GAS_CMD_READ_CONCENTRATION= 0x03    # 读取设备浓度数值信息

# 设备控制命令字
GAS_CMD_CONTROL_PUMP      = 0x01    # 控制泵

# 设备操作命令字
GAS_CMD_OP_CALIBRATE      = 0x01    # 设备操作-校准
GAS_CMD_OP_FACTORY_RESET  = 0x02    # 设备操作-恢复出厂设置

# 默认广播短地址
GAS_DEFAULT_SHORT_ADDR    = 0x1234  # 默认短地址 0x1234 (4660)

# 操作结果状态码
GAS_RESULT_NORMAL         = 0x00    # 操作成功 / 正常
GAS_RESULT_ERROR          = 0x01    # 操作失败 / 异常

# 系统状态位定义 (Bit0 报警, Bit1 泵堵塞, Bit2 电源故障)
GAS_STATUS_ALARM          = (1 << 0)  # Bit0: 报警
GAS_STATUS_PUMP_BLOCK     = (1 << 1)  # Bit1: 泵堵塞
GAS_STATUS_POWER_FAULT    = (1 << 2)  # Bit2: 电源故障

# 报警模式定义
GAS_ALARM_MODE_NORMAL     = 0x00    # 常规报警
GAS_ALARM_MODE_INTERVAL   = 0x01    # 区间报警

# 报警种类定义
GAS_ALARM_KIND_DEFAULT    = 0x00    # 默认
GAS_ALARM_KIND_TWA        = 0x01    # TWA
GAS_ALARM_KIND_STEL       = 0x02    # STEL
GAS_ALARM_KIND_MAC        = 0x03    # MAC


class GasProtocol:
    """
    气体传感器通用通讯协议处理类
    基于: 《传感器模组数据读取用户协议V1.00-20250427》及 C 语言标准驱动实现 (gas_controller.c/h)
    支持 Modbus RTU CRC16 校验计算、数据帧序列化封装解封装、浓度放大倍数转换及气体单位映射。
    """

    @staticmethod
    def calculate_crc16(data: bytes) -> int:
        """
        计算 Modbus CRC16 校验码
        多项式 0xA001, 初始值 0xFFFF
        计算范围: 帧标识到数据段
        """
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc & 0xFFFF

    @staticmethod
    def build_frame(short_addr: int, func_code: int, cmd_code: int, data: bytes = b'') -> bytes:
        """
        构建协议请求数据帧:
        +--------+--------+------------+--------+--------+--------+----------+--------+------+ 
        |  帧头  |  长度  |   帧标识   | 短地址 | 功能码 | 命令字 |   数据   | CRC校验 | 帧尾 |
        | 0x5A   | 2Byte  |   1Byte    | 2Byte  | 1Byte  | 1Byte  |  NByte   |  2Byte  | 0x5B |
        +--------+--------+------------+--------+--------+--------+----------+--------+------+
        长度定义: 从帧标识(包含)到校验(包含)的字节数
        """
        data_len = len(data)
        crc_len = 1 + 2 + 1 + 1 + data_len + 2

        frame = bytearray()
        frame.append(GAS_FRAME_HEADER)
        frame.append((crc_len >> 8) & 0xFF)
        frame.append(crc_len & 0xFF)

        crc_payload = bytearray()
        crc_payload.append(0x00)  # 帧标识
        crc_payload.append((short_addr >> 8) & 0xFF)
        crc_payload.append(short_addr & 0xFF)
        crc_payload.append(func_code)
        crc_payload.append(cmd_code)
        if data:
            crc_payload.extend(data)

        # 高字节在前 (大端格式 CRC)
        crc = GasProtocol.calculate_crc16(bytes(crc_payload))
        crc_bytes = bytes([(crc >> 8) & 0xFF, crc & 0xFF])

        frame.extend(crc_payload)
        frame.extend(crc_bytes)
        frame.append(GAS_FRAME_TAIL)

        return bytes(frame)

    @staticmethod
    def verify_frame(frame: bytes, expected_func: int, expected_cmd: int) -> Tuple[bool, bytes, str]:
        """
        校验响应帧格式及 CRC16 完整性
        """
        if not frame or len(frame) < 10:
            return False, b'', f"响应帧长度不足: {len(frame)} 字节"

        if frame[0] != GAS_FRAME_HEADER or frame[-1] != GAS_FRAME_TAIL:
            return False, b'', f"帧头或帧尾异常: Head=0x{frame[0]:02X}, Tail=0x{frame[-1]:02X}"

        frame_length = (frame[1] << 8) | frame[2]
        if len(frame) != frame_length + 4:
            if len(frame) >= frame_length + 4 and frame[frame_length + 3] == GAS_FRAME_TAIL:
                frame = frame[:frame_length + 4]
            else:
                return False, b'', f"长度字段与实际字节数不匹配: Expect={frame_length+4}, Got={len(frame)}"

        crc_calc = GasProtocol.calculate_crc16(frame[3:-3])
        crc_recv = (frame[-3] << 8) | frame[-2]
        if crc_calc != crc_recv:
            return False, b'', f"CRC16校验失败: Calc=0x{crc_calc:04X}, Recv=0x{crc_recv:04X}"

        func_code = frame[6]
        cmd_code = frame[7]
        if func_code != expected_func:
            return False, b'', f"功能码不匹配: Expect=0x{expected_func:02X}, Got=0x{func_code:02X}"

        # 设备应答命令字或上 0x80 (cmd | 0x80)，同时兼容未置位的固件
        if cmd_code != (expected_cmd | 0x80) and cmd_code != expected_cmd:
            return False, b'', f"命令字不匹配: Expect=0x{expected_cmd|0x80:02X}, Got=0x{cmd_code:02X}"

        payload = frame[8:-3]
        return True, payload, "OK"

    @staticmethod
    def get_magnification_factor(mag: int) -> float:
        """根据协议附录枚举值解析浓度放大倍数"""
        if mag == 1:
            return 10.0
        elif mag == 2:
            return 100.0
        elif mag == 3:
            return 1000.0
        return 1.0

    @staticmethod
    def unit_to_string(unit: int) -> str:
        """根据协议附录转换气体单位字符串 (0x00 ~ 0x17)"""
        units = [
            "PPM", "%VOL", "%LEL", "PPHM", "Mg/m3", "ppb", "Mg/L", "G/m3",
            "℃", "%RH", "KPa", "Nm3/h", "Ug/m3", "None", "umol/mol", "Lux",
            "m", "bar", "ms", "°", "mL/min", "Pa", "mm", "dB"
        ]
        if 0 <= unit < len(units):
            return units[unit]
        return "Unknown"

    @staticmethod
    def parse_system_status(status_byte: int) -> Dict[str, bool]:
        """解析系统状态字节: Bit0 报警, Bit1 泵堵塞, Bit2 电源故障"""
        return {
            "alarm": bool(status_byte & GAS_STATUS_ALARM),
            "pump_block": bool(status_byte & GAS_STATUS_PUMP_BLOCK),
            "power_fault": bool(status_byte & GAS_STATUS_POWER_FAULT)
        }

    @staticmethod
    def parse_base_info_payload(payload: bytes, short_addr: int) -> Dict[str, Any]:
        """
        解析设备基本信息响应 (命令 0x01/0x01, 应答 0x01/0x81)
        依据协议文档 1.3.2 节:
        测量通道总数(1B) + 气体种类数(1B) + 设备UID(12B) + 厂家信息(20B) + 硬件版本(20B) + 软件版本(20B) + 出厂Unix时间(4B)
        """
        if len(payload) < 2:
            return {}

        ch_count = payload[0]
        gas_type_count = payload[1]
        uid = payload[2:14].hex().upper() if len(payload) >= 14 else "UNKNOWN"

        vendor = ""
        hw_ver = ""
        sw_ver = ""
        build_time_str = ""

        if len(payload) >= 34:
            vendor = payload[14:34].decode('ascii', errors='ignore').strip('\x00 ').strip()
        if len(payload) >= 54:
            hw_ver = payload[34:54].decode('ascii', errors='ignore').strip('\x00 ').strip()
        if len(payload) >= 74:
            sw_ver = payload[54:74].decode('ascii', errors='ignore').strip('\x00 ').strip()
        if len(payload) >= 78:
            build_ts = int.from_bytes(payload[74:78], byteorder='big', signed=False)
            if build_ts > 0:
                try:
                    build_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(build_ts))
                except Exception as e:
                    logger.error('解析出厂时间戳异常:', exc_info=True)
                    build_time_str = str(build_ts)

        return {
            "channel_count": ch_count,
            "gas_type_count": gas_type_count,
            "device_uid": uid,
            "manufacturer": vendor,
            "hardware_version": hw_ver,
            "software_version": sw_ver,
            "build_time": build_time_str,
            "short_addr": f"0x{short_addr:04X}"
        }

    @staticmethod
    def parse_channel_info_payload(payload: bytes, channel_configs: Optional[List[Dict[str, Any]]] = None, sensor_id: int = 1) -> Dict[str, Any]:
        """
        解析设备通道完整参数信息响应 (命令 0x01/0x02, 应答 0x01/0x82)
        依据协议文档 1.3.3 节与 gas_controller.c:
        数据体 = 系统状态(1B) + 通道数量(1B) + N*80字节通道详细数据
        单个通道80字节:
          通道编码(1B) + 名称(20B) + 量程(4B) + 放大倍数(1B) + 单位(1B) +
          一级报警点(4B) + 一级回程差(4B) + 一级模式(1B) +
          二级报警点(4B) + 二级回程差(4B) + 二级模式(1B) +
          三级报警点(4B) + 三级回程差(4B) + 三级模式(1B) +
          报警种类(1B) + 浓度(4B) + 报警状态(1B) + 原始AD(4B) + 保留(16B)
        """
        if len(payload) < 2:
            return {"system_status": 0, "status_flags": {}, "channel_count": 0, "channels": []}

        pos = 0
        sys_status = payload[pos]
        pos += 1
        ch_count = payload[pos]
        pos += 1

        channels = []
        for idx in range(ch_count):
            if pos + 80 > len(payload):
                break
            ch_code = payload[pos]
            pos += 1

            if channel_configs and idx < len(channel_configs):
                cfg_code = channel_configs[idx].get("channel_code")
                if cfg_code:
                    ch_code = cfg_code

            # 气体名称 20 byte ascii
            gas_name = payload[pos:pos+20].decode('ascii', errors='ignore').strip('\x00 ').strip()
            if not gas_name or gas_name.startswith("GAS_"):
                if channel_configs and idx < len(channel_configs):
                    gas_name = channel_configs[idx].get("name", gas_name)
                else:
                    gas_name = f"GAS_{ch_code}"
            pos += 20

            # 量程 4 byte (协议文档示例报文中为大端整型，同时兼容部分固件的 IEEE-754 浮点)
            raw_range_bytes = payload[pos:pos+4]
            try:
                f_val = struct.unpack('>f', raw_range_bytes)[0]
                int_val = int.from_bytes(raw_range_bytes, byteorder='big', signed=False)
                # 若为正常有效浮点数
                if 0.01 <= f_val <= 10000000.0:
                    range_val = f_val
                else:
                    range_val = float(int_val)
            except Exception:
                range_val = 0.0
            pos += 4

            # 放大倍数 1 byte
            mag = payload[pos]
            pos += 1
            factor = GasProtocol.get_magnification_factor(mag)

            # 单位 1 byte
            unit_val = payload[pos]
            pos += 1
            unit_str = GasProtocol.unit_to_string(unit_val)

            # 一级报警点 4 byte, 回程差 4 byte, 模式 1 byte
            l1_raw = int.from_bytes(payload[pos:pos+4], byteorder='big', signed=True)
            pos += 4
            l1_hyst_raw = int.from_bytes(payload[pos:pos+4], byteorder='big', signed=True)
            pos += 4
            l1_mode = payload[pos]
            pos += 1

            # 二级报警点 4 byte, 回程差 4 byte, 模式 1 byte
            l2_raw = int.from_bytes(payload[pos:pos+4], byteorder='big', signed=True)
            pos += 4
            l2_hyst_raw = int.from_bytes(payload[pos:pos+4], byteorder='big', signed=True)
            pos += 4
            l2_mode = payload[pos]
            pos += 1

            # 三级报警点 4 byte, 回程差 4 byte, 模式 1 byte
            l3_raw = int.from_bytes(payload[pos:pos+4], byteorder='big', signed=True)
            pos += 4
            l3_hyst_raw = int.from_bytes(payload[pos:pos+4], byteorder='big', signed=True)
            pos += 4
            l3_mode = payload[pos]
            pos += 1

            # 报警种类 1 byte (0:默认, 1:TWA, 2:STEL, 3:MAC)
            alarm_kind = payload[pos]
            pos += 1

            # 实时浓度 4 byte int32
            conc_raw = int.from_bytes(payload[pos:pos+4], byteorder='big', signed=True)
            pos += 4
            conc_val = round(float(conc_raw) / factor, 4) if factor > 0 else float(conc_raw)

            # 报警状态 1 byte
            alarm_status = payload[pos]
            pos += 1

            # 原始AD值 4 byte uint32
            raw_ad = int.from_bytes(payload[pos:pos+4], byteorder='big', signed=False)
            pos += 4

            # 跳过保留区域 16 bytes
            pos += 16

            channels.append({
                "sensor_id": sensor_id,
                "channel_code": ch_code,
                "name": gas_name,
                "range": round(range_val, 2),
                "magnification": mag,
                "unit": unit_str,
                "concentration": conc_val,
                "alarm_point_level1": round(float(l1_raw) / factor, 2) if factor > 0 else float(l1_raw),
                "alarm_hysteresis_level1": round(float(l1_hyst_raw) / factor, 2) if factor > 0 else float(l1_hyst_raw),
                "alarm_mode_level1": l1_mode,
                "alarm_point_level2": round(float(l2_raw) / factor, 2) if factor > 0 else float(l2_raw),
                "alarm_hysteresis_level2": round(float(l2_hyst_raw) / factor, 2) if factor > 0 else float(l2_hyst_raw),
                "alarm_mode_level2": l2_mode,
                "alarm_point_level3": round(float(l3_raw) / factor, 2) if factor > 0 else float(l3_raw),
                "alarm_hysteresis_level3": round(float(l3_hyst_raw) / factor, 2) if factor > 0 else float(l3_hyst_raw),
                "alarm_mode_level3": l3_mode,
                "alarm_kind": alarm_kind,
                "alarm_status": alarm_status,
                "raw_ad_value": raw_ad
            })

        return {
            "system_status": sys_status,
            "status_flags": GasProtocol.parse_system_status(sys_status),
            "channel_count": len(channels),
            "channels": channels
        }

    @staticmethod
    def parse_concentration_payload(payload: bytes, channel_configs: Optional[List[Dict[str, Any]]] = None, sensor_id: int = 1) -> Dict[str, Any]:
        """
        解析实时浓度数据包 (命令 0x01/0x03, 应答 0x01/0x83)
        依据协议文档 1.3.4 节:
        数据体 = 系统状态(1B) + 通道数量(1B) + 每个通道10字节:
          [通道编码(1B) + 浓度int32(4B) + 通道状态(1B) + 原始AD int32(4B)]
        """
        if len(payload) < 2:
            return {"system_status": 0, "status_flags": {}, "channel_count": 0, "channels": []}

        pos = 0
        sys_status = payload[pos]
        pos += 1
        ch_count = payload[pos]
        pos += 1

        channels = []
        for _ in range(ch_count):
            if pos + 10 > len(payload):
                break
            ch_code = payload[pos]
            pos += 1

            conc_raw = int.from_bytes(payload[pos:pos+4], byteorder='big', signed=True)
            pos += 4
            conc_val = float(conc_raw)

            ch_status = payload[pos]
            pos += 1

            raw_ad = int.from_bytes(payload[pos:pos+4], byteorder='big', signed=False)
            pos += 4

            name = f"GAS_{ch_code}"
            unit_str = ""
            if channel_configs:
                for cfg in channel_configs:
                    cfg_code = cfg.get("channel_code", 0)
                    if cfg_code == ch_code or (ch_code < 10 and cfg_code % 10 == ch_code):
                        ch_code = cfg_code
                        name = cfg.get("name", name)
                        unit_str = cfg.get("unit", "")
                        mag = cfg.get("magnification", 0)
                        factor = GasProtocol.get_magnification_factor(mag)
                        if factor > 0:
                            conc_val /= factor
                        break

            conc_val = round(conc_val, 4) if conc_val != int(conc_val) else conc_val

            channels.append({
                "sensor_id": sensor_id,
                "channel_code": ch_code,
                "name": name,
                "concentration": conc_val,
                "unit": unit_str,
                "status": ch_status,
                "raw_ad_value": raw_ad
            })

        return {
            "system_status": sys_status,
            "status_flags": GasProtocol.parse_system_status(sys_status),
            "channel_count": len(channels),
            "channels": channels
        }


class GasDriver:
    """
    气体传感器底座驱动类 (支持8合一、1合一及M-B6泵吸式六合一模组)
    严格对齐《传感器模组数据读取用户协议V1.00-20250427》规范
    支持 RS485 / TTL 多传感器串口总线互斥访问，提供浓度采集、通道参数查询、气泵控制、零点/目标校准及恢复出厂操作。
    """
    _port_locks: Dict[str, threading.Lock] = {}
    _port_lock_guard = threading.Lock()

    def __init__(
        self,
        sensor_id: int = 1,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 9600,
        data_bits: int = 8,
        stop_bits: int = 1,
        parity: str = 'N',
        short_addr: int = GAS_DEFAULT_SHORT_ADDR,
        timeout: float = 2.0,
        channel_configs: Optional[List[Dict[str, Any]]] = None
    ):
        self.sensor_id = sensor_id
        self.port = port
        self.baudrate = int(baudrate)
        self.data_bits = int(data_bits)
        self.stop_bits = int(stop_bits)
        self.parity = str(parity).upper()
        self.short_addr = int(short_addr)
        self.timeout = float(timeout)
        self.channel_configs = channel_configs or []

        self.serial_conn: Optional[serial.Serial] = None

        with GasDriver._port_lock_guard:
            if self.port not in GasDriver._port_locks:
                GasDriver._port_locks[self.port] = threading.Lock()

        logger.debug(f"✨ 初始化 GasDriver [ID={self.sensor_id}] -> 串口: [{self.port}] (Baud:{self.baudrate}), 短地址: 0x{self.short_addr:04X}, 通道数: {len(self.channel_configs)}")

    def _get_serial_connection(self) -> Optional[serial.Serial]:
        """获取或创建串口连接句柄"""
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
            logger.info(f"✅ [GasDriver ID={self.sensor_id}] 成功打开串口: {self.port}")
            return self.serial_conn
        except Exception as e:
            logger.error(f"❌ [GasDriver ID={self.sensor_id}] 打开串口失败 [{self.port}]: {e}")
            self.serial_conn = None
            return None

    def _send_and_receive(self, send_bytes: bytes, expected_func: int, expected_cmd: int) -> Optional[bytes]:
        """发送帧并接收响应，内部包含单次自动恢复与重连逻辑"""
        lock = GasDriver._port_locks.get(self.port, threading.Lock())
        
        with lock:
            try:
                conn = self._get_serial_connection()
                if not conn:
                    return None

                conn.reset_input_buffer()
                conn.reset_output_buffer()

                logger.debug(f"📤 [GasDriver ID={self.sensor_id} @ {self.port}] 发送请求 (Hex): {send_bytes.hex().upper()}")
                conn.write(send_bytes)
                conn.flush()
                time.sleep(0.05)

                head_buf = conn.read(3)
                if len(head_buf) < 3:
                    logger.warning(f"⚠️ [GasDriver ID={self.sensor_id}] 响应头超时或长度不足 (Hex: {head_buf.hex().upper()})")
                    raise TimeoutError("响应头读超时")

                if head_buf[0] != GAS_FRAME_HEADER:
                    rem = conn.read(64)
                    full_tmp = head_buf + rem
                    idx = full_tmp.find(bytes([GAS_FRAME_HEADER]))
                    if idx != -1 and len(full_tmp) >= idx + 3:
                        head_buf = full_tmp[idx:idx+3]
                        rem = full_tmp[idx+3:]
                        frame_len = (head_buf[1] << 8) | head_buf[2]
                        needed = (frame_len + 4) - len(head_buf) - len(rem)
                        if needed > 0:
                            rem += conn.read(needed)
                        resp_frame = head_buf + rem
                    else:
                        raise ValueError("响应中未找到有效帧头 0x5A")
                else:
                    frame_len = (head_buf[1] << 8) | head_buf[2]
                    rem = conn.read(frame_len + 1)
                    resp_frame = head_buf + rem

                logger.debug(f"📥 [GasDriver ID={self.sensor_id} @ {self.port}] 收到响应 (Hex): {resp_frame.hex().upper()}")
                ok, payload, msg = GasProtocol.verify_frame(resp_frame, expected_func, expected_cmd)
                if ok:
                    return payload
                else:
                    logger.warning(f"⚠️ [GasDriver ID={self.sensor_id}] 响应校验失败: {msg}")
                    return None

            except Exception as e:
                logger.warning(f"⚠️ [GasDriver ID={self.sensor_id}] 通信异常 ({e})，尝试重启串口重试...")
                self.disconnect()
                
                try:
                    conn = self._get_serial_connection()
                    if conn:
                        conn.reset_input_buffer()
                        conn.write(send_bytes)
                        conn.flush()
                        time.sleep(0.05)
                        head_buf = conn.read(3)
                        if len(head_buf) == 3 and head_buf[0] == GAS_FRAME_HEADER:
                            frame_len = (head_buf[1] << 8) | head_buf[2]
                            rem = conn.read(frame_len + 1)
                            resp_frame = head_buf + rem
                            logger.debug(f"📥 [GasDriver ID={self.sensor_id}] 重传后收到响应 (Hex): {resp_frame.hex().upper()}")
                            ok, payload, _ = GasProtocol.verify_frame(resp_frame, expected_func, expected_cmd)
                            if ok:
                                return payload
                except Exception as retry_e:
                    logger.error(f"❌ [GasDriver ID={self.sensor_id}] 二次重试彻底失败: {retry_e}")
                return None

    def read_base_info(self) -> Optional[Dict[str, Any]]:
        """
        读取设备完整基础信息 (功能码 0x01, 命令字 0x01)
        符合协议文档 1.3.1 节
        """
        send_data = bytes([0x01])
        frame = GasProtocol.build_frame(self.short_addr, GAS_FUNC_CODE_READ, GAS_CMD_READ_BASE_INFO, send_data)
        payload = self._send_and_receive(frame, GAS_FUNC_CODE_READ, GAS_CMD_READ_BASE_INFO)
        if not payload:
            return None
        info = GasProtocol.parse_base_info_payload(payload, self.short_addr)
        if info:
            info["sensor_id"] = self.sensor_id
        return info

    def read_channel_info(self, channel_codes: Optional[List[int]] = None) -> Optional[Dict[str, Any]]:
        """
        读取设备通道完整参数信息 (功能码 0x01, 命令字 0x02)
        符合协议文档 1.3.3 节
        """
        if not channel_codes:
            count = len(self.channel_configs) if self.channel_configs else 6
            channel_codes = [c.get("channel_code", i+1) for i, c in enumerate(self.channel_configs)] if self.channel_configs else list(range(1, count + 1))

        count = len(channel_codes)
        send_data = bytearray([count])
        send_data.extend(channel_codes)

        frame = GasProtocol.build_frame(self.short_addr, GAS_FUNC_CODE_READ, GAS_CMD_READ_CHANNEL_INFO, bytes(send_data))
        payload = self._send_and_receive(frame, GAS_FUNC_CODE_READ, GAS_CMD_READ_CHANNEL_INFO)
        if payload is None:
            return None
        return GasProtocol.parse_channel_info_payload(payload, self.channel_configs, self.sensor_id)

    def read_concentration(self, channel_codes: Optional[List[int]] = None) -> Optional[Dict[str, Any]]:
        """
        读取设备浓度数值信息并进行放大倍数换算 (功能码 0x01, 命令字 0x03)
        符合协议文档 1.3.4 节
        """
        if not channel_codes:
            count = len(self.channel_configs) if self.channel_configs else 8
            channel_codes = [c.get("channel_code", i+1) for i, c in enumerate(self.channel_configs)] if self.channel_configs else list(range(1, count + 1))

        count = len(channel_codes)
        send_data = bytearray([count])
        send_data.extend(channel_codes)

        frame = GasProtocol.build_frame(self.short_addr, GAS_FUNC_CODE_READ, GAS_CMD_READ_CONCENTRATION, bytes(send_data))
        payload = self._send_and_receive(frame, GAS_FUNC_CODE_READ, GAS_CMD_READ_CONCENTRATION)
        if payload is None:
            return None
        return GasProtocol.parse_concentration_payload(payload, self.channel_configs, self.sensor_id)

    def control_pump(self, on_off: int, flow_level: int = 5, flow_rate: int = 0) -> bool:
        """
        控制传感器内置采样气泵 (功能码 0x05, 命令字 0x01)
        符合协议文档 2.3 节:
        下发数据: 开关状态(1B: 0x01开/0x00关) + 流量级别(1B: 1-10, 255速率控制) + 流量速率(2B)
        应答数据: 结果(1B: 0x00正常/0x01异常) + 当前开关(1B) + 当前级别(1B) + 当前速率(2B)
        """
        send_data = bytes([
            on_off & 0xFF,
            flow_level & 0xFF,
            (flow_rate >> 8) & 0xFF,
            flow_rate & 0xFF
        ])
        frame = GasProtocol.build_frame(self.short_addr, GAS_FUNC_CODE_CONTROL, GAS_CMD_CONTROL_PUMP, send_data)
        logger.info(f"🔄 [GasDriver ID={self.sensor_id}] 下发控制气泵指令 -> 开关:{on_off}, 流量级别:{flow_level}, 速率:{flow_rate}")
        payload = self._send_and_receive(frame, GAS_FUNC_CODE_CONTROL, GAS_CMD_CONTROL_PUMP)
        if payload is not None and len(payload) >= 1:
            res_code = payload[0]
            if res_code == GAS_RESULT_NORMAL:
                cur_state = ""
                if len(payload) >= 5:
                    c_on = payload[1]
                    c_level = payload[2]
                    c_rate = (payload[3] << 8) | payload[4]
                    cur_state = f" (当前状态: 开关={c_on}, 级别={c_level}, 速率={c_rate})"
                logger.info(f"✅ [GasDriver ID={self.sensor_id}] 控制气泵操作成功{cur_state}")
                return True
            else:
                logger.error(f"❌ [GasDriver ID={self.sensor_id}] 控制气泵模组返回异常状态码: 0x{res_code:02X}")
                return False
        logger.error(f"❌ [GasDriver ID={self.sensor_id}] 控制气泵指令无响应或校验失败")
        return False

    def calibrate_channel(self, channel_code: int, level: int, cal_data: Union[int, float], cal_ad: int) -> bool:
        """
        气体通道校准操作 (功能码 0x06, 命令字 0x01)
        符合协议文档 2.4.1 & 2.4.2 节:
        下发数据 (10字节，加上命令字0x01共11字节):
          通道号(1B) + 级别(1B: 0零点/1一级目标/2二级目标) + 校准数据(4B int32，按放大倍数换算的原始整型) + 校准AD(4B uint32)
        应答数据 (11字节):
          通道号(1B) + 级别(1B) + 校准数据(4B int32) + 校准AD(4B uint32) + 结果(1B: 0x00成功/0xXX错误码)
        校准结果字段位于第 10 索引字节 / 末字节 (payload[-1])
        """
        raw_ch_code = channel_code
        if channel_code in [11, 12, 13, 14, 15, 16]:
            raw_ch_code = channel_code - 10
        elif channel_code == 21:
            raw_ch_code = channel_code - 20

        send_data = bytearray([raw_ch_code & 0xFF, level & 0xFF])
        # 校准目标数据: 4字节大端整型 (按通道放大倍数换算后的原始整型值，与读浓度报文定义保持一致)
        factor = 1.0
        if self.channel_configs:
            for cfg in self.channel_configs:
                cfg_code = cfg.get("channel_code", 0)
                if cfg_code == channel_code or (channel_code < 10 and cfg_code % 10 == channel_code):
                    mag = cfg.get("magnification", 0)
                    factor = GasProtocol.get_magnification_factor(mag)
                    break

        raw_cal_data = int(round(float(cal_data) * factor))
        send_data.extend(raw_cal_data.to_bytes(4, byteorder='big', signed=True))
        # 校准AD: 4字节大端无符号整型
        send_data.extend(int(cal_ad).to_bytes(4, byteorder='big', signed=False))

        frame = GasProtocol.build_frame(self.short_addr, GAS_FUNC_CODE_OPERATE, GAS_CMD_OP_CALIBRATE, bytes(send_data))
        logger.info(f"🎯 [GasDriver ID={self.sensor_id}] 下发通道校准指令 -> 通道:{channel_code}(物理:{raw_ch_code}), 级别:{level}, 目标值:{float(cal_data):.2f}(原始整型:{raw_cal_data}), AD:{cal_ad}")
        payload = self._send_and_receive(frame, GAS_FUNC_CODE_OPERATE, GAS_CMD_OP_CALIBRATE)
        if payload:
            # 协议规范末字节为校准结果 (11字节规范应答末字节为操作结果)
            result_code = payload[-1]
            if result_code == GAS_RESULT_NORMAL:
                logger.info(f"✅ [GasDriver ID={self.sensor_id}] 通道 {channel_code} 校准成功")
                return True
            logger.error(f"❌ [GasDriver ID={self.sensor_id}] 通道 {channel_code} 校准异常代码: 0x{result_code:02X} (Payload: {payload.hex().upper()})")
        return False

    def factory_reset(self, channel_code: int = 0xFF, restore_flag: int = 0xFF) -> bool:
        """
        恢复出厂设置 (功能码 0x06, 命令字 0x02)
        符合协议文档 2.4.1 & 2.4.2 节:
        下发数据: 恢复出厂操作码 0x02(1B) + 通道编号(1B: 0x80以下设备通道, 0x80以上设备其它, 0xFF全部) + 恢复标志(1B: 0xFF全部恢复)
        应答数据: 通道编号(1B) + 恢复标志(1B) + 恢复结果(1B: 0x00成功) -> 规范总长 3 字节，结果在第 2 字节
        """
        send_data = bytes([GAS_CMD_OP_FACTORY_RESET, channel_code & 0xFF, restore_flag & 0xFF])
        frame = GasProtocol.build_frame(self.short_addr, GAS_FUNC_CODE_OPERATE, GAS_CMD_OP_FACTORY_RESET, send_data)
        logger.info(f"♻️ [GasDriver ID={self.sensor_id}] 下发恢复出厂设置指令 -> 通道:0x{channel_code:02X}, 标志:0x{restore_flag:02X}")
        payload = self._send_and_receive(frame, GAS_FUNC_CODE_OPERATE, GAS_CMD_OP_FACTORY_RESET)
        if payload and len(payload) >= 3:
            # 官方规范响应共 3 字节: [通道号, 恢复标志, 恢复结果]，结果在末字节
            result_code = payload[-1]
            if result_code == GAS_RESULT_NORMAL:
                logger.info(f"✅ [GasDriver ID={self.sensor_id}] 恢复出厂设置成功")
                return True
            else:
                logger.error(f"❌ [GasDriver ID={self.sensor_id}] 恢复出厂设置失败，异常代码: 0x{result_code:02X}")
        return False

    def disconnect(self):
        """安全关闭串口连接"""
        if self.serial_conn:
            try:
                if self.serial_conn.is_open:
                    self.serial_conn.close()
                logger.info(f"🛑 [GasDriver ID={self.sensor_id}] 已断开串口: {self.port}")
            except Exception as e:
                logger.debug(f"断开串口异常: {e}")
            finally:
                self.serial_conn = None
