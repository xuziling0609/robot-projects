"""
PluginManager - 边缘网关能力插件调度管理器
==========================================

设计背景与架构意图:
-----------------
在机器人边缘网关架构中，机器人所具备的各种软硬件能力（如导航底盘 NavPlugin、
工业机械臂 ArmPlugin、双目/云台相机 CameraPlugin、多气体检测 GasPlugin、
门禁控制器 DoorPlugin、电梯梯控 ElevatorPlugin、无线充电桩 StationPlugin 等）
均被抽象为独立解耦的插件模块 (BasePlugin)。

PluginManager 作为全网关能力插件的核心调度中枢与生命周期宿主，承担以下核心职责：
1. 【动态插件深度发现 (Dynamic Discovery & Reflection)】:
   自动扫描 plugins/ 目录下的所有独立子包，解析各自专属的 config.yaml 配置文件，
   根据配置动态穿透搜索并实例化继承自 BasePlugin 的目标类，注入独立参数字典 (params)。
2. 【控制反转与能力解耦契约 (Dependency Inversion & Capabilities)】:
   维护能力契约映射表 (capabilities)，支持基于能力契约 (如 "door_control", "elevator_dispatch")
   动态定位服务插件，实现上层编排调度对底层硬件具体类名的完全解耦。
3. 【全网关物模型与状态聚合 (Schema & State Aggregation)】:
   一键汇总所有已加载插件的物模型能力描述 (Capabilities Schema) 供 MQTT 向云平台注册；
   汇总全量插件的实时在线/工作指标状态供 TelemetryManager 心跳合流上报。
4. 【整机紧急联动与全局停机 (Global Abort & Lifecycle Management)】:
   提供 trigger_global_abort() 接口，在系统关机、急停或突发致命异常时，一键联动通知
   所有已挂载插件执行底层硬件的安全归位与中断。
"""

import os
import importlib
import pkgutil
import inspect
import threading
from typing import Dict, List, Optional, Any

from core.logger_manager import get_logger
from plugins.base import BasePlugin
from core.config_manager import ConfigManager

logger = get_logger("PluginManager")


class PluginManager:
    """
    边缘网关插件调度管理器 (并发安全单例模式)
    负责能力插件的动态反射发现、编程式注册、能力解耦路由与全局生命周期急停。
    """
    _instance: Optional["PluginManager"] = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> "PluginManager":
        """
        线程安全双重检测锁 (DCL) 单例实现，杜绝多线程并发初始化竞态。
        """
        if not cls._instance:
            with cls._instance_lock:
                if not cls._instance:
                    instance = super(PluginManager, cls).__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self):
        """
        初始化插件管理器内部注册表与并发互斥锁。
        通过 _initialized 标志确保即使多次调用 PluginManager() 构造函数，也绝不重复重置内存表。
        """
        if getattr(self, "_initialized", False):
            return

        with self._instance_lock:
            if getattr(self, "_initialized", False):
                return
            self._lock = threading.RLock()
            self.plugins: Dict[str, BasePlugin] = {}
            self.capabilities: Dict[str, BasePlugin] = {}
            self._initialized = True
            logger.info("PluginManager 插件调度管理器初始化就绪 (并发安全单例模式)")

    def reset(self) -> None:
        """
        清空当前已注册的所有插件与能力契约。
        主要用于测试环境清理隔离以及整机重启时的内存表重置。
        """
        with self._lock:
            count = len(self.plugins)
            self.plugins.clear()
            self.capabilities.clear()
            logger.info("PluginManager 已完成内存注册表重置 (清空插件数: %d)", count)

    def register_plugin(
        self,
        plugin_type: str,
        plugin_instance: BasePlugin,
        capabilities: Optional[List[str]] = None
    ) -> None:
        """
        编程式显式挂载插件实例。

        :param plugin_type: 插件唯一标识类型名称 (如 "NavPlugin", "DoorPlugin")
        :param plugin_instance: 继承自 BasePlugin 的插件实例对象
        :param capabilities: 可选的该插件声明支持的能力列表 (如 ["door_control", "rfid_scan"])
        """
        if not plugin_type or not isinstance(plugin_type, str):
            raise ValueError("plugin_type 必须为非空字符串")
        if plugin_instance is None:
            raise ValueError("plugin_instance 不能为空")

        with self._lock:
            self.plugins[plugin_type] = plugin_instance
            if capabilities:
                for cap in capabilities:
                    self.capabilities[cap] = plugin_instance
            logger.info(
                "成功编程式注册插件: [%s] (挂载能力: %s, 当前总插件数: %d)",
                plugin_type, capabilities or [], len(self.plugins)
            )

    def unregister_plugin(self, plugin_type: str) -> Optional[BasePlugin]:
        """
        安全注销已挂载的插件并同步清理其关联的能力契约。

        :param plugin_type: 拟注销的插件类型名称
        :return: 被注销的插件实例对象，若未找到则返回 None
        """
        with self._lock:
            if plugin_type not in self.plugins:
                logger.warning("尝试注销未挂载的插件: %s", plugin_type)
                return None

            removed_instance = self.plugins.pop(plugin_type)
            # 同步清理 capabilities 中指向该实例的所有能力映射
            caps_to_remove = [
                cap for cap, inst in self.capabilities.items()
                if inst is removed_instance
            ]
            for cap in caps_to_remove:
                self.capabilities.pop(cap, None)

            logger.info("已成功注销插件: [%s] (同步清理能力映射: %s)", plugin_type, caps_to_remove)
            return removed_instance

    def has_plugin(self, plugin_type: str) -> bool:
        """
        快速自省接口：判定指定类型的插件是否已被注册。

        :param plugin_type: 插件类型名称
        :return: 若已注册返回 True，否则返回 False
        """
        with self._lock:
            return plugin_type in self.plugins

    def list_plugins(self) -> List[str]:
        """
        自省接口：获取当前所有已挂载插件的名称列表。

        :return: 插件类型名称列表 (浅拷贝)
        """
        with self._lock:
            return list(self.plugins.keys())

    def get_plugin(self, plugin_type: str) -> BasePlugin:
        """
        按类型标识获取插件实例。供 TaskManager 在调度执行具体原子动作时调用。

        :param plugin_type: 目标插件类型名称
        :return: 对应的 BasePlugin 实例对象
        :raises KeyError: 当目标插件未注册时抛出
        """
        with self._lock:
            if plugin_type not in self.plugins:
                raise KeyError(f"能力插件未注册: {plugin_type}")
            return self.plugins[plugin_type]

    def get_plugin_by_capability(self, capability: str) -> BasePlugin:
        """
        基于能力契约获取插件实例 (依赖倒置 DIP 解耦核心)。

        :param capability: 声明的能力标识字符串 (如 "door_control")
        :return: 提供该能力的 BasePlugin 实例对象
        :raises KeyError: 当未找到提供该能力的插件时抛出
        """
        with self._lock:
            if capability not in self.capabilities:
                raise KeyError(f"未找到提供 [{capability}] 能力的插件。")
            return self.capabilities[capability]

    def discover_plugins(self, plugins_dir: str = "plugins") -> None:
        """
        遍历扫描插件目录，根据各子包下的 config.yaml 配置动态反射加载插件。

        :param plugins_dir: 插件存放的根目录相对或绝对路径，默认为工程根目录下的 "plugins"
        """
        logger.info("开始扫描本地插件库: %s/", plugins_dir)

        base_dir = os.path.abspath(plugins_dir)
        if not os.path.exists(base_dir):
            logger.error("插件目录不存在: %s", base_dir)
            return

        for item in os.listdir(base_dir):
            plugin_path = os.path.join(base_dir, item)

            # 过滤非目录及双下划线内部隐藏目录
            if not os.path.isdir(plugin_path) or item.startswith("__"):
                continue

            config_file = os.path.join(plugin_path, "config.yaml")
            if not os.path.exists(config_file):
                continue

            # 使用全局配置加载器读取插件专属配置并挂载到内存树
            try:
                plugin_config = ConfigManager().load_plugin(item, config_file)
            except Exception as cfg_err:
                logger.error("加载插件 [%s] 配置文件失败: %s", item, cfg_err, exc_info=True)
                continue

            if not plugin_config:
                continue

            # 检查插件是否启用
            if not plugin_config.get("enabled", True):
                logger.info("插件 [%s] 在配置中被禁用 (enabled=False)，跳过挂载", item)
                continue

            # 提取类名与能力契约
            target_class_name = plugin_config.get("plugin_type")
            if not target_class_name:
                logger.error("插件 [%s] 的 config.yaml 缺失 'plugin_type' 字段！", item)
                continue

            capabilities = plugin_config.get("capabilities", [])
            params = plugin_config.get("params", {})

            # 深度扫描反射并载入插件模块
            self._load_plugin_module(item, target_class_name, params, capabilities)

    def _load_plugin_module(
        self,
        package_name: str,
        target_class_name: str,
        params: dict,
        capabilities: list
    ) -> None:
        """
        利用 pkgutil 与 inspect 深度扫描子包内的所有 .py 模块，反射寻找并实例化目标类。

        :param package_name: 子包目录名称 (如 "nav", "door")
        :param target_class_name: 拟实例化的目标类名 (如 "NavPlugin")
        :param params: 注入给插件构造函数的独立参数字典
        :param capabilities: 插件声明的能力契约列表
        """
        try:
            module_name = f"plugins.{package_name}"
            # 1. 优先尝试从包本身 (对应 __init__.py) 获取类
            package = importlib.import_module(module_name)
            target_class = getattr(package, target_class_name, None)

            # 2. 若 __init__.py 未导出，则深度遍历该子目录下的所有 .py 模块文件
            if not target_class and hasattr(package, "__path__"):
                for _, modname, _ in pkgutil.iter_modules(package.__path__):
                    sub_module_name = f"{module_name}.{modname}"
                    try:
                        sub_module = importlib.import_module(sub_module_name)
                        for _, obj in inspect.getmembers(sub_module):
                            if (
                                inspect.isclass(obj)
                                and issubclass(obj, BasePlugin)
                                and obj is not BasePlugin
                                and obj.__name__ == target_class_name
                            ):
                                target_class = obj
                                break
                    except Exception as mod_err:
                        logger.warning("扫描子模块 [%s] 发生异常: %s", sub_module_name, mod_err)

                    if target_class:
                        break

            # 3. 实例化目标类并注册至内存表
            if target_class:
                plugin_instance = target_class(config=params)
                with self._lock:
                    self.plugins[target_class_name] = plugin_instance
                    for cap in capabilities:
                        self.capabilities[cap] = plugin_instance
                logger.info(
                    "成功挂载能力插件: [%s] (来源: %s/, 注册能力: %s)",
                    target_class_name, package_name, capabilities
                )
            else:
                logger.error(
                    "深度扫描 [%s/] 失败，未找到继承 BasePlugin 的目标类 [%s]",
                    package_name, target_class_name
                )

        except Exception as e:
            logger.error("动态加载插件 [%s] 发生未捕获异常: %s", package_name, e, exc_info=True)

    def trigger_global_abort(self) -> int:
        """
        整机全局紧急联动中止 (Global Emergency Abort)。

        在系统接收到 SIGTERM 终止信号、平滑退出或不可逆硬件急停时调用：
        安全遍历所有已注册插件，调用其 abort() / stop() 接口，迫使机械臂、底盘底盘、
        旋转云台、开门机等底层硬件立即安全断电或停机。

        :return: 成功触发急停的插件数量
        """
        with self._lock:
            plugins_snapshot = list(self.plugins.items())

        logger.warning("⚡ 触发整机全局插件联动急停 (待通知插件数: %d)...", len(plugins_snapshot))
        aborted_count = 0

        for name, plugin_inst in plugins_snapshot:
            try:
                if hasattr(plugin_inst, "abort") and callable(plugin_inst.abort):
                    plugin_inst.abort()
                    aborted_count += 1
                    logger.info("已成功向插件 [%s] 发送 abort 中止指令", name)
                elif hasattr(plugin_inst, "stop") and callable(plugin_inst.stop):
                    plugin_inst.stop()
                    aborted_count += 1
                    logger.info("已成功向插件 [%s] 发送 stop 停机指令", name)
            except Exception as abort_err:
                logger.error("向插件 [%s] 发送急停指令发生异常: %s", name, abort_err, exc_info=True)

        logger.info("整机全局急停联动处理完毕 (已响应插件数: %d/%d)", aborted_count, len(plugins_snapshot))
        return aborted_count

    def get_all_capabilities(self) -> List[Dict[str, Any]]:
        """
        获取所有已加载插件的能力物模型 (Schema) 列表。
        用于 MQTT 客户端在启动建连成功后，向云平台物模型管理服务统一报到注册。

        :return: 各插件物模型字典列表
        """
        with self._lock:
            plugins_snapshot = list(self.plugins.items())

        capabilities = []
        for plugin_name, plugin_instance in plugins_snapshot:
            try:
                if hasattr(plugin_instance, "get_capabilities") and callable(plugin_instance.get_capabilities):
                    caps = plugin_instance.get_capabilities()
                    if caps:
                        capabilities.append(caps)
                else:
                    logger.warning("插件 [%s] 未实现 get_capabilities 方法，跳过该项物模型上报", plugin_name)
            except Exception as e:
                logger.error("获取插件 [%s] 能力描述时出错: %s", plugin_name, e, exc_info=True)

        logger.debug("成功聚合 %d 个插件的能力物模型，准备上报云平台", len(capabilities))
        return capabilities

    def get_all_plugin_states(self) -> Dict[str, Any]:
        """
        搜集并聚合全量已加载插件的当前实时状态。
        用于心跳上报以及实时状态推送时构建 plugin_states 字段。

        :return: 字典映射 {plugin_name: status_dict}
        """
        with self._lock:
            plugins_snapshot = list(self.plugins.items())

        states = {}
        for plugin_name, plugin_instance in plugins_snapshot:
            try:
                state_data = None
                if hasattr(plugin_instance, "get_status") and callable(plugin_instance.get_status):
                    raw_state = plugin_instance.get_status()
                    if isinstance(raw_state, dict):
                        state_data = raw_state
                    elif isinstance(raw_state, bool):
                        state_data = {"status": "ONLINE" if raw_state else "OFFLINE"}

                if state_data is None:
                    if hasattr(plugin_instance, "status") and callable(plugin_instance.status):
                        is_online = bool(plugin_instance.status())
                        state_data = {"status": "ONLINE" if is_online else "OFFLINE"}
                    else:
                        state_data = {"status": "ONLINE"}

                states[plugin_name] = state_data
            except Exception as e:
                logger.error("获取插件 [%s] 状态异常: %s", plugin_name, e)
                states[plugin_name] = {"status": "ERROR", "message": str(e)}

        return states