import socket
import threading
import struct
import time
import logging

# ==================== 日志配置 ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] [Elevator-Sim] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("ElevatorSimulator")

class ElevatorSimulator:
    """云迹 LoRa 梯控 TCP 模拟器 (默认端口: 10023)"""

    def __init__(self, host: str = "0.0.0.0", port: int = 10023):
        self.host = host
        self.port = port
        self.running = False
        self.server_sock = None

    def start(self):
        self.running = True
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(5)

        logger.info("=" * 70)
        logger.info(f"🛗 云迹梯控 TCP 模拟器启动... 监听: {self.host}:{self.port}")
        logger.info("=" * 70)

        try:
            while self.running:
                sock, addr = self.server_sock.accept()
                logger.info(f"🔌 [ElevatorSimulator] 客户端连接: {addr}")
                threading.Thread(target=self._handle_client, args=(sock, addr), daemon=True).start()
        except KeyboardInterrupt:
            logger.info("🛑 梯控模拟器停止")
        finally:
            self.stop()

    def _handle_client(self, sock: socket.socket, addr):
        try:
            while self.running:
                data = sock.recv(1024)
                if not data:
                    break

                hex_str = data.hex(' ')
                logger.info(f"📥 [ElevatorSimulator] 收到帧数据 ({len(data)} B): {hex_str}")

                if data.startswith(b'\x7F\xF7') and len(data) >= 8:
                    cmd_byte = data[13] if len(data) > 13 else 0x00
                    logger.info(f"  └─ 🛗 梯控指令解析 -> Cmd Code: 0x{cmd_byte:02X}")
                    
                    # 组装成功 Ack 帧响应
                    ack_frame = b'\x7F\xF7\x0A\x29\x47\x0F\x11\x22\x33\x44\x55\x66\x01\x00\x00\x00'
                    sock.sendall(ack_frame)
                    logger.info("  └─ 📤 发送梯控 Ack 成功帧")
        except Exception as e:
            logger.warning(f"⚠️ [ElevatorSimulator] 客户端 {addr} 错误: {e}")
        finally:
            sock.close()

    def stop(self):
        self.running = False
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception as e:
                logger.error('操作引发异常:', exc_info=True)
                pass

def start_elevator_simulator(host="0.0.0.0", port=10023):
    sim = ElevatorSimulator(host, port)
    sim.start()

if __name__ == "__main__":
    start_elevator_simulator()
