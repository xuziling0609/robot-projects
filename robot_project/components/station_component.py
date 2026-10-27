import time
from typing import Dict, Any, Optional
from core.logger_manager import get_logger
from components.base_component import BaseComponent

logger = get_logger("StationComponent")

class StationComponent(BaseComponent):
    """
    充电站组件
    包含进出充电站的完整业务流。
    出站: 开门 -> 退出充电 -> 导航出站 -> 关门（系统默认/正向配置）
    进站: 导航到门外 -> 开门 -> 导航进站 -> 进入充电 -> 关门
    """
    
    def __init__(self, plugin_manager):
        super().__init__(plugin_manager)
        self.station_plugin = plugin_manager.get_plugin_by_capability("station_control")
        self.nav_plugin = plugin_manager.get_plugin_by_capability("navigation")
        self._internal_state = "IDLE"
        self._current_params = {}
        
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self._is_aborted = False
        self._current_params = params
        
        direction = params.get("direction", "leave")  # 用户只配置出站，默认 leave
        inner_point = params.get("inner_point")
        outer_point = params.get("outer_point")
        ips = params.get("ips")
        
        if inner_point is None or outer_point is None or not ips:
            return {"status": "error", "message": "缺少必填参数: inner_point, outer_point, ips"}
            
        if not self.station_plugin or not self.nav_plugin:
            return {"status": "error", "message": "依赖的底层插件 StationPlugin 或 NavPlugin 未加载"}

        try:
            if direction == "leave":
                return self._execute_leave(inner_point, outer_point, ips)
            elif direction == "enter":
                return self._execute_enter(inner_point, outer_point, ips)
            else:
                return {"status": "error", "message": f"未知的 direction: {direction}"}
        except Exception as e:
            logger.error(f"[{self.component_type}] 执行异常: {e}")
            return {"status": "error", "message": str(e)}

    def _execute_enter(self, inner_point, outer_point, ips):
        # 1. 导航到站外点
        self._internal_state = "NAV_TO_OUTER"
        logger.info(f"[{self.component_type}] [进站] 1. 导航到站外点 {outer_point}")
        res = self.nav_plugin.execute(action="start_nav", params={"goal_point": outer_point})
        if self._check_abort(): return self._handle_abort("任务被打断")
        if res.get("status") != "success": return self._handle_abort("导航异常终止", res)

        # 2. 充电站开门
        self._internal_state = "STATION_OPENING"
        logger.info(f"[{self.component_type}] [进站] 2. 充电站开门 {ips}")
        res = self.station_plugin.execute(action="open", params={"ips": ips})
        if self._check_abort(): return self._handle_abort("充电站开门被打断")
        if res.get("status") != "success": return self._handle_abort("开门异常终止", res)

        # 3. 导航到站内点
        self._internal_state = "NAV_TO_INNER"
        logger.info(f"[{self.component_type}] [进站] 3. 导航到站内点 {inner_point}")
        res = self.nav_plugin.execute(action="start_nav", params={"goal_point": inner_point})
        if self._check_abort(): return self._handle_abort("导航进站被打断")
        if res.get("status") != "success": return self._handle_abort("导航进站异常终止", res)

        # 4. 进入充电
        self._internal_state = "START_CHARGE"
        logger.info(f"[{self.component_type}] [进站] 4. 进入充电 (执行 motion_cmd: 1)")
        res = self.nav_plugin.execute(action="execute_motion", params={"motion_cmd": 1})
        if self._check_abort(): return self._handle_abort("进入充电动作被打断")
        if res.get("status") != "success": return self._handle_abort("充电动作异常终止", res)

        # 5. 充电站关门
        self._internal_state = "STATION_CLOSING"
        logger.info(f"[{self.component_type}] [进站] 5. 充电站关门 {ips}")
        res = self.station_plugin.execute(action="close", params={"ips": ips})
        if self._check_abort(): return self._handle_abort("充电站关门被打断")
        if res.get("status") != "success": return self._handle_abort("关门异常终止", res)

        self._internal_state = "COMPLETED"
        return {"status": "success", "message": "成功进入充电站并开始充电"}

    def _execute_leave(self, inner_point, outer_point, ips):
        # 1. 充电站开门
        self._internal_state = "STATION_OPENING"
        logger.info(f"[{self.component_type}] [出站] 1. 充电站开门 {ips}")
        res = self.station_plugin.execute(action="open", params={"ips": ips})
        if self._check_abort(): return self._handle_abort("充电站开门被打断")
        if res.get("status") != "success": return self._handle_abort("开门异常终止", res)

        # 2. 导航插件退出充电
        self._internal_state = "EXIT_CHARGE"
        logger.info(f"[{self.component_type}] [出站] 2. 退出充电 (执行 motion_cmd: 2)")
        res = self.nav_plugin.execute(action="execute_motion", params={"motion_cmd": 2})
        if self._check_abort(): return self._handle_abort("退出充电动作被打断")
        if res.get("status") != "success": return self._handle_abort("退出充电异常终止", res)

        # 3. 导航到站外点
        self._internal_state = "NAV_TO_OUTER"
        logger.info(f"[{self.component_type}] [出站] 3. 导航到站外点 {outer_point}")
        res = self.nav_plugin.execute(action="start_nav", params={"goal_point": outer_point})
        if self._check_abort(): return self._handle_abort("出站导航被打断")
        if res.get("status") != "success": return self._handle_abort("出站导航异常终止", res)

        # 4. 充电站关门
        self._internal_state = "STATION_CLOSING"
        logger.info(f"[{self.component_type}] [出站] 4. 充电站关门 {ips}")
        res = self.station_plugin.execute(action="close", params={"ips": ips})
        if self._check_abort(): return self._handle_abort("充电站关门被打断")
        if res.get("status") != "success": return self._handle_abort("关门异常终止", res)

        self._internal_state = "COMPLETED"
        return {"status": "success", "message": "成功退出充电站"}

    def abort(self) -> None:
        self._is_aborted = True
        logger.warning(f"🚨 [{self.component_type}] 收到打断信号，当前内部状态: {self._internal_state}")
        
        if self.nav_plugin and hasattr(self.nav_plugin, "abort"):
            self.nav_plugin.abort() # 打断导航阻塞
        if self.station_plugin and hasattr(self.station_plugin, "abort"):
            self.station_plugin.abort() # 打断充电站指令阻塞

        # 控制权交还给 Worker 线程中的 execute()，由其完成安全回滚
        
    def _handle_abort(self, msg: str, original_res: dict = None) -> dict:
        self._rollback()
        status = "aborted" if self._is_aborted else (original_res.get("status", "error") if original_res else "error")
        message = original_res.get("message", msg) if original_res else msg
        return {"status": status, "message": message}
        
    def _rollback(self) -> None:
        ips = self._current_params.get("ips", [])
        if not self.station_plugin or not ips:
            return
            
        logger.info(f"[{self.component_type}] 执行撤回打断逻辑，当前所处阶段: {self._internal_state}")
        
        if self._internal_state == "NAV_TO_OUTER":
            logger.info(f"[{self.component_type}] 撤回：前往站外点途中，尚未开门，安全。")
            self.nav_plugin.execute(action="abort_nav", params={})
            
        elif self._internal_state == "STATION_OPENING":
            logger.info(f"[{self.component_type}] 撤回：充电站开门阶段，车未进站，恢复关门状态以确保安全。")
            self.station_plugin.execute(action="close", params={"ips": ips})
            
        elif self._internal_state == "NAV_TO_INNER":
            logger.critical(f"⚠️ [{self.component_type}] 撤回：机器人正在驶入充电站！门已强制保持常开状态，防止门机误动夹车！")
            self.nav_plugin.execute(action="abort_nav", params={})
            
        elif self._internal_state in ["START_CHARGE", "EXIT_CHARGE"]:
            logger.critical(f"⚠️ [{self.component_type}] 撤回：机器人正进入/退出充电对接姿态！门保持常开！")
            
        elif self._internal_state == "STATION_CLOSING":
            logger.info(f"[{self.component_type}] 撤回：车已在站内，门正在关闭。重新下发关门指令闭锁。")
            
        elif self._internal_state == "COMPLETED":
            logger.info(f"[{self.component_type}] 撤回：进站已彻底完成，无视。")

    def _check_abort(self) -> bool:
        if self._is_aborted:
            logger.warning(f"🚨 [{self.component_type}] 检测到中止信号，退出执行循环")
            return True
        return False


    @classmethod
    def get_capability(cls) -> Dict[str, Any]:
        return {
            "component_type": "StationComponent",
            "component_name": "充电站组件",
            "description": "包含进出充电站的完整业务流",
            "scopes": ["task"],
            "params": [
                {"name": "direction", "label": "动作方向", "type": "string", "default": "leave", "required": False, "ui_component": "select", "options": [{"name": "出站", "value": "leave"}, {"name": "进站", "value": "enter"}]},
                {"name": "inner_point", "label": "站内点位ID", "type": "int", "required": True, "ui_component": "input_number"},
                {"name": "outer_point", "label": "站外点位ID", "type": "int", "required": True, "ui_component": "input_number"},
                {"name": "ips", "label": "充电站IP地址数组", "type": "array", "required": True, "ui_component": "input_array"}
            ],
            "returns": {
                "type": "object",
                "fields": [
                    {"name": "status", "label": "执行状态", "type": "string"},
                    {"name": "message", "label": "描述", "type": "string"}
                ]
            }
        }
