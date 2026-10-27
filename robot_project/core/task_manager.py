"""
边缘网关任务调度中枢 (TaskManager)

【核心架构设计】：
1. Actor 模式 (单线调度中枢)：
   - 通过 PriorityQueue 优先级队列接收所有上游指令 (控制指令优先级=10，普通任务=50)。
   - 唯一由单线程 Actor (_controller_loop) 串行消费指令，避免多线程并发修改 task_state 产生竞态。
2. Worker 异步执行模式：
   - 耗时的多步骤任务或单动作，由 Actor 瞬间解析后交由独立的 Worker 线程异步执行，主 Actor 立即释放继续侦听 abort/pause 控制指令。
3. 线程同步原语 (Event-driven)：
   - 使用 threading.Event (_pause_event) 实现任务挂起与瞬间唤醒，彻底告别 while-sleep 忙轮询，零 CPU 损耗。
4. 轨迹逆向安全返航 (RTH Compiler)：
   - 拦截 "rth" 动作瞬间打断当前动作，提取走过的 Nav 点位轨迹与 rth，
     通过 RthManager 一次性静态编译出包含前置清洗、边动作查表、终点追加的返航流水线。
"""

import os
import time
import uuid
import queue
import math
import threading
from typing import Optional, Dict, Any, Callable, List

from core.logger_manager import get_logger
from core.config_manager import ConfigManager
from core.plugin_manager import PluginManager
from core.component_manager import ComponentManager
from core.event_manager import EventManager, TaskEvent
from core.context_manager import ContextManager
from core.task_storage_manager import TaskStorageManager
from core.rth_manager import RthManager

from utils import generate_msg_id

logger = get_logger("TaskManager")


class TaskManager:
    """
    边缘网关任务流转与调度管理器 (TaskManager)
    统一处理 MQTT 下行通道 (/edge/gateway/{robot_id}/cmd/down) 发起的命令报文。
    """

    def __init__(self, plugin_manager: Optional[PluginManager] = None, 
                 config_loader: Optional[ConfigManager] = None,
                 response_callback: Optional[Callable[..., Any]] = None,
                 storage_manager: Optional[TaskStorageManager] = None,
                 storage_dir: Optional[str] = None):
        """
        初始化任务调度管理器
        :param plugin_manager: 底层原子能力插件管理器 (NavPlugin, CameraPlugin, ArmPlugin 等)
        :param config_loader: 全局配置加载器 (读取网关超时、通信等配置)
        :param response_callback: 平台 ACK 上报回调函数 (通常绑定 MQTTManager.publish_response)
        :param storage_manager: 可选的任务持久化存储管理器实例 (优先使用，用于测试沙箱注入)
        :param storage_dir: 可选的存储目录路径 (若未注入 storage_manager，用于构造 TaskStorageManager)
        """
        
        # 1. 核心依赖注入
        self.plugin_manager = plugin_manager or PluginManager()
        self.component_manager = ComponentManager(self.plugin_manager)
        self.config_loader = config_loader or ConfigManager()
        self.response_callback = response_callback
        
        # 2. 离线任务存储管理器 (支持显式注入或通过 storage_dir 沙箱初始化)
        if storage_manager is not None:
            self.storage_manager = storage_manager
        else:
            self.storage_manager = TaskStorageManager(self.config_loader, storage_dir=storage_dir)
        
        # 3. 任务运行状态与上下文跟踪
        self._task_state: str = "IDLE"             # 任务全局状态 (IDLE / RUNNING / PAUSED / FINISH / FAILED / ABORTED)
        self._current_step: int = 1               # 当前执行的步骤号 (1-based, 对应 JSON 中的 step)
        self._current_step_index: int = 0         # 当前执行的步骤索引 (0-based, 数组下标)
        self._current_plugin = None               # 当前正在运行的插件/组件实例引用 (用于 abort/pause 穿透)
        self._last_plugin = None                  # 最近执行过的插件/组件引用 (用于 resume 穿透)
        self.current_execution_queue: list = []   # 当前任务的完整步骤队列快照 (供 RTH 编译器逆序推导)
        
        # 4. 线程同步原语：基于 Event 实现毫秒级暂停与恢复
        self._pause_event = threading.Event()
        self._pause_event.set()                   # 初始为 set (处于非暂停状态，流水线畅通)
        
        # 5. 暂停超时保护定时器 (暂停超过 auto_rth_timeout_sec 后自动触发安全返航)
        self._auto_rth_timer: Optional[threading.Timer] = None
        
        # 6. 单线程 Actor 指令优先级队列与主控线程启动
        self.cmd_queue = queue.PriorityQueue()
        self._is_running = True
        self._controller_thread = threading.Thread(
            target=self._controller_loop, daemon=True, name="TaskControllerActor"
        )
        self._controller_thread.start()
        
        # 7. 订阅全网关告警事件 (当硬件传感器发生致命告警时自动触发 auto_action 调度)
        EventManager().subscribe("alarm_auto_action", self._handle_alarm_auto_action)

        # 8. 任务执行专属会话与抢占令牌机制 (Task Execution Session & Preemption Tokens)
        self._worker_lock = threading.RLock()
        self._active_task_token: Optional[str] = None          # 当前唯一活跃任务的会话 Token (UUID)
        self._active_abort_event: Optional[threading.Event] = None  # 当前唯一活跃任务的专属打断事件
        self._active_worker_thread: Optional[threading.Thread] = None # 当前活跃工作线程引用

    def _create_task_session(self, thread_name: str = "TaskWorker") -> tuple:
        """
        创建全新的任务执行专属会话令牌，并原子废黜旧任务
        :return: (task_token, task_abort_event)
        """
        with self._worker_lock:
            # 1. 废黜并打断旧任务会话
            if self._active_abort_event is not None:
                logger.warning(f"🚨 [TaskManager] 废黜旧任务会话 [token={self._active_task_token[:8] if self._active_task_token else 'unknown'}...]")
                self._active_abort_event.set()

            # 2. 生成全新会话令牌与专属取消事件
            new_token = str(uuid.uuid4())
            new_abort_event = threading.Event()
            self._active_task_token = new_token
            self._active_abort_event = new_abort_event
            return new_token, new_abort_event

    # ---------------------------------------------------------
    # 状态属性与对外公共接口 (Public APIs)
    # ---------------------------------------------------------

    @property
    def task_state(self) -> str:
        """获取当前任务引擎运行状态 (IDLE / RUNNING / PAUSED / FINISH / FAILED / ABORTED)"""
        return self._task_state

    @task_state.setter
    def task_state(self, value: str):
        """
        更新任务状态属性：
        1. 记录本地变量；
        2. 自动同步更新到 ContextManager 内存共享池供遥测/其他插件极速读取；
        3. 广播 global_state_changed 全网关事件。
        """
        self._task_state = value
        ContextManager.update_robot_task({"status": value.lower()})
        try:
            EventManager().publish(TaskEvent(
                event_type="global_state_changed", task_id="system", extra_data={"state": value}
            ))
        except Exception:
            pass

    def get_task_state(self) -> str:
        """获取当前任务状态 (供 TelemetryManager 心跳上报等模块调用)"""
        return self.task_state

    def handle_task(self, payload: Dict[str, Any]) -> None:
        """
        接收上游 (MQTTManager / 本地定时器) 推送的原始报文，按优先级推入 Actor 队列。
        - 优先级规则：control (控制类) 与 action (单动作) 为 10 (高优插队)；普通任务管理/执行为 50。
        """
        cmd_type = payload.get("cmd_type", "unknown")
        priority = 10 if cmd_type in ["control", "action"] else 50
        self.cmd_queue.put((priority, payload))
        logger.debug(f"📥 [Actor Queue] 推入指令 ({cmd_type}), 当前排队数: {self.cmd_queue.qsize()}")

    def stop(self) -> None:
        """安全停止 TaskControllerActor 主线程"""
        self._is_running = False
        self.cmd_queue.put((-1, {"cmd_type": "_SYSTEM_EXIT"}))
        logger.info("🛑 [TaskManager] 已发送停机指令，等待 Controller 退出...")

    # ---------------------------------------------------------
    # Actor 主线程与统一指令分流器 (Dispatcher)
    # ---------------------------------------------------------

    def _controller_loop(self):
        """
        核心 Actor 主线程：
        采用单线程串行从优先级队列中取出指令并派发处理，彻底消除多线程修改 task_state 带来的并发锁竞争。
        """
        logger.info("🚀 [TaskManager] 主控单线 Actor 启动，等待调度指令...")
        while self._is_running:
            try:
                priority, payload = self.cmd_queue.get()
                if payload.get("cmd_type") == "_SYSTEM_EXIT":
                    logger.info("🛑 [TaskManager] Controller 收到停机指令，退出循环。")
                    break
                self._process_payload(payload)
                self.cmd_queue.task_done()
            except Exception as e:
                logger.error(f"❌ [TaskManager] Actor 执行指令异常: {e}")

    def _process_payload(self, payload: Dict[str, Any]) -> None:
        """
        统一指令分流入口 (Dispatcher Router)：
        将平台下发的不规范/多种语义报文进行规范化解耦，路由至对应的专用处理器：
        1. 单动作特权打断 (cmd_type=action, action=abort)
        2. 全局控制指令 (pause, resume, abort, rth)
        3. 离线任务管理与调度 (save, run, list, delete, clear)
        4. 即时单能力指令 (单动作/单宏组件)
        """
        start_time = time.time()
        msg_id = str(payload.get("msg_id", payload.get("task_id", "UNKNOWN")))
        cmd_type = payload.get("cmd_type")
        action = payload.get("action")
        task_id = payload.get("task_id")
        task_name = payload.get("task_name") or payload.get("name") or task_id or ""

        # 分支 1：单动作特权打断 (优先处理正在运行的即时无状态指令)
        if cmd_type == "action" and action == "abort":
            self._handle_action_abort(msg_id)
            return

        # 分支 2：全局任务控制类指令判定 (pause, resume, abort, rth)
        is_global_control = (cmd_type == "task" or not payload.get("plugin_type")) and \
                            action in ["pause", "resume", "abort", "rth"] and cmd_type != "action"
        if is_global_control:
            cached_task = ContextManager.get_robot_task()
            eff_task_id = task_id or cached_task.get("task_id") or ""
            eff_task_name = task_name or cached_task.get("task_name") or eff_task_id

            if action == "pause":
                self._handle_control_pause(msg_id, eff_task_id, eff_task_name, start_time)
            elif action == "resume":
                self._handle_control_resume(msg_id, eff_task_id, eff_task_name, start_time)
            elif action == "abort":
                self._handle_control_abort(msg_id, eff_task_id, eff_task_name, start_time)
            elif action == "rth":
                self._handle_control_rth(payload, msg_id, eff_task_id, eff_task_name, start_time)
            return

        # 分支 3：离线任务管理与调度执行 (save, run, delete, list, clear)
        if cmd_type == "task" or "task_id" in payload or "steps" in payload:
            target_task_id = task_id or "TASK_DEFAULT"
            steps_in_payload = payload.get("steps")

            # 3.1 任务库持久化与 CRUD 管理指令 (必须带显式 action)
            if action in ["delete", "list", "clear", "save", "update", "create", "sync", "modify", "edit"]:
                self._handle_task_management(payload, action, target_task_id, task_name, msg_id, start_time, steps_in_payload)
                return

            # 3.2 安全防御：严禁直接下发动态 steps 就地执行，所有任务必须先 save 再 run (内部返航流水线豁免)
            if steps_in_payload is not None and not payload.get("_is_rth"):
                self._send_error_response(
                    msg_id, 4000, 
                    "不支持直接下发动态任务链执行！所有任务必须先通过 action: 'save' 保存为离线任务，再通过 action: 'run' 触发执行。",
                    {"task_id": target_task_id, "duration_ms": int((time.time() - start_time) * 1000)}
                )
                return

            # 3.3 校验 action 动作合法性
            if action not in ["run", "execute", None]:
                self._send_error_response(
                    msg_id, 4000, 
                    f"不支持的任务指令动作 [{action}]。有效动作包括: save, sync, run, pause, resume, abort, rth, delete, list, clear"
                )
                return

            # 3.4 启动执行已保存的离线任务
            self._handle_task_run(payload, msg_id, target_task_id, task_name, cmd_type, start_time)
            return

        # 分支 4：即时单能力指令 (action) -> 异步分发给 ActionWorker
        elif cmd_type == "action" or ("plugin_type" in payload and "action" in payload) or ("component_type" in payload):
            threading.Thread(
                target=self._handle_single_action,
                args=(payload, msg_id, start_time),
                daemon=True,
                name="ActionWorker"
            ).start()
            return

        # 分支 5：无法识别的未知命令报文
        else:
            self._send_error_response(msg_id, 4000, "无效的命令报文: 无法识别 cmd_type、task_id、steps 或 plugin_type/action")

    # ---------------------------------------------------------
    # 控制指令处理器 (Control Handlers: pause, resume, abort, rth)
    # ---------------------------------------------------------

    def _handle_control_pause(self, msg_id: str, task_id: str, task_name: str, start_time: float) -> None:
        """
        处理暂停指令 (pause)：
        1. 校验当前状态必须为 RUNNING，否则直接幂等忽略；
        2. 清除 pause_event (使 Worker 线程进入阻塞等待)；
        3. 状态置为 PAUSED，启动超时自动返航守护定时器；
        4. 透传调用当前底层插件的 pause() 方法；
        5. 回复平台 ACK_EXECUTE 成功响应。
        """
        duration_ms = int((time.time() - start_time) * 1000)
        resp_data = {"task_id": task_id, "task_name": task_name, "task_action": "pause", "duration_ms": duration_ms}

        if self.task_state == "PAUSED":
            resp_data["task_status"] = "PAUSED"
            logger.info(f"✅ 任务 [{task_name}] 已处于暂停状态，幂等返回成功")
            self._send_success_response(msg_id, f"任务 [{task_name}] 已处于暂停状态", resp_data)
            return

        if self.task_state != "RUNNING":
            resp_data["task_status"] = self.task_state
            logger.warning(f"⚠️ 收到 pause 指令，但当前任务状态为 [{self.task_state}]，无法暂停")
            self._send_error_response(msg_id, 4000, f"当前状态 [{self.task_state}] 无法执行暂停操作", resp_data)
            return

        # 核心：清空事件，使 Worker 线程在 _wait_if_paused 中挂起
        self._pause_event.clear()
        self.task_state = "PAUSED"
        logger.info(f"⏸️ 收到暂停指令: [{task_name}] (msg_id: {msg_id})")

        # 启动超时自动返航保护定时器 (如 300 秒未恢复，自动强行返航防死锁)
        timeout_sec = float(self.config_loader.get("gateway", {}).get("auto_rth_timeout_sec", 300))
        self._clear_auto_rth_timer()
        self._auto_rth_timer = threading.Timer(timeout_sec, self._trigger_auto_rth, args=[task_id or task_name])
        self._auto_rth_timer.start()
        logger.info(f"⏳ 已启动 {timeout_sec} 秒自动返航倒计时保护...")

        EventManager().publish(TaskEvent(
            event_type="task_paused", task_id=task_id or task_name, task_name=task_name,
            step=getattr(self, "_current_step", 1), reason="收到平台 pause 暂停指令"
        ))

        # 向当前正在执行的子任务插件透传 pause() 调用
        if self._current_plugin is not None:
            try:
                self._current_plugin.pause()
                logger.info(f"⏸️ 已向当前子任务插件 [{type(self._current_plugin).__name__}] 透传 pause() 调用")
            except Exception as e:
                logger.warning(f"⚠️ 向插件透传 pause() 时异常: {e}")

        resp_data["task_status"] = "PAUSED"
        
        # 【双闭环更新】1. 向控制指令的 msg_id 回复成功
        self._send_success_response(msg_id, f"任务 [{task_name}] 暂停成功", resp_data)
        
        # 【双闭环更新】2. 必须向原任务的 msg_id 上报状态变更，否则平台原任务卡片状态不会更新
        cached_task = ContextManager.get_robot_task()
        orig_msg_id = cached_task.get("msg_id")
        if orig_msg_id and orig_msg_id != msg_id:
            logger.info(f"📤 向原任务 [{orig_msg_id}] 同步状态更新: PAUSED")
            self._send_success_response(orig_msg_id, f"任务 [{task_name}] 已挂起暂停", resp_data)

    def _handle_control_resume(self, msg_id: str, task_id: str, task_name: str, start_time: float) -> None:
        """
        处理恢复指令 (resume)：
        1. 校验当前状态必须为 PAUSED，否则直接幂等忽略；
        2. 取消超时自动返航定时器；
        3. 状态置为 RUNNING，设置 pause_event 瞬间唤醒 Worker 线程；
        4. 透传调用当前底层插件的 resume() 方法；
        5. 回复平台 ACK_EXECUTE 成功响应。
        """
        duration_ms = int((time.time() - start_time) * 1000)
        resp_data = {"task_id": task_id, "task_name": task_name, "task_action": "resume", "duration_ms": duration_ms}

        if self.task_state == "RUNNING":
            resp_data["task_status"] = "RUNNING"
            logger.info(f"✅ 任务 [{task_name}] 已处于运行状态，幂等返回成功")
            self._send_success_response(msg_id, f"任务 [{task_name}] 已处于运行状态", resp_data)
            return

        if self.task_state != "PAUSED":
            resp_data["task_status"] = self.task_state
            logger.warning(f"⚠️ 收到 resume 指令，但当前任务状态为 [{self.task_state}]，无法恢复")
            self._send_error_response(msg_id, 4000, f"当前状态 [{self.task_state}] 无法执行恢复操作", resp_data)
            return

        self._clear_auto_rth_timer()
        self.task_state = "RUNNING"
        self._pause_event.set()  # 核心：瞬间唤醒正在等待的流水线 Worker 线程
        logger.info(f"▶️ 收到恢复执行指令: [{task_name}] (msg_id: {msg_id})")

        EventManager().publish(TaskEvent(
            event_type="task_resumed", task_id=task_id or task_name, task_name=task_name,
            step=getattr(self, "_current_step", 1), reason="收到平台 resume 恢复指令"
        ))

        # 向底层插件透传 resume() 调用
        target_plugin = self._current_plugin or getattr(self, "_last_plugin", None)
        if target_plugin is not None:
            try:
                target_plugin.resume()
                logger.info(f"▶️ 已向子任务插件 [{type(target_plugin).__name__}] 透传 resume() 调用")
            except Exception as e:
                logger.warning(f"⚠️ 向插件透传 resume() 时异常: {e}")

        resp_data["task_status"] = "RUNNING"
        
        # 【双闭环更新】1. 向控制指令的 msg_id 回复成功
        self._send_success_response(msg_id, f"任务 [{task_name}] 恢复执行成功", resp_data)
        
        # 【双闭环更新】2. 向原任务的 msg_id 上报状态变更，通知平台任务已恢复
        cached_task = ContextManager.get_robot_task()
        orig_msg_id = cached_task.get("msg_id")
        if orig_msg_id and orig_msg_id != msg_id:
            logger.info(f"📤 向原任务 [{orig_msg_id}] 同步状态更新: RUNNING")
            self._send_success_response(orig_msg_id, f"任务 [{task_name}] 已恢复运行", resp_data)

    def _handle_control_abort(self, msg_id: str, task_id: str, task_name: str, start_time: float) -> None:
        """
        处理终止/取消指令 (abort)：
        1. 校验当前状态为 RUNNING 或 PAUSED，否则直接幂等忽略；
        2. 状态置为 ABORTED，唤醒挂起的线程以使其安全退出；
        3. 透传调用当前底层插件的 abort() 紧急刹车；
        4. 回复平台 ACK_EXECUTE 成功响应。
        """
        duration_ms = int((time.time() - start_time) * 1000)
        resp_data = {"task_id": task_id, "task_name": task_name, "task_action": "abort", "duration_ms": duration_ms}

        if self.task_state not in ["RUNNING", "PAUSED"]:
            resp_data["task_status"] = self.task_state
            logger.warning(f"⚠️ 收到 abort 指令，但当前任务状态为 [{self.task_state}]，直接忽略")
            if self.response_callback:
                self.response_callback(msg_id=msg_id, reply_type="ACK_EXECUTE", code=4000, message="当前没有可取消的任务", data=resp_data)
            return

        self._clear_auto_rth_timer()
        with self._worker_lock:
            if self._active_abort_event is not None:
                self._active_abort_event.set()
            self._active_task_token = None

        self.task_state = "ABORTED"
        self._pause_event.set()  # 唤醒挂起的流水线以检测到 ABORTED 并安全终止退出
        logger.info(f"🛑 收到终止/打断指令: [{task_name}] (msg_id: {msg_id})")

        EventManager().publish(TaskEvent(
            event_type="task_cancelled", task_id=task_id or task_name, task_name=task_name,
            step=getattr(self, "_current_step", 1), reason="收到平台 abort 取消指令"
        ))

        # 透传调用插件 abort()
        if self._current_plugin is not None:
            try:
                self._current_plugin.abort()
                logger.info("🛑 已向当前子任务插件透传 abort() 调用")
            except Exception as e:
                logger.warning(f"⚠️ 向插件透传 abort() 时异常: {e}")
            finally:
                self._current_plugin = None

        # 联动急停所有宏组件
        try:
            self.component_manager.abort_all_active_components()
        except Exception as e:
            logger.warning(f"⚠️ 联动急停活跃宏组件时异常: {e}")

        resp_data["task_status"] = "ABORTED"
        # 【双闭环更新】控制指令回复成功，原任务的 msg_id 回复将由工作线程退出时调用 send_aborted_ack 自动完成！
        self._send_success_response(msg_id, f"任务 [{task_name}] 已成功终止/打断", resp_data)

    def _handle_control_rth(self, payload: Dict[str, Any], msg_id: str, task_id: str, task_name: str, start_time: float) -> None:
        """
        处理安全返航指令 (rth - Return To Home)：
        1. 校验当前状态必须在 RUNNING/PAUSED/FAILED 范围内；
        2. 立即打断当前正在执行的动作，并设为 ABORTED；
        3. 提取任务元数据 (优先使用 payload 指定的 rth，其次取全局上下文，最后从磁盘获取)；
        4. 调用 RthManager 静态编译器一次性生成全部返航步骤；
        5. 打上 _is_rth=True 标记，提交给独立的 RthWorker 线程启动返航执行流水线。
        """
        duration_ms = int((time.time() - start_time) * 1000)
        resp_data = {"task_id": task_id, "task_name": task_name, "action": "rth", "duration_ms": duration_ms}

        self._clear_auto_rth_timer()
        if self.task_state not in ["RUNNING", "PAUSED", "FAILED"]:
            resp_data["status"] = self.task_state.lower()
            logger.warning(f"⚠️ 收到 rth 指令，但当前任务状态为 [{self.task_state}]，直接忽略")
            if self.response_callback:
                self.response_callback(msg_id=msg_id, reply_type="ACK_EXECUTE", code=4000, message="当前状态不可返航", data=resp_data)
            return

        logger.warning("🚨 收到全局返航指令 (RTH)！准备截断当前任务并逆向生成返航路径...")
        
        # 1. 强制原子废黜原任务会话，杜绝原任务被意外唤醒复活
        with self._worker_lock:
            old_worker_thread = self._active_worker_thread
            if self._active_abort_event is not None:
                self._active_abort_event.set()

        # 2. 立即打断当前物理插件
        if self._current_plugin is not None:
            try:
                self._current_plugin.abort()
            except Exception as e:
                logger.error(f"返航前执行插件 abort 异常: {e}")

        # 3. 联动急停所有宏组件
        try:
            self.component_manager.abort_all_active_components()
        except Exception as e:
            logger.error(f"返航前执行宏组件联动急停异常: {e}")

        # 4. 广播原任务已取消，并瞬间唤醒可能在 pause 等待的原线程使其感知 token 退出
        self.task_state = "ABORTED"
        self._pause_event.set()

        # 5. 若原工作线程仍然存活，等待其感知 token 废黜并安全退出 (最多 1 秒)
        if old_worker_thread is not None and old_worker_thread.is_alive():
            logger.info("⏳ 正在等待原任务工作线程平滑退出...")
            old_worker_thread.join(timeout=1.0)

        # 6. 核心：提取任务元数据 (层级降级保护：payload 覆盖 > ContextManager > StorageManager 磁盘补查)
        task_metadata = ContextManager.get_robot_task()
        if payload.get("rth") is not None:
            task_metadata["rth"] = payload["rth"]
        elif not task_metadata.get("rth") and task_id:
            disk_data = self.storage_manager.get_task_data(task_id) or {}
            if "rth" in disk_data:
                task_metadata["rth"] = disk_data["rth"]

        # 提取当前正在执行的真实任务 ID 和名称，防止告警联动的临时 ID 污染平台溯源
        real_task_id = task_metadata.get("task_id") or task_id
        real_task_name = task_metadata.get("task_name") or task_name

        # 7. 一次性静态编译返航动作序列
        builder = RthManager()
        rth_steps = builder.build(self.current_execution_queue, getattr(self, "_current_step_index", 0), task_metadata)

        if not rth_steps:
            logger.warning("返航链生成为空，无需返航")
            if self.response_callback:
                self.response_callback(msg_id=msg_id, reply_type="ACK_EXECUTE", code=0, message="当前无可返航步骤")
            return

        logger.info(f"✨ 成功生成返航链，准备倒序执行 {len(rth_steps)} 个步骤...")
        rth_task_id = f"{real_task_id}_RTH"
        rth_task_name = f"{real_task_name}_返航"
        rth_payload = dict(payload)
        rth_payload["steps"] = rth_steps
        rth_payload["action"] = "run"
        rth_payload["task_id"] = rth_task_id
        rth_payload["task_name"] = rth_task_name
        rth_payload["_is_rth"] = True  # 核心标示：豁免动态任务链校验
        msg_id = msg_id.replace("task", "rth")
        rth_payload["msg_id"] = msg_id
        # 8. 创建专属返航会话并启动独立 RthWorker 线程
        rth_token, rth_abort_event = self._create_task_session("RthWorker")
        rth_thread = threading.Thread(
            target=self._execute_task_steps,
            args=(rth_payload, rth_steps, rth_task_id, rth_task_name, msg_id, "task", start_time, rth_token, rth_abort_event),
            daemon=True,
            name="RthWorker"
        )
        with self._worker_lock:
            self._active_worker_thread = rth_thread
        rth_thread.start()

    # ---------------------------------------------------------
    # 任务库管理与调度执行 (Storage & Run Handlers)
    # ---------------------------------------------------------

    def _handle_task_management(self, payload: Dict[str, Any], action: Optional[str],
                                target_task_id: str, task_name: str, msg_id: str,
                                start_time: float, steps_in_payload: Optional[list]) -> None:
        """
        离线任务库的 CRUD 管理指令：
        - delete: 删除指定任务的磁盘文件与缓存；
        - list: 盘点当前本地保存的所有离线任务清单；
        - clear: 一键清空本地任务库；
        - save / update: 原子落盘保存任务 (将 rth 等扩展字段完整透传存盘)。
        """
        duration_ms = int((time.time() - start_time) * 1000)

        if action == "delete":
            logger.info(f"🗑️ 收到离线任务删除指令: [{target_task_id}] (msg_id: {msg_id})")
            del_res = self.storage_manager.delete_task(target_task_id)
            code = 0 if del_res.get("status") == "success" else 5000
            resp_data = {"task_id": target_task_id, "task_name": task_name, "duration_ms": duration_ms}
            if self.response_callback:
                self.response_callback(msg_id=msg_id, reply_type="ACK_EXECUTE", code=code, message=del_res.get("message"), data=resp_data)

        elif action == "list":
            logger.info(f"📋 收到离线任务清单查询指令 (msg_id: {msg_id})")
            list_res = self.storage_manager.list_tasks()
            self._send_success_response(msg_id, "获取本地离线任务清单成功", {**list_res, "duration_ms": duration_ms})

        elif action == "clear":
            logger.info(f"🧹 收到清空本地离线任务指令 (msg_id: {msg_id})")
            clear_res = self.storage_manager.clear_tasks()
            self._send_success_response(msg_id, clear_res.get("message"), {**clear_res, "duration_ms": duration_ms})

        elif action in ["save", "update", "create", "sync", "modify", "edit"] or not action:
            if steps_in_payload is not None:
                steps_to_save = steps_in_payload if isinstance(steps_in_payload, list) else []
                # 剥离系统控制类字段，将其余元数据 (如 rth_point, task_type, priority 等) 完整持久化落盘
                metadata = {k: v for k, v in payload.items() if k not in ["cmd_type", "action", "task_id", "task_name", "steps", "msg_id", "timestamp"]}
                self.storage_manager.save_task_to_disk(task_id=target_task_id, steps=steps_to_save, name=task_name, metadata=metadata)
                logger.info(f"💾 离线任务 [{target_task_id}] 已保存/修改成功 (含元数据: {list(metadata.keys())})")
                resp_data = {"task_id": target_task_id, "task_name": task_name, "steps_count": len(steps_to_save), "action": action or "save", "duration_ms": duration_ms}
                self._send_success_response(msg_id, f"任务 [{target_task_id}] 保存/修改完成", resp_data)

    def _handle_task_run(self, payload: Dict[str, Any], msg_id: str, target_task_id: str,
                         task_name: str, cmd_type: str, start_time: float) -> None:
        """
        触发执行离线任务：
        1. 状态互斥校验：若当前处于 RUNNING 或 PAUSED，拒绝执行新任务；
        2. 从磁盘或缓存读取完整任务定义 (自动兼容 steps 为 list 或包装字典的情况)；
        3. 将持久化的元数据 (如 rth) 合并回运行时 payload 中；
        4. 异步启动 TaskWorker 线程执行多步骤流水线。
        """
        if self.task_state in ["RUNNING", "PAUSED"]:
            self._send_error_response(
                msg_id, 4009,
                f"当前网关有任务处于 [{self.task_state}] 状态，拒绝下发并执行新任务！请先等待当前任务完成、重试恢复或强行终止。",
                {"task_id": target_task_id, "task_name": task_name, "current_task_state": self.task_state, "duration_ms": int((time.time() - start_time) * 1000)}
            )
            return

        logger.info(f"📂 收到离线任务载入执行指令: [{target_task_id}] (msg_id: {msg_id})")
        task_data = self.storage_manager.get_task_data(target_task_id)

        # ------------------------------------------------------------------
        # [校验]: 当前位置与 rth_point 偏差是否超过设定阈值
        # ------------------------------------------------------------------
        current_pos = ContextManager.get_status_field("localization")
        rth_info = task_data.get("rth") if isinstance(task_data, dict) else None
        
        if current_pos and isinstance(current_pos, dict) and rth_info and isinstance(rth_info, dict):
            try:
                curr_x, curr_y = float(current_pos.get("x", 0)), float(current_pos.get("y", 0))
                
                rth_loc = rth_info.get("localization")
                if not rth_loc or len(rth_loc) < 2:
                    raise ValueError("rth中缺少localization坐标数组或长度不足")
                
                rth_x, rth_y = float(rth_loc[0]), float(rth_loc[1])
                
                distance = math.hypot(curr_x - rth_x, curr_y - rth_y)
                max_deviation = float(self.config_loader.get("gateway", {}).get("max_rth_deviation_m", 1.0))
                
                if distance > max_deviation:
                    err_msg = f"无法执行任务：机器人当前位置距任务起点(rth)过远 (偏差 {distance:.2f} 米，大于允许的 {max_deviation} 米阈值)"
                    logger.warning(f"⚠️ {err_msg}")
                    self._send_error_response(
                        msg_id, 4010, err_msg,
                        {"task_id": target_task_id, "distance_m": round(distance, 2), "max_allowed_m": max_deviation, "duration_ms": int((time.time() - start_time) * 1000)}
                    )
                    return
            except (ValueError, TypeError) as e:
                logger.error(f"解析坐标计算距离时异常: {e}")
        # ------------------------------------------------------------------

        # 兼容 list (旧配置) 或 dict (标准落盘格式) 的任务数据结构
        if isinstance(task_data, list):
            execution_queue = task_data
        elif isinstance(task_data, dict):
            execution_queue = task_data.get("steps", [])
            for k, v in task_data.items():
                if k not in payload:
                    payload[k] = v  # 将持久化的 rth 合并入运行时 payload
        else:
            execution_queue = []

        if not execution_queue:
            self._send_error_response(msg_id, 4005, f"本地任务库与 data/ 目录中均不存在离线任务: [{target_task_id}]，任务终止。")
            return

        # 启动专属工作线程执行步骤流
        task_token, task_abort_event = self._create_task_session("TaskWorker")
        worker_thread = threading.Thread(
            target=self._execute_task_steps,
            args=(payload, execution_queue, target_task_id, task_name, msg_id, cmd_type, start_time, task_token, task_abort_event),
            daemon=True,
            name="TaskWorker"
        )
        with self._worker_lock:
            self._active_worker_thread = worker_thread
        worker_thread.start()

    # ---------------------------------------------------------
    # 任务流水线执行引擎 (Pipeline Execution Engine)
    # ---------------------------------------------------------

    def _wait_if_paused(self, msg_id: str, step_num: int, start_time: float,
                        task_token: Optional[str] = None,
                        task_abort_event: Optional[threading.Event] = None) -> bool:
        """
        基于 threading.Event 的高效挂起等待函数 (消灭忙轮询)：
        - 当 task_state == PAUSED 时，通过 _pause_event.wait(0.2) 阻塞当前工作线程；
        - 每轮循环与唤醒后严格核验任务专属会话令牌 (task_token) 与取消事件 (task_abort_event)；
        - 若任务在暂停期间被取消 (ABORTED) 或被新任务/RTH抢占废黜，返回 False (安全终止退出)；
        - 当收到合法 resume 指令且会话令牌依然有效时，返回 True (继续运行)。
        :return: True 表示恢复继续运行，False 表示在暂停期间被取消、被取代或终止
        """
        while self.task_state == "PAUSED":
            self._pause_event.wait(timeout=0.2)
            # 严格核验专属取消事件与令牌有效性
            if (task_abort_event and task_abort_event.is_set()) or \
               (task_token and self._active_task_token != task_token) or \
               self.task_state == "ABORTED":
                token_str = task_token[:8] if task_token else "none"
                logger.warning(f"🛑 [步骤 {step_num}] 任务 [token={token_str}] 在暂停等待期间被取消或被新任务/RTH取代，安全终止退出")
                return False

        # 退出 while 循环后进行二次严格核验
        if (task_abort_event and task_abort_event.is_set()) or \
           (task_token and self._active_task_token != task_token) or \
           self.task_state == "ABORTED":
            token_str = task_token[:8] if task_token else "none"
            logger.warning(f"🛑 [步骤 {step_num}] 任务 [token={token_str}] 唤醒后核验失败 (已被抢占/取消)，立即终止")
            return False

        return True

    def _handle_step_error(self, err_msg: str, code: int, step_num: int, total_steps: int,
                           plugin_type: str, action_name: str, target_task_id: str,
                           task_name: str, msg_id: str, start_time: float,
                           task_token: Optional[str] = None,
                           task_abort_event: Optional[threading.Event] = None) -> bool:
        """
        收敛统一的步骤失败处理、事件发布与自动挂起等待逻辑：
        1. 检查任务是否已被废黜，若已废黜直接退出；
        2. 记录 ERROR 日志并发布 subtask_failed 事件；
        3. 向平台发送 ACK_EXECUTE 失败响应 (标明 awaiting_platform_action=True)；
        4. 将任务状态自动置为 PAUSED 并挂起，等待平台下发 resume 重试或 abort 终止。
        :return: True 表示收到平台重试/恢复指令，False 表示被终止退出
        """
        if (task_abort_event and task_abort_event.is_set()) or \
           (task_token and self._active_task_token != task_token):
            return False

        logger.error(f"❌ {err_msg}")
        duration_ms = int((time.time() - start_time) * 1000)
        EventManager().publish(TaskEvent(
            event_type="subtask_failed", task_id=target_task_id, task_name=task_name,
            subtask_id=f"step_{step_num}", plugin_type=plugin_type,
            step=step_num, step_index=step_num, reason=err_msg
        ))
        err_data = {
            "plugin_type": plugin_type, "action": action_name,
            "duration_ms": duration_ms, "failed_step": step_num,
            "awaiting_platform_action": True
        }
        if self.response_callback:
            self.response_callback(
                msg_id=msg_id, reply_type="ACK_EXECUTE", code=code,
                message=f"{err_msg} (已自动挂起PAUSED，等待平台重试/终止)",
                data=err_data
            )
        self.task_state = "PAUSED"
        self._pause_event.clear()
        logger.warning(f"⏸️ [步骤 {step_num}/{total_steps}] 任务已自动挂起(PAUSED)，等待平台重试/终止...")
        return self._wait_if_paused(msg_id, step_num, start_time, task_token, task_abort_event)

    def _execute_task_steps(self, payload: Dict[str, Any], execution_queue: list,
                            target_task_id: str, task_name: str, msg_id: str,
                            cmd_type: str, start_time: float,
                            task_token: Optional[str] = None,
                            task_abort_event: Optional[threading.Event] = None) -> None:
        """
        核心任务流水线工作线程 (Worker Pipeline Loop)：
        顺序执行 execution_queue 中的每一个子动作，处理组件调度、进度 ACK 上报、暂停挂起与异常重试。
        每一步执行严格依赖专属 task_token 与 task_abort_event，确保被抢占或取消时立刻安全退出，
        并在退出时通过 send_aborted_ack 闭包确保向平台可靠发送原任务的终态取消失败 ACK (ACK_EXECUTE, code=4009)。
        """
        if not self.plugin_manager:
            self._send_error_response(msg_id, 5000, "PluginManager 尚未初始化")
            return

        step_index = 0
        self._current_step_index = 0
        self.current_execution_queue = execution_queue
        total_steps = len(execution_queue)
        token_str = task_token[:8] if task_token else "none"
        logger.info(f"🚀 开始执行命令流: [{msg_id}] (会话token: {token_str}), 共 {total_steps} 个动作")

        # 终态 ACK 单次上报闭包守护
        task_ack_sent = False

        def send_aborted_ack(reason: str, at_step: int, code: int = 4009, task_status: str = "ABORTED") -> None:
            nonlocal task_ack_sent
            if not task_ack_sent:
                task_ack_sent = True
                duration_ms = int((time.time() - start_time) * 1000)
                logger.warning(f"🛑 [TaskManager] 向平台发送任务 [{msg_id}] 终态回复: step={at_step}/{total_steps}, status={task_status}, code={code}, reason={reason}")
                if not task_token or self._active_task_token == task_token:
                    ContextManager.update_robot_task({"status": task_status, "msg_id": None})
                if self.response_callback:
                    message = f"任务 [{task_name}] 在步骤 {at_step}/{total_steps} 因 [{reason}] 已终止取消" if code == 4009 else f"任务 [{task_name}] 因步骤 {at_step} 发生致命异常已彻底崩溃终止: {reason}"
                    self.response_callback(
                        msg_id=msg_id, reply_type="ACK_EXECUTE", code=code,
                        message=message,
                        data={
                            "task_id": target_task_id,
                            "task_name": task_name,
                            "task_status": task_status,
                            "aborted_at_step": at_step,
                            "total_steps": total_steps,
                            "duration_ms": duration_ms
                        }
                    )

        # 将当前任务元数据注入全局共享内存池
        ContextManager.update_robot_task(payload)
        self.task_state = "RUNNING"
        self._pause_event.set()
        self._current_plugin = None
        last_result = None

        while step_index < total_steps:
            # 1. 严格核验专属取消事件与令牌有效性 (被抢占/取消时向平台发送取消 ACK 并安全退出)
            if (task_abort_event and task_abort_event.is_set()) or \
               (task_token and self._active_task_token != task_token):
                logger.warning(f"🛑 [步骤 {step_index + 1}/{total_steps}] 任务 [token={token_str}] 已被全局废黜或取代，安全退出流水线")
                send_aborted_ack("任务已被抢占或废黜", step_index + 1)
                return

            self._current_step_index = step_index
            item = execution_queue[step_index]
            step_num = item.get("step", step_index + 1)
            self._current_step = step_num
            plugin_type = item.get("plugin_type")
            action_name = item.get("action")
            params = item.get("params", {}) or {}

            # 2. 检查是否已被全局打断
            if self.task_state == "ABORTED" or (task_abort_event and task_abort_event.is_set()):
                logger.warning(f"🛑 [步骤 {step_num}/{total_steps}] 任务已被取消，跳过后续所有步骤")
                send_aborted_ack("收到终止取消指令", step_num)
                return

            # 3. 检查当前是否处于暂停状态，挂起等待
            if not self._wait_if_paused(msg_id, step_num, start_time, task_token, task_abort_event):
                send_aborted_ack("暂停等待期间收到取消指令或被新任务/RTH取代", step_num)
                return

            step_start_time = time.time()
            try:
                # 3.5 执行前，发送 step_status: started 的 ACK_PROGRESS
                if self.response_callback:
                    self.response_callback(
                        msg_id=msg_id, reply_type="ACK_PROGRESS", code=0,
                        message=f"开始执行步骤 {step_num}/{total_steps} [{plugin_type}.{action_name}]",
                        data={
                            "task_id": target_task_id,
                            "task_name": task_name,
                            "step": step_num,
                            "total_steps": total_steps,
                            "plugin_type": plugin_type,
                            "plugin_action": action_name,
                            "task_status": "RUNNING",
                            "step_status": "started",
                            "duration_ms": 0
                        }
                    )

                # 4. 动态分发执行：区分业务宏组件 (Component) 与底层原子插件 (Plugin)
                if "component_type" in item:
                    comp_type = item.get("component_type")
                    logger.info(f"▶ [步骤 {step_num}/{total_steps}] 调度宏组件 [{comp_type}] 执行")
                    comp = self.component_manager.get_component_instance(comp_type)
                    self._current_plugin = comp
                    last_result = comp.execute(params)
                    self._last_plugin = comp
                    self._current_plugin = None
                elif "plugin_type" in item:
                    logger.info(f"▶ [步骤 {step_num}/{total_steps}] 调度插件 [{plugin_type}] 执行 [{action_name}]")
                    plugin = self.plugin_manager.get_plugin(plugin_type)
                    self._current_plugin = plugin
                    last_result = plugin.execute(action=action_name, params=params)
                    self._last_plugin = plugin
                    self._current_plugin = None
                else:
                    raise KeyError("步骤配置错误：缺少 component_type 或 plugin_type")

                # 5. 执行后再次核验令牌有效性
                if (task_abort_event and task_abort_event.is_set()) or \
                   (task_token and self._active_task_token != task_token):
                    logger.warning(f"🛑 [步骤 {step_num}] 动作完成后核验发现任务已被废黜，终止后续步骤")
                    send_aborted_ack("执行中被新任务/RTH取代废黜", step_num)
                    return

                # 6. 检查动作是否触发了暂停信号 (例如插件内部主动挂起)
                is_paused_signal = (
                    self.task_state == "PAUSED" or
                    getattr(self._last_plugin, "_is_paused", False) is True or
                    (last_result and last_result.get("status") == "paused")
                )

                if is_paused_signal:
                    self.task_state = "PAUSED"
                    self._pause_event.clear()
                    logger.warning(f"⏸️ [步骤 {step_num}/{total_steps}] 捕获到 pause 暂停信号/中断，挂起等待 resume 恢复...")
                    if not self._wait_if_paused(msg_id, step_num, start_time, task_token, task_abort_event):
                        send_aborted_ack("步骤暂停期间被取消或被取代", step_num)
                        return
                    if (task_abort_event and task_abort_event.is_set()) or \
                       (task_token and self._active_task_token != task_token):
                        send_aborted_ack("任务被抢占废黜", step_num)
                        return
                    logger.info(f"▶️ 任务已恢复运行 (RUNNING)，重新尝试执行步骤 {step_num} [{action_name}]...")
                    continue

                # 7. 检查插件是否返回执行失败
                if last_result and last_result.get("status") == "error":
                    err_msg = f"步骤 {step_num} 执行失败: {last_result.get('message')}"
                    code = 4008 if "超时" in last_result.get("message", "") else 5000
                    if not self._handle_step_error(err_msg, code, step_num, total_steps, plugin_type, action_name,
                                                   target_task_id, task_name, msg_id, start_time,
                                                   task_token, task_abort_event):
                        send_aborted_ack("步骤失败挂起后被取消终止", step_num)
                        return
                    if (task_abort_event and task_abort_event.is_set()) or \
                       (task_token and self._active_task_token != task_token):
                        send_aborted_ack("任务被抢占废黜", step_num)
                        return
                    logger.info(f"▶️ 收到平台重试/恢复指令，重新尝试执行步骤 {step_num} [{action_name}]...")
                    continue

            except KeyError as e:
                err_msg = f"找不到对应的能力组件: {e}"
                logger.error(f"❌ {err_msg}")
                if self.response_callback:
                    step_duration_ms = int((time.time() - step_start_time) * 1000)
                    self.response_callback(
                        msg_id=msg_id, reply_type="ACK_PROGRESS", code=4004,
                        message=err_msg,
                        data={
                            "task_id": target_task_id,
                            "task_name": task_name,
                            "step": step_num,
                            "total_steps": total_steps,
                            "plugin_type": plugin_type or str(e),
                            "plugin_action": action_name,
                            "task_status": "FAILED",
                            "step_status": "failed",
                            "duration_ms": step_duration_ms
                        }
                    )
                self.task_state = "FAILED"
                send_aborted_ack(err_msg, step_num, code=4004, task_status="FAILED")
                return

            except Exception as e:
                err_msg = f"执行步骤 {step_num} 时发生未捕获异常: {e}"
                logger.error(f"❌ {err_msg}")
                if self.response_callback:
                    step_duration_ms = int((time.time() - step_start_time) * 1000)
                    self.response_callback(
                        msg_id=msg_id, reply_type="ACK_PROGRESS", code=5000,
                        message=err_msg,
                        data={
                            "task_id": target_task_id,
                            "task_name": task_name,
                            "step": step_num,
                            "total_steps": total_steps,
                            "plugin_type": plugin_type,
                            "plugin_action": action_name,
                            "task_status": "FAILED",
                            "step_status": "failed",
                            "duration_ms": step_duration_ms
                        }
                    )
                self.task_state = "FAILED"
                send_aborted_ack(str(e), step_num, code=5000, task_status="FAILED")
                return

            # 8. 单步成功：核验令牌后向平台推送步骤进度 ACK (ACK_PROGRESS)
            if (task_abort_event and task_abort_event.is_set()) or \
               (task_token and self._active_task_token != task_token):
                logger.warning(f"🛑 [步骤 {step_num}] 进度上报前发现任务已被废黜，放弃发送进度 ACK")
                send_aborted_ack("单步成功后被新任务抢占废黜", step_num)
                return

            if self.response_callback:
                step_duration_ms = int((time.time() - step_start_time) * 1000)
                progress_data = {
                    "task_id": target_task_id,
                    "task_name": task_name,
                    "step": step_num,
                    "total_steps": total_steps,
                    "plugin_type": plugin_type,
                    "plugin_action": action_name,
                    "task_status": "RUNNING",
                    "step_status": "success",
                    "duration_ms": step_duration_ms,
                    "result": last_result
                }
                self.response_callback(
                    msg_id=msg_id, reply_type="ACK_PROGRESS", code=0,
                    message=f"步骤 {step_num}/{total_steps} [{plugin_type}.{action_name}] 执行完成",
                    data=progress_data
                )

            step_index += 1

        # 9. 全流程执行完毕：仅在当前任务会话仍然有效且未被抢占时，更新状态并上报最终任务完成 ACK
        if (task_abort_event and task_abort_event.is_set()) or \
           (task_token and self._active_task_token != task_token):
            logger.warning(f"🛑 任务 [token={token_str}] 执行完毕但发现已被新任务抢占，跳过 FINISH 广播")
            send_aborted_ack("任务完成前被新任务抢占", total_steps)
            return

        task_ack_sent = True
        self.task_state = "FINISH"
        ContextManager.update_robot_task({"status": "FINISH", "msg_id": None})
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"🏁 命令 [{msg_id}] 处理圆满完成 (耗时: {duration_ms}ms)。")

        if self.response_callback:
            success_data = {
                "task_id": target_task_id,
                "task_name": task_name,
                "task_status": "FINISH",
                "total_steps": total_steps,
                "executed_steps": total_steps,
                "duration_ms": duration_ms
            }
            self.response_callback(msg_id=msg_id, reply_type="ACK_EXECUTE", code=0, message="任务完成", data=success_data)

    # ---------------------------------------------------------
    # 即时单能力指令执行器 (Instant Action Executor)
    # ---------------------------------------------------------

    def _handle_single_action(self, payload: Dict[str, Any], msg_id: str, start_time: float) -> None:
        """
        处理无状态即时单动作/单宏组件指令：
        - 适用于调试、单个传感器抓拍或单门开关控制；
        - 直接调度 PluginManager 或 ComponentManager 执行并立即返回 ACK。
        """
        logger.info(f"⚡ 收到无状态即时单能力指令 (msg_id: {msg_id})")
        try:
            params = payload.get("params", {}) or {}

            if "component_type" in payload:
                comp_type = payload.get("component_type")
                logger.info(f"▶ 调度无状态宏组件 [{comp_type}] 执行")
                comp = self.component_manager.get_component_instance(comp_type)
                self._current_plugin = comp
                last_result = comp.execute(params)
                self._current_plugin = None
            elif "plugin_type" in payload:
                plugin_type = payload.get("plugin_type")
                action_name = payload.get("action")
                logger.info(f"▶ 调度无状态插件 [{plugin_type}] 执行 [{action_name}]")
                plugin = self.plugin_manager.get_plugin(plugin_type)
                self._current_plugin = plugin
                last_result = plugin.execute(action=action_name, params=params)
                self._current_plugin = None
            else:
                raise KeyError("无效的动作指令: 缺少 component_type 或 plugin_type")

            duration_ms = int((time.time() - start_time) * 1000)
            if last_result and last_result.get("status") == "success":
                self._send_success_response(msg_id, "动作执行成功", {"result": last_result, "duration_ms": duration_ms})
            elif last_result and last_result.get("status") == "aborted":
                msg = last_result.get('message', '任务被打断')
                logger.info(f"🛑 即时指令已安全终止: {msg}")
                if self.response_callback:
                    self.response_callback(msg_id=msg_id, reply_type="ACK_EXECUTE", code=4009, message=f"动作已被打断: {msg}", data={"result": last_result, "duration_ms": duration_ms})
            else:
                msg = last_result.get('message') if last_result else '未知错误'
                logger.warning(f"⚠️ 即时指令执行失败: {msg}")
                if self.response_callback:
                    self.response_callback(msg_id=msg_id, reply_type="ACK_EXECUTE", code=5001, message=f"动作执行失败: {msg}", data={"result": last_result, "duration_ms": duration_ms})
        except Exception as e:
            logger.error(f"❌ 即时动作执行异常: {e}")
            if self.response_callback:
                self.response_callback(msg_id=msg_id, reply_type="ACK_EXECUTE", code=5005, message=f"执行动作时发生未捕获异常: {e}")

    def _handle_action_abort(self, msg_id: str) -> None:
        """单动作特权打断：立即终止当前正在执行的无状态单能力动作"""
        if self._current_plugin is not None:
            logger.info(f"🛑 收到单动作特权打断指令 (msg_id: {msg_id})，立即终止当前无状态动作")
            try:
                self._current_plugin.abort()
            except Exception as e:
                logger.error(f"打断单动作时异常: {e}")
        else:
            logger.warning("⚠️ 收到单动作打断指令，但当前并无正在执行的单动作。")

    # ---------------------------------------------------------
    # 辅助工具方法 (Helpers & Responses)
    # ---------------------------------------------------------

    def _send_error_response(self, msg_id: str, code: int, message: str, data: Optional[dict] = None) -> None:
        """统一发送错误 ACK 响应 (reply_type=ACK_EXECUTE)"""
        logger.error(f"❌ {message}")
        if self.response_callback:
            self.response_callback(msg_id=msg_id, reply_type="ACK_EXECUTE", code=code, message=message, data=data)

    def _send_success_response(self, msg_id: str, message: str, data: Optional[dict] = None) -> None:
        """统一发送成功 ACK 响应 (reply_type=ACK_EXECUTE)"""
        if self.response_callback:
            self.response_callback(msg_id=msg_id, reply_type="ACK_EXECUTE", code=0, message=message, data=data)

    def _clear_auto_rth_timer(self):
        """取消暂停超时自动返航定时器"""
        if hasattr(self, "_auto_rth_timer") and self._auto_rth_timer:
            self._auto_rth_timer.cancel()
            self._auto_rth_timer = None

    def _trigger_auto_rth(self, target_task_id: str):
        """定时器回调：任务暂停超时未恢复，强制构造 fake_rth_payload 触发安全返航"""
        timeout_sec = self.config_loader.get("gateway", {}).get("auto_rth_timeout_sec", 300)
        logger.warning(f"🚨 任务已暂停超时 {timeout_sec} 秒未收到重试，自动触发强制返航！")
        fake_rth_payload = {
            "msg_id": f"rth_{generate_msg_id()}",
            "cmd_type": "task",
            "action": "rth"
        }
        self.handle_task(fake_rth_payload)

    def _handle_alarm_auto_action(self, event: TaskEvent) -> None:
        """告警联动回调：接收到严重硬件告警时，调度触发匹配的自动化动作"""
        action = event.extra_data.get("auto_action")
        if action:
            logger.warning(f"🚨 接收到自动化匹配动作 [{action}]，强制调度中...")
            fake_payload = {
                "msg_id": f"rth_{generate_msg_id()}",
                "cmd_type": "task",
                "action": action
            }
            self.handle_task(fake_payload)
