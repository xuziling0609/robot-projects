import json
import time
import requests
import threading
import logging
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==================== 日志配置 ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] [Nav-Sim] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("NavSimulator")

class NavControllerState:
    """激光导航控制器虚拟物理引擎与状态管理"""
    def __init__(self):
        self.lock = threading.Lock()
        self.mode = "AUTO"
        self.battery_power = 0.95
        self.charging = False
        self.last_battery_time = time.time()

        # 底盘与定位信息
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        self.velocity = 0.0
        self.velocity_angle = 0.0
        self.blocked = False

        # 导航状态
        self.nav_status = "IDLE"  # IDLE, RUNNING, PAUSED, FINISH, FAILED, ABORTED
        self.goal_point = None
        self.goal_x = 0.0
        self.goal_y = 0.0

        # 足式机器人特有
        self.robot_type = 513  # 0x201 = 宇树 Go2
        self.gait_index = 1   # 1 = 平地
        self.motion_cmd = 0
        self.motion_index = 12 # 12 = 站立
        self.jerk_stop = False

        # 主动推送配置
        self.status_push_url = ""
        self.status_push_cycle = 0.5

    def set_blocked(self, blocked: bool):
        """设置底盘受阻状态"""
        with self.lock:
            self.blocked = bool(blocked)

    def set_charging(self, is_charging: bool, power: float = None):
        """设置充电/放电状态及可选初始电量"""
        with self.lock:
            self.charging = bool(is_charging)
            if power is not None:
                self.battery_power = max(0.0, min(1.0, float(power)))
            self.last_battery_time = time.time()

    def update_battery(self):
        """根据当前充电/放电状态模拟电量微变化"""
        with self.lock:
            now = time.time()
            elapsed = now - getattr(self, "last_battery_time", now)
            self.last_battery_time = now
            if elapsed <= 0:
                return

            if self.charging:
                # 充电中：电量逐渐上升 (每秒约 0.2%)
                self.battery_power = min(1.0, self.battery_power + elapsed * 0.002)
            else:
                # 放电中：运行状态下耗电快，空闲下耗电慢
                drain_rate = 0.0002 if self.nav_status == "RUNNING" else 0.00005
                self.battery_power = max(0.05, self.battery_power - elapsed * drain_rate)

    def to_status_json(self) -> dict:
        self.update_battery()
        with self.lock:
            return {
                "result": 0,
                "error": "",
                "mode": self.mode,
                "chassis": {
                    "velocity": self.velocity,
                    "velocity_angle": self.velocity_angle,
                    "blocked": self.blocked,
                    "odom": 120.5,
                    "time": 3600.0
                },
                "battery": {
                    "power": round(self.battery_power, 4),
                    "percentage": round(self.battery_power * 100, 2),
                    "charging": self.charging,
                    "is_charging": self.charging,
                    "voltage": round(27.2 if self.charging else 24.8 + self.battery_power * 0.4, 2),
                    "current": round(-5.0 if self.charging else 1.2, 2)
                },
                "map": {
                    "name": "building_1_f3",
                    "width": 1000,
                    "height": 1000,
                    "origin_x": -25.0,
                    "origin_y": -25.0,
                    "resolution": 0.05
                },
                "localization": {
                    "status": "OK",
                    "confidence": 0.99,
                    "x": self.x,
                    "y": self.y,
                    "theta": self.theta,
                    "point_id": self.goal_point or 0
                },
                "navigation": {
                    "status": self.nav_status,
                    "goal": self.goal_point if self.goal_point is not None else 0,
                    "current_goal": self.goal_point if self.goal_point is not None else 0,
                    "goal_point": self.goal_point if self.goal_point is not None else 0,
                    "target_x": self.goal_x,
                    "target_y": self.goal_y,
                    "remaining_distance": 0.0 if self.nav_status == "FINISH" else 5.2,
                    "remaining_time": 0.0 if self.nav_status == "FINISH" else 10.0
                },
                "quadruped": {
                    "robot_type": self.robot_type,
                    "gait_index": self.gait_index,
                    "motion_cmd": self.motion_cmd,
                    "motion_index": self.motion_index,
                    "jerk_stop": self.jerk_stop
                }
            }

state = NavControllerState()

class NavWebAPIRequestHandler(BaseHTTPRequestHandler):
    """根据《激光导航控制器接口协议》设计的 WebAPI Mock 接收器"""

    def _send_json_response(self, data: dict, status_code=200):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        logger.info(f"📥 [NavSimulator HTTP GET] {path} | Query: {query_params}")

        # 4.1 获取接口信息
        if path == "/kc/mrc/info":
            self._send_json_response({
                "result": 0,
                "error": "",
                "firmware": "v2.1.0-Release",
                "device_id": "KC_NAV_CONTROLLER_888",
                "uptime": 120500
            })

        # 4.2 获取实时状态
        elif path == "/kc/mrc/status":
            self._send_json_response(state.to_status_json())

        # 4.2.2 充放电快捷控制与电量查询/设置 (GET 调试支持)
        elif path in ["/kc/mrc/battery/set", "/kc/mrc/charge/set", "/kc/mrc/charge", "/kc/mrc/discharge"]:
            is_charging = None
            if path == "/kc/mrc/discharge":
                is_charging = False
            elif path == "/kc/mrc/charge" and not query_params:
                is_charging = True

            if "charging" in query_params:
                val = query_params["charging"][0].lower()
                is_charging = val in ["true", "1", "yes", "on"]
            elif "action" in query_params:
                act = query_params["action"][0].lower()
                if act in ["charge", "start", "start_charge", "on", "1"]:
                    is_charging = True
                elif act in ["discharge", "stop", "stop_charge", "off", "0"]:
                    is_charging = False

            power = None
            if "power" in query_params:
                try:
                    power = float(query_params["power"][0])
                except Exception:
                    pass
            elif "percentage" in query_params:
                try:
                    power = float(query_params["percentage"][0]) / 100.0
                except Exception:
                    pass

            if is_charging is not None or power is not None:
                if is_charging is not None:
                    state.set_charging(is_charging, power=power)
                elif power is not None:
                    state.set_charging(state.charging, power=power)
                state_str = "充电中" if state.charging else "放电中"
                logger.info(f"  └─ ⚡ [NavSimulator GET] 切换电池充放电状态 -> [{state_str}], 当前电量={round(state.battery_power*100, 1)}%")

            self._send_json_response({
                "result": 0,
                "error": "",
                "battery": {
                    "power": round(state.battery_power, 4),
                    "percentage": round(state.battery_power * 100, 2),
                    "charging": state.charging,
                    "is_charging": state.charging
                }
            })

        # 4.2.3 底盘状态设置 (GET 调试支持)
        elif path in ["/kc/mrc/chassis/set", "/kc/mrc/blocked/set"]:
            if "blocked" in query_params:
                val = query_params["blocked"][0].lower()
                state.set_blocked(val in ["true", "1", "yes", "on"])
            logger.info(f"  └─ 🚧 [NavSimulator GET] 切换底盘受阻状态 -> [{state.blocked}]")
            self._send_json_response({
                "result": 0,
                "error": "",
                "chassis": {
                    "blocked": state.blocked
                }
            })

        else:
            self._send_json_response({"result": 1, "error": f"未知 GET 接口: {path}"}, 404)

    def do_POST(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            body = json.loads(body_bytes.decode("utf-8"))
        except Exception as e:
            logger.error('操作引发异常:', exc_info=True)
            body = {}

        logger.info(f"📥 [NavSimulator HTTP POST] {path} | Body: {body}")

        # 4.2.1 配置主动推送
        if path == "/kc/mrc/setting/set":
            url = body.get("status_push_url", "")
            cycle = body.get("status_push_cycle", 0.5)
            state.status_push_url = url
            state.status_push_cycle = cycle
            logger.info(f"  └─ ⚙️ 已更新主动推送配置: url={url}, cycle={cycle}s")
            self._send_json_response({"result": 0, "error": ""})

        # 4.3 模式设置
        elif path == "/kc/mrc/mode/set":
            mode = body.get("mode", "AUTO")
            state.mode = mode
            logger.info(f"  └─ 🔄 切换模式为: {mode}")
            self._send_json_response({"result": 0, "error": ""})

        # 4.7 足式机器人手动遥控 (速度命令)
        elif path == "/kc/mrc/control/speed":
            if state.mode != "MANU":
                logger.warning(f"  └─ ⚠️ 手动遥控失败: 机器人当前处于 [{state.mode}] 模式，未处于手动模式 (code=128)")
                self._send_json_response({"result": 128, "error": "机器人未处于手动模式"}, 200)
                return

            speed_x = float(body.get("speed_x", 0.0))
            speed_y = float(body.get("speed_y", 0.0))
            speed_theta = float(body.get("speed_theta", 0.0))
            with state.lock:
                state.velocity = speed_x
                state.velocity_angle = speed_theta
            logger.info(f"  └─ 🕹️ 收到手动遥控速度: speed_x={speed_x} m/s, speed_y={speed_y} m/s, speed_theta={speed_theta} rad/s")
            self._send_json_response({"result": 0, "error": ""})

        # 4.8 手动设置机器人位置
        elif path == "/kc/mrc/position/set":
            point_id = body.get("point_id", 0)
            x = float(body.get("x", 0.0))
            y = float(body.get("y", 0.0))
            theta = float(body.get("theta", 0.0))
            with state.lock:
                state.x = x
                state.y = y
                state.theta = theta
                if point_id != 0:
                    state.goal_point = point_id
            logger.info(f"  └─ 📍 手动设置机器人位置: point_id={point_id}, x={x}, y={y}, theta={theta}")
            self._send_json_response({"result": 0, "error": ""})

        # 4.13 从路径外返回路径
        elif path == "/kc/mrc/navigation/return_to_path":
            state.nav_status = "RUNNING"
            logger.info("  └─ 🔄 收到从路径外返回路径指令 (return_to_path)")
            self._send_json_response({"result": 0, "error": ""})

        # 4.10 开启导航
        elif path == "/kc/mrc/navigation/start":
            goal = body.get("goal_point") if body.get("goal_point") is not None else body.get("goal")
            try:
                state.goal_point = int(goal) if goal is not None else None
            except Exception as e:
                logger.error('操作引发异常:', exc_info=True)
                state.goal_point = goal
            state.goal_x = body.get("goal_x", 0.0)
            state.goal_y = body.get("goal_y", 0.0)
            state.nav_status = "RUNNING"
            logger.info(f"  └─ 🚀 导航已启动 -> 目标点 [{state.goal_point}]，开启模拟位移与到达逻辑...")

            def simulate_nav_journey(target_goal):
                time.sleep(1.0)
                with state.lock:
                    state.nav_status = "FINISH"
                    if isinstance(target_goal, (int, float)):
                        state.x = float(target_goal * 1.5)
                        state.y = float(target_goal * 2.0)
                logger.info(f"  └─ 🎯 模拟器: 机器人已到位目标点 [{target_goal}]，nav_status 已切为 FINISH！")

            threading.Thread(target=simulate_nav_journey, args=(state.goal_point,), daemon=True).start()
            self._send_json_response({"result": 0, "error": ""})

        # 4.11 暂停导航
        elif path == "/kc/mrc/navigation/pause":
            state.nav_status = "PAUSED"
            logger.info("  └─ ⏸️ 导航已暂停 (PAUSED)")
            self._send_json_response({"result": 0, "error": ""})

        # 4.12 恢复导航
        elif path == "/kc/mrc/navigation/resume":
            state.nav_status = "RUNNING"
            logger.info("  └─ ▶️ 导航已恢复 (RUNNING)")
            self._send_json_response({"result": 0, "error": ""})

        # 4.13 终止导航
        elif path == "/kc/mrc/navigation/abort":
            state.nav_status = "ABORTED"
            logger.info("  └─ 🛑 导航已取消打断 (ABORTED)")
            self._send_json_response({"result": 0, "error": ""})

        # 4.16 步态切换
        elif path == "/kc/mrc/gait":
            gait = body.get("gait_index")
            state.gait_index = gait
            logger.info(f"  └─ 🦿 切换足式步态 -> [{gait}]")
            self._send_json_response({"result": 0, "error": ""})

        # 4.17 动作执行 (包括进入充电 / 退出充电)
        elif path == "/kc/mrc/motion":
            cmd = body.get("motion_cmd")
            idx = body.get("motion_index")
            state.motion_cmd = cmd
            state.motion_index = idx

            # 切换充电/放电 (1: 进入充电, 2: 退出充电)
            if cmd == 1:
                state.set_charging(True)
                logger.info("  └─ ⚡ [NavSimulator] 收到进入充电指令 (motion_cmd=1) -> 切换为 [充电中] 状态")
            elif cmd == 2:
                state.set_charging(False)
                logger.info("  └─ 🔋 [NavSimulator] 收到退出充电指令 (motion_cmd=2) -> 切换为 [放电中] 状态")
            else:
                logger.info(f"  └─ 🧍 触发足式动作 -> cmd={cmd}, index={idx}")

            self._send_json_response({"result": 0, "error": ""})

        # 4.18 阻尼急停
        elif path == "/kc/mrc/jerk":
            jerk = body.get("jerk", True)
            state.jerk_stop = jerk
            logger.info(f"  └─ 🚨 阻尼急停请求 -> jerk={jerk}")
            self._send_json_response({"result": 0, "error": ""})

        # 4.19 (扩展) 充放电快捷控制与电量修改
        elif path in ["/kc/mrc/battery/set", "/kc/mrc/charge/set", "/kc/mrc/charge", "/kc/mrc/discharge"]:
            is_charging = body.get("charging")
            if path == "/kc/mrc/discharge":
                is_charging = False
            elif path == "/kc/mrc/charge" and not body:
                is_charging = True

            action = str(body.get("action", "")).lower()
            if action in ["charge", "start", "start_charge", "on", "1"]:
                is_charging = True
            elif action in ["discharge", "stop", "stop_charge", "off", "0"]:
                is_charging = False

            power = body.get("power")
            if power is None and "percentage" in body:
                try:
                    power = float(body.get("percentage")) / 100.0
                except Exception:
                    pass

            if is_charging is not None or power is not None:
                if is_charging is not None:
                    state.set_charging(bool(is_charging), power=power)
                elif power is not None:
                    state.set_charging(state.charging, power=power)
                state_str = "充电中" if state.charging else "放电中"
                logger.info(f"  └─ ⚡ [NavSimulator POST] 切换电池充放电状态 -> [{state_str}], 当前电量={round(state.battery_power*100, 1)}%")

            self._send_json_response({
                "result": 0,
                "error": "",
                "battery": {
                    "power": round(state.battery_power, 4),
                    "percentage": round(state.battery_power * 100, 2),
                    "charging": state.charging,
                    "is_charging": state.charging
                }
            })

        # 4.20 (扩展) 底盘状态设置
        elif path in ["/kc/mrc/chassis/set", "/kc/mrc/blocked/set"]:
            if "blocked" in body:
                state.set_blocked(bool(body.get("blocked")))
            logger.info(f"  └─ 🚧 [NavSimulator POST] 切换底盘受阻状态 -> [{state.blocked}]")
            self._send_json_response({
                "result": 0,
                "error": "",
                "chassis": {
                    "blocked": state.blocked
                }
            })

        else:
            self._send_json_response({"result": 1, "error": f"未知 POST 接口: {path}"}, 404)

    def log_message(self, format, *args):
        pass

def status_push_loop():
    """按文档 4.2.1 向 status_push_url 持续 HTTP POST 主动推送状态的后台线程"""
    while True:
        url = state.status_push_url
        cycle = state.status_push_cycle

        if url:
            try:
                status_payload = state.to_status_json()
                requests.post(url, json=status_payload, timeout=2.0)
            except Exception as e:
                logger.warning(f"⚠️ 导航状态主动推送失败 [{url}]: {e}")

        time.sleep(cycle)

def start_nav_simulator(host="0.0.0.0", port=17808):
    logger.info("=" * 70)
    logger.info("🤖 导航控制器 xRobotWebAPI (V2.1) 模拟服务启动中...")
    logger.info(f"📡 服务监听地址: http://{host}:{port}/kc/mrc/")
    logger.info("支持接口: status, setting/set, mode/set, navigation/start, gait, motion, jerk 等")
    logger.info("=" * 70)

    threading.Thread(target=status_push_loop, daemon=True).start()

    server = HTTPServer((host, port), NavWebAPIRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("🛑 导航模拟器接收到终止信号，正在安全退出...")
        server.server_close()

if __name__ == "__main__":
    start_nav_simulator()
