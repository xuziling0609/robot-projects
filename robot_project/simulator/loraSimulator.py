import socket
import threading
import time
import logging

# ==================== 日志配置 ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] [Lora-Sim] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("LoraSimulator")

class LoraSimulator:
    """LoRa 硬件网关 TCP 模拟器 (默认端口: 10024)"""
    def __init__(self, host: str = "0.0.0.0", port: int = 10024):
        self.host = host
        self.port = port
        self.running = False
        self.server_sock = None
        self.clients = []
        self.clients_lock = threading.Lock()

    def _broadcast(self, data: bytes, exclude_sock: socket.socket = None):
        """将数据广播转发给所有其他已连接的客户端 (实现中继透传)"""
        with self.clients_lock:
            targets = [c for c in self.clients if c != exclude_sock]
        for c in targets:
            try:
                c.sendall(data)
            except Exception as e:
                logger.warning(f"⚠️ [LoraSimulator] 转发数据到客户端失败: {e}")

    def start(self):
        self.running = True
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(5)

        logger.info("=" * 70)
        logger.info(f"📡 LoRa 网关 TCP 模拟器启动中... 监听: {self.host}:{self.port}")
        logger.info("=" * 70)

        threading.Thread(target=self._heartbeat_sender_loop, daemon=True).start()

        try:
            while self.running:
                sock, addr = self.server_sock.accept()
                logger.info(f"🔌 [LoraSimulator] 客户端已连接: {addr}")
                with self.clients_lock:
                    self.clients.append(sock)
                threading.Thread(target=self._client_handler, args=(sock, addr), daemon=True).start()
        except KeyboardInterrupt:
            logger.info("🛑 LoRa 模拟器正在关闭...")
        finally:
            self.stop()

    def _client_handler(self, sock: socket.socket, addr):
        try:
            while self.running:
                data = sock.recv(1024)
                if not data:
                    break
                
                hex_str = data.hex(' ')
                logger.info(f"📥 [LoraSimulator] 收到来自 {addr} 的数据 ({len(data)} B): {hex_str}")

                # 1. 识别 0xC5 0xC5 状态上报报文 (Header: 0xC5 0xC5 ... End: 0x0D 0x0A)
                if len(data) >= 2 and data[0] == 0xC5 and data[1] == 0xC5:
                    try:
                        text = data[2:].rstrip(b'\r\n').decode('utf-8', errors='ignore')
                        logger.info(f"  └─ 📊 收到机器人状态上报数据: {text}")
                    except Exception as e:
                        logger.error('操作引发异常:', exc_info=True)
                    # 将状态上报报文广播转发给所有其他客户端 (如调试助手)
                    self._broadcast(data, exclude_sock=sock)
                    logger.info("  └─ 📢 已将状态上报报文广播转发给其他客户端")

                else:
                    # 尝试按字符串解析并转发
                    try:
                        text = data.decode('utf-8', errors='ignore').strip()
                        logger.info(f"  └─ 📄 文本/JSON 内容: {text}")
                    except Exception as e:
                        logger.error('操作引发异常:', exc_info=True)
                    self._broadcast(data, exclude_sock=sock)
        except Exception as e:
            logger.warning(f"⚠️ [LoraSimulator] 客户端 {addr} 异常断开: {e}")
        finally:
            with self.clients_lock:
                if sock in self.clients:
                    self.clients.remove(sock)
            try:
                sock.close()
            except Exception:
                pass
            logger.info(f"🔒 [LoraSimulator] 客户端 {addr} 连接已释放")

    def _heartbeat_sender_loop(self):
        """定期向所有已连接的客户端发送 LoRa 触发报文 (0xA0 0x50)"""
        while self.running:
            time.sleep(15.0)
            with self.clients_lock:
                targets = list(self.clients)
            if targets:
                trigger_pkt = bytes([0xA4, 0x54, 0xCB, 0xCE, 0xE5, 0xD1, 0x0D, 0x0A])
                for c in targets:
                    try:
                        c.sendall(trigger_pkt)
                    except Exception as e:
                        logger.error('操作引发异常:', exc_info=True)
                        pass

    def stop(self):
        self.running = False
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception as e:
                logger.error('操作引发异常:', exc_info=True)
        with self.clients_lock:
            targets = list(self.clients)
            self.clients.clear()
        for c in targets:
            try:
                c.close()
            except Exception as e:
                logger.error('操作引发异常:', exc_info=True)

def start_lora_simulator(host="0.0.0.0", port=10024):
    sim = LoraSimulator(host, port)
    sim.start()

if __name__ == "__main__":
    start_lora_simulator()
