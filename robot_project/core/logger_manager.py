import os
import sys
import logging
import threading
from logging.handlers import TimedRotatingFileHandler
from typing import Dict, List, Optional, Union

try:
    import colorlog
    HAS_COLORLOG = True
except ImportError:
    HAS_COLORLOG = False


class LoggerManager:
    """
    边缘网关全局统一日志管理器 (LoggerManager)

    【核心能力】
    1. DCL 线程安全单例：高并发场景下安全初始化；
    2. 双层级日志模型：
       - 根日志器 (EdgeGateway)：统管控制台彩色格式化输出与本地午夜滚动归档；
       - 子模块日志器 (EdgeGateway.<sub_module>)：继承全局输出配置，拥有独立命名空间，可按模块调整级别；
    3. 动态调级：支持运行时动态修改全局或特定子模块的日志级别；
    4. 句柄管理：支持停机或测试重置时的文件描述符释放；
    5. 防死锁降级：通过延迟导入读取 ConfigManager 配置，失败时自动平滑降级为 INFO。
    """

    _instance: Optional["LoggerManager"] = None
    _instance_lock = threading.RLock()

    def __new__(cls, name: str = "EdgeGateway", log_dir: str = "logs") -> "LoggerManager":
        """
        DCL (Double-Checked Locking) 双重检测锁单例构建
        
        :param name: 根日志器名称，默认 "EdgeGateway"
        :param log_dir: 日志文件存储根目录，默认 "logs"
        """
        if not cls._instance:
            with cls._instance_lock:
                if not cls._instance:
                    instance = super(LoggerManager, cls).__new__(cls)
                    instance._initialized = False
                    instance._initializing = False
                    cls._instance = instance
        return cls._instance

    def __init__(self, name: str = "EdgeGateway", log_dir: str = "logs"):
        """
        初始化日志管理器（仅在首次构建时执行一次）
        
        :param name: 根日志器名称
        :param log_dir: 日志输出目录
        """
        if getattr(self, "_initialized", False) or getattr(self, "_initializing", False):
            return

        with self._instance_lock:
            if getattr(self, "_initialized", False) or getattr(self, "_initializing", False):
                return

            self._initializing = True
            try:
                self._root_name = name
                self._log_dir = log_dir
                self._sub_loggers_lock = threading.RLock()
                self._sub_loggers: Dict[str, logging.Logger] = {}

                # 先建立基础根 Logger，防止 _get_level_from_config 回调 get_logger 时产生空指针或循环递归
                self._root_logger = logging.getLogger(name)
                self._root_logger.setLevel(logging.INFO)

                # 1. 尝试从 ConfigManager 获取全局默认日志级别（带循环依赖防死锁保护）
                self._current_level = self._get_level_from_config()

                # 2. 初始化根 Logger 及输出 Handlers
                self._init_root_logger(self._root_name, self._log_dir, self._current_level)

                self._initialized = True
            finally:
                self._initializing = False

    def _get_level_from_config(self) -> int:
        """
        通过统一的 ConfigManager 动态获取日志级别配置，具备防死锁与容错降级保护
        
        :return: logging 级别整数常量 (默认 logging.INFO)
        """
        default_level = logging.INFO
        try:
            # 核心防死锁设计：局部延迟导入（Lazy Import）
            from core.config_manager import ConfigManager

            config = ConfigManager().load_main()
            level_str = config.get("log_level", "INFO").strip().upper()

            level_map = {
                "DEBUG": logging.DEBUG,
                "INFO": logging.INFO,
                "WARNING": logging.WARNING,
                "WARN": logging.WARNING,
                "ERROR": logging.ERROR,
                "CRITICAL": logging.CRITICAL,
            }
            return level_map.get(level_str, default_level)
        except Exception as e:
            # 当 ConfigManager 尚未就绪或配置读取异常时，实施安全降级
            sys.stderr.write(f"⚠️ [LoggerManager] 通过 ConfigManager 获取配置失败，默认降级为 INFO 级别: {e}\n")
            return default_level

    def _init_root_logger(self, name: str, log_dir: str, level: int) -> None:
        """
        初始化根日志器，配置彩色控制台 Handler 与每日午夜自动滚动文件 Handler
        
        :param name: 根日志器名称
        :param log_dir: 日志目录
        :param level: 初始日志级别
        """
        self._root_logger = logging.getLogger(name)
        self._root_logger.setLevel(level)

        # 避免在同一实例或反复调用时重复添加 Handler
        if self._root_logger.handlers:
            return

        # 1. 确保日志目录存在
        try:
            if not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
        except Exception as e:
            sys.stderr.write(f"⚠️ [LoggerManager] 创建日志目录 [{log_dir}] 失败: {e}\n")

        # 2. 控制台 Handler 配置 (支持彩色输出)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)

        if HAS_COLORLOG:
            console_formatter = colorlog.ColoredFormatter(
                "%(log_color)s[%(asctime)s] [%(levelname)s] [%(name)s] [%(filename)s:%(lineno)d] -> %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
                log_colors={
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "bold_red",
                },
            )
        else:
            console_formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(name)s] [%(filename)s:%(lineno)d] -> %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        console_handler.setFormatter(console_formatter)
        self._root_logger.addHandler(console_handler)

        # 3. 本地文件按天轮转 Handler 配置
        log_file_path = os.path.join(log_dir, "gateway.log")
        try:
            file_handler = TimedRotatingFileHandler(
                filename=log_file_path,
                when="midnight",       # 触发时机：每天午夜 (00:00)
                interval=1,            # 间隔：1天
                backupCount=30,        # 最多保留 30 天日志归档
                encoding="utf-8",
            )
            file_handler.suffix = "%Y-%m-%d"
            file_handler.setLevel(level)

            file_formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(name)s] [%(filename)s:%(lineno)d] -> %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_formatter)
            self._root_logger.addHandler(file_handler)
        except Exception as e:
            sys.stderr.write(f"⚠️ [LoggerManager] 初始化本地滚动日志文件 [{log_file_path}] 失败: {e}\n")

    @property
    def logger(self) -> logging.Logger:
        """获取根 Logger 实例"""
        return self._root_logger

    def get_child_logger(self, module_name: str) -> logging.Logger:
        """
        获取或派生指定子模块的独立 Logger 实例
        
        【设计优势】
        - 派生自根 Logger (例如 EdgeGateway.NavPlugin)，完全继承根 Logger 的控制台与滚动文件 Handler，无需重复挂载 Handler；
        - 日志输出带有独立的子模块命名空间标记；
        - 支持针对该模块单独使用 set_level 动态调整日志级别。
        
        :param module_name: 业务子模块名称 (如 "NavPlugin", "TaskManager")
        :return: logging.Logger 实例
        """
        if not module_name or module_name == self._root_name:
            return self._root_logger

        with self._sub_loggers_lock:
            if module_name in self._sub_loggers:
                return self._sub_loggers[module_name]

            # 规范化子 Logger 名称：统一归属到根命名空间下 (如 EdgeGateway.NavPlugin)
            if not module_name.startswith(f"{self._root_name}."):
                full_name = f"{self._root_name}.{module_name}"
            else:
                full_name = module_name

            child_logger = logging.getLogger(full_name)
            # 默认设为 NOTSET，使其完全继承根 Logger 的级别判定
            child_logger.setLevel(logging.NOTSET)
            self._sub_loggers[module_name] = child_logger
            return child_logger

    def set_level(self, level: Union[int, str], module_name: Optional[str] = None) -> None:
        """
        动态调整日志级别
        
        :param level: 目标级别，支持 int (logging.DEBUG) 或 str ("DEBUG", "INFO", "WARN", "ERROR")
        :param module_name: 可选。指定要调整的子模块名称；若为 None 则调整全局根 Logger 与所有 Handler 的级别
        """
        if isinstance(level, str):
            level_map = {
                "DEBUG": logging.DEBUG,
                "INFO": logging.INFO,
                "WARNING": logging.WARNING,
                "WARN": logging.WARNING,
                "ERROR": logging.ERROR,
                "CRITICAL": logging.CRITICAL,
            }
            parsed_level = level_map.get(level.strip().upper(), logging.INFO)
        else:
            parsed_level = int(level)

        if module_name:
            # 针对特定子模块调级
            logger_obj = self.get_child_logger(module_name)
            logger_obj.setLevel(parsed_level)
            self._root_logger.info(f"🔧 [LoggerManager] 模块 [{module_name}] 日志级别已动态调整为: {logging.getLevelName(parsed_level)}")
        else:
            # 调整全局根 Logger 及 Handlers
            self._current_level = parsed_level
            self._root_logger.setLevel(parsed_level)
            for handler in self._root_logger.handlers:
                handler.setLevel(parsed_level)
            self._root_logger.info(f"🔧 [LoggerManager] 全局根日志级别已动态调整为: {logging.getLevelName(parsed_level)}")

    def get_level(self) -> int:
        """获取当前全局根日志器生效的日志级别"""
        return self._root_logger.level

    def list_loggers(self) -> List[str]:
        """列出当前已注册/派生的所有子模块日志器名称"""
        with self._sub_loggers_lock:
            return sorted(list(self._sub_loggers.keys()))

    def close(self) -> None:
        """
        安全关闭并清理所有挂载的 Handlers，释放本地文件描述符
        常用于系统正常停机或测试套件销毁阶段
        """
        with self._instance_lock:
            if hasattr(self, "_root_logger") and self._root_logger:
                for handler in list(self._root_logger.handlers):
                    try:
                        handler.flush()
                        handler.close()
                        self._root_logger.removeHandler(handler)
                    except Exception as e:
                        sys.stderr.write(f"⚠️ [LoggerManager] 关闭日志 Handler 异常: {e}\n")

    @classmethod
    def reset(cls) -> None:
        """
        彻底重置单例状态与清理资源（专供单元测试环境使用）
        """
        with cls._instance_lock:
            if cls._instance:
                cls._instance.close()
                cls._instance = None


def get_logger(name: str = "EdgeGateway") -> logging.Logger:
    """
    全局便捷获取 Logger 实例的标准入口函数

    【用法示例】
    ```python
    from core.logger_manager import get_logger

    # 获取根日志器
    logger = get_logger()
    logger.info("边缘网关启动就绪")

    # 获取子模块日志器（独立命名空间，继承全局输出配置）
    nav_logger = get_logger("NavPlugin")
    nav_logger.debug("规划返航路径...")
    ```

    :param name: 日志器模块名称，默认为根名称 "EdgeGateway"
    :return: 对应的 logging.Logger 实例
    """
    manager = LoggerManager()
    if name == "EdgeGateway" or not name:
        return manager.logger
    return manager.get_child_logger(name)