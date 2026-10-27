"""
机器人全局实时公共内存状态树 (ContextManager)

【模块定位与设计理念】：
1. 统一内存共享中枢 (Single Source of Truth)：
   - 解决分布式/解耦插件架构下，底盘、传感器、导航、任务调度器之间频繁共享实时数据的性能与并发瓶颈；
   - 避免各插件间相互持有对象引用产生强耦合，所有跨插件的状态查询与任务上下文共享均经由 ContextManager 进行。
2. 线程安全与高性能保障：
   - 采用可重入互斥锁 (threading.RLock) 保护底层核心字典；
   - 提供细粒度原子读取接口 (get_task_field / get_status_field)，在锁内极速获取单字段，避免频繁触发庞大字典的全量深/浅拷贝；
   - 全量读取接口 (get_robot_status / get_robot_task) 返回数据拷贝副本，严格隔离读写，防止外部修改污染共享内存池。
3. 契约规范与向后兼容性：
   - 规范声明了标准任务字段 (status, task_id, task_name, msg_id, rth 等) 与底盘状态字段；
   - 100% 保持既有类属性与核心读写接口兼容，无需改动现有业务插件的调用代码。
"""

import threading
from typing import Dict, Any, Optional


class ContextManager:
    """
    机器人全局实时内存状态树 (公共内存池)
    供各个解耦插件 (NavPlugin, TaskManager, LoraPlugin, RecordPlugin 等) 高性能、线程安全地共享实时数据。
    """

    # 可重入互斥锁：保护全局状态池与任务池的并发读写安全
    _lock = threading.RLock()

    # =========================================================
    # 1. 状态池 (Robot Status Pool)
    # 规约字段通常由底盘驱动、导航插件 (NavPlugin) 周期性上报更新：
    # - battery (float/int)     : 电池电量百分比 (0~100)
    # - speed (float)           : 机器人当前线速度 (m/s)
    # - position (dict/tuple)   : 当前世界坐标位姿 {"x": 0.0, "y": 0.0, "yaw": 0.0}
    # - current_point (int/str) : 当前所在拓扑节点编号
    # - mode (str)              : 底盘模式 (auto, manual, estop 等)
    # - is_charging (bool)      : 是否处于充电状态
    # =========================================================
    robot_status: Dict[str, Any] = {}

    # =========================================================
    # 2. 任务池 (Robot Task Context Pool)
    # 规约字段由任务调度引擎 (TaskManager) 在任务流转周期中统一维护：
    # - status (str)            : 任务运行状态，标准枚举值:
    #                             "idle"    - 空闲无任务
    #                             "running" - 任务正在流水线执行中
    #                             "paused"  - 任务被挂起/暂停等待恢复
    #                             "finish"  - 任务已全部成功完成
    #                             "aborted" - 任务被打断/手动终止
    #                             "failed"  - 任务发生不可恢复的故障
    # - task_id (str/None)      : 当前正在执行的离线任务 ID (如 "TASK_OFFLINE_F3_01")
    # - task_name (str/None)    : 任务显示名称 (如 "3楼配电房巡检预设任务")
    # - msg_id (str/None)       : 平台下发该指令的唯一交互流水号
    # - rth (dict/None)         : 任务绑定的专属安全返航目标 (包含 localization 和 point_id)
    # - current_step (int)      : 当前正在执行的步骤序号 (1-based)
    # - total_steps (int)       : 任务的总步骤数
    # =========================================================
    robot_task: Dict[str, Any] = {
        "status": "idle",
        "task_id": None,
        "task_name": None,
        "msg_id": None,
        "rth": None,
        "current_step": 0,
        "total_steps": 0
    }

    # ---------------------------------------------------------
    # 状态池操作接口 (Status Pool Methods)
    # ---------------------------------------------------------

    @classmethod
    def update_robot_status(cls, new_status: Dict[str, Any]) -> None:
        """
        更新机器人底层硬件/底盘实时状态 (由底盘驱动或 NavPlugin 周期性调用)
        :param new_status: 包含最新状态键值对的字典 (如 {"battery": 95, "speed": 0.8})
        """
        if not new_status or not isinstance(new_status, dict):
            return
        with cls._lock:
            cls.robot_status.update(new_status)

    @classmethod
    def get_robot_status(cls) -> Dict[str, Any]:
        """
        获取机器人当前完整底层状态树的浅拷贝副本 (隔离修改，防止外部污染共享内存)
        :return: 包含当前所有状态键值的字典副本
        """
        with cls._lock:
            return cls.robot_status.copy()

    @classmethod
    def get_status_field(cls, key: str, default: Any = None) -> Any:
        """
        锁内原子读取底盘状态中的单一字段 (高性能，无需拷贝整个大字典)
        :param key: 字段名 (如 "battery", "speed")
        :param default: 键不存在时的默认返回值
        :return: 字段值或默认值
        """
        with cls._lock:
            return cls.robot_status.get(key, default)

    @classmethod
    def reset_status(cls) -> None:
        """
        清空机器人底层状态池 (生命周期重置，通常在系统初始化或单元测试时调用)
        """
        with cls._lock:
            cls.robot_status.clear()

    # ---------------------------------------------------------
    # 任务池操作接口 (Task Context Pool Methods)
    # ---------------------------------------------------------

    @classmethod
    def update_robot_task(cls, task_info: Dict[str, Any]) -> None:
        """
        更新机器人当前任务上下文与流转进度 (由 TaskManager 在任务生命周期节点调用)
        :param task_info: 包含最新任务字段的字典 (如 {"status": "running", "step": 3})
        """
        if not task_info or not isinstance(task_info, dict):
            return
        with cls._lock:
            cls.robot_task.update(task_info)

    @classmethod
    def get_robot_task(cls) -> Dict[str, Any]:
        """
        获取当前机器人任务上下文的浅拷贝副本 (隔离修改，防止外部污染共享内存)
        :return: 包含当前任务全量元数据的字典副本
        """
        with cls._lock:
            return cls.robot_task.copy()

    @classmethod
    def get_task_field(cls, key: str, default: Any = None) -> Any:
        """
        锁内原子读取任务上下文中的单一字段 (高性能，无需拷贝整个大字典)
        :param key: 字段名 (如 "rth", "status", "task_id")
        :param default: 键不存在时的默认返回值
        :return: 字段值或默认值
        """
        with cls._lock:
            return cls.robot_task.get(key, default)

    @classmethod
    def get_task_status(cls, default: str = "idle") -> str:
        """
        便捷接口：获取当前任务状态的小写字符串表示
        :return: 状态字符串 (如 "idle", "running", "paused", "finish", "aborted", "failed")
        """
        with cls._lock:
            status = cls.robot_task.get("status")
            return str(status).lower() if status is not None else default

    @classmethod
    def get_task_id(cls) -> Optional[str]:
        """
        便捷接口：获取当前正在执行的任务 ID
        :return: task_id 字符串，若无任务则返回 None
        """
        with cls._lock:
            return cls.robot_task.get("task_id")

    @classmethod
    def get_rth(cls) -> Optional[Any]:
        """
        便捷接口：获取当前任务绑定的专属返航目标 (rth)
        :return: 包含 localization 和 point_id 的字典，或 None
        """
        with cls._lock:
            return cls.robot_task.get("rth")

    @classmethod
    def is_task_active(cls) -> bool:
        """
        便捷判定：当前网关是否有处于活跃运行中或暂停中的任务
        :return: 若状态为 "running" 或 "paused" 返回 True，否则返回 False
        """
        with cls._lock:
            status = str(cls.robot_task.get("status", "idle")).lower()
            return status in ["running", "paused"]

    @classmethod
    def reset_task(cls, status: str = "idle") -> None:
        """
        重置任务上下文池至干净的初始状态 (生命周期重置，通常在任务彻底终结或单元测试时调用)
        :param status: 重置后的任务状态，默认 "idle"
        """
        with cls._lock:
            cls.robot_task = {
                "status": status,
                "task_id": None,
                "task_name": None,
                "msg_id": None,
                "rth": None,
                "current_step": 0,
                "total_steps": 0
            }
