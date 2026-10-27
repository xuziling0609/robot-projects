"""
TelemetryManager - 状态上报与心跳调度管理器
==========================================

设计背景与架构意图:
-----------------
在机器人边缘网关架构中，各类传感器硬件、运动底盘、机械臂与外设以能力插件 (Plugin) 的形式注册到 PluginManager。
网关需要以固定的心跳频率，将整机全量插件的运行状态、实时指标（如电量、速度、瓦斯浓度、局放幅值、门禁状态等）
以及当前任务调度引擎的执行状态进行合流汇总，通过 MQTT 协议统一上报给上层物联网/巡检云平台 (/status/up)。

历史缺陷与重构目标:
-----------------
1. 【消除单插件异常导致的雪崩 (Fault Isolation)】:
   历史实现中无保护地直接调用插件方法，任何单个传感器（如串口偶发抖动、通信超时）发生抛错即导致整机心跳中断。
   重构后构筑单插件级的细粒度 try-except 隔离壁垒，确保单个硬件异常绝不影响其他插件的状态合流。

2. 【标准事件总线契约对接 (Standard Event Contract)】:
   使用 core.event_manager 的 EventType.TELEMETRY_SWEEP_READY 强契约枚举发布告警扫描事件，
   消除局部 import 与裸字符串硬编码。

3. 【响应式线程模型与毫秒级停机 (Responsive Thread & Graceful Shutdown)】:
   基于 threading.Event() 构建心跳主循环，彻底消除原始 time.sleep(1.0) 导致的停机延迟，
   支持 stop(timeout=...) 阻塞回收线程，杜绝孤儿后台守护线程。

4. 【状态快照自省与高可观测性 (Observability)】:
   在内存中维护最近一次采集的遥测快照与时间戳，提供 get_latest_telemetry()、is_running()、
   trigger_sweep() 等标准化自省与管理接口。
"""

import time
import threading
import copy
from typing import Optional, Dict, Any

from core.logger_manager import get_logger
from core.plugin_manager import PluginManager
from core.mqtt_manager import MQTTManager
from core.task_manager import TaskManager
from core.event_manager import EventManager, TaskEvent, EventType

logger = get_logger("TelemetryManager")


class TelemetryManager:
    """
    状态上报与心跳调度管理器 (TelemetryManager)
    专职负责网关全量能力插件实时状态搜集、合流组装与 MQTT 心跳状态上报。
    """

    def __init__(
        self,
        plugin_manager: PluginManager,
        mqtt_manager: MQTTManager,
        task_manager: Optional[TaskManager] = None,
        interval: float = 5.0
    ):
        """
        初始化遥测管理器。

        :param plugin_manager: 插件管理器实例，用于动态扫描并访问已注册的能力插件
        :param mqtt_manager: MQTT 客户端管理器实例，用于向云端发布合流后的状态心跳
        :param task_manager: 可选的任务管理器实例，用于获取当前整机任务状态 (如 IDLE, RUNNING, PAUSED)
        :param interval: 状态心跳上报周期 (秒)，默认 5.0 秒
        """
        self.pm = plugin_manager
        self.mqtt_cli = mqtt_manager
        self.task_engine = task_manager
        self.interval = float(interval)

        # 线程生命周期与同步控制
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # 运行状态与最近一次采集缓存
        self._last_publish_time: float = 0.0
        self._latest_telemetry_cache: Dict[str, Any] = {}
        self._latest_sweep_timestamp: float = 0.0

        # 全局事件总线单例引用
        self._event_manager = EventManager()

    @property
    def _running(self) -> bool:
        """向后兼容属性：反映心跳线程是否正在运行"""
        return not self._stop_event.is_set() and (self._thread is not None and self._thread.is_alive())

    @_running.setter
    def _running(self, value: bool) -> None:
        """向后兼容属性设置器"""
        if value:
            self._stop_event.clear()
        else:
            self._stop_event.set()

    def is_running(self) -> bool:
        """
        自省接口：查询心跳管理线程当前是否处于运行状态。

        :return: 若后台心跳线程处于活跃状态返回 True，否则返回 False
        """
        return not self._stop_event.is_set() and (self._thread is not None and self._thread.is_alive())

    def get_latest_telemetry(self) -> Dict[str, Any]:
        """
        自省接口：获取最近一次成功采集合流的插件遥测数据快照（深拷贝）。

        :return: 插件遥测数据字典，包含最新采集的各个插件状态指标
        """
        with self._lock:
            return copy.deepcopy(self._latest_telemetry_cache)

    def get_latest_sweep_timestamp(self) -> float:
        """
        自省接口：获取最近一次完成遥测扫描的 Unix 时间戳 (秒)。

        :return: 时间戳浮点数，若从未扫描过返回 0.0
        """
        with self._lock:
            return self._latest_sweep_timestamp

    def collect_plugin_telemetry(self) -> Dict[str, Any]:
        """
        全量扫描并收集所有活跃能力插件暴露的遥测数据字典。

        设计特性:
        1. 【单插件细粒度异常隔离】: 遍历各个插件并调用 status() / get_status() 时，
           包裹独立的 try-except 保护，某单个硬件故障不影响其余插件采集；
        2. 【数据优先级自适应】: 优先获取标准 get_status() 结构化字典，兜底读取
           latest_telemetry 通用遥测字段；
        3. 【事件总线触发】: 采集前发布 EventType.TELEMETRY_SWEEP_READY 事件，
           驱动 AlarmManager 执行规则扫盘评估。

        :return: 合流后的插件数据字典 {plugin_name: telemetry_data}
        """
        # 1. 发布事件以触发解耦的 AlarmManager 进行告警阈值扫盘
        try:
            sweep_event = TaskEvent(
                event_type=EventType.TELEMETRY_SWEEP_READY,
                task_id="system",
                task_name="telemetry_sweep",
                extra_data={"plugin_manager": self.pm}
            )
            self._event_manager.publish(sweep_event)
        except Exception as event_err:
            logger.error("告警扫盘触发事件发布异常: %s", event_err, exc_info=True)

        plugins_dict: Dict[str, Any] = {}

        # 2. 遍历插件管理器中的全量插件，逐一构筑异常隔离屏障
        if self.pm and hasattr(self.pm, "plugins"):
            for name, plugin_inst in self.pm.plugins.items():
                try:
                    # 检查插件是否处于就绪/在线状态
                    is_online = True
                    if hasattr(plugin_inst, "status") and callable(plugin_inst.status):
                        is_online = bool(plugin_inst.status())

                    if not is_online:
                        continue

                    plugin_data = None

                    # 优先尝试获取定制化的结构化状态数据 (如 NavPlugin 的底盘、电量、坐标)
                    if hasattr(plugin_inst, "get_status") and callable(plugin_inst.get_status):
                        status_data = plugin_inst.get_status()
                        if isinstance(status_data, dict):
                            plugin_data = status_data

                    # 若未实现 get_status() 或返回非字典，尝试读取通用的 latest_telemetry 属性
                    if plugin_data is None:
                        plugin_data = getattr(plugin_inst, "latest_telemetry", None)

                    # 仅在非空时收入上报字典（支持动态自动清理与下线）
                    if plugin_data:
                        plugins_dict[name] = plugin_data

                except Exception as plugin_err:
                    # 细粒度隔离：记录警告并跳过当前故障插件，保障全网关遥测合流不中断
                    logger.warning("插件 [%s] 状态采集异常，已自动隔离防护: %s", name, plugin_err)

        # 3. 线程安全更新内存快照缓存与时间戳
        with self._lock:
            self._latest_telemetry_cache = copy.deepcopy(plugins_dict)
            self._latest_sweep_timestamp = time.time()

        return plugins_dict

    def publish_status_once(self) -> None:
        """
        执行单次全量插件状态合流并发布至 MQTT 状态主题 (/status/up)。
        """
        try:
            plugins_dict = self.collect_plugin_telemetry()
            task_state = self.task_engine.get_task_state() if self.task_engine else "IDLE"

            self.mqtt_cli.publish_status(
                task_state=task_state,
                robot_status={"plugins": plugins_dict}
            )
            self._last_publish_time = time.time()
            logger.debug("成功上报机器人状态心跳 (任务状态: %s, 活跃插件数: %d)", task_state, len(plugins_dict))
        except Exception as pub_err:
            logger.error("状态合流上报至 MQTT 发生异常: %s", pub_err, exc_info=True)

    def trigger_sweep(self) -> None:
        """
        手动强制触发一次状态采集与 MQTT 上报 (便于外部指令或调试)。
        """
        self.publish_status_once()

    def start(self) -> None:
        """
        启动后台配置化周期的定时心跳上报守护线程。

        如果已在运行中则安全忽略。
        """
        if self.is_running():
            logger.warning("TelemetryManager 心跳线程已在运行中，无需重复启动")
            return

        self._stop_event.clear()

        def heartbeat_loop() -> None:
            logger.info("启动 TelemetryManager 状态心跳管理线程 (上报周期: %.1fs)...", self.interval)
            while not self._stop_event.is_set():
                try:
                    now = time.time()
                    # 检查距上次上报的时间差是否满足配置周期 (预留 0.5s 弹性容差)
                    if now - self._last_publish_time >= max(0.1, self.interval - 0.5):
                        self.publish_status_once()
                except Exception as loop_err:
                    logger.error("状态心跳主循环异常: %s", loop_err, exc_info=True)

                # 以 0.5s 为步长响应式等待，收到停止信号时可瞬时退出
                self._stop_event.wait(timeout=min(0.5, max(0.1, self.interval)))

            logger.info("TelemetryManager 状态心跳管理线程已安全退出。")

        self._thread = threading.Thread(
            target=heartbeat_loop,
            daemon=True,
            name="TelemetryManagerHeartbeat"
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """
        安全平滑停止心跳管理线程。

        :param timeout: 等待后台线程退出的最长阻塞超时时间 (秒)，默认 2.0 秒
        """
        if self._stop_event.is_set() and (self._thread is None or not self._thread.is_alive()):
            return

        logger.info("正在停止 TelemetryManager 状态心跳管理线程...")
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("TelemetryManager 线程在 %.1fs 内未完全终止，强制移交后台守护回收", timeout)
            else:
                logger.info("TelemetryManager 线程已平滑回收完毕。")
        self._thread = None
