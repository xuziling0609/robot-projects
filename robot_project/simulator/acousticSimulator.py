import os
import io
import json
import logging
import threading
import time
import struct
import socket
import random
import numpy as np
import cv2
import av
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==================== 日志配置 ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] [Acoustic-Sim] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("AcousticSimulator")

# ==================== 状态数据 ====================
SIM_STATE = {
    "spl": 55.0,  # 默认正常声压 (dB)
    "threshold": 80.0,
    "freq_lower": 10000.0,
    "freq_upper": 40000.0,
    "has_fault": False  # 是否注入局放故障
}

# 静态底图路径与单帧 H.264 缓存
SCENE_IMAGE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "acoustic", "acoustic_scene.png"))
CACHED_VIDEO_BYTES: bytes = b''

def load_and_encode_h264_frame(image_path: str) -> bytes:
    """读取可见光背景图并编码为合法的单帧标准 H.264 IDR 裸流帧 (含 SPS + PPS + IDR Slice)"""
    img = None
    if os.path.exists(image_path):
        try:
            img = cv2.imread(image_path)
        except Exception as e:
            logger.error(f"❌ 读取背景图像失败 {image_path}: {e}")

    if img is None:
        logger.warning(f"⚠️ 背景底图未读取成功 [{image_path}]，生成默认工业测试背景图...")
        img = np.zeros((720, 1280, 3), dtype=np.uint8)
        img[:] = (35, 40, 45)
        cv2.putText(img, "SIM ACOUSTIC SCENE (1280x720)", (360, 360),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (200, 200, 200), 2)

    h, w = img.shape[:2]
    w = w - (w % 2)
    h = h - (h % 2)
    img = img[:h, :w]

    try:
        out_buf = io.BytesIO()
        container = av.open(out_buf, mode='w', format='h264')
        stream = container.add_stream('h264', rate=10)
        stream.width = w
        stream.height = h
        stream.pix_fmt = 'yuv420p'
        stream.options = {
            'preset': 'ultrafast',
            'tune': 'zerolatency',
            'x264-params': 'keyint=1:min-keyint=1:scenecut=0'
        }
        av_frame = av.VideoFrame.from_ndarray(img, format='bgr24')
        for packet in stream.encode(av_frame):
            container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
        container.close()

        h264_bytes = out_buf.getvalue()
        # 重点：追加 Annex B 访问单元定界符 AUD (0x09)，确保流式 Parser 能立即判定该 IDR 帧闭合并输出 Packet
        if not h264_bytes.endswith(b'\x00\x00\x00\x01\x09\x10'):
            h264_bytes += b'\x00\x00\x00\x01\x09\x10'

        logger.info(f"✅ 成功编码单帧 H.264 视频关键帧裸流 (尺寸: {w}x{h}, 大小: {len(h264_bytes)} 字节)")
        return h264_bytes
    except Exception as e:
        logger.error(f"❌ H.264 裸流编码失败: {e}", exc_info=True)
        return b'\x00\x00\x00\x01\x67\x42\x00\x0a\xf8\x41\xa2'

def generate_gaussian_grid(spl: float, has_fault: bool) -> list:
    """生成 32x24 的二维高斯声成像热力网格 (物理聚焦光斑)"""
    # 基础环境底噪 (46 ~ 50 dB)
    noise = np.random.uniform(46.0, 50.0, size=(24, 32)).astype(np.float32)

    if has_fault or spl >= 80.0:
        # 对应底图重要位置 (列 20, 行 8) 产生聚集放电/异常高频声斑
        center_c, center_r = 20.0, 8.0
        sigma = 3.0
        y_indices, x_indices = np.ogrid[:24, :32]
        dist_sq = (x_indices - center_c) ** 2 + (y_indices - center_r) ** 2
        peak_spl = max(spl, 85.0)
        gaussian_peak = (peak_spl - 48.0) * np.exp(-dist_sq / (2.0 * (sigma ** 2)))
        noise += gaussian_peak

    return noise.flatten().tolist()

# ==================== HTTP 模拟器 ====================
class AcousticHTTPRequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, data: dict, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        path = self.path.split("?")[0]
        logger.info(f"🎤 [HTTP GET] {self.path}")

        if path == "/spl":
            self._send_json({"spl": SIM_STATE["spl"]})
        elif path == "/threshold":
            self._send_json({"value": SIM_STATE["threshold"]})
        elif path == "/status":
            self._send_json({
                "app": "C168",
                "cam_width": 1920,
                "cam_height": 1080,
                "cpu_temp": 45.5,
                "device_no": "SIM_ACOUSTIC_001",
                "version": "1.0.6"
            })
        elif path == "/prpd":
            if SIM_STATE["has_fault"]:
                self._send_json({
                    "discharge_acceptance": 98.5,
                    "discharge_malfunction_grade": 2,
                    "discharge_type": 1,
                    "x": [0.0, 1.0],
                    "y": [0.5, 0.6]
                })
            else:
                self._send_json({
                    "discharge_acceptance": 0.0,
                    "discharge_malfunction_grade": 0,
                    "discharge_type": 0,
                    "x": [],
                    "y": []
                })
        elif path in ["/reset", "/spl/reset"]:
            SIM_STATE["spl"] = 55.0
            SIM_STATE["has_fault"] = False
            logger.info("🌿 [AcousticSim] 状态已重置为正常 (SPL=55.0, 无故障)")
            self._send_json({"status": "success", "message": "已重置为正常状态", "spl": 55.0, "has_fault": False})
        else:
            self._send_json({"status": "success"})

    def do_POST(self):
        path = self.path.split("?")[0]
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        payload = json.loads(post_data.decode('utf-8')) if post_data else {}

        logger.info(f"🎤 [HTTP POST] {self.path} Payload: {payload}")

        if path == "/threshold":
            SIM_STATE["threshold"] = float(payload.get("value", 80.0))
            self._send_json({"value": SIM_STATE["threshold"]})
        elif path == "/spl":
            if "spl" in payload:
                SIM_STATE["spl"] = float(payload["spl"])
            logger.info(f"💉 [AcousticSim] 更新声压 SPL -> {SIM_STATE['spl']} dB")
            self._send_json({"status": "success", "spl": SIM_STATE["spl"]})
        elif path in ["/fault", "/simulate/fault"]:
            if "has_fault" in payload:
                SIM_STATE["has_fault"] = bool(payload["has_fault"])
            if "spl" in payload:
                SIM_STATE["spl"] = float(payload["spl"])
            elif SIM_STATE["has_fault"] and SIM_STATE["spl"] < 80.0:
                SIM_STATE["spl"] = 95.0
            logger.info(f"💉 [AcousticSim] 设置局放故障 -> has_fault={SIM_STATE['has_fault']}, spl={SIM_STATE['spl']}")
            self._send_json({"status": "success", "has_fault": SIM_STATE["has_fault"], "spl": SIM_STATE["spl"]})
        elif path in ["/reset", "/spl/reset"]:
            SIM_STATE["spl"] = 55.0
            SIM_STATE["has_fault"] = False
            logger.info("🌿 [AcousticSim] 状态已重置为正常 (SPL=55.0, 无故障)")
            self._send_json({"status": "success", "message": "已重置为正常状态", "spl": 55.0, "has_fault": False})
        else:
            self._send_json({"status": "success", "message": "OK"})

    def log_message(self, format, *args):
        pass

def start_http_server(port=8000):
    server = HTTPServer(("0.0.0.0", port), AcousticHTTPRequestHandler)
    logger.info(f"🌐 启动 HTTP 模拟服务端口: {port}")
    server.serve_forever()

# ==================== TCP 二进制流模拟器 ====================
def build_tcp_frame(frame_no: int) -> bytes:
    """构建探头 13052 端口的小端二进制 Payload"""
    base_spl = SIM_STATE["spl"]
    spl = base_spl + random.uniform(-1.0, 1.0)
    has_fault = SIM_STATE["has_fault"] or (spl >= SIM_STATE["threshold"])

    payload_parts = []

    # 1. frame_no (I), spl (f)
    payload_parts.append(struct.pack('<If', frame_no, spl))

    # 2. sound_len (I) = 0
    payload_parts.append(struct.pack('<I', 0))
    # 3. sound_filter_len (I) = 0
    payload_parts.append(struct.pack('<I', 0))

    # 4. grid_len (I) = 768 (32x24), 模拟二维高斯热力图数据
    grid_len = 768
    grid_data = generate_gaussian_grid(spl, has_fault)
    payload_parts.append(struct.pack('<I', grid_len))
    payload_parts.append(struct.pack(f'<{grid_len}f', *grid_data))

    # 5. prpd_xy_len (I)
    if has_fault:
        prpd_len = 2  # x1, y1
        prpd_data = [180.0, 0.85]
    else:
        prpd_len = 0
        prpd_data = []

    payload_parts.append(struct.pack('<I', prpd_len))
    if prpd_len > 0:
        payload_parts.append(struct.pack(f'<{prpd_len}f', *prpd_data))

    # 6. video_frame_type (I) = 1 (Keyframe)
    payload_parts.append(struct.pack('<I', 1))

    # 7. video_len (I) & 真实的单帧 H.264 IDR 裸流数据
    video_bytes = CACHED_VIDEO_BYTES or b''
    payload_parts.append(struct.pack('<I', len(video_bytes)))
    payload_parts.append(video_bytes)

    full_payload = b''.join(payload_parts)
    pkt_size = len(full_payload)

    # 头部添加 4 字节数据包总长度
    return struct.pack('<I', pkt_size) + full_payload

def handle_tcp_client(client_socket, addr):
    logger.info(f"🔌 [TCP] 客户端已连接: {addr}")
    frame_no = 0
    try:
        while True:
            frame_data = build_tcp_frame(frame_no)
            client_socket.sendall(frame_data)
            frame_no += 1
            time.sleep(0.1)
    except Exception as e:
        logger.warning(f"🔌 [TCP] 客户端 {addr} 断开: {e}")
    finally:
        client_socket.close()

def start_tcp_server(port=13052):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", port))
    server.listen(5)
    logger.info(f"⚡ 启动 TCP 二进制流模拟服务端口: {port}")

    while True:
        client_sock, addr = server.accept()
        threading.Thread(target=handle_tcp_client, args=(client_sock, addr), daemon=True).start()

def init_cached_video():
    """初始化并缓存合法的 H.264 视频关键帧字节"""
    global CACHED_VIDEO_BYTES
    logger.info(f"📷 正在预加载并编码可见光背景图: {SCENE_IMAGE_PATH} ...")
    CACHED_VIDEO_BYTES = load_and_encode_h264_frame(SCENE_IMAGE_PATH)

def start_acoustic_simulator(http_host="0.0.0.0", http_port=8000, tcp_port=13052):
    init_cached_video()

    # 启动 HTTP 线程
    server = HTTPServer((http_host, http_port), AcousticHTTPRequestHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info(f"🌐 启动 HTTP 模拟服务端口: {http_port}")

    # 启动 TCP 线程
    threading.Thread(target=start_tcp_server, args=(tcp_port,), daemon=True).start()

if __name__ == "__main__":
    start_acoustic_simulator()
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        logger.info("🛑 声纹模拟器安全退出...")
