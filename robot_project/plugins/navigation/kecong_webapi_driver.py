import json
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional, Callable
from core.logger_manager import get_logger

logger = get_logger("KecongWebAPIDriver")

class _StatusPushHTTPHandler(BaseHTTPRequestHandler):
    on_status_received_callback = None

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b""
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"result": 0, "error": ""}).encode('utf-8'))

        try:
            body_str = post_data.decode('utf-8').strip()
            if not body_str:
                return
            status_json = json.loads(body_str)
            if _StatusPushHTTPHandler.on_status_received_callback:
                _StatusPushHTTPHandler.on_status_received_callback(status_json)
        except Exception as e:
            logger.error(f"❌ 解析科聪主动推送 HTTP 报文失败: {e}")

    def log_message(self, format, *args):
        pass

class _ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True

class StatusPushServer:
    """接收导航控制器主动推送 HTTP POST 状态包的服务端 (按文档 4.2.1 接收)"""
    def __init__(self, port: int = 17809, callback: Optional[Callable[[dict], Any]] = None):
        self.port = port
        self.callback = callback
        self.server = None
        self.thread = None

    def start(self):
        _StatusPushHTTPHandler.on_status_received_callback = self.callback
        try:
            self.server = _ReusableHTTPServer(('0.0.0.0', self.port), _StatusPushHTTPHandler)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            logger.info(f"✅ 科聪状态主动推送接收 HTTP 服务已启动 (端口: {self.port})")
        except Exception as e:
            logger.error(f"❌ 启动推送 HTTP 接收服务失败 (端口: {self.port}): {e}")

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()

class KecongWebAPIDriver:
    """
    科聪激光导航控制器底层 WebAPI 驱动 (xRobotWebAPI V2.1)
    封装全量 HTTP 请求接口（身份认证、主动推送设置、导航控制、步态/动作控制与阻尼急停）
    """

    def __init__(self, ip: str = "192.168.100.178", port: int = 17808, 
                 app_code: str = "", default_robot_type: int = 513, timeout: float = 5.0):
        self.ip = ip
        self.port = port
        self.app_code = app_code
        self.default_robot_type = default_robot_type
        self.timeout = timeout
        self.base_url = f"http://{self.ip}:{self.port}/kc/mrc"

    def _request(self, method: str, path: str, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """统一 HTTP 请求派发函数，包含 AppCode 认证与异常处理"""
        url = f"{self.base_url}{path}?AppCode={self.app_code}"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        
        try:
            if method.upper() == "GET":
                resp = requests.get(url, headers=headers, timeout=self.timeout)
            else:
                resp = requests.post(url, headers=headers, json=json_data or {}, timeout=self.timeout)
                
            resp.raise_for_status()
            res_json = resp.json()
            return res_json
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 通信异常 [{method} {path}]: {e}")
            return {"result": -1, "error": f"HTTP 通信失败: {str(e)}"}
        except Exception as e:
            logger.error(f"❌ 报文解析异常 [{method} {path}]: {e}")
            return {"result": -1, "error": f"报文解析异常: {str(e)}"}

    def get_info(self) -> Dict[str, Any]:
        """获取控制器接口信息"""
        return self._request("GET", "/info")

    def get_status(self) -> Dict[str, Any]:
        """获取机器人导航运行状态 (包含 mode, chassis, battery, map, localization, navigation)"""
        return self._request("GET", "/status")

    def set_push_settings(self, status_push_url: str, status_push_cycle: float = 0.5) -> Dict[str, Any]:
        """
        修改主动推送设置 (文档 4.2.1)
        :param status_push_url: 机器人运行状态主动推送 URL
        :param status_push_cycle: 周期 s (0.1 ~ 10)
        """
        payload = {
            "status_push_url": status_push_url,
            "status_push_cycle": float(status_push_cycle)
        }
        return self._request("POST", "/setting/set", payload)

    def set_mode(self, mode: str) -> Dict[str, Any]:
        """切换运行模式: MANU (手动模式) / AUTO (自动模式)"""
        return self._request("POST", "/mode/set", {"mode": mode.upper()})

    def manual_control(self, speed_x: float, speed_y: float = 0.0, speed_theta: float = 0.0) -> Dict[str, Any]:
        """足式机器人手动遥控 (速度单位 m/s, 角速度 rad/s)"""
        payload = {
            "speed_x": float(speed_x),
            "speed_y": float(speed_y),
            "speed_theta": float(speed_theta)
        }
        return self._request("POST", "/control/speed", payload)

    def set_position(self, point_id: int = 0, x: float = 0.0, y: float = 0.0, theta: float = 0.0) -> Dict[str, Any]:
        """手动设置机器人定位位置 (需在手动模式下)"""
        payload = {
            "point_id": int(point_id),
            "x": float(x),
            "y": float(y),
            "theta": float(theta)
        }
        return self._request("POST", "/position/set", payload)

    def start_nav(self, type_val: int = 0, goal_point: Optional[int] = None,
                  path_start_id: Optional[int] = None, path_end_id: Optional[int] = None,
                  goal_x: Optional[float] = None, goal_y: Optional[float] = None, goal_theta: Optional[float] = None,
                  assigned_path: Optional[list] = None, forbidden_path: Optional[list] = None) -> Dict[str, Any]:
        """
        启动机器人导航命令 (需在自动模式下)
        :param type_val: 0-导航到路径点, 1-导航到路径上的点
        """
        payload = {"type": type_val}
        if goal_point is not None: payload["goal_point"] = int(goal_point)
        if path_start_id is not None: payload["path_start_id"] = int(path_start_id)
        if path_end_id is not None: payload["path_end_id"] = int(path_end_id)
        if goal_x is not None: payload["goal_x"] = float(goal_x)
        if goal_y is not None: payload["goal_y"] = float(goal_y)
        if goal_theta is not None: payload["goal_theta"] = float(goal_theta)
        if assigned_path is not None: payload["assigned_path"] = assigned_path
        if forbidden_path is not None: payload["forbidden_path"] = forbidden_path

        return self._request("POST", "/navigation/start", payload)

    def pause_nav(self) -> Dict[str, Any]:
        """暂停导航"""
        return self._request("POST", "/navigation/pause")

    def resume_nav(self) -> Dict[str, Any]:
        """继续导航"""
        return self._request("POST", "/navigation/resume")

    def abort_nav(self) -> Dict[str, Any]:
        """取消/打断导航"""
        return self._request("POST", "/navigation/abort")

    def return_to_path(self) -> Dict[str, Any]:
        """从路径外自动切回返回路径"""
        return self._request("POST", "/navigation/return_to_path")

    def set_gait(self, gait_index: int, robot_type: Optional[int] = None) -> Dict[str, Any]:
        """切换足式机器人步态 (如平地/楼梯/灵动等)"""
        r_type = robot_type if robot_type is not None else self.default_robot_type
        payload = {
            "robot_type": int(r_type),
            "gait_index": int(gait_index)
        }
        return self._request("POST", "/gait", payload)

    def execute_motion(self, motion_cmd: int, motion_index: Optional[int] = None, robot_type: Optional[int] = None) -> Dict[str, Any]:
        """
        执行足式机器人动作
        :param motion_cmd: 0-无效, 1-进入充电, 2-退出充电, 100-自定义动作
        :param motion_index: 动作编号 (趴下/站立等)
        """
        r_type = robot_type if robot_type is not None else self.default_robot_type
        payload = {"motion_cmd": int(motion_cmd)}
        if r_type is not None: payload["robot_type"] = int(r_type)
        if motion_index is not None: payload["motion_index"] = int(motion_index)

        return self._request("POST", "/motion", payload)

    def jerk_stop(self, jerk: bool = True) -> Dict[str, Any]:
        """急停请求：true-进入机器人本体阻尼状态, false-退出阻尼状态"""
        return self._request("POST", "/jerk", {"jerk": bool(jerk)})
