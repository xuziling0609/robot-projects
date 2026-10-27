import json
import logging
import os
import re
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==================== 日志配置 ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] [Camera-Sim] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("CameraSimulator")

# 假 1x1 像素 JPEG 图像 Bytes 标头，供抓图异常兜底返回
FAKE_JPEG_BYTES = bytes([
    0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
    0x01, 0x01, 0x00, 0x48, 0x00, 0x48, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
    0x00, 0x03, 0x02, 0x02, 0x03, 0x02, 0x02, 0x03, 0x03, 0x03, 0x03, 0x04,
    0x03, 0x03, 0x04, 0x05, 0x08, 0x05, 0x05, 0x04, 0x04, 0x05, 0x0A, 0x07,
    0x07, 0x06, 0x08, 0x0C, 0x0A, 0x0C, 0x0C, 0x0B, 0x0A, 0x0B, 0x0B, 0x0D,
    0x0E, 0x12, 0x0F, 0x0D, 0x0E, 0x11, 0x0E, 0x0B, 0x0B, 0x10, 0x16, 0x10,
    0x11, 0x13, 0x14, 0x15, 0x15, 0x15, 0x0C, 0x0F, 0x17, 0x18, 0x16, 0x14,
    0x18, 0x12, 0x14, 0x15, 0x14, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
    0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
    0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
    0x09, 0x0A, 0x0B, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3F,
    0x00, 0x7F, 0x00, 0x3A, 0xFE, 0x24, 0xBF, 0xFF, 0xD9
])

# 图像静态文件路径定义
CAMERA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "camera")
VIS_IMAGE_PATH = os.path.join(CAMERA_DIR, "vis.png")
TH_IMAGE_PATH = os.path.join(CAMERA_DIR, "th.png")

def get_channel_picture(channel: int) -> bytes:
    """根据通道号获取对应图片：通道 1 (可见光: vis.png)，通道 2 (热成像: th.png)"""
    target_path = TH_IMAGE_PATH if channel in [2, 201, 202] else VIS_IMAGE_PATH
    try:
        if os.path.exists(target_path):
            with open(target_path, "rb") as f:
                return f.read()
    except Exception as e:
        logger.error(f"读取抓图图片文件失败 [{target_path}]: {e}")
    return FAKE_JPEG_BYTES

class CameraISAPIRequestHandler(BaseHTTPRequestHandler):
    """海康威视 ISAPI 协议 HTTP 模拟接收器"""

    def _send_json(self, data: dict, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _send_xml(self, xml_str: str, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.end_headers()
        self.wfile.write(xml_str.strip().encode("utf-8"))

    def _is_xml_requested(self) -> bool:
        accept = self.headers.get("Accept", "").lower()
        return "xml" in accept

    def _send_binary(self, raw_bytes: bytes, content_type="image/jpeg", status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw_bytes)))
        self.end_headers()
        self.wfile.write(raw_bytes)

    def do_GET(self):
        path = self.path.split("?")[0]
        logger.info(f"📷 [CameraSimulator GET] {self.path}")

        # 设备基础信息
        if path == "/ISAPI/System/deviceInfo":
            if self._is_xml_requested():
                self._send_xml("""<?xml version="1.0" encoding="UTF-8"?>
<DeviceInfo version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">
    <deviceName>HM-TD5567T-7_W</deviceName>
    <deviceID>CAM_888888</deviceID>
    <model>HM-TD5567T-7_W</model>
    <serialNumber>HM-TD5567T-20260728ABC</serialNumber>
    <macAddress>44:47:cc:11:22:33</macAddress>
    <firmwareVersion>V5.5.42</firmwareVersion>
    <encoderVersion>V2.2</encoderVersion>
</DeviceInfo>""")
            else:
                self._send_json({
                    "DeviceInfo": {
                        "deviceName": "HM-TD5567T-7_W",
                        "deviceID": "CAM_888888",
                        "model": "HM-TD5567T-7_W",
                        "serialNumber": "HM-TD5567T-20260728ABC",
                        "macAddress": "44:47:cc:11:22:33",
                        "firmwareVersion": "V5.5.42",
                        "encoderVersion": "V2.2"
                    }
                })

        # 抓图截图 (/ISAPI/Streaming/channels/{ch}/picture)
        elif "/picture" in path:
            ch = 1
            match = re.search(r'/channels/(\d+)/picture', path)
            if match:
                ch = int(match.group(1))
            elif "?" in self.path:
                query = self.path.split("?", 1)[1]
                for part in query.split("&"):
                    if part.startswith("channel="):
                        try:
                            ch = int(part.split("=")[1])
                        except Exception:
                            pass

            img_bytes = get_channel_picture(ch)
            ch_desc = "热成像通道(th.png)" if ch in [2, 201, 202] else "可见光通道(vis.png)"
            logger.info(f"📸 [CameraSimulator] 响应抓图 -> 通道 {ch} [{ch_desc}], 长度: {len(img_bytes)} 字节")
            self._send_binary(img_bytes, content_type="image/jpeg")

        # 热成像实时测温
        elif "/thermometry/realTimeInfo" in path:
            if self._is_xml_requested():
                self._send_xml("""<?xml version="1.0" encoding="UTF-8"?>
<ThermalThermometry version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">
    <ruleId>1</ruleId>
    <ruleName>全局点测温</ruleName>
    <highestTemperature>36.8</highestTemperature>
    <lowestTemperature>24.2</lowestTemperature>
    <averageTemperature>28.5</averageTemperature>
    <unit>CELSIUS</unit>
</ThermalThermometry>""")
            else:
                self._send_json({
                    "ThermalThermometry": {
                        "ruleId": 1,
                        "ruleName": "全局点测温",
                        "highestTemperature": 36.8,
                        "lowestTemperature": 24.2,
                        "averageTemperature": 28.5,
                        "unit": "CELSIUS"
                    }
                })

        else:
            if self._is_xml_requested():
                self._send_xml("""<?xml version="1.0" encoding="UTF-8"?>
<ResponseStatus version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">
    <statusCode>1</statusCode>
    <statusString>OK</statusString>
    <subStatusCode>ok</subStatusCode>
</ResponseStatus>""")
            else:
                self._send_json({"status": "success", "message": "OK"})

    def do_PUT(self):
        logger.info(f"📷 [CameraSimulator PUT] {self.path}")
        if self._is_xml_requested():
            self._send_xml("""<?xml version="1.0" encoding="UTF-8"?>
<ResponseStatus version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">
    <statusCode>1</statusCode>
    <statusString>OK</statusString>
    <subStatusCode>ok</subStatusCode>
</ResponseStatus>""")
        else:
            self._send_json({
                "ResponseStatus": {
                    "statusCode": 1,
                    "statusString": "OK",
                    "subStatusCode": "ok"
                }
            })

    def do_POST(self):
        logger.info(f"📷 [CameraSimulator POST] {self.path}")
        if self._is_xml_requested():
            self._send_xml("""<?xml version="1.0" encoding="UTF-8"?>
<ResponseStatus version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">
    <statusCode>1</statusCode>
    <statusString>OK</statusString>
    <subStatusCode>ok</subStatusCode>
</ResponseStatus>""")
        else:
            self._send_json({
                "ResponseStatus": {
                    "statusCode": 1,
                    "statusString": "OK",
                    "subStatusCode": "ok"
                }
            })

    def log_message(self, format, *args):
        pass

def start_camera_simulator(host="0.0.0.0", port=8080):
    logger.info("=" * 70)
    logger.info(f"📷 海康威视 HM-TD5567T 双光云台摄像头 ISAPI 模拟器启动... http://{host}:{port}")
    logger.info("=" * 70)
    server = HTTPServer((host, port), CameraISAPIRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("🛑 摄像头模拟器停止服务")
        server.server_close()

if __name__ == "__main__":
    start_camera_simulator()
