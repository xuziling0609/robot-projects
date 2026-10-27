# -*- coding: utf-8 -*-
"""
================================================================================
机器人边缘网关 - 全局解耦事件管理器 (EventManager / EventBus)
================================================================================
核心职责：
1. 【发布-订阅总线 (Pub/Sub Event Bus)】：
   构建解耦的进程内事件总线，连接调度核心 (TaskManager)、遥测扫盘 (TelemetryManager)、
   多级告警 (AlarmManager) 及各类硬件插件 (Camera/Gas/Acoustic/Door/Nav)。
2. 【双模式派发 (Dual Dispatch Mode)】：
   - 异步高吞吐派发 (`publish`)：多生产者非阻塞推入线程安全队列 (<1ms)，后台守护线程异步串行派发；
   - 同步直接派发 (`publish_sync`)：高优先级/状态突变事件即时响应，零延迟同步驱动订阅者回调。
3. 【并发安全保障 (Concurrency & Thread-Safety)】：
   - 双重检测锁单例 (Double-Checked Locking Singleton)，保障多线程并发初始化时单例唯一；
   - 读写互斥锁 (_listeners_lock) 隔离监听器增删，遍历派发采用快照机制，根除字典迭代冲突 (RuntimeError)。
4. 【生命周期闭环 (Lifecycle Management)】：
   - 支持动态注销 (`unsubscribe`) 与清空 (`clear_listeners`)，防止内存泄漏；
   - 提供 `reset()` 接口便于单测快速还原干净状态；
   - 提供自省接口 (`get_queue_size`, `get_listener_count`, `is_running`) 支撑可观测性。
================================================================================
"""

import queue
import threading
import time
from enum import Enum
from typing import Callable, Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from core.logger_manager import get_logger

logger = get_logger("EventManager")


# ==============================================================================
# 1. 标准事件类型契约枚举 (EventType)
# ==============================================================================

class EventType(str, Enum):
    """
    系统标准事件类型枚举契约。
    
    继承 `str` 和 `Enum`，使得枚举成员具备字符串语义 (如 `EventType.TASK_PAUSED == "task_paused"` 恒为 True)，
    可直接无缝传递给原有的字符串比较逻辑、日志打印和字典查找，实现 100% 向后兼容。
    """
    # --- 调度器全局状态突变事件 ---
    GLOBAL_STATE_CHANGED = "global_state_changed"
    """调度器全局运行状态突变 (例如 IDLE -> RUNNING, RUNNING -> PAUSED, 载入任务等)，广播给业务插件"""

    # --- 任务生命周期突变事件 ---
    SUBTASK_FAILED = "subtask_failed"
    """子任务/步骤执行失败，携带失败原因与步骤号"""

    TASK_PAUSED = "task_paused"
    """任务主动或被动暂停，附带暂停上下文"""

    TASK_RESUMED = "task_resumed"
    """任务自暂停态恢复执行"""

    TASK_CANCELLED = "task_cancelled"
    """任务被平台指令取消/终止打断"""

    # --- 告警与联动事件 ---
    ALARM_AUTO_ACTION = "alarm_auto_action"
    """告警规则命中严重阈值后触发的自动打断或应急处置事件"""

    TELEMETRY_SWEEP_READY = "telemetry_sweep_ready"
    """遥测管理器扫盘采集完成，通知告警分析器进行阈值对比研判"""

    # --- 通配符类型 ---
    ALL = "*"
    """通配符：订阅系统发布的全部类型事件"""


# ==============================================================================
# 2. 核心事件载荷数据结构 (TaskEvent)
# ==============================================================================

@dataclass
class TaskEvent:
    """
    标准化事件载荷数据契约对象。
    
    属性说明：
        event_type (str | EventType): 事件类型，推荐使用 EventType 常量，也可传普通字符串。
        task_id (str): 关联的主任务 ID (如 TASK_OFFLINE_001、system 等)。
        task_name (str): 关联的任务可读名称。
        subtask_id (str): 关联的子任务或动作标识符。
        plugin_type (str): 触发事件或执行报错的插件类型 (如 NavPlugin, CameraPlugin)。
        step (int): 步骤编号 (从 1 开始计数)。
        step_index (int): 步骤在步骤列表中的下标索引 (从 0 开始计数，兼容历史保留)。
        reason (str): 状态突变或失败的原因描述。
        timestamp (float): 事件生成时间戳 (默认 time.time()，精确到秒级小数)。
        extra_data (Dict[str, Any]): 业务扩展键值对字典，用于传递任意上下文载荷。
    """
    event_type: Union[str, EventType]
    task_id: str
    task_name: str = ""
    subtask_id: str = ""
    plugin_type: str = ""
    step: int = 1
    step_index: int = 0
    reason: str = ""
    timestamp: float = field(default_factory=time.time)
    extra_data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # 确保 event_type 规范为原生字符串类型存储，便于哈希与查找
        if isinstance(self.event_type, Enum):
            self.event_type = str(self.event_type.value)
        else:
            self.event_type = str(self.event_type)

    def get(self, key: str, default: Any = None) -> Any:
        """
        向后兼容字典风格的安全读取接口。
        
        优先检查是否为 TaskEvent 本身的属性；若不存在，则在 extra_data 字典中检索。
        此方法保证了存量代码使用类似 `event.get("state")` 或 `event.get("custom_field")` 时平滑运行。
        
        Args:
            key: 目标属性或 extra_data 键名
            default: 不存在时返回的默认值
            
        Returns:
            获取到的值或 default
        """
        if hasattr(self, key):
            return getattr(self, key)
        if self.extra_data and isinstance(self.extra_data, dict):
            return self.extra_data.get(key, default)
        return default

    def __repr__(self) -> str:
        return (
            f"TaskEvent(type={self.event_type!r}, task_id={self.task_id!r}, "
            f"step={self.step}, reason={self.reason!r})"
        )


# ==============================================================================
# 3. 全局解耦事件管理器单例 (EventManager)
# ==============================================================================

class EventManager:
    """
    边缘网关全局解耦事件管理器 (EventManager - 线程安全单例)。
    
    设计模式与核心机制：
    1. 【双重检测锁单例 (DCL Singleton)】：
       确保在多线程高并发创建实例时，仅存在一个唯一的总线实例，消灭竞态风险。
    2. 【细粒度读写互斥锁 (_listeners_lock)】：
       保护 `_listeners` 订阅注册表的增删改查；派发事件时快速生成快照，释放锁后再调用回调，
       彻底避免字典遍历过程中的并发修改异常 (RuntimeError) 与回调内部死锁风险。
    3. 【后台消费守护线程 (_worker_thread)】：
       异步排队推入 (`publish`) 后，由单消费线程平滑消化，保障系统 IO 响应速度与吞吐。
    4. 【同步直派通道 (publish_sync)】：
       针对高实时性事件（如急停中断、关键告警）提供跳过队列直接同步派发能力。
    """
    _instance: Optional["EventManager"] = None
    _instance_lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "EventManager":
        """双重检测锁保障全局唯一实例"""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    # 订阅监听器字典：{ event_type: [handler_1, handler_2, ...] }
                    instance._listeners = {}
                    # 监听器增删与快照互斥锁
                    instance._listeners_lock = threading.Lock()
                    # 异步缓冲事件队列
                    instance._queue = queue.Queue()
                    # 运行标志与后台消费线程
                    instance._running = False
                    instance._worker_thread = None
                    cls._instance = instance
        return cls._instance

    # --------------------------------------------------------------------------
    # 订阅与注销接口 (Subscription APIs)
    # --------------------------------------------------------------------------

    def subscribe(self, event_type: Union[str, EventType], handler: Callable[[TaskEvent], None]) -> None:
        """
        线程安全地向事件总线注册监听器。
        
        Args:
            event_type: 要订阅的事件类型 (字符串或 EventType 枚举)。传入 "*" 表示通配订阅全量事件。
            handler: 事件触发时的回调函数，签名必须为 Callable[[TaskEvent], None]。
        """
        if not callable(handler):
            logger.warning(f"⚠️ [EventManager] 注册失败：传入的回调 handler 不是可调用对象: {handler}")
            return

        key = str(event_type.value) if isinstance(event_type, Enum) else str(event_type)
        with self._listeners_lock:
            if key not in self._listeners:
                self._listeners[key] = []
            if handler not in self._listeners[key]:
                self._listeners[key].append(handler)
                handler_name = getattr(handler, "__name__", str(handler))
                logger.info(f"📢 [EventManager] 注册事件监听器: type='{key}', handler={handler_name}")

    def unsubscribe(self, event_type: Union[str, EventType], handler: Callable[[TaskEvent], None]) -> bool:
        """
        线程安全地注销指定的事件监听器。
        
        用于插件销毁、页面关闭或测试还原时释放监听引用，杜绝内存泄漏。
        
        Args:
            event_type: 原订阅的事件类型 (字符串或 EventType 枚举)。
            handler: 原注册的回调函数对象。
            
        Returns:
            bool: 是否成功注销并移除了该监听器。
        """
        key = str(event_type.value) if isinstance(event_type, Enum) else str(event_type)
        with self._listeners_lock:
            if key in self._listeners and handler in self._listeners[key]:
                self._listeners[key].remove(handler)
                # 若对应事件类型的监听器列表已为空，清除该键
                if not self._listeners[key]:
                    del self._listeners[key]
                handler_name = getattr(handler, "__name__", str(handler))
                logger.info(f"🗑️ [EventManager] 注销事件监听器: type='{key}', handler={handler_name}")
                return True
        return False

    def clear_listeners(self, event_type: Optional[Union[str, EventType]] = None) -> None:
        """
        线程安全地清空监听器。
        
        Args:
            event_type: 可选。若指定则仅清空该事件类型的监听列表；若为 None 则清空全部事件的监听器。
        """
        with self._listeners_lock:
            if event_type is None:
                self._listeners.clear()
                logger.info("🧹 [EventManager] 已清空全部事件类型的监听器")
            else:
                key = str(event_type.value) if isinstance(event_type, Enum) else str(event_type)
                if key in self._listeners:
                    del self._listeners[key]
                    logger.info(f"🧹 [EventManager] 已清空事件类型 [{key}] 的监听器")

    # --------------------------------------------------------------------------
    # 事件发布接口 (Publishing APIs)
    # --------------------------------------------------------------------------

    def publish(self, event: TaskEvent) -> None:
        """
        异步非阻塞推入事件队列 (多生产者安全，耗时 < 1ms)。
        
        事件将被暂存入队列中，由后台消费守护线程平滑取出并派发给对应监听器。
        如果消费线程尚未通过 `start()` 启动，事件会安全缓存在队列中等待消费。
        
        Args:
            event: 标准化的 TaskEvent 事件对象。
        """
        if not event or not isinstance(event, TaskEvent):
            logger.warning(f"⚠️ [EventManager] 忽略非法事件推入: {event}")
            return

        self._queue.put(event)
        logger.debug(f"📤 [EventManager] 异步推入事件队列: type={event.event_type}, task_id={event.task_id}")

    def publish_sync(self, event: TaskEvent) -> None:
        """
        同步直接派发事件 (阻塞当前调用线程)。
        
        绕过后台异步队列，立即对当前所有精确匹配及通配符订阅者执行回调。
        适用于紧急打断、关键状态突变或单测中需要确定性即时响应的场景。
        
        Args:
            event: 标准化的 TaskEvent 事件对象。
        """
        if not event or not isinstance(event, TaskEvent):
            logger.warning(f"⚠️ [EventManager] 忽略非法同步事件: {event}")
            return

        logger.debug(f"⚡ [EventManager] 同步直派事件: type={event.event_type}, task_id={event.task_id}")
        self._dispatch_event(event)

    # --------------------------------------------------------------------------
    # 核心分发与线程主循环 (Internal Dispatch & Worker Thread)
    # --------------------------------------------------------------------------

    def _dispatch_event(self, event: TaskEvent) -> None:
        """
        执行具体的事件派发逻辑。
        
        关键安全机制：
        1. 在互斥锁保护下快速获取匹配 handler 列表的【浅拷贝快照】，随后立即释放锁；
        2. 在锁外逐一执行回调函数，防止用户回调耗时过长导致其他线程注册事件被死锁阻塞；
        3. 单个 handler 的抛错通过 try-except 完全隔离，确保不会中断后续其他订阅者的调用。
        """
        event_type_str = str(event.event_type)
        with self._listeners_lock:
            # 拷贝精确匹配该类型的 handlers
            handlers_snapshot = list(self._listeners.get(event_type_str, []))
            # 叠加通配符 '*' 的全量事件 handlers (去重保护)
            if event_type_str != "*":
                for wild_h in self._listeners.get("*", []):
                    if wild_h not in handlers_snapshot:
                        handlers_snapshot.append(wild_h)

        for handler in handlers_snapshot:
            try:
                handler(event)
            except Exception as e:
                handler_name = getattr(handler, "__name__", str(handler))
                logger.error(
                    f"❌ [EventManager] 监听器 [{handler_name}] 处理事件 ({event_type_str}) 异常: {e}",
                    exc_info=True
                )

    def _process_queue(self) -> None:
        """后台事件队列消费守护线程的主循环"""
        while self._running:
            try:
                # 设定超时便于在 stop() 时优雅退出阻塞
                event: TaskEvent = self._queue.get(timeout=0.5)
                self._dispatch_event(event)
                self._queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"❌ [EventManager] 队列处理主循环异常: {e}", exc_info=True)

    # --------------------------------------------------------------------------
    # 生命周期与可观测性接口 (Lifecycle & Observability APIs)
    # --------------------------------------------------------------------------

    def start(self) -> None:
        """
        幂等启动后台事件消费守护线程。
        若线程已在运行，重复调用将直接跳过。
        """
        if not self._running:
            self._running = True
            self._worker_thread = threading.Thread(
                target=self._process_queue,
                daemon=True,
                name="EventManagerThread"
            )
            self._worker_thread.start()
            logger.info("🚀 [EventManager] 后台消费守护线程已启动")

    def stop(self, timeout: float = 2.0) -> None:
        """
        安全停止后台事件消费线程。
        
        Args:
            timeout: 等待守护线程正常退出的超时时间 (秒)。
        """
        if not self._running:
            return

        self._running = False
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)
        logger.info("🛑 [EventManager] 后台消费守护线程已安全停止")

    def reset(self) -> None:
        """
        重置事件总线的所有内部状态（清空队列、停机并清空所有监听器）。
        主要供单元测试、系统热重启或配置重载使用。
        """
        self.stop(timeout=1.0)
        # 清空积压队列
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except (queue.Empty, ValueError):
                break
        self.clear_listeners()
        logger.info("🔄 [EventManager] 事件管理器状态已全部重置还原")

    def get_queue_size(self) -> int:
        """获取当前异步事件队列中待消费的积压任务数量"""
        return self._queue.qsize()

    def get_listener_count(self, event_type: Optional[Union[str, EventType]] = None) -> int:
        """
        获取当前已注册的监听器总数。
        
        Args:
            event_type: 可选。若指定则统计该类型的监听器数量；若为 None 则统计全部类型的监听器总数。
        """
        with self._listeners_lock:
            if event_type is not None:
                key = str(event_type.value) if isinstance(event_type, Enum) else str(event_type)
                return len(self._listeners.get(key, []))
            return sum(len(handlers) for handlers in self._listeners.values())

    def is_running(self) -> bool:
        """查询后台消费守护线程当前是否处于存活运行状态"""
        return self._running and (self._worker_thread is not None and self._worker_thread.is_alive())


# ==============================================================================
# 兼容别名与外部导出
# ==============================================================================
EventBus = EventManager
