import json
import socket
import threading
import logging
import time

# ==================== 日志配置 ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] [Arm-Sim] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("ArmSimulator")

class ArmSimulator:
    """
    工业级机械臂 TCP 硬件控制模拟器
    模拟底层机械臂的 TCP 闭环通讯行为:
    1. 接收网关 JSON 下发: {"action": "goto", "point": 0} / {"action": "pause"} / {"action": "goback"}
    2. 立刻回复 {"result": "start"}
    3. 模拟运动延迟后，回复 {"result": "success"}
    """
    def __init__(self, host='0.0.0.0', port=10020, motion_delay=0.5):
        self.host = host
        self.port = port
        self.motion_delay = motion_delay
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def handle_client(self, conn: socket.socket, addr):
        logger.info(f"🔗 接受来自网关的 TCP 连接: {addr}")
        buffer = ""
        try:
            while True:
                chunk = conn.recv(1024)
                if not chunk:
                    logger.info(f"💔 网关 {addr} 断开连接")
                    break

                buffer += chunk.decode('utf-8', errors='ignore')

                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    if not line:
                        continue

                    logger.info(f"📥 收到网关 JSON 报文: {line}")
                    try:
                        cmd = json.loads(line)
                        action = cmd.get("action")
                        point = cmd.get("point")

                        if action in ["goto", "pause", "goback"]:
                            logger.info(f"⚙️ 正在处理动作 [{action}] (点位: {point})")
                            # 1. 阶段 1: 立刻回复 start
                            start_resp = json.dumps({"result": "start"}) + "\n"
                            conn.sendall(start_resp.encode('utf-8'))
                            logger.info(f"📤 [阶段 1] 回复运动启动: {start_resp.strip()}")

                            # 2. 模拟机械臂运动执行过程
                            time.sleep(self.motion_delay)

                            # 3. 阶段 2: 回复 success
                            success_resp = json.dumps({"result": "success"}) + "\n"
                            conn.sendall(success_resp.encode('utf-8'))
                            logger.info(f"📤 [阶段 2] 回复到达目标点完成: {success_resp.strip()}")
                        else:
                            fail_resp = json.dumps({"result": "fail", "message": f"未知动作: {action}"}) + "\n"
                            conn.sendall(fail_resp.encode('utf-8'))
                            logger.warning(f"⚠️ 未知动作，回复失败: {fail_resp.strip()}")

                    except json.JSONDecodeError as e:
                        logger.error(f"❌ 解析下发 JSON 报文失败: {e}")
                        err_resp = json.dumps({"result": "fail", "message": "JSON 格式非法"}) + "\n"
                        conn.sendall(err_resp.encode('utf-8'))

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
        logger.info(f"🦾 机械臂 TCP 硬件模拟器已启动，监听 {self.host}:{self.port}")
        logger.info("=" * 60)

        try:
            while True:
                conn, addr = self.server_socket.accept()
                client_thread = threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True)
                client_thread.start()
        except KeyboardInterrupt:
            logger.info("\n🛑 收到退出信号，模拟器正在关闭...")
            self.server_socket.close()

def start_arm_simulator(host="0.0.0.0", port=10020):
    sim = ArmSimulator(host=host, port=port)
    sim.start()

if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 10020
    start_arm_simulator(port=port)
