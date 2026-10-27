import time
from typing import Dict, Any, Optional
from components.base_component import BaseComponent
from core.logger_manager import get_logger

logger = get_logger("ElevatorComponent")

class ElevatorComponent(BaseComponent):
    """
    呼梯组件
    包含乘梯上下楼的完整业务流。
    正向: 导航到出发点 -> 呼梯到出发层 -> 开门 -> 进电梯 -> 关门 -> 呼梯到目标层 -> 开门 -> 出电梯 -> 关门
    反向: 导航到目标点 -> 呼梯到目标层 -> 开门 -> 进电梯 -> 关门 -> 呼梯到出发层 -> 开门 -> 出电梯 -> 关门
    """
    
    def __init__(self, plugin_manager):
        super().__init__(plugin_manager)
        self.elevator_plugin = plugin_manager.get_plugin_by_capability("elevator_control")
        self.nav_plugin = plugin_manager.get_plugin_by_capability("navigation")
        self._internal_state = "IDLE"
        self._current_params = {}
        
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self._is_aborted = False
        self._current_params = params
        
        addr = params.get("addr")
        start_floor = params.get("start_floor")
        start_point = params.get("start_point")
        start_ele_point = params.get("start_ele_point")
        target_floor = params.get("target_floor")
        target_point = params.get("target_point")
        target_ele_point = params.get("target_ele_point")
        
        if addr is None or start_floor is None or start_point is None or start_ele_point is None or target_floor is None or target_point is None or target_ele_point is None:
            return {"status": "error", "message": "缺少必填参数: addr, start_floor, start_point, start_ele_point, target_floor, target_point, target_ele_point"}
            
        if not self.elevator_plugin or not self.nav_plugin:
            return {"status": "error", "message": "依赖的底层插件 ElevatorPlugin 或 NavPlugin 未加载"}

        try:
            return self._execute_logic(addr, start_floor, start_point, start_ele_point, target_floor, target_point, target_ele_point)
        except Exception as e:
            logger.error(f"[{self.component_type}] 执行异常: {e}")
            return {"status": "error", "message": str(e)}

    def _execute_logic(self, addr, start_floor, start_point, start_ele_point, target_floor, target_point, target_ele_point):
        # 1. 导航到出发点
        self._internal_state = "NAV_TO_START"
        logger.info(f"[{self.component_type}] 1. 导航到出发点 {start_point}")
        res = self.nav_plugin.execute(action="start_nav", params={"goal_point": start_point})
        if self._check_abort(): return self._handle_abort("任务被打断")
        if res.get("status") != "success": return self._handle_abort("导航异常终止", res)

        # 2. 呼梯 (出发楼层)
        self._internal_state = "CALL_ELEVATOR_START"
        logger.info(f"[{self.component_type}] 2. 呼梯到出发楼层 {start_floor}")
        res = self.elevator_plugin.execute(action="goToFloor", params={"addr": addr, "floor": start_floor})
        if self._check_abort(): return self._handle_abort("呼梯被打断")
        if res.get("status") != "success": return self._handle_abort("呼梯异常终止", res)

        # 3. 电梯开门
        self._internal_state = "OPEN_DOOR_START"
        logger.info(f"[{self.component_type}] 3. 电梯开门")
        res = self.elevator_plugin.execute(action="openDoor", params={"addr": addr})
        if self._check_abort(): return self._handle_abort("开门被打断")
        if res.get("status") != "success": return self._handle_abort("开门异常终止", res)

        # 4. 导航到地图连接点 (start_ele_point)
        self._internal_state = "NAV_TO_START_ELE_POINT"
        logger.info(f"[{self.component_type}] 4. 导航到地图连接点 {start_ele_point}")
        res = self.nav_plugin.execute(action="start_nav", params={"goal_point": start_ele_point})
        if self._check_abort(): return self._handle_abort("进梯导航被打断")
        if res.get("status") != "success": return self._handle_abort("进梯导航异常终止", res)

        # 5. 电梯关门
        self._internal_state = "CLOSE_DOOR_START"
        logger.info(f"[{self.component_type}] 5. 电梯关门")
        res = self.elevator_plugin.execute(action="closeDoor", params={"addr": addr})
        if self._check_abort(): return self._handle_abort("关门被打断")
        if res.get("status") != "success": return self._handle_abort("关门异常终止", res)

        # 6. 呼梯 (目标楼层)
        self._internal_state = "CALL_ELEVATOR_TARGET"
        logger.info(f"[{self.component_type}] 6. 呼梯到目标楼层 {target_floor}")
        res = self.elevator_plugin.execute(action="goToFloor", params={"addr": addr, "floor": target_floor})
        if self._check_abort(): return self._handle_abort("目标层呼梯被打断")
        if res.get("status") != "success": return self._handle_abort("目标层呼梯异常终止", res)

        # 7. 电梯开门
        self._internal_state = "OPEN_DOOR_TARGET"
        logger.info(f"[{self.component_type}] 7. 电梯开门")
        res = self.elevator_plugin.execute(action="openDoor", params={"addr": addr})
        if self._check_abort(): return self._handle_abort("目标层开门被打断")
        if res.get("status") != "success": return self._handle_abort("目标层开门异常终止", res)

        # 8. 导航到目标点
        self._internal_state = "NAV_TO_TARGET"
        logger.info(f"[{self.component_type}] 8. 导航到目标点 {target_point}")
        res = self.nav_plugin.execute(action="start_nav", params={"goal_point": target_point})
        if self._check_abort(): return self._handle_abort("出梯导航被打断")
        if res.get("status") != "success": return self._handle_abort("出梯导航异常终止", res)

        # 9. 电梯关门
        self._internal_state = "CLOSE_DOOR_TARGET"
        logger.info(f"[{self.component_type}] 9. 电梯关门")
        res = self.elevator_plugin.execute(action="closeDoor", params={"addr": addr})
        if self._check_abort(): return self._handle_abort("最后关门被打断")
        if res.get("status") != "success": return self._handle_abort("最后关门异常终止", res)

        self._internal_state = "COMPLETED"
        return {"status": "success", "message": "乘梯到达目标点"}

    def abort(self) -> None:
        self._is_aborted = True
        logger.warning(f"🚨 [{self.component_type}] 收到打断信号，当前内部状态: {self._internal_state}")
        if self.nav_plugin and hasattr(self.nav_plugin, "abort"):
            self.nav_plugin.abort()
        if self.elevator_plugin and hasattr(self.elevator_plugin, "abort"):
            self.elevator_plugin.abort()
            
        # 注意：此处不再盲目等待 0.6 秒并强行执行 rollback。
        # 控制权直接退回 TaskWorker 中的 execute 逻辑，等底层动作彻底退出阻塞并确认停止后，
        # 才会在此 worker 中安全执行 _rollback。
        
    def _handle_abort(self, msg: str, original_res: dict = None) -> dict:
        self._rollback()
        status = "aborted" if self._is_aborted else (original_res.get("status", "error") if original_res else "error")
        message = original_res.get("message", msg) if original_res else msg
        return {"status": status, "message": message}
        
    def _rollback(self) -> None:
        addr = self._current_params.get("addr")
        start_point = self._current_params.get("start_point")
        if not self.elevator_plugin or not addr:
            return
            
        logger.info(f"[{self.component_type}] 执行撤回打断逻辑，当前所处阶段: {self._internal_state}")
        
        if self._internal_state == "NAV_TO_START":
            logger.info(f"[{self.component_type}] 撤回：前往乘梯出发点途中，未开始呼梯，安全。")
            self.nav_plugin.execute(action="abort_nav", params={})
            
        elif self._internal_state == "CALL_ELEVATOR_START":
            logger.info(f"[{self.component_type}] 撤回：正在等待电梯到达出发层，车未进梯。")
            self.elevator_plugin.execute(action="closeDoor", params={"addr": addr})
            
        elif self._internal_state == "OPEN_DOOR_START":
            logger.info(f"[{self.component_type}] 撤回：出发层电梯开门阶段，车未进梯，恢复关门状态以确保安全。")
            self.elevator_plugin.execute(action="closeDoor", params={"addr": addr})
            
        elif self._internal_state == "NAV_TO_START_ELE_POINT":
            logger.critical(f"⚠️ [{self.component_type}] 撤回：机器人正在驶入电梯！电梯门已强制保持常开状态，防止门机误动夹车！")
            self.nav_plugin.execute(action="abort_nav", params={})
            
        elif self._internal_state == "CLOSE_DOOR_START":
            logger.info(f"[{self.component_type}] 撤回：车已在电梯内，门正在关闭。重新下发关门指令闭锁。")
            
        elif self._internal_state == "CALL_ELEVATOR_TARGET":
            logger.info(f"[{self.component_type}] 撤回：车已在电梯内，电梯正前往目标楼层。")
            
        elif self._internal_state == "OPEN_DOOR_TARGET":
            logger.info(f"[{self.component_type}] 撤回：目标层电梯开门阶段，车未出梯，恢复关门状态以确保安全。")
            self.elevator_plugin.execute(action="closeDoor", params={"addr": addr})
            
        elif self._internal_state == "NAV_TO_TARGET":
            logger.critical(f"⚠️ [{self.component_type}] 撤回：机器人正在驶出电梯！电梯门已强制保持常开状态，防止门机误动夹车！")
            self.nav_plugin.execute(action="abort_nav", params={})
            
        elif self._internal_state == "CLOSE_DOOR_TARGET":
            logger.info(f"[{self.component_type}] 撤回：车已安全出梯，门正在关闭。重新下发关门指令闭锁。")
            
        elif self._internal_state == "COMPLETED":
            logger.info(f"[{self.component_type}] 撤回：乘梯动作已全部完成，无视。")

    def _check_abort(self) -> bool:
        if self._is_aborted:
            logger.warning(f"🚨 [{self.component_type}] 检测到中止信号，退出执行循环")
            return True
        return False

    @classmethod
    def get_capability(cls) -> Dict[str, Any]:
        return {
            "component_type": "ElevatorComponent",
            "component_name": "呼梯组件",
            "description": "包含乘梯上下楼的完整业务流",
            "scopes": ["task"],
            "params": [
                {"name": "addr", "label": "电梯编号", "type": "int", "required": True, "ui_component": "input_number"},
                {"name": "start_floor", "label": "出发楼层", "type": "int", "required": True, "ui_component": "input_number"},
                {"name": "start_point", "label": "出发点", "type": "int", "required": True, "ui_component": "input_number"},
                {"name": "start_ele_point", "label": "出发地图连接点", "type": "int", "required": True, "ui_component": "input_number"},
                {"name": "target_floor", "label": "目标楼层", "type": "int", "required": True, "ui_component": "input_number"},
                {"name": "target_point", "label": "目标点", "type": "int", "required": True, "ui_component": "input_number"},
                {"name": "target_ele_point", "label": "目标地图连接点", "type": "int", "required": True, "ui_component": "input_number"}
            ],
            "returns": {
                "type": "object",
                "fields": [
                    {"name": "status", "label": "执行状态", "type": "string"},
                    {"name": "message", "label": "描述", "type": "string"}
                ]
            }
        }
