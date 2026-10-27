import time
import json
import hashlib
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from core.logger_manager import get_logger

logger = get_logger("YunjiNetDriver")

class YunjiNetDriver:
    """云迹云端开放平台 API 呼梯驱动 (遵循 V5 协议)"""
    
    def __init__(self, config: dict):
        self.host_api = config.get("host_api", "https://openapi.yunjichina.com.cn") 
        self.appname = config.get("appname", "fulang_d48abh")                             
        self.secret = config.get("secret", "CHANGE_ME")           
        self.fixed_place_id = config.get("fixed_place_id", "CHANGE_ME")
        self.assets = config.get("assets", {
            18191: {"deviceUuid": "050041000232304A50394653", "deviceSecret": "CHANGE_ME"},
            18198: {"deviceUuid": "2F0041000232304A50394653", "deviceSecret": "CHANGE_ME"} 
        })

        # 初始化带有快速失败机制的 HTTP 会话 (0次重试)
        self.session = requests.Session()
        retry_strategy = Retry(total=0, connect=0, read=0, status_forcelist=[500, 502, 503, 504], raise_on_status=False)
        self.session.mount("https://", HTTPAdapter(max_retries=retry_strategy))

    def _calculate_check(self, device_uuid, ts, device_secret):
        """生成设备安全签名 check 参数，算法为 md5(deviceUuid+"|"+ts+"|"+deviceSecret)"""
        return hashlib.md5(f"{device_uuid}|{ts}|{device_secret}".encode('utf-8')).hexdigest().lower()

    def _calculate_sign(self, params, ts):
        """生成请求签名 sign 参数，字典序排序并过滤空值，追加 appname、secret、ts"""
        kvs = []
        for key, value in params.items():
            if key.lower() in {'appname', 'secret', 'ts', 'sign'} or value is None or value == "": 
                continue
            value_str = json.dumps(value, sort_keys=True, separators=(',', ':')) if isinstance(value, (dict, list)) else str(value).strip()
            kvs.append(f"{key.strip()}:{value_str}")
        kvs.sort() 
        sign_str = "|".join(kvs) + f"|appname:{self.appname}|secret:{self.secret}|ts:{ts}"
        return hashlib.md5(sign_str.encode('utf-8')).hexdigest().lower()

    def _build_base_payload(self, asset: dict) -> tuple:
        """构建基础鉴权 payload 和时间戳"""
        ts = int(time.time() * 1000) 
        payload = {
            "deviceUuid": asset["deviceUuid"], 
            "placeId": self.fixed_place_id,
            "check": self._calculate_check(asset["deviceUuid"], ts, asset["deviceSecret"])
        }
        return payload, ts

    def call_lift(self, lift_no: int, to_floor: int) -> bool:
        """调用公网 API 呼叫电梯"""
        asset = self.assets.get(lift_no)
        if not asset: return False
            
        payload, ts = self._build_base_payload(asset)
        payload.update({"liftNo": lift_no, "toFloor": to_floor})
        payload.update({"appname": self.appname, "ts": ts, "sign": self._calculate_sign(payload, ts)})
        
        try:
            logger.info(f"🌐 开始云端网络呼梯 (Lift: {lift_no}, Floor: {to_floor})")
            res = self.session.post(f"{self.host_api}/openapi/v5/lift/call", json=payload, timeout=(2.0, 5.0))
            return res.json().get("errcode") == 0
        except Exception as e:
            logger.warning(f"⚠️ 网络模块呼梯异常: {e}")
            return False

    def delay_close(self, lift_no: int, seconds: int = 5) -> bool:
        """调用公网 API 延迟关门。参数 seconds 范围为 0-9，0 表示立即关门"""
        asset = self.assets.get(lift_no)
        if not asset: return False
            
        payload, ts = self._build_base_payload(asset)
        payload.update({"liftNo": lift_no, "seconds": seconds})
        payload.update({"appname": self.appname, "ts": ts, "sign": self._calculate_sign(payload, ts)})
        
        try:
            logger.info(f"🌐 开始云端网络延迟关门 (Lift: {lift_no}, 延迟: {seconds}s)")
            res = self.session.post(f"{self.host_api}/openapi/v5/lift/open", json=payload, timeout=(2.0, 5.0))
            return res.json().get("errcode") == 0
        except Exception as e:
            logger.warning(f"⚠️ 网络模块延迟关门异常: {e}")
            return False

    def query_status(self, lift_no: int) -> dict:
        """
        电梯状态查询接口
        返回云端电梯的当前楼层、运行方向、门状态等详细信息。
        """
        asset = self.assets.get(lift_no)
        if not asset:
            logger.error(f"❌ 未找到电梯 {lift_no} 的云迹资产配置")
            return {}
            
        payload, ts = self._build_base_payload(asset)
        payload.update({"liftNo": lift_no})
        payload.update({"appname": self.appname, "ts": ts, "sign": self._calculate_sign(payload, ts)})
        
        try:
            logger.info(f"🌐 开始云端网络查询电梯状态 (Lift: {lift_no})")
            res = self.session.post(f"{self.host_api}/openapi/v5/lift/status", json=payload, timeout=(2.0, 5.0))
            response_data = res.json()
            
            # errcode 为 0 表示调用成功
            if response_data.get("errcode") == 0:
                result = response_data.get("result", {})
                logger.debug(f"✅ 获取到电梯 {lift_no} 状态: 楼层 [{result.get('floor')}], 门状态 [{result.get('liftDoorStatus')}]")
                return result
            else:
                logger.warning(f"⚠️ 云端状态查询返回错误: {response_data.get('errmsg')}")
                return {}
        except Exception as e:
            logger.warning(f"⚠️ 网络模块状态查询异常: {e}")
            return {}