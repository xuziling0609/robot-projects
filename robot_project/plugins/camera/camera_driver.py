import os
import time
import base64
import requests
from requests.auth import HTTPDigestAuth
from typing import Dict, Any, Optional, Tuple
from core.logger_manager import get_logger

logger = get_logger("CameraDriver")

class IsapiException(Exception):
    """ISAPI 协议交互异常"""
    pass

class CameraDriver:
    """
    海康威视 ISAPI 摄像头底层驱动 (CameraDriver) - 专为 HM-TD5567T-7_W 双光测温云台相机定制
    根据 《ISAPI开发指南_工业测温_测温云台》 与 《Event and Digest Auth》 规范开发：
    1. 认证机制：严格遵循 HTTP/HTTPS Digest 摘要认证 (HTTPDigestAuth)。
    2. 数据协议：全量采用海康威视原生 XML 报文协议交互 (Content-Type: application/xml)，不使用 json 协议，彻底消除机载解析器 badXmlContent 异常。
    3. 图像抓图：针对双光相机提供可见光与热成像双通道抓图 (/ISAPI/Streaming/channels/{ch}/picture)，支持本地落盘与 Base64 返回。
    4. 核心功能覆盖：
       - 图像实时抓图/截图 (/ISAPI/Streaming/channels/{ch}/picture)
       - 系统基础信息查询与配置 (/ISAPI/System/deviceInfo)
       - 云台连续控制与定点定位 (/ISAPI/PTZCtrl/channels/{ch}/continuous, presets/{id}/goto)
       - 工业测温/热成像实时温度获取 (/ISAPI/Thermal/channels/{ch}/thermometry/realTimeInfo)
       - 事件布防监听与告警订阅 (/ISAPI/Event/notification/subscribeEvent)
    """
    def __init__(
        self,
        camera_id: int,
        name: str,
        ip: str,
        port: int = 80,
        protocol: str = "http",
        username: str = "admin",
        password: str = "",
        timeout: float = 5.0,
        channel: int = 1,
        ptz_enabled: bool = True,
        thermal_enabled: bool = True,
        model: str = "HM-TD5567T-7_W"
    ):
        self.camera_id = camera_id
        self.name = name
        self.ip = ip
        self.port = port
        self.protocol = protocol.lower()
        self.username = username
        self.password = password
        self.timeout = timeout
        self.channel = channel
        self.ptz_enabled = ptz_enabled
        self.thermal_enabled = thermal_enabled
        self.model = model

        self.base_url = f"{self.protocol}://{self.ip}:{self.port}"
        
        # 初始化 HTTP 会话并绑定 Digest 摘要认证 (Digest Authentication)
        self.session = requests.Session()
        self.session.auth = HTTPDigestAuth(self.username, self.password)
        self.session.headers.update({
            "Accept": "application/xml, text/xml, */*",
            "User-Agent": "Antigravity-ISAPI-Client/1.0"
        })

    @staticmethod
    def _xml_element_to_dict(element) -> Any:
        """递归将 XML ElementTree 转为嵌套 Dict / 列表"""
        children = list(element)
        if not children:
            text = element.text
            return text.strip() if text else ""
        result = {}
        for child in children:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            val = CameraDriver._xml_element_to_dict(child)
            if tag in result:
                if not isinstance(result[tag], list):
                    result[tag] = [result[tag]]
                result[tag].append(val)
            else:
                result[tag] = val
        return result

    @staticmethod
    def _dict_to_xml(data: Any, root_tag: Optional[str] = None) -> str:
        """将 Dict 数据结构或字符串转为标准 ISAPI XML 报文"""
        if isinstance(data, (bytes, bytearray)):
            data = data.decode("utf-8")
        if isinstance(data, str):
            data_str = data.strip()
            if not data_str.startswith("<?xml"):
                return f'<?xml version="1.0" encoding="UTF-8"?>\n{data_str}'
            return data_str

        def _to_xml_str(tag: str, val: Any) -> str:
            if isinstance(val, dict):
                inner = "".join(_to_xml_str(k, v) for k, v in val.items())
                return f"<{tag}>{inner}</{tag}>"
            elif isinstance(val, list):
                return "".join(_to_xml_str(tag, item) for item in val)
            elif isinstance(val, bool):
                return f"<{tag}>{'true' if val else 'false'}</{tag}>"
            elif isinstance(val, float) and val.is_integer():
                return f"<{tag}>{int(val)}</{tag}>"
            elif val is None:
                return f"<{tag}/>"
            else:
                return f"<{tag}>{val}</{tag}>"

        if isinstance(data, dict):
            if root_tag:
                inner = "".join(_to_xml_str(k, v) for k, v in data.items())
                return f'<?xml version="1.0" encoding="UTF-8"?>\n<{root_tag} version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">{inner}</{root_tag}>'
            elif len(data) == 1:
                r_tag, content = next(iter(data.items()))
                if isinstance(content, dict):
                    inner = "".join(_to_xml_str(k, v) for k, v in content.items())
                    return f'<?xml version="1.0" encoding="UTF-8"?>\n<{r_tag} version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">{inner}</{r_tag}>'
                else:
                    inner = _to_xml_str(r_tag, content)
                    return f'<?xml version="1.0" encoding="UTF-8"?>\n{inner}'
            else:
                inner = "".join(_to_xml_str(k, v) for k, v in data.items())
                return f'<?xml version="1.0" encoding="UTF-8"?>\n<Root version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">{inner}</Root>'

        return f'<?xml version="1.0" encoding="UTF-8"?>\n{str(data)}'

    def _parse_response_body(self, response: requests.Response) -> Any:
        """解析响应 Body，以 XML 协议为主，同时兼顾解析 JSON"""
        content_type = response.headers.get("Content-Type", "").lower()
        text = response.text.strip()
        if not text:
            return {}

        # 优先使用 XML 解析
        if "xml" in content_type or text.startswith("<"):
            try:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(text)
                parsed_dict = self._xml_element_to_dict(root)
                root_tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
                return {root_tag: parsed_dict} if root_tag else parsed_dict
            except Exception as e:
                logger.debug(f"[Camera ID={self.camera_id}] XML 解析失败: {e}")

        # 兼顾解析 JSON (如某些网关中间层返回 JSON)
        if "json" in content_type or (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
            try:
                return response.json()
            except Exception:
                pass

        return text

    def _request(
        self,
        method: str,
        endpoint: str,
        xml_data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Any] = None,
        root_tag: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        统一发起 ISAPI 请求方法
        全量遵循海康威视原生 XML 协议规范交互，不使用 json 协议，避免机载解析器抛出 badXmlContent / Invalid JSON Content 异常
        """
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        url = self.base_url + endpoint

        req_params = dict(params) if params else {}
        # 严禁在 URL 中附带任何 format 参数
        req_params.pop("format", None)

        method_upper = method.upper()
        payload = xml_data if xml_data is not None else json_data

        headers = {}
        data_to_send = None

        if payload is not None:
            xml_str = self._dict_to_xml(payload, root_tag=root_tag)
            data_to_send = xml_str.encode("utf-8")
            headers["Content-Type"] = "application/xml; charset=UTF-8"
            logger.debug(f"🌐 [Camera ID={self.camera_id} | {self.model}] 发起 ISAPI XML 请求 -> {method_upper} {url} | 参数: {req_params} | 载荷:\n{xml_str}")
        else:
            logger.debug(f"🌐 [Camera ID={self.camera_id} | {self.model}] 发起 ISAPI XML 请求 -> {method_upper} {url} | 参数: {req_params}")

        try:
            response = self.session.request(
                method=method_upper,
                url=url,
                params=req_params if req_params else None,
                data=data_to_send,
                headers=headers if headers else None,
                timeout=self.timeout
            )

            if response.status_code in [200, 201, 202]:
                data = self._parse_response_body(response)
                return {
                    "status": "success",
                    "status_code": response.status_code,
                    "data": data
                }
            else:
                err_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.warning(f"⚠️ [Camera ID={self.camera_id}] ISAPI XML 请求失败: {err_msg}")
                return {
                    "status": "error",
                    "status_code": response.status_code,
                    "message": err_msg,
                    "data": self._parse_response_body(response)
                }

        except requests.exceptions.RequestException as e:
            err_msg = f"连接设备通信异常: {str(e)}"
            logger.debug(f"❌ [Camera ID={self.camera_id}] {err_msg}")
            return {
                "status": "error",
                "status_code": 0,
                "message": err_msg,
                "data": None
            }

    def _request_binary(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Tuple[int, bytes, str]:
        """
        获取二进制流（如抓图 JPEG 图像）请求方法
        不再附加 format=json，且 Accept 为 image/jpeg 或通配符
        """
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        url = self.base_url + endpoint
        logger.debug(f"📸 [Camera ID={self.camera_id} | {self.model}] 发起二进制图像请求 -> GET {url}")

        try:
            # 针对抓图临时覆盖 Accept 请求头
            headers = {"Accept": "image/jpeg, image/*, */*"}
            response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
            if response.status_code == 200:
                return 200, response.content, "success"
            else:
                return response.status_code, b"", f"HTTP {response.status_code}: {response.text[:150]}"
        except Exception as e:
            return 0, b"", f"通信异常: {str(e)}"

    # ========================== 1. 抓图与图像获取 ==========================
    def capture_picture(
        self,
        channel: Optional[int] = None,
        return_base64: bool = True
    ) -> Dict[str, Any]:
        """
        摄像头抓图 (/ISAPI/Streaming/channels/{ch}/picture)
        针对 HM-TD5567T-7_W 双光相机：
        - channel=1 或 101: 抓取可见光通道图像 (Visible Light)
        - channel=2 或 201: 抓取热成像通道红外图像 (Thermal Imaging)
        :param channel: 抓图通道号 (缺省默认取 self.channel)
        :param return_base64: 是否在结果中附带 base64 编码字符串
        """
        ch = channel if channel is not None else self.channel
        # 双光通道说明日志
        ch_name = "可见光通道" if ch in [1, 101, 102] else ("热成像通道" if ch in [2, 201, 202] else f"通道{ch}")
        logger.info(f"📸 [Camera ID={self.camera_id} | {self.model}] 发起抓图指令 -> 目标: {ch_name} (Channel={ch})")

        status_code, img_bytes, msg = self._request_binary(f"/ISAPI/Streaming/channels/{ch}/picture")
        if status_code != 200 or not img_bytes:
            err_msg = f"抓图获取图像失败 ({msg})"
            logger.error(f"❌ [Camera ID={self.camera_id}] {err_msg}")
            return {"status": "error", "status_code": status_code, "message": err_msg}

        # 校验并添加 JPG 文件头 (\xff\xd8)
        if not img_bytes.startswith(b'\xff\xd8'):
            jpg_header = bytes([
                0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
                0x01, 0x01, 0x00, 0x48, 0x00, 0x48, 0x00, 0x00
            ])
            img_bytes = jpg_header + img_bytes

        # 转 Base64 并加 jpg 数据头
        raw_b64 = base64.b64encode(img_bytes).decode("ascii")
        b64_str = f"data:image/jpeg;base64,{raw_b64}"

        ret_data = {
            "camera_id": self.camera_id,
            "camera_name": self.name,
            "model": self.model,
            "channel": ch,
            "channel_type": ch_name,
            "image_size_bytes": len(img_bytes),
            "base64": b64_str,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        return {
            "status": "success",
            "status_code": status_code,
            "message": f"成功抓取 {self.model} {ch_name} 图像",
            "data": ret_data
        }

    # ========================== 2. 系统与设备信息管理 ==========================
    def get_device_info(self) -> Dict[str, Any]:
        """查询设备基本信息 (/ISAPI/System/deviceInfo) -> 包含型号、序列号、固件版本等"""
        return self._request("GET", "/ISAPI/System/deviceInfo")

    def set_device_info(self, info_data: Dict[str, Any]) -> Dict[str, Any]:
        """修改设备基本信息 (/ISAPI/System/deviceInfo)"""
        return self._request("PUT", "/ISAPI/System/deviceInfo", xml_data=info_data, root_tag="DeviceInfo")

    # ========================== 3. PTZ 云台控制 ==========================
    def ptz_control(
        self,
        pan: float = 0.0,
        tilt: float = 0.0,
        zoom: float = 0.0,
        channel: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        云台连续运动控制 (/ISAPI/PTZCtrl/channels/{ch}/continuous)
        海康 ISAPI XML 协议规范要求 pan, tilt, zoom 必须为整数 (-100 ~ 100)，严禁带小数位或注入非标准节点如 rotate
        :param pan: 水平速度 (-100 ~ 100 整数, 正数为右)
        :param tilt: 垂直速度 (-100 ~ 100 整数, 正数为上)
        :param zoom: 变倍速度 (-100 ~ 100 整数, 正数为放大)
        :param channel: 控制通道号 (默认取 self.channel)
        """
        if not self.ptz_enabled:
            return {"status": "error", "message": "当前摄像头未开启云台 PTZ 控制功能"}

        ch = channel or self.channel
        pan_int = max(-100, min(100, int(round(float(pan)))))
        tilt_int = max(-100, min(100, int(round(float(tilt)))))
        zoom_int = max(-100, min(100, int(round(float(zoom)))))

        payload = {
            "PTZData": {
                "pan": pan_int,
                "tilt": tilt_int,
                "zoom": zoom_int
            }
        }
        logger.info(f"🎯 [Camera ID={self.camera_id}] 下发云台控制 XML 指令 -> 通道:{ch} | Pan:{pan_int}, Tilt:{tilt_int}, Zoom:{zoom_int}")
        return self._request("PUT", f"/ISAPI/PTZCtrl/channels/{ch}/continuous", xml_data=payload)

    def ptz_stop(self, channel: Optional[int] = None) -> Dict[str, Any]:
        """停止云台运动 (各轴速度设为 0)"""
        logger.info(f"🛑 [Camera ID={self.camera_id}] 下发云台停止运动指令")
        return self._ptz_stop_internal(channel)

    def _ptz_stop_internal(self, channel: Optional[int] = None) -> Dict[str, Any]:
        ch = channel or self.channel
        payload = {
            "PTZData": {
                "pan": 0,
                "tilt": 0,
                "zoom": 0
            }
        }
        return self._request("PUT", f"/ISAPI/PTZCtrl/channels/{ch}/continuous", xml_data=payload)

    def ptz_goto_preset(self, preset_id: int, channel: Optional[int] = None) -> Dict[str, Any]:
        """调用云台预置点 (/ISAPI/PTZCtrl/channels/{ch}/presets/{preset_id}/goto)"""
        if not self.ptz_enabled:
            return {"status": "error", "message": "当前摄像头未开启云台 PTZ 控制功能"}
            
        ch = channel or self.channel
        logger.info(f"📍 [Camera ID={self.camera_id}] 调运云台预置点 -> 通道:{ch}, 预置点 ID:{preset_id}")
        return self._request("PUT", f"/ISAPI/PTZCtrl/channels/{ch}/presets/{preset_id}/goto")

    # ========================== 4. 工业测温 / 热成像功能 ==========================
    def get_thermometry_info(self, channel: Optional[int] = None) -> Dict[str, Any]:
        """
        实时工业测温数据查询 (/ISAPI/Thermal/channels/{ch}/thermometry/realTimeInfo)
        通过海康原生 XML 协议获取当前规则内的最高温度 (highestTemperature)、最低温度 (lowestTemperature)、平均温度 (averageTemperature) 及超温报警状态
        """
        if not self.thermal_enabled:
            return {"status": "error", "message": "当前摄像头未开启热成像/工业测温能力"}

        ch = channel or self.channel
        logger.debug(f"🌡️ [Camera ID={self.camera_id}] 正在通过 XML 协议查询通道 {ch} 的工业测温与热成像数据...")
        
        # 1. 优先尝试主实时测温接口 realTimeInfo
        res = self._request("GET", f"/ISAPI/Thermal/channels/{ch}/thermometry/realTimeInfo")
        if res["status"] == "success":
            return res

        # 2. 如果通道 ch 获取失败且 ch != 1，尝试回退热成像通道 1
        if ch != 1:
            logger.debug(f"🔄 [Camera ID={self.camera_id}] 尝试切换至通道 1 查询 realTimeInfo...")
            res_ch1 = self._request("GET", "/ISAPI/Thermal/channels/1/thermometry/realTimeInfo")
            if res_ch1["status"] == "success":
                return res_ch1

        # 3. 尝试读取规则测温接口 (/thermometry/rules)
        logger.debug(f"🔄 [Camera ID={self.camera_id}] 尝试切换至测温规则列表接口 (/thermometry/rules)...")
        res_rules = self._request("GET", f"/ISAPI/Thermal/channels/{ch}/thermometry/rules")
        if res_rules["status"] == "success":
            return res_rules

        # 4. 尝试读取测温基础根接口 (/thermometry)
        logger.debug(f"🔄 [Camera ID={self.camera_id}] 尝试读取测温基础接口 (/thermometry)...")
        res_root = self._request("GET", f"/ISAPI/Thermal/channels/{ch}/thermometry")
        if res_root["status"] == "success":
            return res_root

        return res

    # ========================== 5. 事件布防与事件订阅 ==========================
    def start_guard(self, event_type: str = "thermal_alarm") -> Dict[str, Any]:
        """
        开启 ISAPI 事件布防与告警订阅 (/ISAPI/Event/notification/subscribeEvent)
        对齐 Java 示例工程 AlarmGuardDemo.java 中 f0001 / f0003 功能 (XML 协议)
        """
        payload = {
            "SubscribeEvent": {
                "eventMode": "all",
                "eventType": event_type,
                "eventDescription": f"Antigravity ISAPI Guard Subscription for {event_type}"
            }
        }
        logger.info(f"🛡️ [Camera ID={self.camera_id}] 正在下发事件订阅与布防 XML 指令 (模式: all, 事件: {event_type})...")
        return self._request("POST", "/ISAPI/Event/notification/subscribeEvent", xml_data=payload)

    def stop_guard(self, event_type: str = "thermal_alarm") -> Dict[str, Any]:
        """
        关闭 ISAPI 事件布防与告警订阅
        对齐 Java 示例工程 AlarmGuardDemo.java 中 f0002 / f0004 功能 (XML 协议)
        """
        payload = {
            "SubscribeEvent": {
                "eventMode": "off",
                "eventType": event_type
            }
        }
        logger.info(f"🔕 [Camera ID={self.camera_id}] 正在下发关闭布防与取消订阅 XML 指令...")
        return self._request("PUT", "/ISAPI/Event/notification/subscribeEvent", xml_data=payload)

    def get_status(self) -> Dict[str, Any]:
        """检测驱动在线状态与配置参数"""
        res = self.get_device_info()
        online = (res["status"] == "success")
        return {
            "camera_id": self.camera_id,
            "name": self.name,
            "model": self.model,
            "url": self.base_url,
            "protocol": self.protocol,
            "online": online,
            "ptz_enabled": self.ptz_enabled,
            "thermal_enabled": self.thermal_enabled,
            "device_info": res.get("data") if online else None
        }
