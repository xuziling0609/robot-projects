import socket
import threading
import logging
import time

# ==================== 日志配置 ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] [Station-Sim] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("StationSimulator")

# ==================== Tasio211 协议报文映射 ====================
# 收到的指令
CMD_READ_STATE   = bytes.fromhex("11 01 00 00 00 02 BF 5B")
CMD_MULTI_CLOSE  = bytes.fromhex("11 0F 00 00 00 02 01 00 DF 9B")
CMD_DO1_JOG_OPEN = bytes.fromhex("11 10 96 04 00 03 06 02 00 00 FF 01 00 4A 0D")
CMD_DO2_JOG_CLOSE= bytes.fromhex("11 10 96 08 00 03 06 02 00 00 FF 01 00 8A 32")

# 对应的标准成功回包
RESP_STATE_OK    = bytes.fromhex("11 01 01 00 55 48")
RESP_MULTI_CLOSE = bytes.fromhex("11 0F 00 00 00 02 D6 9A")
RESP_DO1_OK      = bytes.fromhex("11 10 96 04 00 03 EE D1")
RESP_DO2_OK      = bytes.fromhex("11 10 96 08 00 03 2E D2")

# 模拟设备的错误状态（用于测试 Driver 中的 MULTI_CLOSE 复位逻辑）
RESP_STATE_DIRTY = bytes.fromhex("11 01 01 00 55 48") # 状态异常报文

class StationSimulator:
    """充电站 Tasio211 DO 继电器硬件控制模拟器"""
    def __init__(self, host='0.0.0.0', port=10022):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # 状态机：默认启动时设为 True，测试先多路关闭复位逻辑
        self.is_dirty = True

    def handle_client(self, conn, addr):
        logger.info(f"🔗 接受来自网关的 TCP 连接: {addr}")
        try:
            while True:
                data = conn.recv(1024)
                if not data:
                    logger.info(f"💔 网关 {addr} 主动断开了连接")
                    break
                
                hex_data = data.hex(" ").upper()
                logger.debug(f"📥 收到指令: {hex_data}")
                
                response = b''
                
                if data == CMD_READ_STATE:
                    if self.is_dirty:
                        logger.warning("-> 模拟器处于脏状态，返回不匹配的状态报文，触发网关复位逻辑")
                        response = RESP_STATE_DIRTY
                    else:
                        logger.info("-> 收到状态查询，返回状态匹配 [OK]")
                        response = RESP_STATE_OK
                        
                elif data == CMD_MULTI_CLOSE:
                    logger.info("-> 收到多路关闭指令，清理设备状态 [OK]")
                    self.is_dirty = False
                    response = RESP_MULTI_CLOSE
                    
                elif data == CMD_DO1_JOG_OPEN:
                    logger.info("-> 收到 DO1 点动开门指令 [OK]")
                    response = RESP_DO1_OK
                    
                elif data == CMD_DO2_JOG_CLOSE:
                    logger.info("-> 收到 DO2 点动关门指令 [OK]")
                    response = RESP_DO2_OK
                    
                else:
                    logger.error(f"-> 收到未知指令: {hex_data}")
                    continue

                time.sleep(0.05)
                conn.sendall(response)
                logger.debug(f"📤 返回报文: {response.hex(' ').upper()}")

        except socket.timeout:
            logger.warning(f"⌛ 连接 {addr} 空闲超时")
        except ConnectionResetError:
            logger.warning(f"💥 连接 {addr} 被强制重置")
        except Exception as e:
            logger.error(f"❌ 处理连接时发生异常: {e}")
        finally:
            conn.close()

    def start(self):
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        logger.info("=" * 60)
        logger.info(f"🔌 充电站 Tasio211 继电器模拟器已启动，监听 {self.host}:{self.port}")
        logger.info("=" * 60)

        try:
            while True:
                conn, addr = self.server_socket.accept()
                client_thread = threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True)
                client_thread.start()
        except KeyboardInterrupt:
            logger.info("\n🛑 收到退出信号，模拟器正在关闭...")
            self.server_socket.close()

# 兼容别名导出
Tasio211Simulator = StationSimulator

def start_station_simulator(host="0.0.0.0", port=10022):
    sim = StationSimulator(host=host, port=port)
    sim.start()

if __name__ == "__main__":
    start_station_simulator()