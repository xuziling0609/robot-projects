import requests
import socket
import struct
import threading
import time
from core.logger_manager import get_logger
from core.tcp_manager import TCPManager

logger = get_logger("AcousticDriver")

class AcousticDriver:
    def __init__(self, ip: str, port: int = 80, tcp_port: int = 13052, timeout: float = 3.0):
        self.ip = ip
        self.tcp_port = tcp_port
        self.base_url = f"http://{ip}:{port}"
        self.timeout = timeout
        self._is_tcp_running = False
        self.on_frame_callback = None
    def _get(self, endpoint: str) -> dict:
        try:
            res = requests.get(f"{self.base_url}{endpoint}", timeout=self.timeout)
            if res.status_code == 200:
                return res.json()
            return {}
        except Exception as e:
            logger.debug(f"Acoustic GET {endpoint} failed: {e}")
            return {}

    def _post(self, endpoint: str, payload: dict) -> dict:
        try:
            res = requests.post(f"{self.base_url}{endpoint}", json=payload, timeout=self.timeout)
            if res.status_code == 200:
                return res.json()
            return {}
        except Exception as e:
            logger.debug(f"Acoustic POST {endpoint} failed: {e}")
            return {}

    # 1. 查询当前声压级 /spl
    def get_spl(self) -> float:
        return self._get("/spl").get("spl", 0.0)

    # 2. 查询/设置成像阈值 /threshold
    def get_threshold(self) -> float:
        return self._get("/threshold").get("value", 0.0)

    def set_threshold(self, value: float) -> dict:
        return self._post("/threshold", {"value": value})
        
    # 3. 查询/设置动态范围 /dynamic_range
    def get_dynamic_range(self) -> float:
        return self._get("/dynamic_range").get("value", 0.0)
        
    def set_dynamic_range(self, value: float) -> dict:
        return self._post("/dynamic_range", {"value": value})
        
    # 4. 查询/设置成像频段 /freq_range
    def get_freq_range(self) -> dict:
        return self._get("/freq_range")
        
    def set_freq_range(self, lower: float, upper: float) -> dict:
        return self._post("/freq_range", {"freq_lower": lower, "freq_upper": upper})
        
    # 5. 查询/设置设备时间 /time
    def get_time(self) -> dict:
        return self._get("/time")
        
    def set_time(self, time_str: str) -> dict:
        return self._post("/time", {"time": time_str})
        
    # 6. 查询/设置设备网络 /usernetwork
    def get_usernetwork(self) -> dict:
        return self._get("/usernetwork")
        
    def set_usernetwork(self, net_cfg: dict) -> dict:
        return self._post("/usernetwork", net_cfg)

    # 7. 设备重启 /reboot
    def reboot(self) -> bool:
        return "cmd" in self._get("/reboot")

    # 8. 设备采样率 /fs
    def get_fs(self) -> dict:
        return self._get("/fs")

    # 9. 查询/设置距离 /distance
    def get_distance(self) -> float:
        return self._get("/distance").get("value", 0.0)
        
    def set_distance(self, value: float) -> dict:
        return self._post("/distance", {"value": value})
        
    # 10. 查询/设置平均因子 /ema_factor
    def get_ema_factor(self) -> float:
        return self._get("/ema_factor").get("value", 0.0)
        
    def set_ema_factor(self, value: float) -> dict:
        return self._post("/ema_factor", {"value": value})
        
    # 11. 查询/设置参考通道 /ref_channel
    def get_ref_channel(self) -> float:
        return self._get("/ref_channel").get("value", 0.0)
        
    def set_ref_channel(self, value: float) -> dict:
        return self._post("/ref_channel", {"value": value})
        
    # 12. 查询当前时域信号数据 /time_domain
    def get_time_domain(self) -> dict:
        return self._get("/time_domain")
        
    # 13. 查询当前频域处理数据 /freq_domain
    def get_freq_domain(self) -> dict:
        return self._get("/freq_domain")
        
    # 14. 查询当前 prpd 处理数据 /prpd
    def get_prpd(self) -> dict:
        return self._get("/prpd")
        
    # 15. 查询序列号 /sn
    def get_sn(self) -> dict:
        return self._get("/sn")
        
    # 16. 查询设备状态 /status
    def get_status(self) -> dict:
        return self._get("/status")
        
    # 17. 查询固件版本信息 /version
    def get_version(self) -> dict:
        return self._get("/version")
        
    # 18. 查询/设置使能通道详情 /rms_enable
    def get_rms_enable(self) -> bool:
        return self._get("/rms_enable").get("rms", False)
        
    def set_rms_enable(self, enable: bool) -> dict:
        return self._post("/rms_enable", {"rms": enable})
        
    # 19. 查询通道详情 /rms
    def get_rms(self) -> dict:
        return self._get("/rms")

    # ================= TCP 长连接实时流协议解析 =================
    def start_tcp_stream(self, callback):
        """启动后台 TCP 解析线程，通过 callback(spl, grid_data, prpd_len, video_data, v_type) 返回帧数据"""
        self.on_frame_callback = callback
        self._is_tcp_running = True
        threading.Thread(target=self._tcp_stream_loop, daemon=True).start()
        
    def stop_tcp_stream(self):
        self._is_tcp_running = False

    def _tcp_stream_loop(self):
        if not self.ip:
            logger.warning("⚠️ [AcousticDriver] 未配置有效 IP 地址，跳过 TCP 流连接")
            return

        while self._is_tcp_running:
            try:
                # 统一交由全局 TCPManager 获取与管理长连接缓存
                sock = TCPManager().get_connection(self.ip, self.tcp_port, self.timeout)
                
                while self._is_tcp_running:
                    header = self._recv_exactly(sock, 4)
                    if not header: break
                    pkt_size = struct.unpack('<I', header)[0]
                    
                    payload = self._recv_exactly(sock, pkt_size)
                    if not payload: break
                    
                    self._parse_frame(payload)
                    
                # 若因数据中断跳出内层循环，主动通知 manager 释放失效链路
                TCPManager().release_connection(self.ip, self.tcp_port)
                    
            except Exception as e:
                TCPManager().release_connection(self.ip, self.tcp_port)
                if self._is_tcp_running:
                    logger.warning(f"⚠️ [AcousticDriver] TCP 流读取异常, 即将重连: {e}")
                    time.sleep(3.0)

    def _recv_exactly(self, sock, count):
        buf = b''
        while count > 0:
            try:
                newbuf = sock.recv(count)
                if not newbuf: return None
                buf += newbuf
                count -= len(newbuf)
            except socket.timeout:
                continue
        return buf

    def _parse_frame(self, payload: bytes):
        """解析小端二进制帧结构"""
        try:
            offset = 0
            # frame_no
            frame_no = struct.unpack_from('<I', payload, offset)[0]
            offset += 4
            # spl
            spl = struct.unpack_from('<f', payload, offset)[0]
            offset += 4
            
            # sound_len
            sound_len = struct.unpack_from('<I', payload, offset)[0]
            offset += 4 + sound_len * 4
            
            # filter_len
            filter_len = struct.unpack_from('<I', payload, offset)[0]
            offset += 4 + filter_len * 4
            
            # grid_len
            grid_len = struct.unpack_from('<I', payload, offset)[0]
            offset += 4
            grid_data = struct.unpack_from(f'<{grid_len}f', payload, offset) if grid_len > 0 else ()
            offset += grid_len * 4
            
            # prpd_len
            prpd_len = struct.unpack_from('<I', payload, offset)[0]
            offset += 4 + prpd_len * 4
            
            # video_type
            v_type = struct.unpack_from('<I', payload, offset)[0]
            offset += 4
            
            # video_len
            v_len = struct.unpack_from('<I', payload, offset)[0]
            offset += 4
            
            video_data = payload[offset : offset + v_len]
            
            if self.on_frame_callback:
                self.on_frame_callback(spl, grid_data, prpd_len, video_data, v_type)
                
        except struct.error:
            pass # 忽略畸形包
