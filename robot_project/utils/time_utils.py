import time
import random
from datetime import datetime

def get_timestamp_ms() -> int:
    """
    公共方法：获取当前时间的 13 位毫秒级时间戳。
    常用于 MQTT 报文的时间戳字段（精度极高，无浮点数误差）。
    
    :return: 13位整数时间戳，例如 1689999999123
    """
    return time.time_ns() // 1_000_000

def format_time_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    公共方法：获取当前时间的格式化字符串，方便用于日志或本地显示。
    """
    return time.strftime(fmt, time.localtime())

def generate_msg_id() -> str:
    """
    公共方法：生成符合规范格式 20260728-092443-471-250 的 msg_id。
    格式: YYYYMMDD-HHMMSS-fff-rrr (年月日-时分秒-毫秒-随机序号)
    适用于能力上报、状态上报及告警上报等 MQTT 报文。
    """
    now = datetime.now()
    date_part = now.strftime("%Y%m%d")
    time_part = now.strftime("%H%M%S")
    ms_part = f"{now.microsecond // 1000:03d}"
    rand_part = f"{random.randint(0, 999):03d}"
    return f"{date_part}-{time_part}-{ms_part}-{rand_part}"