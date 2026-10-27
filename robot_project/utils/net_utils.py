import socket
from core.logger_manager import get_logger

logger = get_logger("NetUtils")
def get_local_ip(target_ip: str = "192.168.100.178") -> str:
    """
    获取与目标 IP/局域网连通的本机真实 LAN IP 地址。
    通过 UDP 路由探测（无需真正建立 TCP 连接），避免返回 127.0.0.1 回环地址。
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((target_ip, 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        logger.error('操作引发异常:', exc_info=True)
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception as e:
            logger.error('操作引发异常:', exc_info=True)
            return "127.0.0.1"
