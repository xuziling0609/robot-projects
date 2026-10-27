import time
import threading
from plugins.base import BasePlugin
from core.logger_manager import get_logger

from .yunjinet_driver import YunjiNetDriver
from .yunjilora_driver import YunjiLoraDriver

logger = get_logger("ElevatorPlugin")

class ElevatorPlugin(BasePlugin):
    """双模电梯控制调度插件 (可安全打断的同步阻塞版)"""

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.yunji_driver = YunjiNetDriver(self.config)
        self.lora_driver = YunjiLoraDriver(self.config)
        
        # 任务缓存池，用于管理各电梯的打断事件与状态
        self.monitor_tasks = {}
        self._is_paused: bool = False
        logger.info("✅ ElevatorPlugin 双模电梯插件(可打断同步版)挂载成功。")

    def _is_lora_online(self, addr: int) -> bool:
        """动态探测本地 LoRa 局域网是否通畅"""
        return self.lora_driver.query_local_floor(addr) is not None

    def _send_delay_close(self, addr: int, seconds: int):
        """双模发送延时关门指令"""
        if self._is_lora_online(addr):
            self.lora_driver.delay_close(addr, delay_sec=seconds)
        else:
            self.yunji_driver.delay_close(addr, seconds=seconds)

    def _hold_door_loop(self, addr: int, cancel_event: threading.Event):
        """循环保持开门守护线程"""
        logger.info(f"🚪 [电梯 {addr}] 启动延时开门守护 (每 3 秒下发 seconds=5)...")
        while not cancel_event.is_set():
            self._send_delay_close(addr, seconds=5)
            if cancel_event.wait(3.0):
                logger.info(f"🛑 [电梯 {addr}] 收到中止信号，开门守护循环已结束。")
                break

    def execute(self, action: str, params: dict) -> dict:
        """插件标准执行入口"""
        if action.lower() != "pause" and self._is_paused:
            logger.warning(f"⏸️ [{self.plugin_name}] 处于暂停状态，中断动作。")
            return {"status": "paused", "message": "电梯动作因暂停被中断"}
        if action.lower() in ["status", "get_status"]:
            is_online = self.get_status()
            return {
                "status": "success" if is_online else "error",
                "message": "电梯插件在线" if is_online else "电梯插件本地 TCP 连接失败",
                "data": {"online": is_online}
            }

        addr = params.get("addr")
        if not addr: 
            return {"status": "error", "message": "缺少必要的 addr 参数"}
        
        # 确保该电梯拥有专属的任务控制上下文
        if addr not in self.monitor_tasks:
            self.monitor_tasks[addr] = {
                "cancel_event": threading.Event(),
                "arrived_event": threading.Event()
            }
            
        task = self.monitor_tasks[addr]
        cancel_event = task["cancel_event"]

        # 1. 接口：goToFloor (表面同步阻塞等待，内部事件驱动可随时打断)
        if action == "goToFloor":
            floor = params.get("floor")
            if floor is None:
                return {"status": "error", "message": "缺少 floor 参数"}
            
            # 💡 核心优化：若有残留旧任务正在执行，立刻发送打断信号将其唤醒清理
            if not cancel_event.is_set():
                cancel_event.set()
            
            # 创建全新的同步控制事件
            cancel_event = threading.Event()
            arrived_event = threading.Event()
            task["cancel_event"] = cancel_event
            task["arrived_event"] = arrived_event
            
            # 下发呼梯指令
            if self._is_lora_online(addr):
                call_success = self.lora_driver.call_lift(addr, floor)
            else:
                call_success = self.yunji_driver.call_lift(addr, floor)
                
            if not call_success:
                return {"status": "error", "message": "本地与云端呼梯接口均调用失败"}
                
            # 🚀 巧妙的设计：将耗时的防抖检测丢进后台线程
            def background_wait():
                logger.info(f"🚀 [电梯 {addr}] 后台防抖线程启动，等待到达楼层: {floor}")
                consecutive_hits = 0
                has_arrived = False
                
                for attempt in range(2):
                    start_time = time.time()
                    while time.time() - start_time < 30.0:
                        # 如果外部下发了 abort 或新指令，瞬间退出，绝不卡死
                        if cancel_event.is_set():
                            return
                        
                        if self._is_lora_online(addr):
                            curr_floor = self.lora_driver.query_local_floor(addr)
                            mapped_target = (200 + abs(floor)) if floor < 0 else floor
                            is_match = (curr_floor == mapped_target)
                        else:
                            status = self.yunji_driver.query_status(addr)
                            is_match = (status and status.get("floor") == floor)

                        if is_match:
                            consecutive_hits += 1
                            if consecutive_hits >= 3:
                                has_arrived = True
                                break
                        else:
                            consecutive_hits = 0
                        
                        time.sleep(1.0)
                        
                    if has_arrived:
                        break
                    
                    if attempt == 0 and not cancel_event.is_set():
                        logger.warning(f"⚠️ [电梯 {addr}] 等待超时，后台补发呼梯指令...")
                        if self._is_lora_online(addr):
                            self.lora_driver.call_lift(addr, floor)
                        else:
                            self.yunji_driver.call_lift(addr, floor)
                
                if has_arrived and not cancel_event.is_set():
                    logger.info(f"✅ [电梯 {addr}] 后台确认已到达 {floor} 层，通知主线程放行。")
                    arrived_event.set() # 唤醒主线程

            threading.Thread(target=background_wait, daemon=True, name=f"BgWait-{addr}").start()

            # ⏳ 主线程在此处进行“带中断响应”的同步阻塞等待 (最多等 60 秒)
            # 原理：每 0.5 秒检查一次 cancel_event。如果期间收到打断或急停，立刻退出，绝不卡死！
            logger.info(f"⏳ [电梯 {addr}] 主线程开始同步阻塞等待电梯到位...")
            total_waited = 0.0
            while total_waited < 60.0:
                if self._is_paused:
                    logger.warning(f"⏸️ [电梯 {addr}] 状态轮询过程中检测到 pause 暂停信号，终止轮询。")
                    return {"status": "paused", "message": "电梯动作因暂停被中断"}

                if cancel_event.is_set():
                    logger.warning(f"⚠️ [电梯 {addr}] 同步等待期间收到外部打断/急停信号，提前退出。")
                    if self._is_paused:
                        return {"status": "paused", "message": "电梯动作因暂停被中断"}
                    return {"status": "error", "message": "电梯等待过程被外部指令打断"}
                
                # 检查后台线程是否已经成功触发了到达事件
                if arrived_event.wait(0.5):
                    return {"status": "success", "message": f"电梯已成功到达 {floor} 层"}
                
                total_waited += 0.5

            return {"status": "error", "message": f"等待电梯到达 {floor} 层超时 (60s)"}
            
        # 2. 接口：循环开门
        elif action == "openDoor":
            threading.Thread(
                target=self._hold_door_loop,
                args=(addr, cancel_event),
                daemon=True,
                name=f"LiftOpen-{addr}"
            ).start()
            return {"status": "success", "message": "已开启电梯循环保持开门模式"}
            
        # 3. 接口：立刻关门
        elif action == "closeDoor":
            if not cancel_event.is_set():
                cancel_event.set() # 瞬间触发打断，正在同步等待的 goToFloor 会立刻苏醒报错并退出
                
            logger.info(f"🚪 [电梯 {addr}] 终止开门守护，下发立刻关门指令 (seconds=0)")
            self._send_delay_close(addr, seconds=0)
            return {"status": "success", "message": "已关闭电梯门"}
            
        return {"status": "error", "message": f"不支持的动作: {action}"}

    def pause(self) -> None:
        """暂停电梯控制：瞬间唤醒并中断当前阻塞，下发立刻关门"""
        if self._is_paused:
            logger.warning(f"[{self.plugin_name}] 电梯插件已处于暂停状态，忽略 pause 请求")
            return
        self._is_paused = True
        logger.warning(f"⏸️ [{self.plugin_name}] 收到暂停信号！正在强行中断所有电梯任务...")
        for addr, task in self.monitor_tasks.items():
            if not task["cancel_event"].is_set():
                task["cancel_event"].set()
                task["arrived_event"].set()  # 顺便放开阻塞
                self._send_delay_close(addr, seconds=0)

    def resume(self) -> None:
        """恢复电梯控制"""
        self._is_paused = False
        logger.info(f"▶️ [{self.plugin_name}] 恢复电梯控制，暂停标志已清除。")

    def abort(self) -> dict:
        """【接口契约】全局急停：瞬间唤醒所有卡住的同步线程"""
        self._is_paused = False
        logger.warning("🚨 ElevatorPlugin 收到全局急停信号！正在强行唤醒并中断所有电梯任务...")
        for addr, task in self.monitor_tasks.items():
            if not task["cancel_event"].is_set():
                task["cancel_event"].set()
                task["arrived_event"].set() # 顺便放开阻塞
                self._send_delay_close(addr, seconds=0)
        return {"status": "success", "message": "所有电梯调度任务已安全中止"}

    def get_status(self) -> bool:
        """测试梯控本地 TCP 连接状态 (复用 TCP 连接池)"""
        try:
            from core.tcp_manager import TCPManager
            pool = TCPManager()
            sock = pool.get_connection(self.lora_driver.ip, self.lora_driver.port, timeout=2.0)
            return sock is not None
        except Exception as e:
            logger.error('操作引发异常:', exc_info=True)
            return False

    def get_capabilities(self) -> dict:
        """获取电梯插件标准能力清单元数据 (Schema)"""
        return {
            "plugin_type": self.__class__.__name__,
            "plugin_name": "电梯插件",
            "description": "基于云基双模电梯控制器的呼梯、乘梯及开关门联动控制能力",
            "version": "1.2.0",
            "supported_actions": [
                {
                    "action": "goToFloor",
                    "action_name": "电梯呼梯",
                    "description": "呼叫电梯并乘梯前往指定目标楼层（同步阻塞至到位）",
                    "scopes": ["task"],
                    "params": [
                        {"name": "addr", "label": "电梯编号", "type": "int", "default": 18191, "required": False, "ui_component": "input_number"},
                        {"name": "floor", "label": "目标楼层", "type": "int", "required": True, "ui_component": "input_number"}
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
                    "action": "openDoor",
                    "action_name": "电梯开门",
                    "description": "开启电梯保持开门轮询模式（进出电梯保护）",
                    "scopes": ["task"],
                    "params": [
                        {"name": "addr", "label": "电梯编号", "type": "int", "default": 18191, "required": False, "ui_component": "input_number"}
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
                    "action": "closeDoor",
                    "action_name": "电梯关门",
                    "description": "立即关闭电梯门并解除开门保持守护",
                    "scopes": ["task"],
                    "params": [
                        {"name": "addr", "label": "电梯编号", "type": "int", "default": 18191, "required": False, "ui_component": "input_number"}
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
                    "action": "status",
                    "action_name": "状态查询",
                    "description": "查询电梯控制器网络连接状态",
                    "scopes": ["config"],
                    "params": [],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "online", "label": "在线状态", "type": "bool"}
                        ]
                    }
                }
            ]
        }