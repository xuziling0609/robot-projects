# -*- coding: utf-8 -*-
"""
业务宏组件管理中枢 (ComponentManager)

架构定位与职责说明：
----------------------------------------------------------------------------------------------------
在边缘网关系统中，物理与通信能力划分为两层模型：
1. **原子插件层 (Atomic Plugins, `plugins/`)**：
   - 负责单一物理设备或单一协议通信的直接驱动（如底盘 ChassisPlugin、门禁 DoorPlugin、机械臂 ArmPlugin）；
   - 具有全局单例属性，由 `PluginManager` 统一管理。
2. **复合宏组件层 (Macro-Components, `components/`)**：
   - 负责跨多个原子插件协同编排的复杂业务流（例如：过门 DoorComponent、乘梯 ElevatorComponent、对桩充电 StationComponent）；
   - 继承自 `BaseComponent`，由本管理器 `ComponentManager` 统一负责动态发现、按需实例化、能力聚合及生命周期追踪。

关键设计哲学与核心机制：
----------------------------------------------------------------------------------------------------
1. **线程安全的组件注册表 (Thread-Safe Component Registry)**：
   - 内部由 `threading.RLock()` 读写可重入互斥锁保护，彻底杜绝并发获取实例、重载或动态注册时的字典竞态冲突。
2. **弱引用活跃实例追踪与整机联动急停 (WeakSet Active Tracking & Emergency Abort)**：
   - 使用 `weakref.WeakSet` 追踪运行中的宏组件实例，GC 自动回收无内存泄漏；
   - 提供 `abort_all_active_components()` 联动急停接口，在系统中断、急停或故障时主动遍历触发 `abort()`，
     实现物理防夹（如门禁防夹回滚）与状态安全回滚。
3. **能力元数据缓存与单组件故障隔离 (Capability Caching & Fault Isolation)**：
   - `get_all_capabilities()` 引入局部缓存机制，避免高频反射开销；
   - 细粒度 `try-except` 隔离单个异常组件，确保某个组件的能力异常绝不阻碍整机能力汇总与上报。
4. **编程式注册、注销与单测隔离 (Programmatic CRUD & Clean Reset)**：
   - 提供 `register_component()`, `unregister_component()`, `reload_components()`, `reset()` 等全套 API，
     便于运行时扩展与测试环境的绝对隔离。
"""

import importlib
import inspect
import pkgutil
import threading
import weakref
import os
import yaml
from typing import Dict, Any, Type, List, Optional

from core.logger_manager import get_logger
from components.base_component import BaseComponent

logger = get_logger("ComponentManager")


class ComponentManager:
    """
    业务宏组件管理器 (ComponentManager)

    负责自动发现、编程式注册、按需多实例工厂创建以及活跃宏组件的生命周期监管与急停联动。
    """

    def __init__(self, plugin_manager):
        """
        初始化业务宏组件管理器

        :param plugin_manager: 全局插件管理器实例 (PluginManager)，作为宏组件操作原子插件的底座
        """
        self.plugin_manager = plugin_manager

        # 内部并发控制互斥锁
        self._lock = threading.RLock()

        # 宏组件类注册表：键为组件类名 (如 "DoorComponent")，值为对应的 BaseComponent 子类
        self.components: Dict[str, Type[BaseComponent]] = {}

        # 活跃组件实例弱引用集合：自动感知实例的消亡，避免持有强引用导致内存泄漏
        self._active_components: weakref.WeakSet[BaseComponent] = weakref.WeakSet()

        # 能力元数据聚合缓存
        self._capabilities_cache: Optional[List[Dict[str, Any]]] = None

        # 自动执行目录扫描并加载合规的宏组件类
        self._load_components()

    def _load_components(self) -> None:
        """
        动态反射扫描 `components` 模块目录，自动发现并注册所有继承自 `BaseComponent` 的具体子类。

        设计特性：
        - 单模块加载故障隔离：即使某个组件存在语法错误或第三方依赖缺失，仅记录 ERROR，不影响其他合法组件加载；
        - 自动过滤 `BaseComponent` 基类自身，仅注册具体派生类。
        """
        import components
        package = components
        prefix = package.__name__ + "."

        # 读取 components/config.yaml 配置文件
        config_path = os.path.join(os.path.dirname(package.__file__), "config.yaml")
        enabled_config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    yaml_data = yaml.safe_load(f) or {}
                    enabled_config = yaml_data.get("components", {})
            except Exception as e:
                logger.error(f"读取宏组件配置文件 {config_path} 异常: {e}")

        loaded_count = 0
        with self._lock:
            for importer, modname, ispkg in pkgutil.iter_modules(package.__path__, prefix):
                try:
                    module = importlib.import_module(modname)
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, BaseComponent) and obj is not BaseComponent:
                            comp_type = obj.__name__
                            
                            # 检查配置，默认为 True
                            is_enabled = enabled_config.get(comp_type, True)
                            if not is_enabled:
                                logger.info(f"⏸️ 业务宏组件 [{comp_type}] 在配置中被禁用，跳过加载")
                                continue
                                
                            self.components[comp_type] = obj
                            loaded_count += 1
                            logger.info(f"🧩 成功加载业务宏组件: [{comp_type}] (模块: {modname})")
                except Exception as e:
                    logger.error(f"❌ 加载业务宏组件模块 [{modname}] 失败: {e}", exc_info=True)

            # 刷新能力元数据缓存
            self._capabilities_cache = None

        logger.info(f"✨ 业务宏组件扫描完成，共成功加载 {loaded_count} 个组件类")

    def register_component(
        self,
        comp_class: Type[BaseComponent],
        name: Optional[str] = None,
        override: bool = False
    ) -> None:
        """
        编程式注册宏组件类（支持动态扩展与单元测试 Mock 注入）

        :param comp_class: 继承自 BaseComponent 的宏组件类
        :param name: 自定义组件标识名；若为 None 则默认使用类名 (comp_class.__name__)
        :param override: 若组件名已存在，是否允许覆盖；默认 False，若重复则抛出 ValueError
        :raises TypeError: 当传入的不是 BaseComponent 的子类时抛出
        :raises ValueError: 当组件已存在且 override 为 False 时抛出
        """
        if not isinstance(comp_class, type) or not issubclass(comp_class, BaseComponent) or comp_class is BaseComponent:
            raise TypeError(f"组件类必须是 BaseComponent 的有效具体子类，传入: {comp_class}")

        comp_name = name or comp_class.__name__

        with self._lock:
            if comp_name in self.components and not override:
                raise ValueError(f"业务宏组件 [{comp_name}] 已存在，禁止重复注册 (若需覆盖请显式指定 override=True)")

            self.components[comp_name] = comp_class
            self._capabilities_cache = None
            logger.info(f"🧩 编程式成功注册宏组件: [{comp_name}]")

    def unregister_component(self, component_type: str) -> bool:
        """
        编程式注销指定类型的宏组件类

        :param component_type: 组件类型标识名
        :return: 若注销成功返回 True；若组件原本不存在则返回 False
        """
        with self._lock:
            if component_type in self.components:
                del self.components[component_type]
                self._capabilities_cache = None
                logger.info(f"🗑️ 业务宏组件 [{component_type}] 已成功注销")
                return True
            return False

    def reload_components(self) -> int:
        """
        重新扫描并重载所有组件（用于现场热部署更新）

        :return: 当前加载的组件类总数
        """
        with self._lock:
            self.components.clear()
            self._capabilities_cache = None
            self._load_components()
            return len(self.components)

    def get_component_instance(self, component_type: str) -> BaseComponent:
        """
        获取指定业务宏组件的全新实例（多实例工厂模式）

        设计原则：
        - 每次调用均使用 `self.plugin_manager` 实例化一个全新的对象，确保每次任务调度的状态机完全隔离与干净；
        - 自动将创建的实例登记至 `_active_components` 弱引用集合中，用于支持全局急停 (`abort_all_active_components`) 联动。

        :param component_type: 宏组件类型名称 (例如 "DoorComponent")
        :return: 继承自 BaseComponent 的具体组件实例
        :raises ValueError: 当请求未注册的未知组件类型时抛出
        """
        with self._lock:
            comp_class = self.components.get(component_type)
            if not comp_class:
                raise ValueError(f"未知业务宏组件类型: {component_type} (当前可用: {list(self.components.keys())})")

            # 实例化全新组件
            instance = comp_class(self.plugin_manager)

            # 自动挂载至弱引用追踪集合，生命周期交由 Python GC，绝无内存泄漏
            self._active_components.add(instance)
            return instance

    def abort_all_active_components(self) -> int:
        """
        安全联动急停：对当前所有处于存活/活跃状态的宏组件实例触发打断回滚 (`abort()`)

        业务价值：
        - 在整机全局急停 (`global_abort`)、安全避障脱困或任务强行取消时，
          统一召回所有执行中的宏组件（如正在过门、乘梯或充电），
          触发内部 `_rollback` 防止物理夹车或撞击。

        :return: 成功触发打断的活跃组件实例数量
        """
        with self._lock:
            # 获取当前存活活跃实例的浅拷贝快照，避免遍历时并发修改
            active_list = list(self._active_components)

        aborted_count = 0
        for inst in active_list:
            try:
                inst_type = getattr(inst, "component_type", inst.__class__.__name__)
                logger.warning(f"🚨 [ComponentManager] 正在联动急停活跃宏组件实例: [{inst_type}]")
                inst.abort()
                aborted_count += 1
            except Exception as e:
                logger.error(f"❌ 触发宏组件实例 [{inst}] 急停时异常: {e}", exc_info=True)

        logger.info(f"🛑 全量活跃宏组件急停处理完成，共打断 {aborted_count}/{len(active_list)} 个实例")
        return aborted_count

    def get_all_capabilities(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        聚合上报所有已注册业务宏组件的能力契约 (API JSON Schema)

        设计特性：
        - 结果缓存：若未发生增删改且未指定 force_refresh，直接复用已缓存的能力列表；
        - 细粒度容错隔离：若某个组件未实现 (`NotImplementedError`) 则静默跳过；
          若组件类方法抛出未知异常，则记录警告并跳过，绝不阻断其他合法组件的能力汇总。

        :param force_refresh: 是否强制穿透缓存并重新计算
        :return: 能力元数据字典列表
        """
        with self._lock:
            if not force_refresh and self._capabilities_cache is not None:
                return [dict(c) for c in self._capabilities_cache]

            caps: List[Dict[str, Any]] = []
            # 针对字典项生成快照后再遍历
            components_snapshot = list(self.components.items())

        # 锁外反射获取，提升并发性并避免死锁
        for name, comp_class in components_snapshot:
            try:
                cap = comp_class.get_capability()
                if isinstance(cap, dict) and cap:
                    caps.append(cap)
            except NotImplementedError:
                # 组件基类或子类未实现能力声明，合规静默忽略
                pass
            except Exception as e:
                logger.warning(f"⚠️ 业务宏组件 [{name}] 获取能力元数据时异常，已隔离: {e}")

        with self._lock:
            self._capabilities_cache = caps
            return [dict(c) for c in caps]

    def list_components(self) -> List[str]:
        """
        获取当前所有已注册的业务宏组件类型名称列表（排好序）

        :return: 组件类型名称列表
        """
        with self._lock:
            return sorted(list(self.components.keys()))

    def has_component(self, component_type: str) -> bool:
        """
        检查指定类型的业务宏组件是否已注册

        :param component_type: 组件类型标识名
        :return: 若已注册返回 True，否则返回 False
        """
        with self._lock:
            return component_type in self.components

    def get_active_component_count(self) -> int:
        """
        获取当前正在内存中存活/运行的宏组件实例总数

        :return: 活跃实例数量
        """
        with self._lock:
            return len(self._active_components)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取宏组件管理器的运行时健康度与自省统计指标

        :return: 包含组件总数、活跃实例数、能力契约数等指标的字典
        """
        with self._lock:
            caps_count = len(self._capabilities_cache) if self._capabilities_cache is not None else -1
            return {
                "registered_components_count": len(self.components),
                "registered_components": self.list_components(),
                "active_components_count": len(self._active_components),
                "capabilities_cache_cached": self._capabilities_cache is not None,
                "cached_capabilities_count": caps_count,
            }

    def reset(self) -> None:
        """
        彻底重置宏组件管理器（专供单元测试环境或系统全量重置使用）

        清空注册表、解绑活跃实例集合并清空能力缓存。
        """
        with self._lock:
            self.components.clear()
            self._active_components.clear()
            self._capabilities_cache = None
            logger.info("🧹 [ComponentManager] 宏组件管理器状态已彻底重置")
