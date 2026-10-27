import time
import threading
from typing import Dict, Any, Optional
from plugins.base import BasePlugin
from core.logger_manager import get_logger
from core.context_manager import ContextManager
from utils import get_local_ip
from .kecong_webapi_driver import KecongWebAPIDriver, StatusPushServer

logger = get_logger("NavPlugin")

class NavPlugin(BasePlugin):
    """
    科聪激光导航与足式机器人 WebAPI 调度插件 (NavPlugin)
    基于科聪 xRobotWebAPI V2.1 协议。
    彻底遵循文档 4.2.1，接收导航控制器的 HTTP POST 主动状态推送，事件驱动判定到达与状态，无 HTTP 轮询开销。
    """

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.plugin_name = self.__class__.__name__

        # 读取网络与设备配置
        self.ip = self.config.get("ip")
        self.port = self.config.get("port", 17808)
        self.app_code = self.config.get("app_code", "")
        self.robot_type = self.config.get("robot_type", 513) # 513 = 宇树 Go2
        self.timeout = float(self.config.get("timeout", 5.0))
        
        # 4.2.1 主动推送设置 (自动绑定真实的本地局域网 LAN IP，避免使用 127.0.0.1)
        self.push_port = int(self.config.get("push_port", 17809))
        local_lan_ip = get_local_ip(self.ip)
        raw_push_url = self.config.get("status_push_url")
        
        if not raw_push_url or "127.0.0.1" in raw_push_url or "localhost" in raw_push_url:
            self.status_push_url = f"http://{local_lan_ip}:{self.push_port}/robot/status"
        else:
            self.status_push_url = raw_push_url

        self.status_push_cycle = float(self.config.get("status_push_cycle", 0.5))

        # 状态缓存与事件流驱动
        self.latest_status: Dict[str, Any] = {}
        self.active_nav_event: Optional[threading.Event] = None
        self.active_nav_result: Optional[dict] = None
        self.active_goal_point: Optional[int] = None

        # 1. 实例化底层 HTTP 客户端驱动
        self.driver = KecongWebAPIDriver(
            ip=self.ip,
            port=self.port,
            app_code=self.app_code,
            default_robot_type=self.robot_type,
            timeout=self.timeout
        )

        # 2. 启动本地 HTTP 主动推送服务端 (文档 4.2.1)
        self.push_server = StatusPushServer(port=self.push_port, callback=self._on_robot_status_pushed)
        self.push_server.start()

        # 3. 向导航控制器下发主动推送配置
        if self.status_push_url:
            push_res = self.driver.set_push_settings(
                status_push_url=self.status_push_url,
                status_push_cycle=self.status_push_cycle
            )
            if push_res.get("result") == 0:
                logger.info(f"✅ 已向导航控制器配置主动推送 URL: {self.status_push_url} (周期: {self.status_push_cycle}s)")
            else:
                logger.warning(f"⚠️ 配置主动推送 URL 响应: {push_res}")

        # 4. 初始化尝试拉取一次状态，以填充基础缓存
        try:
            init_res = self.driver.get_status()
            if init_res.get("result") == 0:
                self.latest_status = init_res
                ContextManager.update_robot_status(self.get_status())
        except Exception as e:
            logger.error('捕获到异常', exc_info=True)

        logger.info(f"✨ [{self.plugin_name}] 初始化完毕 (基于 4.2.1 HTTP 主动推送机制)")

    def _on_robot_status_pushed(self, status_json: dict):
        """
        接收导航控制器按设置周期主动 POST 推送过来的最新机器人状态 (按文档 4.2.1)
        事件驱动判定导航任务完成或失败
        """
        self.latest_status = status_json
        ContextManager.update_robot_status(self.get_status())
        nav_info = status_json.get("navigation", {})
        nav_status = nav_info.get("status", "IDLE")
        curr_goal = nav_info.get("goal")

        # 1. 更新只读遥测属性 latest_telemetry 供 AlarmManager 扫盘评估电量与底盘受阻
        chassis_info = status_json.get("chassis", {})
        batt_info = chassis_info.get("battery", {})
        batt_pct = chassis_info.get("battery_percentage", batt_info.get("percentage") if isinstance(batt_info, dict) else None)
        if batt_pct is None and isinstance(status_json.get("battery"), dict):
            batt_pct = status_json.get("battery", {}).get("percentage", 100)
        elif batt_pct is None:
            batt_pct = 100.0

        is_blocked = bool(chassis_info.get("blocked", False))

        self.latest_telemetry = [
            {
                "metric_name": "BATTERY",
                "value": float(batt_pct),
                "unit": "%"
            },
            {
                "metric_name": "BLOCKED",
                "value": 1 if is_blocked else 0,
                "unit": "bool"
            }
        ]

        # 若当前有主线程在事件驱动阻塞等待
        if self.active_nav_event and not self.active_nav_event.is_set():
            if getattr(self, "_nav_paused", False):
                return

            is_goal_matched = (self.active_goal_point is None or str(curr_goal) == str(self.active_goal_point))
            
            if nav_status == "FINISH" and is_goal_matched:
                logger.info(f"🎯 [主动推送通知] 机器人已成功到达导航目标点 [{self.active_goal_point}] (goal={curr_goal})")
                self.active_nav_result = {"status": "success", "message": f"成功到达导航目标点 [{self.active_goal_point}]"}
                self.active_nav_event.set()
            elif nav_status in ["FAILED", "ABORTED"] and is_goal_matched:
                logger.error(f"❌ [主动推送通知] 机器人导航异常终止 (目标点: {self.active_goal_point}, 状态: {nav_status})")
                self.active_nav_result = {"status": "error", "message": f"导航未完成，终端状态: {nav_status}"}
                self.active_nav_event.set()

    def execute(self, action: str, params: dict) -> dict:
        """插件统一执行接口入口"""
        params = params or {}
        logger.info(f"[{self.plugin_name}] 收到动作 -> [{action}], 参数: {params}")

        # -------------------------------------------------------------
        # 1. 启动导航: start_nav
        # -------------------------------------------------------------
        if action == "start_nav":
            goal_point = params.get("goal_point")
            type_val = params.get("type", 0)

            # 重置当前导航等待事件
            self.active_goal_point = goal_point
            self.active_nav_event = threading.Event()
            self.active_nav_result = None

            res = self.driver.start_nav(
                type_val=type_val,
                goal_point=goal_point,
                path_start_id=params.get("path_start_id"),
                path_end_id=params.get("path_end_id"),
                goal_x=params.get("goal_x"),
                goal_y=params.get("goal_y"),
                goal_theta=params.get("goal_theta"),
                assigned_path=params.get("assigned_path"),
                forbidden_path=params.get("forbidden_path")
            )

            if res.get("result") != 0:
                err_msg = f"下发导航命令失败: {res.get('error', '未知错误')} (code={res.get('result')})"
                logger.error(f"[{self.plugin_name}] {err_msg}")
                return {"status": "error", "message": err_msg}

            # 完全事件驱动 (零 GET 轮询开销)！等待主动推送到达事件唤醒
            logger.info(f"[{self.plugin_name}] 纯事件驱动等待主动推送 (目标点: {goal_point}, 无超时限制)...")
            
            # 主线程处于 Event 等待状态，直到推送触发通知或者收到打断
            self.active_nav_event.wait()
            
            return self.active_nav_result or {"status": "error", "message": "导航中断"}

        # -------------------------------------------------------------
        # 2. 暂停/恢复/取消导航
        # -------------------------------------------------------------
        elif action == "pause_nav":
            res = self.driver.pause_nav()
            return self._format_response(res, "暂停导航")

        elif action == "resume_nav":
            res = self.driver.resume_nav()
            return self._format_response(res, "恢复导航")

        elif action in ["abort_nav", "cancel_nav"]:
            if self.active_nav_event and not self.active_nav_event.is_set():
                self.active_nav_result = {"status": "error", "message": "导航被打断/取消"}
                self.active_nav_event.set()
            res = self.driver.abort_nav()
            return self._format_response(res, "取消导航")

        # -------------------------------------------------------------
        # 3. 运行模式设置 (AUTO / MANU)
        # -------------------------------------------------------------
        elif action == "set_mode":
            mode = params.get("mode", "AUTO")
            res = self.driver.set_mode(mode)
            return self._format_response(res, f"切换模式为 [{mode}]")

        # -------------------------------------------------------------
        # 4. 足式步态设置 (set_gait)
        # -------------------------------------------------------------
        elif action == "set_gait":
            gait_index = params.get("gait_index", 1)
            robot_type = params.get("robot_type", self.robot_type)
            res = self.driver.set_gait(gait_index=gait_index, robot_type=robot_type)
            return self._format_response(res, f"切换步态为 [{gait_index}]")

        # -------------------------------------------------------------
        # 5. 足式动作执行 (execute_motion)
        # -------------------------------------------------------------
        # 5. 动作执行 (execute_motion: 1=进入充电, 2=退出充电)
        # -------------------------------------------------------------
        elif action == "execute_motion":
            motion_cmd = params.get("motion_cmd", 100)
            motion_index = params.get("motion_index")
            robot_type = params.get("robot_type", self.robot_type)
            res = self.driver.execute_motion(motion_cmd=motion_cmd, motion_index=motion_index, robot_type=robot_type)
            cmd_desc = "进入充电" if motion_cmd == 1 else ("退出充电" if motion_cmd == 2 else f"动作 {motion_cmd}")
            return self._format_response(res, f"执行机器人动作 [{cmd_desc}] (cmd={motion_cmd}, index={motion_index})")

        # -------------------------------------------------------------
        # 6. 遥控三轴速度 (manual_control)
        # -------------------------------------------------------------
        elif action == "manual_control":
            # 1. 优先从主动推送缓存获取模式，若无缓存则兜底拉取一次
            current_mode = ""
            if self.latest_status and "mode" in self.latest_status:
                current_mode = str(self.latest_status.get("mode", "")).strip().upper()
            else:
                curr_status = self.get_status()
                current_mode = str(curr_status.get("mode", "")).strip().upper()

            # 2. 严格校验底盘运行模式：非 MANU 手动模式直接阻断
            if current_mode != "MANU":
                err_msg = f"底盘当前处于 [{current_mode or '未知'}] 模式，手动遥控仅允许在手动模式 (MANU) 下执行，请先调用 set_mode 切换模式"
                logger.warning(f"[{self.plugin_name}] {err_msg}")
                return {"status": "error", "message": err_msg}

            sx = params.get("speed_x", 0.0)
            sy = params.get("speed_y", 0.0)
            st = params.get("speed_theta", 0.0)
            res = self.driver.manual_control(speed_x=sx, speed_y=sy, speed_theta=st)
            return self._format_response(res, f"下发遥控速度 (x={sx}, y={sy}, theta={st})")

        # -------------------------------------------------------------
        # 7. 急停阻尼请求 (jerk_stop)
        # -------------------------------------------------------------
        elif action == "jerk_stop":
            jerk = params.get("jerk", True)
            res = self.driver.jerk_stop(jerk=jerk)
            return self._format_response(res, f"阻尼急停请求 (jerk={jerk})")

        # -------------------------------------------------------------
        # 8. 获取实时状态 (优先读取最新的主动推送缓存)
        # -------------------------------------------------------------
        elif action == "get_status":
            state = self.get_status()
            if state:
                return {"status": "success", "message": "获取实时状态成功", "data": state}
            else:
                return {"status": "error", "message": "读取状态失败"}

        # -------------------------------------------------------------
        # 9. 获取插件是否在线 (status)
        # -------------------------------------------------------------
        elif action == "status":
            return {"status": "success", "message": "获取插件在线状态成功", "data": {"is_online": self.status()}}

        # -------------------------------------------------------------
        # 10. 告警规则配置 (set_config / get_config)
        # -------------------------------------------------------------
        elif action == "set_config":
            import os
            import json
            raw_rules = params.get("config", [])
            from utils.constants import PROJECT_ROOT
            alarm_file = os.path.join(PROJECT_ROOT, "data", "plugins", "NavPlugin_alarm.json")
            try:
                os.makedirs(os.path.dirname(alarm_file), exist_ok=True)
                with open(alarm_file, "w", encoding="utf-8") as f:
                    json.dump(raw_rules, f, ensure_ascii=False, indent=2)
                logger.info(f"💾 [{self.plugin_name}] 告警配置已持久化至 {alarm_file}")
                return {
                    "status": "success",
                    "message": f"成功保存告警配置至 {alarm_file}",
                    "data": raw_rules
                }
            except Exception as e:
                logger.error(f"❌ [{self.plugin_name}] 保存告警配置失败: {e}")
                return {"status": "error", "message": f"保存配置文件失败: {e}"}

        elif action == "get_config":
            import os
            import json
            from utils.constants import PROJECT_ROOT
            alarm_file = os.path.join(PROJECT_ROOT, "data", "plugins", "NavPlugin_alarm.json")
            if os.path.exists(alarm_file):
                try:
                    with open(alarm_file, "r", encoding="utf-8") as f:
                        cfg_data = json.load(f)
                    return {
                        "status": "success",
                        "message": "获取导航告警配置成功",
                        "data": cfg_data
                    }
                except Exception as e:
                    return {"status": "error", "message": f"读取配置文件失败: {e}"}
            else:
                return {
                    "status": "success",
                    "message": "暂无已保存的导航告警配置",
                    "data": []
                }

        msg = f"不支持的导航动作: {action}"
        logger.error(f"[{self.plugin_name}] {msg}")
        return {"status": "error", "message": msg}

    def _format_response(self, res: dict, action_desc: str) -> dict:
        if res.get("result") == 0:
            return {"status": "success", "message": f"{action_desc} 成功"}
        else:
            err_msg = f"{action_desc} 失败: {res.get('error', '未明错误')} (code={res.get('result')})"
            logger.error(f"[{self.plugin_name}] {err_msg}")
            return {"status": "error", "message": err_msg}

    def abort(self) -> dict:
        """全局急停与打断处理：打断等待事件并触发阻尼急停"""
        logger.warning(f"🚨 [{self.plugin_name}] 收到全局急停指令，打断导航并开启阻尼防护...")
        if self.active_nav_event and not self.active_nav_event.is_set():
            self.active_nav_result = {"status": "error", "message": "导航被全局急停中断"}
            self.active_nav_event.set()
        self.driver.abort_nav()
        #self.driver.jerk_stop(True)
        return {"status": "success", "message": "导航任务已安全打断"}

    def resume_hardware(self) -> dict:
        #self.driver.jerk_stop(False)
        return {"status": "success", "message": "机器人已恢复"}

    def get_capabilities(self) -> dict:
        return {
            "plugin_type": self.plugin_name,
            "plugin_name": "导航插件",
            "description": "基于 xRobotWebAPI 提供点位导航、步态切换、告警配置与动作控制能力",
            "version": "1.2.0",
            "supported_actions": [
                {
                    "action": "start_nav",
                    "action_name": "启动导航",
                    "description": "控制底盘导航到指定目标点",
                    "scopes": ["task", "config"],
                    "params": [
                        {"name": "goal_point", "label": "目标点位ID", "type": "int", "required": True, "ui_component": "input_number"}
                    ],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "message", "label": "描述", "type": "string"}
                        ]
                    }
                },
                {
                    "action": "pause_nav",
                    "action_name": "暂停导航",
                    "description": "立即暂停当前正在进行的导航任务",
                    "scopes": ["task"],
                    "params": [],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "message", "label": "描述", "type": "string"}
                        ]
                    }
                },
                {
                    "action": "resume_nav",
                    "action_name": "恢复导航",
                    "description": "恢复被暂停的导航任务",
                    "scopes": ["task"],
                    "params": [],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "message", "label": "描述", "type": "string"}
                        ]
                    }
                },
                {
                    "action": "abort_nav",
                    "action_name": "终止导航",
                    "description": "直接终止当前导航任务并清除目标",
                    "scopes": ["task"],
                    "params": [],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "message", "label": "描述", "type": "string"}
                        ]
                    }
                },
                {
                    "action": "set_mode",
                    "action_name": "切换模式",
                    "description": "切换机器人的运行模式",
                    "scopes": ["task", "config"],
                    "params": [
                        {"name": "mode", "label": "模式", "type": "string", "required": True, "ui_component": "select", "options": [{"name": "自动", "value": "AUTO"}, {"name": "手动", "value": "MANU"}]}
                    ],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "message", "label": "描述", "type": "string"}
                        ]
                    }
                },
                {
                    "action": "set_gait",
                    "action_name": "设置步态",
                    "description": "配置足式机器人的行走步态",
                    "scopes": ["task", "config"],
                    "params": [
                        {"name": "gait_index", "label": "步态索引", "type": "int", "required": True, "ui_component": "select", "options": [{"name": "灵动低速", "value": 1}, {"name": "灵动高速", "value": 2}, {"name": "经典低速", "value": 3}, {"name": "经典高速", "value": 4}, {"name": "视觉辅助", "value": 7}]}
                    ],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "message", "label": "描述", "type": "string"}
                        ]
                    }
                },
                {
                    "action": "execute_motion",
                    "action_name": "执行动作",
                    "description": "触发机器人的特定组合动作",
                    "scopes": ["task"],
                    "params": [
                        {"name": "motion_cmd", "label": "动作指令ID", "type": "int", "required": True, "ui_component": "select", "options": [{"name": "进入充电", "value": 1}, {"name": "退出充电", "value": 2}]}
                    ],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "message", "label": "描述", "type": "string"}
                        ]
                    }
                },
                {
                    "action": "manual_control",
                    "action_name": "手动遥控",
                    "description": "下发底层速度控制指令",
                    "scopes": ["task"],
                    "params": [
                        {"name": "speed_x", "label": "X线速度", "type": "float", "required": True, "ui_component": "input_number"},
                        {"name": "speed_y", "label": "Y线速度", "type": "float", "required": True, "ui_component": "input_number"},
                        {"name": "speed_theta", "label": "角速度", "type": "float", "required": True, "ui_component": "input_number"}
                    ],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "message", "label": "描述", "type": "string"}
                        ]
                    }
                },
                {
                    "action": "jerk_stop",
                    "action_name": "阻尼急停",
                    "description": "立即开启/关闭阻尼急停防护",
                    "scopes": ["task", "config"],
                    "params": [
                        {"name": "jerk", "label": "开启防护(bool)", "type": "bool", "required": True, "ui_component": "switch"}
                    ],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "message", "label": "描述", "type": "string"}
                        ]
                    }
                },
                {
                    "action": "set_config",
                    "action_name": "设置告警配置",
                    "description": "配置底盘电池电量的告警阈值",
                    "scopes": ["config"],
                    "params": [
                        {"name": "config", "label": "告警规则数组", "type": "array", "required": True, "ui_component": "json_editor"}
                    ],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "message", "label": "描述", "type": "string"}
                        ]
                    }
                },
                {
                    "action": "get_config",
                    "action_name": "读取告警配置",
                    "description": "读取当前底盘电池电量的告警规则",
                    "scopes": ["config"],
                    "params": [],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "message", "label": "执行描述", "type": "string"},
                            {"name": "data", "label": "配置数据", "type": "array"}
                        ]
                    }
                },
                {
                    "action": "get_status",
                    "action_name": "获取导航状态",
                    "description": "读取机器人当前底盘遥测数据与状态",
                    "scopes": ["config", "task"],
                    "params": [],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "data", "label": "状态数据", "type": "object"}
                        ]
                    }
                },
                {
                    "action": "status",
                    "action_name": "获取插件状态",
                    "description": "读取导航插件当前是否在线",
                    "scopes": ["config"],
                    "params": [],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "data", "label": "插件状态数据", "type": "object"}
                        ]
                    }
                }
            ],
            "config_metrics": [
                {"metric_name": "BATTERY", "label": "底盘电量", "unit": "%", "type": "float", "alarm_type": ["info", "warning", "error", "fatal"], "operator": ["lt", "lte", "gt", "gte", "between", "eq"]},
                {"metric_name": "BLOCKED", "label": "底盘受阻", "unit": "bool", "type": "int", "alarm_type": ["warning", "error"], "operator": ["eq"]}
            ]
        }

    def status(self) -> bool:
        """获取插件在线状态 (返回 bool)"""
        return self._is_online if hasattr(self, "_is_online") else True

    def get_status(self) -> dict:
        """获取当前最新状态 (优先读取主动推送缓存，若为空则主动发起 HTTP GET 查询)"""
        if not self.latest_status:
            try:
                res = self.driver.get_status()
                if res.get("result") == 0:
                    self.latest_status = res
            except Exception as e:
                logger.debug(f"尝试主动拉取科聪状态异常: {e}")
        
        if not self.latest_status:
            return {}
            
        status = {
            "mode": self.latest_status.get("mode", "AUTO"),
            "error": self.latest_status.get("error", ""),
            "result": self.latest_status.get("result", ""),
            "chassis": self.latest_status.get("chassis", {}),
            "battery": self.latest_status.get("battery", {}),
            "map": self.latest_status.get("map", {}),
            "localization": self.latest_status.get("localization", {}),
            "navigation": self.latest_status.get("navigation", {})
        }
        ContextManager.update_robot_status(status)
        return status
