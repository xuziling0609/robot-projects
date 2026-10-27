import os
import pty
import time
import struct
import copy
import random
import errno
import threading
import logging
from typing import List, Dict, Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] [Gas-Sim] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("GasSimulator")

# ============================================================================
# 协议常量定义 (严格与 gas_driver.py 及 传感器模组用户协议V1.00-20250427 对齐)
# ============================================================================

GAS_FRAME_HEADER          = 0x5A    # 协议帧头
GAS_FRAME_TAIL            = 0x5B    # 协议帧尾

# 功能码
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

# 系统状态位定义
GAS_STATUS_ALARM          = (1 << 0)  # Bit0: 报警
GAS_STATUS_PUMP_BLOCK     = (1 << 1)  # Bit1: 泵堵塞
GAS_STATUS_POWER_FAULT    = (1 << 2)  # Bit2: 电源故障


def calculate_crc16(data: bytes) -> int:
    """计算 Modbus CRC16 校验码 (多项式 0xA001, 初值 0xFFFF)"""
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def build_gas_response_frame(short_addr: int, func_code: int, cmd_code: int, payload: bytes = b'') -> bytes:
    """
    构建符合协议规范的标准响应帧:
    帧头(0x5A) + 长度(2B) + 帧标识(0x00) + 短地址(2B) + 功能码(1B) + 命令字(1B, 或上0x80) + 数据(N*B) + CRC(2B) + 帧尾(0x5B)
    """
    data_len = len(payload)
    crc_len = 1 + 2 + 1 + 1 + data_len + 2

    # 应答命令字标准必须或上 0x80 (cmd_code | 0x80)
    resp_cmd = (cmd_code | 0x80) if (cmd_code & 0x80) == 0 else cmd_code

    frame = bytearray()
    frame.append(GAS_FRAME_HEADER)
    frame.append((crc_len >> 8) & 0xFF)
    frame.append(crc_len & 0xFF)

    crc_payload = bytearray()
    crc_payload.append(0x00)  # 帧标识
    crc_payload.append((short_addr >> 8) & 0xFF)
    crc_payload.append(short_addr & 0xFF)
    crc_payload.append(func_code & 0xFF)
    crc_payload.append(resp_cmd & 0xFF)
    if payload:
        crc_payload.extend(payload)

    crc = calculate_crc16(bytes(crc_payload))
    crc_bytes = bytes([(crc >> 8) & 0xFF, crc & 0xFF])

    frame.extend(crc_payload)
    frame.extend(crc_bytes)
    frame.append(GAS_FRAME_TAIL)
    return bytes(frame)


# 默认 6合一 传感器通道模板 (通道号 1..6，严格对齐文档与 gas_driver.py)
DEFAULT_6IN1_CHANNELS = [
    {
        "channel_code": 1, "name": "CO",  "range": 1000.0, "magnification": 1, "unit": 0,
        "alarm_l1_raw": 500, "alarm_l2_raw": 1000, "alarm_l3_raw": 2000,
        "alarm_l1_hyst": 0, "alarm_l2_hyst": 0, "alarm_l3_hyst": 0,
        "alarm_l1_mode": 0, "alarm_l2_mode": 0, "alarm_l3_mode": 0, "alarm_kind": 0,
        "concentration_raw": 120, "alarm_status": 0, "raw_ad": 12000
    },
    {
        "channel_code": 2, "name": "H2S", "range": 100.0,  "magnification": 1, "unit": 0,
        "alarm_l1_raw": 100, "alarm_l2_raw": 200, "alarm_l3_raw": 500,
        "alarm_l1_hyst": 0, "alarm_l2_hyst": 0, "alarm_l3_hyst": 0,
        "alarm_l1_mode": 0, "alarm_l2_mode": 0, "alarm_l3_mode": 0, "alarm_kind": 0,
        "concentration_raw": 10, "alarm_status": 0, "raw_ad": 11000
    },
    {
        "channel_code": 3, "name": "O2",  "range": 30.0,   "magnification": 2, "unit": 1,
        "alarm_l1_raw": 1950, "alarm_l2_raw": 2350, "alarm_l3_raw": 2500,
        "alarm_l1_hyst": 0, "alarm_l2_hyst": 0, "alarm_l3_hyst": 0,
        "alarm_l1_mode": 0, "alarm_l2_mode": 0, "alarm_l3_mode": 0, "alarm_kind": 0,
        "concentration_raw": 2090, "alarm_status": 0, "raw_ad": 20900
    },
    {
        "channel_code": 4, "name": "EX",  "range": 100.0,  "magnification": 1, "unit": 2,
        "alarm_l1_raw": 250, "alarm_l2_raw": 500, "alarm_l3_raw": 750,
        "alarm_l1_hyst": 0, "alarm_l2_hyst": 0, "alarm_l3_hyst": 0,
        "alarm_l1_mode": 0, "alarm_l2_mode": 0, "alarm_l3_mode": 0, "alarm_kind": 0,
        "concentration_raw": 0, "alarm_status": 0, "raw_ad": 10000
    },
    {
        "channel_code": 5, "name": "CO2", "range": 5000.0, "magnification": 1, "unit": 0,
        "alarm_l1_raw": 10000, "alarm_l2_raw": 20000, "alarm_l3_raw": 30000,
        "alarm_l1_hyst": 0, "alarm_l2_hyst": 0, "alarm_l3_hyst": 0,
        "alarm_l1_mode": 0, "alarm_l2_mode": 0, "alarm_l3_mode": 0, "alarm_kind": 0,
        "concentration_raw": 4000, "alarm_status": 0, "raw_ad": 14000
    },
    {
        "channel_code": 6, "name": "NOX", "range": 100.0,  "magnification": 1, "unit": 0,
        "alarm_l1_raw": 200, "alarm_l2_raw": 400, "alarm_l3_raw": 600,
        "alarm_l1_hyst": 0, "alarm_l2_hyst": 0, "alarm_l3_hyst": 0,
        "alarm_l1_mode": 0, "alarm_l2_mode": 0, "alarm_l3_mode": 0, "alarm_kind": 0,
        "concentration_raw": 0, "alarm_status": 0, "raw_ad": 10500
    }
]

# 默认 1合一 传感器通道模板 (通道号 1)
DEFAULT_1IN1_CHANNELS = [
    {
        "channel_code": 1, "name": "SF6", "range": 1000.0, "magnification": 1, "unit": 0,
        "alarm_l1_raw": 500, "alarm_l2_raw": 1000, "alarm_l3_raw": 5000,
        "alarm_l1_hyst": 0, "alarm_l2_hyst": 0, "alarm_l3_hyst": 0,
        "alarm_l1_mode": 0, "alarm_l2_mode": 0, "alarm_l3_mode": 0, "alarm_kind": 0,
        "concentration_raw": 0, "alarm_status": 0, "raw_ad": 10000
    }
]


class SingleGasSensorSimulator:
    """单个气体传感器 POSIX PTY 伪终端模拟器 (支持完整通道参数、浓度动态模拟、标定及出厂重置)"""

    def __init__(self, sensor_name: str, port_symlink: str, channel_count: int = 6, channels: Optional[List[Dict[str, Any]]] = None):
        self.sensor_name = sensor_name
        self.port_symlink = port_symlink
        self.channel_count = channel_count
        self.master_fd = None
        self.slave_fd = None
        self.slave_name = None
        self.running = False

        # 气泵运行状态与参数
        self.pump_on = False
        self.flow_level = 5
        self.flow_rate = 0

        # 系统状态 (Bit0:报警, Bit1:泵堵塞, Bit2:电源故障)
        self.system_status = 0x00

        if channels:
            self.channels = [copy.deepcopy(ch) for ch in channels]
        elif channel_count == 6:
            self.channels = [copy.deepcopy(ch) for ch in DEFAULT_6IN1_CHANNELS]
        elif channel_count == 1:
            self.channels = [copy.deepcopy(ch) for ch in DEFAULT_1IN1_CHANNELS]
        else:
            self.channels = [
                {
                    "channel_code": i + 1, "name": f"GAS_{i+1}", "range": 1000.0, "magnification": 1, "unit": 0,
                    "alarm_l1_raw": 500, "alarm_l2_raw": 1000, "alarm_l3_raw": 2000,
                    "alarm_l1_hyst": 0, "alarm_l2_hyst": 0, "alarm_l3_hyst": 0,
                    "alarm_l1_mode": 0, "alarm_l2_mode": 0, "alarm_l3_mode": 0, "alarm_kind": 0,
                    "concentration_raw": 100, "alarm_status": 0, "raw_ad": 10000
                }
                for i in range(channel_count)
            ]

        self.initial_channels = copy.deepcopy(self.channels)

    def _setup_pty(self):
        self.master_fd, self.slave_fd = pty.openpty()
        self.slave_name = os.ttyname(self.slave_fd)

        if os.path.exists(self.port_symlink) or os.path.islink(self.port_symlink):
            try:
                os.remove(self.port_symlink)
            except Exception as e:
                logger.error('清理已存在软链接异常:', exc_info=True)
                pass
        try:
            os.symlink(self.slave_name, self.port_symlink)
            logger.info(f"🔗 [{self.sensor_name}] 已创建虚拟串口软链接: {self.port_symlink} -> {self.slave_name}")
        except Exception as e:
            logger.warning(f"⚠️ [{self.sensor_name}] 创建软链接失败: {e}")

    def _get_current_concentration_raw(self, ch: dict) -> int:
        """根据采样泵开启状态与微幅波动计算实时模拟浓度原始值"""
        base_conc = ch.get("concentration_raw", 0)
        if self.pump_on:
            jitter = random.randint(-2, 3)
            return max(0, base_conc + jitter)
        else:
            if ch.get("channel_code") in [3, 13] and ch.get("name") == "O2":
                return 2090  # 20.9% VOL
            elif ch.get("name") == "CO2":
                return 4000  # 400 PPM
            return max(0, min(base_conc, 5))

    def _calc_alarm_status(self, ch: dict, conc_raw: int) -> int:
        """根据当前浓度与三级报警阈值计算报警状态"""
        if conc_raw >= ch.get("alarm_l3_raw", 9999999):
            return 3
        elif conc_raw >= ch.get("alarm_l2_raw", 9999999):
            return 2
        elif conc_raw >= ch.get("alarm_l1_raw", 9999999):
            return 1
        return ch.get("alarm_status", 0)

    def _build_channel_info_block(self, ch: dict) -> bytes:
        """
        构建遵循官方文档 1.3.3 节与 gas_controller.c 规范的标准 80 字节通道参数数据块:
        通道编码(1B) + 名称(20B) + 量程(4B) + 放大倍数(1B) + 单位(1B) +
        一级报警(4B) + 一级回程(4B) + 一级模式(1B) +
        二级报警(4B) + 二级回程(4B) + 二级模式(1B) +
        三级报警(4B) + 三级回程(4B) + 三级模式(1B) +
        报警种类(1B) + 浓度(4B) + 报警状态(1B) + 原始AD(4B) + 保留(16B)
        """
        buf = bytearray()
        buf.append(ch["channel_code"] & 0xFF)

        name_bytes = ch["name"].encode('ascii', errors='ignore')[:20]
        buf.extend(name_bytes.ljust(20, b'\x00'))

        # 量程 4 字节 (标准 IEEE-754 浮点数，兼顾大端格式)
        buf.extend(struct.pack('>f', float(ch["range"])))
        buf.append(int(ch["magnification"]) & 0xFF)
        buf.append(int(ch["unit"]) & 0xFF)

        # 一级报警阈值(4B)、回程差(4B)、模式(1B)
        buf.extend(int(ch["alarm_l1_raw"]).to_bytes(4, byteorder='big', signed=True))
        buf.extend(int(ch.get("alarm_l1_hyst", 0)).to_bytes(4, byteorder='big', signed=True))
        buf.append(int(ch.get("alarm_l1_mode", 0)) & 0xFF)

        # 二级报警阈值(4B)、回程差(4B)、模式(1B)
        buf.extend(int(ch["alarm_l2_raw"]).to_bytes(4, byteorder='big', signed=True))
        buf.extend(int(ch.get("alarm_l2_hyst", 0)).to_bytes(4, byteorder='big', signed=True))
        buf.append(int(ch.get("alarm_l2_mode", 0)) & 0xFF)

        # 三级报警阈值(4B)、回程差(4B)、模式(1B)
        buf.extend(int(ch["alarm_l3_raw"]).to_bytes(4, byteorder='big', signed=True))
        buf.extend(int(ch.get("alarm_l3_hyst", 0)).to_bytes(4, byteorder='big', signed=True))
        buf.append(int(ch.get("alarm_l3_mode", 0)) & 0xFF)

        # 报警种类(1B)
        buf.append(int(ch.get("alarm_kind", 0)) & 0xFF)

        # 实时浓度(4B)
        conc_raw = self._get_current_concentration_raw(ch)
        buf.extend(conc_raw.to_bytes(4, byteorder='big', signed=True))

        # 报警状态(1B)
        alarm_st = self._calc_alarm_status(ch, conc_raw)
        buf.append(alarm_st & 0xFF)

        # 原始 AD 值(4B)
        buf.extend(int(ch.get("raw_ad", 10000)).to_bytes(4, byteorder='big', signed=False))

        # 保留区域(16B)
        buf.extend(b'\x00' * 16)
        return bytes(buf)

    def run(self):
        self._setup_pty()
        self.running = True

        logger.info(f"🧪 [{self.sensor_name}] 虚拟串口模拟服务就绪！串口: {self.port_symlink}")

        while self.running:
            try:
                data = os.read(self.master_fd, 1024)
                if not data:
                    time.sleep(0.1)
                    continue

                hex_str = data.hex(' ').upper()
                logger.info(f"📥 [{self.sensor_name}] 收到请求 ({len(data)} B): {hex_str}")

                if len(data) >= 8 and data[0] == GAS_FRAME_HEADER:
                    short_addr = (data[4] << 8) | data[5]
                    func_code = data[6]
                    cmd_code = data[7]
                    logger.info(f"  └─ [{self.sensor_name}] 帧解析 -> 短地址: 0x{short_addr:04X}, 功能码: 0x{func_code:02X}, 命令字: 0x{cmd_code:02X}")

                    # 1. 采样气泵控制 (命令 0x05 / 0x01)
                    if func_code == GAS_FUNC_CODE_CONTROL and cmd_code == GAS_CMD_CONTROL_PUMP:
                        req_payload = data[8:-3]
                        if len(req_payload) >= 1:
                            self.pump_on = (req_payload[0] == 0x01)
                        if len(req_payload) >= 2:
                            self.flow_level = req_payload[1]
                        if len(req_payload) >= 4:
                            self.flow_rate = (req_payload[2] << 8) | req_payload[3]

                        logger.info(f"  └─ 💨 气泵控制 -> 开关状态: {'开启' if self.pump_on else '关闭'}, 流量级别: {self.flow_level}, 速率: {self.flow_rate}")
                        # 官方规范响应: 结果正常(0x00) + 当前开关(1B) + 当前级别(1B) + 当前速率(2B) = 5字节
                        resp_payload = bytes([
                            GAS_RESULT_NORMAL,
                            0x01 if self.pump_on else 0x00,
                            self.flow_level & 0xFF,
                            (self.flow_rate >> 8) & 0xFF,
                            self.flow_rate & 0xFF
                        ])
                        resp = build_gas_response_frame(short_addr, GAS_FUNC_CODE_CONTROL, GAS_CMD_CONTROL_PUMP, resp_payload)
                        os.write(self.master_fd, resp)

                    # 2. 读取设备通道完整参数信息 (命令 0x01 / 0x02) - 80 字节/通道
                    elif func_code == GAS_FUNC_CODE_READ and cmd_code == GAS_CMD_READ_CHANNEL_INFO:
                        req_payload = data[8:-3]
                        if len(req_payload) >= 1:
                            ch_count_req = req_payload[0]
                            req_ch_codes = list(req_payload[1:1 + ch_count_req])
                        else:
                            req_ch_codes = []

                        if not req_ch_codes:
                            target_channels = self.channels
                        else:
                            # 兼容物理通道与虚拟通道编码
                            target_channels = []
                            for ch in self.channels:
                                c = ch["channel_code"]
                                if c in req_ch_codes or (c + 10) in req_ch_codes or (c + 20) in req_ch_codes:
                                    target_channels.append(ch)
                            if not target_channels:
                                target_channels = self.channels

                        logger.info(f"  └─ 📋 通道参数读取 -> 返回 {len(target_channels)} 通道 80 字节完整结构信息")
                        payload = bytearray([self.system_status, len(target_channels)])
                        for ch in target_channels:
                            payload.extend(self._build_channel_info_block(ch))
                        resp = build_gas_response_frame(short_addr, GAS_FUNC_CODE_READ, GAS_CMD_READ_CHANNEL_INFO, bytes(payload))
                        os.write(self.master_fd, resp)

                    # 3. 读取实时浓度数据包 (命令 0x01 / 0x03) - 10 字节/通道
                    elif func_code == GAS_FUNC_CODE_READ and cmd_code == GAS_CMD_READ_CONCENTRATION:
                        req_payload = data[8:-3]
                        if len(req_payload) >= 1:
                            ch_count_req = req_payload[0]
                            req_ch_codes = list(req_payload[1:1 + ch_count_req])
                        else:
                            req_ch_codes = []

                        if not req_ch_codes:
                            target_channels = self.channels
                        else:
                            target_channels = []
                            for ch in self.channels:
                                c = ch["channel_code"]
                                if c in req_ch_codes or (c + 10) in req_ch_codes or (c + 20) in req_ch_codes:
                                    target_channels.append(ch)
                            if not target_channels:
                                target_channels = self.channels

                        logger.info(f"  └─ 📊 实时浓度读取 -> 返回 {len(target_channels)} 通道浓度数据 (气泵状态: {'开启' if self.pump_on else '关闭'})")
                        payload = bytearray([self.system_status, len(target_channels)])
                        for ch in target_channels:
                            payload.append(ch["channel_code"])
                            conc_raw = self._get_current_concentration_raw(ch)
                            payload.extend(conc_raw.to_bytes(4, byteorder='big', signed=True))
                            alarm_st = self._calc_alarm_status(ch, conc_raw)
                            payload.append(alarm_st & 0xFF)
                            payload.extend(int(ch.get("raw_ad", 10000)).to_bytes(4, byteorder='big', signed=False))

                        resp = build_gas_response_frame(short_addr, GAS_FUNC_CODE_READ, GAS_CMD_READ_CONCENTRATION, bytes(payload))
                        os.write(self.master_fd, resp)

                    # 4. 读取设备基本信息 (命令 0x01 / 0x01)
                    elif func_code == GAS_FUNC_CODE_READ and cmd_code == GAS_CMD_READ_BASE_INFO:
                        logger.info(f"  └─ ℹ️ 设备基本信息读取 -> 短地址: 0x{short_addr:04X}, 通道数: {len(self.channels)}")
                        payload = bytearray([len(self.channels), len(self.channels)])
                        payload.extend(bytes.fromhex("1234567890ABCDEF12345678"))  # 12B UID
                        # 厂家、硬件版本、软件版本严格各为 20 字节 ASCII
                        payload.extend(b"M-B6 Gas Sensor".ljust(20, b'\x00'))
                        payload.extend(b"HW_1.0".ljust(20, b'\x00'))
                        payload.extend(b"SW_1.0".ljust(20, b'\x00'))
                        payload.extend((1700000000).to_bytes(4, byteorder='big'))  # 4B 出厂时间戳
                        resp = build_gas_response_frame(short_addr, GAS_FUNC_CODE_READ, GAS_CMD_READ_BASE_INFO, bytes(payload))
                        os.write(self.master_fd, resp)

                    # 5. 通道标定校准 (命令 0x06 / 0x01)
                    elif func_code == GAS_FUNC_CODE_OPERATE and cmd_code == GAS_CMD_OP_CALIBRATE:
                        req_payload = data[8:-3]
                        # 兼容 10 字节规范请求 [ch_code, level, float(4B), ad(4B)] 与 11 字节带操作码请求 [0x01, ch_code, level, ...]
                        offset = 1 if (len(req_payload) >= 11 and req_payload[0] == GAS_CMD_OP_CALIBRATE) else 0
                        ch_code = req_payload[offset] if len(req_payload) > offset else 1
                        level = req_payload[offset + 1] if len(req_payload) > offset + 1 else 0

                        raw_bytes = req_payload[offset+2:offset+6] if len(req_payload) >= offset + 6 else b'\x00\x00\x00\x00'
                        cal_data_raw = int.from_bytes(raw_bytes, byteorder='big', signed=True)
                        cal_data_float = 0.0

                        for ch in self.channels:
                            if ch["channel_code"] == ch_code or ch["channel_code"] == (ch_code % 10):
                                mag = ch.get("magnification", 1)
                                factor = 10.0 if mag == 1 else (100.0 if mag == 2 else (1000.0 if mag == 3 else 1.0))
                                # 优先按放大倍数整型解析；若为极大值则尝试按 IEEE 754 float 解析
                                if abs(cal_data_raw) > 1000000:
                                    try:
                                        cal_data_float = struct.unpack('>f', raw_bytes)[0]
                                        raw_target = int(cal_data_float * factor)
                                    except Exception:
                                        raw_target = cal_data_raw
                                        cal_data_float = float(cal_data_raw) / factor
                                else:
                                    raw_target = cal_data_raw
                                    cal_data_float = float(cal_data_raw) / factor

                                if level == 0:
                                    ch["concentration_raw"] = raw_target
                                    ch["raw_ad"] = cal_ad
                                elif level == 1:
                                    ch["alarm_l1_raw"] = raw_target
                                elif level == 2:
                                    ch["alarm_l2_raw"] = raw_target

                        cal_ad = int.from_bytes(req_payload[offset+6:offset+10], byteorder='big', signed=False) if len(req_payload) >= offset + 10 else 10000
                        logger.info(f"  └─ 🎯 通道标定 -> 通道:{ch_code}, 级别:{level}, 目标值:{cal_data_float:.2f}, AD:{cal_ad}")

                        # 官方规范应答共 11 字节: [ch_code, level, cal_data(4B), cal_ad(4B), 结果0x00(1B)]
                        resp_payload = bytearray([ch_code, level])
                        resp_payload.extend(raw_bytes)
                        resp_payload.extend(cal_ad.to_bytes(4, byteorder='big', signed=False))
                        resp_payload.append(GAS_RESULT_NORMAL)  # 末字节为操作结果 0x00

                        resp = build_gas_response_frame(short_addr, GAS_FUNC_CODE_OPERATE, GAS_CMD_OP_CALIBRATE, bytes(resp_payload))
                        os.write(self.master_fd, resp)

                    # 6. 恢复出厂设置 (命令 0x06 / 0x02)
                    elif func_code == GAS_FUNC_CODE_OPERATE and cmd_code == GAS_CMD_OP_FACTORY_RESET:
                        req_payload = data[8:-3]
                        # 请求数据: [0x02, ch_code, restore_flag]
                        ch_code = req_payload[1] if len(req_payload) > 1 else 0xFF
                        restore_flag = req_payload[2] if len(req_payload) > 2 else 0xFF

                        logger.info(f"  └─ ♻️ 恢复出厂设置 -> 通道:0x{ch_code:02X}, 标志:0x{restore_flag:02X}")
                        if ch_code == 0xFF:
                            self.channels = copy.deepcopy(self.initial_channels)
                        else:
                            for idx, ch in enumerate(self.channels):
                                if ch["channel_code"] == ch_code and idx < len(self.initial_channels):
                                    self.channels[idx] = copy.deepcopy(self.initial_channels[idx])

                        # 官方规范应答共 3 字节: [通道号(1B), 恢复标志(1B), 恢复结果0x00(1B)]
                        resp_payload = bytes([ch_code & 0xFF, restore_flag & 0xFF, GAS_RESULT_NORMAL])
                        resp = build_gas_response_frame(short_addr, GAS_FUNC_CODE_OPERATE, GAS_CMD_OP_FACTORY_RESET, resp_payload)
                        os.write(self.master_fd, resp)

                    else:
                        resp = build_gas_response_frame(short_addr, func_code, cmd_code, bytes([GAS_RESULT_NORMAL]))
                        os.write(self.master_fd, resp)

                elif len(data) >= 6 and data[0] == GAS_FRAME_HEADER:
                    func_code = data[3] if len(data) > 3 else 0x01
                    resp = build_gas_response_frame(GAS_DEFAULT_SHORT_ADDR, func_code, 0x01, bytes([GAS_RESULT_NORMAL]))
                    os.write(self.master_fd, resp)

            except OSError as e:
                if e.errno == errno.EIO:
                    time.sleep(0.2)
                else:
                    logger.debug(f"[{self.sensor_name}] PTY 读取异常: {e}")
                    time.sleep(0.2)
            except Exception as e:
                logger.error(f"❌ [{self.sensor_name}] 运行异常: {e}")
                time.sleep(0.5)

    def set_channel_concentration(self, channel_code: int, concentration_raw: int) -> bool:
        """设置模拟通道当前浓度原始值"""
        for ch in self.channels:
            if ch["channel_code"] == channel_code:
                ch["concentration_raw"] = concentration_raw
                return True
        return False

    def set_system_status(self, alarm: bool = False, pump_block: bool = False, power_fault: bool = False):
        """设置模拟器的系统状态字"""
        st = 0
        if alarm:
            st |= GAS_STATUS_ALARM
        if pump_block:
            st |= GAS_STATUS_PUMP_BLOCK
        if power_fault:
            st |= GAS_STATUS_POWER_FAULT
        self.system_status = st
        logger.info(f"⚡ [{self.sensor_name}] 系统状态更新为: 0x{st:02X} (报警={alarm}, 泵堵塞={pump_block}, 电源故障={power_fault})")

    def stop(self):
        self.running = False
        if self.master_fd:
            try:
                os.close(self.master_fd)
            except Exception as e:
                logger.error('关闭 master_fd 异常:', exc_info=True)
                pass
        if self.slave_fd:
            try:
                os.close(self.slave_fd)
            except Exception as e:
                logger.error('关闭 slave_fd 异常:', exc_info=True)
                pass
        if os.path.islink(self.port_symlink):
            try:
                os.remove(self.port_symlink)
            except Exception as e:
                logger.error('清理软链接异常:', exc_info=True)
                pass


class DualGasSimulator:
    """双串口气体检测模拟器（包含六合一与一合一双传感器）"""

    def __init__(self, port0: str = "/tmp/tty_gas_sim0", port1: str = "/tmp/tty_gas_sim1"):
        self.sim0 = SingleGasSensorSimulator("6合一气体检测模组", port0, channel_count=6)
        self.sim1 = SingleGasSensorSimulator("1合一气体传感器", port1, channel_count=1)

    def start(self):
        logger.info("=" * 70)
        logger.info("🧪 双串口气体检测模拟器 (6合一 + 1合一) 启动中...")
        logger.info(f"  └─ 串口 1 (6合一): {self.sim0.port_symlink}")
        logger.info(f"  └─ 串口 2 (1合一): {self.sim1.port_symlink}")
        logger.info("=" * 70)

        t0 = threading.Thread(target=self.sim0.run, daemon=True)
        t1 = threading.Thread(target=self.sim1.run, daemon=True)
        t0.start()
        t1.start()

        main_symlink = "/tmp/tty_gas_sim"
        if os.path.exists(main_symlink) or os.path.islink(main_symlink):
            try:
                os.remove(main_symlink)
            except Exception as e:
                logger.error('清理主软链接异常:', exc_info=True)
                pass
        try:
            os.symlink(self.sim0.port_symlink, main_symlink)
        except Exception as e:
            logger.error('创建主软链接异常:', exc_info=True)
            pass

        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.sim0.stop()
        self.sim1.stop()


GasSimulator = DualGasSimulator


def start_gas_simulator(port0: str = "/tmp/tty_gas_sim0", port1: str = "/tmp/tty_gas_sim1"):
    sim = DualGasSimulator(port0, port1)
    sim.start()


if __name__ == "__main__":
    start_gas_simulator()
