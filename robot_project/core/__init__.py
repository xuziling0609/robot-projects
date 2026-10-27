"""
边缘网关核心引擎包 (Core Engine Package)

此包包含了系统的基础架构组件，负责全局资源调度、硬件生命周期管理、
网络连接池维护以及任务流的解析与流转。
"""

# 将核心组件暴露到 core 包层级，提供统一的 API 入口
from .plugin_manager import PluginManager
from .tcp_manager import TCPManager, TCPPoolManager
from .config_manager import ConfigManager
from .mqtt_manager import MQTTManager
from .logger_manager import get_logger, LoggerManager
from .task_manager import TaskManager
from .telemetry_manager import TelemetryManager
from .alarm_manager import AlarmManager
from .event_manager import EventManager, EventBus, TaskEvent, EventType
from .context_manager import ContextManager

__all__ = [
    'PluginManager',
    'TCPManager',
    'TCPPoolManager',
    'ConfigManager',
    'MQTTManager',
    'LoggerManager',
    'get_logger',
    'TaskManager',
    'TelemetryManager',
    'AlarmManager',
    'EventManager',
    'EventBus',
    'TaskEvent',
    'EventType',
    'ContextManager'
]