import socket
import threading
import time
import logging

# ==================== 日志配置 ====================
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] [Door-Sim] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("Simulator")


class DoorSimulator:
    """单个开门机对象，维护独立的状态与 10s 运动逻辑"""
    def __init__(self, client_id):
        self.client_id = client_id
        
        # 门状态定义:
        # 0x0000: 关到位
        # 0x0001: 中间位
        # 0x0002: 开到位
        self.door_status = 0x0000  # 默认初始为“关到位”
        
        self.status_lock = threading.Lock()
        self.current_timer = None  # 用于记录当前的延时定时器

    def calculate_crc16(self, data: bytes) -> bytes:
        """计算 Modbus RTU CRC16 校验码"""
        crc = 0xFFFF
        for pos in data:
            crc ^= pos
            for _ in range(8):
                if (crc & 1) != 0:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return crc.to_bytes(2, byteorder='little')

    def _cancel_current_action(self):
        """如果在运动过程中收到新指令，先取消正在运行的计时器"""
        if self.current_timer and self.current_timer.is_alive():
            self.current_timer.cancel()

    def _finish_motion(self, target_status: int, status_name: str):
        """10s 到期后调用的回调函数"""
        with self.status_lock:
            self.door_status = target_status
            logger.info(f"[门 #{self.client_id}] >> 运动完成，状态到达：【{status_name}】")

    def start_motion(self, target_status: int, action_name: str, target_name: str):
        """启动 10s 的开门/关门动作"""
        with self.status_lock:
            self._cancel_current_action()
            # 运动开始，立即进入中间位
            self.door_status = 0x0001 
            logger.info(f"[门 #{self.client_id}] >> 开始执行{action_name}（耗时 10s），当前状态切换为：【中间位】")

        # 开启定时器，10s 后将状态变为目标状态（开到位/关到位）
        self.current_timer = threading.Timer(10.0, self._finish_motion, args=(target_status, target_name))
        self.current_timer.start()

    def stop_motion(self):
        """执行停止动作"""
        with self.status_lock:
            self._cancel_current_action()
            self.door_status = 0x0001  # 停止在中间位
            logger.info(f"[门 #{self.client_id}] >> 执行停止，当前状态维持在：【中间位】")

    def handle_command(self, frame: bytes) -> bytes:
        if len(frame) < 8:
            return b""
            
        addr = frame[0]
        func = frame[1]
        
        if addr != 1:  # 协议从站地址为 1
            return b""

        # 03 功能码：查询门状态
        if func == 0x03:
            with self.status_lock:
                current_status = self.door_status
            data_val = current_status.to_bytes(2, byteorder='big')
            resp_body = bytes([addr, 0x03, 0x02]) + data_val
            crc = self.calculate_crc16(resp_body)
            return resp_body + crc
            
        # 06 功能码：控制开门、关门、停止
        elif func == 0x06:
            reg_val = int.from_bytes(frame[4:6], byteorder='big')
            action_success = True
            
            if reg_val == 0x0001:
                # 收到开门指令：经过 10s 变更为开到位 (0x0002)
                self.start_motion(target_status=0x0002, action_name="开门", target_name="开到位")
            elif reg_val == 0x0002:
                # 收到关门指令：经过 10s 变更为关到位 (0x0000)
                self.start_motion(target_status=0x0000, action_name="关门", target_name="关到位")
            elif reg_val == 0x0003:
                # 收到停止指令：保持在中间位 (0x0001)
                self.stop_motion()
            else:
                action_success = False

            # 返回应答帧
            if action_success:
                return bytes([0x01, 0x06, 0x00, 0x00, 0x00, 0x00, 0x89, 0xCA])
            else:
                return bytes([0x01, 0x06, 0x00, 0x00, 0x00, 0x01, 0x48, 0x0A])
                
        return b""


class StationSimulatorServer:
    """与 stationSimulator.py 风格一致的工业设备模拟器服务端"""
    def __init__(self, host='0.0.0.0', port=10021):
        self.host = host
        self.port = port
        self.client_counter = 0

    def handle_client(self, client_sock, client_addr):
        self.client_counter += 1
        door_id = self.client_counter
        door = DoorSimulator(client_id=door_id)
        
        logger.info(f"[-] 客户端 {client_addr} 已连接，成功分配 [门 #{door_id}] 实例")
        
        try:
            while True:
                data = client_sock.recv(1024)
                if not data:
                    break
                
                logger.debug(f"[门 #{door_id}] 收到指令 (Hex): {data.hex().upper()}")
                response = door.handle_command(data)
                
                if response:
                    client_sock.sendall(response)
                    logger.debug(f"[门 #{door_id}] 响应数据 (Hex): {response.hex().upper()}")
        except ConnectionResetError:
            pass
        finally:
            client_sock.close()
            logger.info(f"[x] 客户端 {client_addr} 断开连接，[门 #{door_id}] 实例已被清理")

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        
        logger.info("=" * 50)
        logger.info(f"🚀 T开门机 硬件模拟器已启动，监听 {self.host}:{self.port}")
        logger.info("=" * 50)

        try:
            while True:
                client_sock, client_addr = self.server_socket.accept()
                threading.Thread(
                    target=self.handle_client, 
                    args=(client_sock, client_addr), 
                    daemon=True
                ).start()
        except KeyboardInterrupt:
            logger.info("\n服务端程序优雅退出。")
        finally:
            self.server_socket.close()

def start_door_simulator(host="0.0.0.0", port=10021):
    sim = StationSimulatorServer(host=host, port=port)
    sim.start()

if __name__ == "__main__":
    start_door_simulator()