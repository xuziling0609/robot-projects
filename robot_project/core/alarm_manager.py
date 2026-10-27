import os
import json
import time
import threading
import yaml
from typing import Dict, Any, List, Optional, Tuple

from core.logger_manager import get_logger
from core.mqtt_manager import MQTTManager
from core.event_manager import EventManager, TaskEvent
from utils.constants import PROJECT_ROOT

logger = get_logger("AlarmManager")
PLUGINS_DATA_DIR = os.path.join(PROJECT_ROOT, "data", "plugins")
TASK_ALARM_CONFIG_PATH = os.path.join(PROJECT_ROOT, "configs", "alarm_config.yaml")


class AlarmManager:
    """
    全局独立告警管理器 (AlarmManager - 工业级线程安全与双告警引擎架构)

    【核心能力与架构定位】
    1. 双重告警引擎支持 (Dual Alarm Engines):
       - 传感器与遥测阈值评估引擎 (Telemetry Sweep Engine):
         实时/周期性扫盘各能力插件的最新遥测数值，基于文件修改时间 (mtime) 零阻塞自动感知热重载规则，并执行多级阈值算子匹配；
       - 任务生命周期事件告警引擎 (Task Lifecycle Alarm Engine):
         零耦合订阅 EventBus 事件总线 (subtask_failed, task_paused, task_resumed, task_cancelled 等)，依据任务告警规则实施防抖抑制并网络上报；
    2. DCL 线程安全单例 (Double-Checked Locking Singleton):
       - 支持多线程并发安全初始化；
    3. 参数化路径注入与环境隔离 (Parametric Path Injection):
       - 支持构造函数注入规则目录与配置文件路径，让单元测试可在独立沙箱运行，彻底杜绝读写污染生产物理目录；
    4. 状态强一致与并发保护 (Thread-Safe Synchronization):
       - 内部采用 `threading.RLock()` 严密保护规则字典与通道状态机，杜绝多线程遍历/修改竞态崩溃；
    5. 可观测自省与运维控制 (Observability & Operational APIs):
       - 提供 `get_active_alarms()` 活跃告警查询、`clear_alarm_state()` 手动复位、`get_stats()` 统计指标自省与 `reset()` 销毁重置能力。
    """

    _instance: Optional["AlarmManager"] = None
    _instance_lock = threading.RLock()

    def __new__(cls, *args, **kwargs) -> "AlarmManager":
        """
        DCL 双重检测锁单例构建
        """
        if not cls._instance:
            with cls._instance_lock:
                if not cls._instance:
                    instance = super(AlarmManager, cls).__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(
        self,
        plugins_data_dir: Optional[str] = None,
        task_alarm_config_path: Optional[str] = None
    ):
        """
        初始化告警管理器（仅在首次构建时执行一次）

        :param plugins_data_dir: 传感器告警规则存储目录 (默认 data/plugins/)
        :param task_alarm_config_path: 任务生命周期告警配置文件物理路径 (默认 configs/alarm_config.yaml)
        """
        if getattr(self, "_initialized", False):
            return

        with self._instance_lock:
            if getattr(self, "_initialized", False):
                return

            self._lock = threading.RLock()
            self._plugins_data_dir = plugins_data_dir or PLUGINS_DATA_DIR
            self._task_alarm_config_path = task_alarm_config_path or TASK_ALARM_CONFIG_PATH

            # 核心规则与状态映射（均受 self._lock 互斥保护）
            self.rules_cfg: Dict[str, Dict[str, Any]] = {}
            self.task_alarm_cfg: Dict[str, Any] = {}
            self._file_mtimes: Dict[str, float] = {}
            self._last_alarm_state: Dict[str, str] = {}
            self._last_event_suppress_times: Dict[str, float] = {}
            self._total_alarms_triggered: int = 0
            self._event_bus_bound: bool = False

            # 加载初始配置与绑定事件总线
            self.check_and_reload_configs()
            self.check_and_reload_task_alarm_config()
            self.bind_event_bus()

            self._initialized = True

    @classmethod
    def report_alarm(
        cls,
        level: str = "warning",
        code: int = 5000,
        message: str = "",
        source_plugin: str = "",
        data: Optional[dict] = None
    ) -> None:
        """
        供外部组件及底层插件主动调用的统一告警上报入口函数
        内部透传至 MQTTManager.send_alarm 执行网络/离线持久化上报

        :param level: 告警级别 ("info", "warning", "error", "fatal")
        :param code: 告警错误码
        :param message: 告警文本描述
        :param source_plugin: 产生告警的源插件/模块名
        :param data: 附加结构化数据字典
        """
        MQTTManager.send_alarm(
            level=level,
            code=code,
            message=message,
            source_plugin=source_plugin,
            data=data
        )

    def check_and_reload_configs(self) -> None:
        """
        扫盘 plugins_data_dir 目录下的 *_alarm.json 文件，
        根据 mtime 文件修改时间戳自动感知并线程安全地热重载传感器阈值规则
        """
        if not os.path.exists(self._plugins_data_dir):
            return

        with self._lock:
            try:
                for filename in os.listdir(self._plugins_data_dir):
                    if filename.endswith("_alarm.json"):
                        file_path = os.path.join(self._plugins_data_dir, filename)
                        try:
                            mtime = os.path.getmtime(file_path)
                            if file_path not in self._file_mtimes or mtime > self._file_mtimes[file_path]:
                                self._file_mtimes[file_path] = mtime
                                with open(file_path, "r", encoding="utf-8") as f:
                                    raw_cfg = json.load(f)
                                if raw_cfg:
                                    self._merge_rules(raw_cfg)
                                    logger.info(f"🔄 [AlarmManager] 自动检测到 {filename} 更新，已热重载传感器规则")
                        except Exception as fe:
                            logger.error(f"❌ [AlarmManager] 读取/重载文件 {filename} 失败: {fe}")
            except Exception as e:
                logger.error(f"❌ [AlarmManager] 扫描 {self._plugins_data_dir} 目录异常: {e}")

    def check_and_reload_task_alarm_config(self) -> None:
        """
        根据 mtime 动态感知并线程安全地热重载 task_alarm_config_path 任务告警配置
        """
        if not os.path.exists(self._task_alarm_config_path):
            return

        with self._lock:
            try:
                mtime = os.path.getmtime(self._task_alarm_config_path)
                if (
                    self._task_alarm_config_path not in self._file_mtimes
                    or mtime > self._file_mtimes[self._task_alarm_config_path]
                ):
                    self._file_mtimes[self._task_alarm_config_path] = mtime
                    with open(self._task_alarm_config_path, "r", encoding="utf-8") as f:
                        cfg_data = yaml.safe_load(f) or {}
                    self.task_alarm_cfg = cfg_data.get("task_alarms", {})
                    logger.info(f"🔄 [AlarmManager] 已成功感知并热重载任务指令告警配置: {self._task_alarm_config_path}")
            except Exception as e:
                logger.error(f"❌ [AlarmManager] 重载 {self._task_alarm_config_path} 异常: {e}")

    def bind_event_bus(self) -> None:
        """
        绑定 EventManager 事件总线订阅，具备防重复订阅保护
        """
        with self._lock:
            if self._event_bus_bound:
                return

            try:
                em = EventManager()
                em.subscribe("subtask_failed", self.handle_task_event)
                em.subscribe("task_paused", self.handle_task_event)
                em.subscribe("task_resumed", self.handle_task_event)
                em.subscribe("task_cancelled", self.handle_task_event)
                em.subscribe("telemetry_sweep_ready", self.handle_telemetry_event)
                self._event_bus_bound = True
                logger.info("✅ [AlarmManager] 已成功订阅 EventManager 任务生命周期与遥测扫盘告警事件")
            except Exception as e:
                logger.error(f"❌ [AlarmManager] 绑定 EventManager 失败: {e}", exc_info=True)

    def unbind_event_bus(self) -> None:
        """
        解绑 EventManager 事件总线订阅，常用于停机销毁或单测隔离
        """
        with self._lock:
            if not self._event_bus_bound:
                return

            try:
                em = EventManager()
                em.unsubscribe("subtask_failed", self.handle_task_event)
                em.unsubscribe("task_paused", self.handle_task_event)
                em.unsubscribe("task_resumed", self.handle_task_event)
                em.unsubscribe("task_cancelled", self.handle_task_event)
                em.unsubscribe("telemetry_sweep_ready", self.handle_telemetry_event)
                self._event_bus_bound = False
                logger.info("🛑 [AlarmManager] 已成功注销 EventManager 事件订阅")
            except Exception as e:
                logger.error(f"❌ [AlarmManager] 解绑 EventManager 失败: {e}")

    def handle_telemetry_event(self, event: TaskEvent) -> None:
        """
        处理遥测扫盘就绪广播事件 (telemetry_sweep_ready)

        :param event: TaskEvent 实例，携带 plugin_manager 引用
        """
        pm = event.extra_data.get("plugin_manager") if event.extra_data else None
        if pm:
            self.sweep_and_evaluate(pm)

    def handle_task_event(self, event: TaskEvent) -> None:
        """
        处理任务生命周期事件 (subtask_failed, task_paused, task_resumed, task_cancelled)

        :param event: TaskEvent 实例
        """
        if not event or not isinstance(event, TaskEvent):
            return

        # 触发配置热重载检测
        self.check_and_reload_task_alarm_config()

        with self._lock:
            rule = self.task_alarm_cfg.get(event.event_type)
            if not rule or not rule.get("enabled", True):
                logger.debug(f"ℹ️ [AlarmManager] 事件类型 '{event.event_type}' 告警未启用或未配置，跳过上报")
                return

            # 防抖抑制频控判定 (Per event_type & task_id)
            suppress_sec = float(rule.get("suppress_seconds", 0))
            key = f"{event.event_type}_{event.task_id}"
            now = time.time()

            if suppress_sec > 0:
                last_time = self._last_event_suppress_times.get(key, 0.0)
                if now - last_time < suppress_sec:
                    logger.info(f"⏳ [AlarmManager] 事件 [{key}] 处于防抖抑制窗口内 ({suppress_sec}s)，跳过本次告警")
                    return
                self._last_event_suppress_times[key] = now

            step_val = (
                event.step
                if (hasattr(event, "step") and event.step is not None and event.step > 0)
                else (event.step_index if (getattr(event, "step_index", 0) > 0) else 1)
            )

            # 格式化告警消息内容
            raw_tmpl = rule.get("message_template", "任务[{task_id}] 触发事件 {event_type}")
            try:
                formatted_msg = raw_tmpl.format(
                    task_id=event.task_id,
                    task_name=event.task_name or event.task_id,
                    subtask_id=event.subtask_id or f"step_{step_val}",
                    step=step_val,
                    step_index=step_val,
                    plugin_type=event.plugin_type or "TaskManager",
                    reason=event.reason or "无详细异常信息",
                )
            except Exception as fe:
                formatted_msg = f"任务[{event.task_id}] 步骤{step_val}: {event.reason} ({fe})"

            alarm_level = rule.get("level", "warning")
            alarm_code = int(rule.get("code", 5000))
            source_plugin = event.plugin_type or "TaskManager"

            payload_data = {
                "task_id": event.task_id,
                "task_name": event.task_name or event.task_id,
                "step": step_val,
                "plugin_type": source_plugin,
                "reason": event.reason,
                "event_type": event.event_type,
            }
            if event.extra_data:
                for k, v in event.extra_data.items():
                    if k not in payload_data:
                        payload_data[k] = v

            self._total_alarms_triggered += 1

        logger.warning(
            f"🚨 [AlarmManager] 上报任务指令告警! [{event.event_type}] -> 等级: {alarm_level}, 错误码: {alarm_code}, 内容: {formatted_msg}"
        )

        MQTTManager.send_alarm(
            level=alarm_level,
            code=alarm_code,
            message=formatted_msg,
            source_plugin=source_plugin,
            data=payload_data,
        )

    def _merge_rules(self, raw_cfg: Any) -> None:
        """
        解析并合并各插件下发的阈值规则列表/对象至全局内存字典 self.rules_cfg (受 _lock 保护)
        """
        if isinstance(raw_cfg, dict) and ("gasType" in raw_cfg or "metric_name" in raw_cfg):
            raw_cfg = [raw_cfg]

        if isinstance(raw_cfg, list):
            for item in raw_cfg:
                if isinstance(item, dict):
                    key = str(item.get("gasType", item.get("metric_name", ""))).upper()
                    if key:
                        self.rules_cfg[key] = item
        elif isinstance(raw_cfg, dict):
            for k, item in raw_cfg.items():
                if isinstance(item, dict):
                    key = str(item.get("gasType", item.get("metric_name", k))).upper()
                    self.rules_cfg[key] = item

    def _check_operator(self, val: Any, op: str, threshold_val: Any) -> bool:
        """
        谓词算子计算引擎 (lt / lte / gt / gte / eq / neq / between / in)
        具备严格的类型安全校验与防崩溃容错
        """
        if val is None or threshold_val is None or op is None:
            return False

        op = str(op).strip().lower()

        # 字符串/离散等值匹配
        if op in ("eq", "=="):
            return str(val).strip() == str(threshold_val).strip()
        elif op in ("neq", "ne", "!="):
            return str(val).strip() != str(threshold_val).strip()
        elif op == "in":
            if isinstance(threshold_val, (list, tuple, set)):
                return str(val).strip() in [str(x).strip() for x in threshold_val]
            return str(val).strip() in str(threshold_val).strip()

        # 数值比较匹配
        try:
            f_val = float(val)
            if op in ("lt", "<"):
                return f_val < float(threshold_val)
            elif op in ("lte", "<="):
                return f_val <= float(threshold_val)
            elif op in ("gt", ">"):
                return f_val > float(threshold_val)
            elif op in ("gte", ">="):
                return f_val >= float(threshold_val)
            elif op == "between":
                if isinstance(threshold_val, (list, tuple)) and len(threshold_val) >= 2:
                    low = float(threshold_val[0])
                    high = float(threshold_val[1])
                    return low <= f_val <= high
        except (ValueError, TypeError):
            return False

        return False

    def evaluate_plugin_telemetry(self, source_plugin: str, telemetry_readings: List[Dict[str, Any]]) -> None:
        """
        评估指定插件的遥测采样数据列表，执行通道级状态机转换与防重复上报

        :param source_plugin: 插件名称 (如 'GasPlugin')
        :param telemetry_readings: 采样字典列表
        """
        self.check_and_reload_configs()

        if not telemetry_readings or not isinstance(telemetry_readings, list):
            return

        with self._lock:
            if not self.rules_cfg:
                return

            for item in telemetry_readings:
                metric_name = str(item.get("name", item.get("metric_name", ""))).upper()
                if not metric_name or metric_name not in self.rules_cfg:
                    continue

                cfg = self.rules_cfg[metric_name]
                threshold_rules = cfg.get("thresholds", {})
                if not threshold_rules or not isinstance(threshold_rules, dict):
                    continue

                raw_val = item.get("value")
                if raw_val is None:
                    raw_val = item.get("concentration", item.get("max_temp", 0.0))

                try:
                    val = float(raw_val)
                except (ValueError, TypeError):
                    val = raw_val

                sensor_id = item.get("sensor_id", item.get("camera_id", 1))
                channel_code = item.get("channel_code", 1)
                unit = item.get("unit", cfg.get("unit", ""))

                channel_key = f"{source_plugin}_{sensor_id}_{channel_code}_{metric_name}"
                matched_level, matched_rule = self._match_rule(val, threshold_rules)
                last_level = self._last_alarm_state.get(channel_key)

                if matched_level in ["fatal", "error", "warning", "info"]:
                    # 仅当状态发生级别跳变（如 NORMAL -> warning 或 warning -> error）时上报，防止重复刷屏
                    if last_level != matched_level:
                        self._last_alarm_state[channel_key] = matched_level
                        self._total_alarms_triggered += 1
                        rule_msg = matched_rule.get("message", f"{metric_name} 触发 {matched_level} 告警")
                        full_msg = f"{rule_msg} (当前数值: {val} {unit})" if unit else f"{rule_msg} (当前值: {val})"
                        alarm_level = "error" if matched_level in ["fatal", "error"] else matched_level

                        logger.warning(
                            f"🚨 [AlarmManager] 传感器告警触发! [{channel_key}] -> 等级: {matched_level}, 内容: {full_msg}"
                        )
                        MQTTManager.send_alarm(
                            level=alarm_level,
                            code=5010,
                            message=full_msg,
                            source_plugin=source_plugin,
                            data={
                                "sensor_id": sensor_id,
                                "channel_code": channel_code,
                                "metric_name": metric_name,
                                "value": val,
                                "unit": unit,
                            },
                        )

                        auto_action = matched_rule.get("auto_action")
                        if auto_action:
                            logger.warning(f"🔄 告警规则命中联动动作 [{auto_action}]，向全局分发触发事件...")
                            EventManager().publish(
                                TaskEvent(
                                    event_type="alarm_auto_action",
                                    task_id=f"alarm_linkage_{int(time.time())}",
                                    task_name="告警阈值联动",
                                    extra_data={"auto_action": auto_action},
                                )
                            )
                else:
                    # 恢复正常态判断
                    if last_level is not None and last_level not in [None, "NORMAL", "info"]:
                        logger.info(f"✅ [AlarmManager] 传感器告警恢复正常 [{channel_key}] (当前值: {val} {unit})")
                    self._last_alarm_state[channel_key] = matched_level or "NORMAL"

    def sweep_and_evaluate(self, plugin_manager: Any) -> None:
        """
        扫盘全量已装载能力插件的 latest_telemetry 属性并评估告警

        :param plugin_manager: PluginManager 实例
        """
        self.check_and_reload_configs()
        self.check_and_reload_task_alarm_config()

        if not plugin_manager or not hasattr(plugin_manager, "plugins") or not plugin_manager.plugins:
            return

        for plugin_name, plugin in list(plugin_manager.plugins.items()):
            telemetry = getattr(plugin, "latest_telemetry", None)
            if telemetry and isinstance(telemetry, list):
                self.evaluate_plugin_telemetry(plugin_name, telemetry)

    def _match_rule(self, val: Any, threshold_rules: dict) -> Tuple[Optional[str], Optional[dict]]:
        """
        按严重等级由高至低顺序匹配规则: fatal -> error -> warning -> info
        """
        for level in ["fatal", "error", "warning", "info"]:
            rule = threshold_rules.get(level)
            if not rule or not isinstance(rule, dict):
                continue
            op = rule.get("operator")
            t_val = rule.get("value")
            if op and t_val is not None and self._check_operator(val, op, t_val):
                return level, rule
        return None, None

    # ---------------------------------------------------------------------
    # 可观测自省与运维干预 API
    # ---------------------------------------------------------------------

    def get_active_alarms(self) -> Dict[str, str]:
        """
        查询当前所有处于非正常告警态的通道快照
        
        :return: 键为 channel_key，值为当前告警级别 (如 'warning', 'error') 的字典
        """
        with self._lock:
            return {
                k: v for k, v in self._last_alarm_state.items()
                if v and v not in ("NORMAL", "info")
            }

    def clear_alarm_state(self, channel_key: Optional[str] = None) -> None:
        """
        手动消除或重置特定通道或全量通道的告警状态

        :param channel_key: 通道键名；若为 None 则清空全量通道告警状态机
        """
        with self._lock:
            if channel_key:
                self._last_alarm_state.pop(channel_key, None)
                logger.info(f"🧹 [AlarmManager] 已重置通道 [{channel_key}] 告警状态")
            else:
                self._last_alarm_state.clear()
                self._last_event_suppress_times.clear()
                logger.info("🧹 [AlarmManager] 已清空全量通道告警状态与防抖时间戳")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取告警管理器运行健康度与自省统计指标
        """
        with self._lock:
            active_alarms = self.get_active_alarms()
            return {
                "rules_count": len(self.rules_cfg),
                "task_alarm_rules_count": len(self.task_alarm_cfg),
                "active_alarm_count": len(active_alarms),
                "active_alarms": active_alarms,
                "total_alarms_triggered": self._total_alarms_triggered,
                "event_bus_bound": self._event_bus_bound,
            }

    @classmethod
    def reset(cls) -> None:
        """
        彻底重置单例状态、解绑事件总线并清空规则（专供单元测试环境使用）
        """
        with cls._instance_lock:
            if cls._instance:
                cls._instance.unbind_event_bus()
                with cls._instance._lock:
                    cls._instance.rules_cfg.clear()
                    cls._instance.task_alarm_cfg.clear()
                    cls._instance._file_mtimes.clear()
                    cls._instance._last_alarm_state.clear()
                    cls._instance._last_event_suppress_times.clear()
                    cls._instance._total_alarms_triggered = 0
                cls._instance = None

