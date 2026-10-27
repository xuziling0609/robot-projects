import time
from typing import Dict, Any, Optional
from core.logger_manager import get_logger
from components.base_component import BaseComponent

logger = get_logger("DoorComponent")

class DoorComponent(BaseComponent):
    """
    自动门穿行组件
    包含开门、穿行、关门以及防夹车回滚的完整业务流。
    """
    
    def __init__(self, plugin_manager):
        super().__init__(plugin_manager)
        self.door_plugin = plugin_manager.get_plugin_by_capability("door_control")
        self.nav_plugin = plugin_manager.get_plugin_by_capability("navigation")
        self._internal_state = "IDLE" # IDLE, NAV_TO_ENTRY, DOOR_OPENING, PASSING, DOOR_CLOSING, COMPLETED
        self._current_params = {}
        
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self._is_aborted = False
        self._current_params = params
        door_ips = params.get("door_ips")
        entry_point = params.get("entry_point")
        exit_point = params.get("exit_point")
        
        if not door_ips or entry_point is None or exit_point is None:
            return {"status": "error", "message": "缺少必填参数: door_ips, entry_point, exit_point"}
            
        if not self.door_plugin or not self.nav_plugin:
            return {"status": "error", "message": "依赖的底层插件 DoorPlugin 或 NavPlugin 未加载"}

        try:
            # 1. 导航到门外入点
            self._internal_state = "NAV_TO_ENTRY"
            logger.info(f"[{self.component_type}] 1. 开始导航至门前入点 {entry_point}")
            res = self.nav_plugin.execute(action="start_nav", params={"goal_point": entry_point})
            if self._check_abort(): return self._handle_abort("任务被打断")
            if res.get("status") != "success": return self._handle_abort("导航异常终止", res)

            # 2. 开门
            self._internal_state = "DOOR_OPENING"
            logger.info(f"[{self.component_type}] 2. 到达入点，触发开门 {door_ips}")
            res = self.door_plugin.execute(action="open", params={"ips": door_ips})
            if self._check_abort(): return self._handle_abort("开门机开门中途打断")
            if res.get("status") != "success": return self._handle_abort("开门异常终止", res)

            # 3. 门控机暂停 (维持当前状态)
            self._internal_state = "DOOR_PAUSING"
            logger.info(f"[{self.component_type}] 3. 门已打开，触发暂停（保持开门状态） {door_ips}")
            res = self.door_plugin.execute(action="pause", params={"ips": door_ips})
            if self._check_abort(): return self._handle_abort("开门机暂停中途被打断")
            if res.get("status") != "success": return self._handle_abort("维持开门异常终止", res)

            # 4. 穿门
            self._internal_state = "PASSING"
            logger.info(f"[{self.component_type}] 4. 已锁定开门状态，开始穿门导航至出点 {exit_point}")
            res = self.nav_plugin.execute(action="start_nav", params={"goal_point": exit_point})
            if self._check_abort(): return self._handle_abort("穿门中途被打断")
            if res.get("status") != "success": return self._handle_abort("穿门异常终止", res)

            # 5. 关门
            self._internal_state = "DOOR_CLOSING"
            logger.info(f"[{self.component_type}] 5. 已安全通过，触发关门 {door_ips}")
            res = self.door_plugin.execute(action="close", params={"ips": door_ips})
            if self._check_abort(): return self._handle_abort("关门中途被打断")
            if res.get("status") != "success": return self._handle_abort("关门异常终止", res)
            
            self._internal_state = "COMPLETED"
            return {"status": "success", "message": "已安全通过自动门"}
            
        except Exception as e:
            logger.error(f"[{self.component_type}] 执行异常: {e}")
            return {"status": "error", "message": str(e)}

    def abort(self) -> None:
        self._is_aborted = True
        logger.warning(f"🚨 [{self.component_type}] 收到打断信号，当前内部状态: {self._internal_state}")
        if self.nav_plugin and hasattr(self.nav_plugin, "abort"):
            self.nav_plugin.abort() # 立即打断底层导航
        if self.door_plugin and hasattr(self.door_plugin, "abort"):
            self.door_plugin.abort() # 立即打断门机轮询
        # 注意：此处不再进行盲目 sleep 且不再强行调用 _rollback。
        # 控制权交还给 Worker 线程中的 execute()，等到底层硬件真实确认打断后，由 execute() 安全发起 _rollback。
        
    def _handle_abort(self, msg: str, original_res: dict = None) -> dict:
        self._rollback()
        status = "aborted" if self._is_aborted else (original_res.get("status", "error") if original_res else "error")
        message = original_res.get("message", msg) if original_res else msg
        return {"status": status, "message": message}
        
    def _check_abort(self) -> bool:
        if self._is_aborted:
            logger.warning(f"🚨 [{self.component_type}] 检测到中止信号，退出执行循环")
            return True
        return False
        
    def _rollback(self) -> None:
        door_ips = self._current_params.get("door_ips", [])
        if not self.door_plugin or not door_ips:
            return
            
        logger.info(f"[{self.component_type}] 执行撤回打断逻辑，当前所处阶段: {self._internal_state}")
        
        if self._internal_state == "NAV_TO_ENTRY":
            logger.info(f"[{self.component_type}] 撤回：尚未触碰门控，无需对门机下发指令，暂停底盘导航。")
            if self.nav_plugin:
                self.nav_plugin.execute(action="abort_nav", params={})
            
        elif self._internal_state in ["DOOR_OPENING", "DOOR_PAUSING"]:
            logger.info(f"[{self.component_type}] 撤回：车未进门，恢复关门状态。")
            self.door_plugin.execute(action="close", params={"ips": door_ips})
            
        elif self._internal_state == "PASSING":
            logger.critical(f"⚠️ [{self.component_type}] 撤回：车正在穿过门框！门已处于暂停常开状态，仅需暂停底盘导航防撞！")
            if self.nav_plugin:
                self.nav_plugin.execute(action="abort_nav", params={})
            
        elif self._internal_state == "DOOR_CLOSING":
            logger.info(f"[{self.component_type}] 撤回：车已过门，门正在关，确保下发关门指令。")
            
        elif self._internal_state == "COMPLETED":
            logger.info(f"[{self.component_type}] 撤回：动作已全部完成，无视。")

    @classmethod
    def get_capability(cls) -> Dict[str, Any]:
        return {
            "component_type": "DoorComponent",
            "component_name": "开门组件",
            "description": "高级业务组件：自动完成开门、穿行、关门，并包含防夹车紧急保护",
            "scopes": ["task"],
            "params": [
                {
                    "name": "door_ips",
                    "label": "IP列表",
                    "type": "array",
                    "required": True,
                    "ui_component": "input_array"
                },
                {
                    "name": "entry_point",
                    "label": "门外点ID",
                    "type": "int",
                    "required": True,
                    "ui_component": "input_number"
                },
                {
                    "name": "exit_point",
                    "label": "门内点ID",
                    "type": "int",
                    "required": True,
                    "ui_component": "input_number"
                }
            ],
            "returns": {
                "type": "object",
                "fields": [
                    {"name": "status", "label": "执行状态", "type": "string"}
                ]
            }
        }
