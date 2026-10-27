import os
import pty
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] [Gdpd-Sim] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("GdpdSimulator")

def calculate_modbus_crc16(data: bytes) -> bytes:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return bytes([crc & 0xFF, (crc >> 8) & 0xFF])

class GdpdSimulator:
    """
    局放采集模组 (TEV/UHF) RS485 Modbus RTU 虚拟串口模拟器
    默认虚拟串口路径: /tmp/tty_gdpd_sim
    """

    def __init__(self, port_symlink: str = "/tmp/tty_gdpd_sim"):
        self.port_symlink = port_symlink
        self.master_fd = None
        self.slave_fd = None
        self.slave_name = None
        self.running = False
        self.sample_count = 0

    def _setup_pty(self):
        self.master_fd, self.slave_fd = pty.openpty()
        self.slave_name = os.ttyname(self.slave_fd)

        if os.path.exists(self.port_symlink) or os.path.islink(self.port_symlink):
            try:
                os.remove(self.port_symlink)
            except Exception as e:
                logger.error('操作引发异常:', exc_info=True)
                pass
        try:
            os.symlink(self.slave_name, self.port_symlink)
            logger.info(f"🔗 已创建虚拟局放串口软链接: {self.port_symlink} -> {self.slave_name}")
        except Exception as e:
            logger.warning(f"⚠️ 创建软链接失败，请直接使用 pts 路径 [{self.slave_name}]: {e}")

    def start(self):
        self._setup_pty()
        self.running = True

        logger.info("=" * 60)
        logger.info(f"⚡ 局放检测模组 RS485 虚拟串口模拟器已启动！")
        logger.info(f"📡 虚拟串口路径: {self.port_symlink} ({self.slave_name})")
        logger.info("=" * 60)

        try:
            while self.running:
                data = os.read(self.master_fd, 1024)
                if not data:
                    break

                hex_str = data.hex(' ').upper()
                logger.info(f"📥 [GdpdSimulator 串口] 收到 Modbus RTU 报文 ({len(data)} B): {hex_str}")

                if len(data) >= 6:
                    if b"\x55\x55" in data:
                        resp = b"\x02\x04\x02\x55\x55\x02\x5F"
                        logger.info("  └─ 🚀 响应启动采集 (START_RET)")
                    elif b"\xAA\xAA" in data:
                        resp = b"\x02\x04\x02\xAA\xAA\x03\xEF"
                        logger.info("  └─ 🛑 响应停止采集 (STOP_RET)")
                    elif b"\x01\x0C" in data:
                        resp = b"\x02\x06\x01\x0C\x00\x00\x48\x06"
                        logger.info("  └─ 🔄 响应频次清零 (FREQ_CLR_RET)")
                    else:
                        self.sample_count += 1
                        sim_peak = 15.0 + (self.sample_count % 5) * 2.0
                        sim_avg = 10.0 + (self.sample_count % 3) * 1.5
                        sim_freq = 50 + (self.sample_count % 10) * 5

                        peak_raw = int(sim_peak * 10)
                        avg_raw = int(sim_avg * 10)
                        freq_raw = int(sim_freq)
                        total_raw = self.sample_count * 10

                        payload = bytes([
                            0x02, 0x04, 0x08,
                            (peak_raw >> 8) & 0xFF, peak_raw & 0xFF,
                            (avg_raw >> 8) & 0xFF, avg_raw & 0xFF,
                            (freq_raw >> 8) & 0xFF, freq_raw & 0xFF,
                            (total_raw >> 8) & 0xFF, total_raw & 0xFF
                        ])
                        resp = payload + calculate_modbus_crc16(payload)
                        logger.info(f"  └─ 📊 响应 Modbus 采集数据 -> 峰值:{sim_peak} dBm, 平均:{sim_avg} dBm, 频次:{sim_freq}")

                    os.write(self.master_fd, resp)
        except OSError:
            pass
        except Exception as e:
            logger.error(f"❌ 虚拟局放串口运行异常: {e}")
        finally:
            self.stop()

    def stop(self):
        self.running = False
        if self.master_fd:
            try:
                os.close(self.master_fd)
            except Exception as e:
                logger.error('操作引发异常:', exc_info=True)
                pass
        if self.slave_fd:
            try:
                os.close(self.slave_fd)
            except Exception as e:
                logger.error('操作引发异常:', exc_info=True)
                pass
        if os.path.islink(self.port_symlink):
            try:
                os.remove(self.port_symlink)
            except Exception as e:
                logger.error('操作引发异常:', exc_info=True)
                pass

def start_gdpd_simulator(port_symlink: str = "/tmp/tty_gdpd_sim"):
    sim = GdpdSimulator(port_symlink=port_symlink)
    sim.start()

if __name__ == "__main__":
    start_gdpd_simulator()
