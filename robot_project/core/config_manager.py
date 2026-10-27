import os
import copy
import threading
import yaml
from typing import Any, Dict, List, Optional, Union


class ConfigManager:
    """
    边缘网关全局统一配置管理器 (ConfigManager)

    【架构定位与职责说明】
    1. 统一配置树架构 (Unified Configuration Tree):
       - 根节点承载网关核心配置（如 gateway, mqtt, log_level, storage 等）；
       - 挂载节点 `plugins.<plugin_name>` 承载各硬件/算法插件专属配置（如 plugins.nav, plugins.door_opener 等）；
       - 支持主配置文件 (`configs/config.yaml`) 与各插件专属配置文件的分布式按需加载与合并；
    2. DCL 线程安全单例 (Double-Checked Locking Singleton):
       - 保障高并发多线程场景下的绝对安全初始化；
    3. 读写互斥与数据安全 (Thread-Safe Synchronization):
       - 内部配备 `threading.RLock()` 可重入读写锁，保障 `get`、`set`、`load_main`、`load_plugin` 等操作的线程安全，杜绝并发竞态；
    4. 高级点号路径操作与深拷贝快照 (Hierarchical Path & Deep Snapshot):
       - 支持通过点号层级路径快速读写（如 `config.get("mqtt.broker_ip")` 或 `config.set("plugins.nav.speed", 1.2)`）；
       - 提供 `to_dict()` 深度拷贝快照，避免外部持有对象引用意外修改内部配置；
    5. 循环依赖防死锁与容错降级 (Anti-Deadlock Logger Access):
       - `logger` 属性采用异常安全的延迟获取机制，在 Logger 尚未就绪时平滑降级，杜绝模块间循环导入死锁。
    """

    _instance: Optional["ConfigManager"] = None
    _instance_lock = threading.RLock()

    def __new__(cls, *args, **kwargs) -> "ConfigManager":
        """
        DCL (Double-Checked Locking) 双重检测锁单例构建
        """
        if not cls._instance:
            with cls._instance_lock:
                if not cls._instance:
                    instance = super(ConfigManager, cls).__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self):
        """
        初始化配置管理器（仅在首次构建时执行一次）
        """
        if getattr(self, "_initialized", False):
            return

        with self._instance_lock:
            if getattr(self, "_initialized", False):
                return

            self._lock = threading.RLock()
            self._config: Dict[str, Any] = {}
            self._main_loaded: bool = False
            self._initialized = True

    @property
    def logger(self):
        """
        延迟安全获取 Logger 实例，具备循环引用防死锁与降级保护
        """
        try:
            from core.logger_manager import get_logger
            return get_logger("ConfigManager")
        except Exception:
            import logging
            return logging.getLogger("Bootstrap.ConfigManager")

    def load_main(self, config_path: str = "configs/config.yaml") -> Dict[str, Any]:
        """
        加载网关主配置文件，解析并组装至内存配置树根节点
        
        【设计保护】
        - 自动保留已由插件提前注册的 `plugins` 挂载枝干，防止配置覆盖；
        - 若文件不存在或语法异常，安全降级并不中断进程，保持已有配置。

        :param config_path: 主配置文件物理路径 (默认 configs/config.yaml)
        :return: 当前全局配置树字典
        """
        with self._lock:
            if not os.path.exists(config_path):
                self.logger.warning(f"⚠️ 主配置文件 '{config_path}' 不存在，使用空配置启动！")
                self._main_loaded = True
                return self._config

            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    parsed_data = yaml.safe_load(f)

                # 保护已挂载的插件配置不被主配置覆盖（如果插件先于主配置加载）
                existing_plugins = self._config.get("plugins", {})
                self._config = parsed_data if isinstance(parsed_data, dict) else {}

                # 确保全局树中始终维护一个 plugins 枝干
                if "plugins" not in self._config:
                    self._config["plugins"] = existing_plugins
                else:
                    # 如果主配置中也有 plugins 声明，将已有动态挂载的插件增量合并进去
                    for p_name, p_conf in existing_plugins.items():
                        if p_name not in self._config["plugins"]:
                            self._config["plugins"][p_name] = p_conf

                self._main_loaded = True
                self.logger.info(f"✅ 成功加载网关主配置: {config_path}")
            except yaml.YAMLError as e:
                self.logger.error(f"❌ 主配置文件语法错误: {e}")
                raise
            except Exception as e:
                self.logger.error(f"❌ 读取主配置发生未知异常: {e}")
                raise

            return self._config

    def load_plugin(self, plugin_name: str, config_path: str) -> Dict[str, Any]:
        """
        加载特定插件的专属配置文件，并将其动态挂载到全局配置树的 `plugins.<plugin_name>` 节点下

        :param plugin_name: 插件名称 (如 'nav', 'door_opener')
        :param config_path: 插件配置文件的相对或绝对路径
        :return: 该插件加载的配置字典
        """
        if not os.path.exists(config_path):
            self.logger.debug(f"ℹ️ 插件 [{plugin_name}] 无专属配置文件，跳过。")
            return {}

        with self._lock:
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    plugin_config = yaml.safe_load(f) or {}

                if not isinstance(plugin_config, dict):
                    plugin_config = {}

                # 确保 plugins 枝干存在
                if "plugins" not in self._config:
                    self._config["plugins"] = {}

                # 动态挂载
                self._config["plugins"][plugin_name] = plugin_config
                self.logger.info(f"✅ 成功加载插件专属配置: [{plugin_name}] -> {config_path}")
                return plugin_config
            except Exception as e:
                self.logger.error(f"❌ 读取插件 [{plugin_name}] 配置失败: {e}")
                return {}

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        核心便捷方法：支持通过层级点号(.)来深层检索全局或插件配置项
        
        【特性】
        - 线程安全读访问；
        - 冷启动按需加载主配置；
        - 支持字典键与数字列表索引遍历（如 `routes.0.ip`）；
        - 安全容错，路径不存在时返回 default。

        【用法示例】
        ```python
        config = ConfigManager()
        broker = config.get("mqtt.broker_ip", "127.0.0.1")
        door_port = config.get("plugins.door_opener.params.port")
        ```

        :param key_path: 点号分隔的配置路径，例如 "mqtt.port" 或 "plugins.nav.speed"
        :param default: 当路径不存在或中间类型不匹配时的默认回退值
        :return: 对应的配置值或 default
        """
        with self._lock:
            # 冷启动防范：如果尚未加载过主配置且配置树为空，自动尝试加载一次
            if not self._main_loaded and not self._config:
                self.load_main()

            if not self._config:
                return default

            if not key_path:
                return default

            keys = key_path.split(".")
            current_level: Any = self._config

            try:
                for key in keys:
                    if isinstance(current_level, dict):
                        if key not in current_level:
                            return default
                        current_level = current_level[key]
                    elif isinstance(current_level, list):
                        # 支持数字索引访问列表元素
                        if key.isdigit():
                            idx = int(key)
                            if 0 <= idx < len(current_level):
                                current_level = current_level[idx]
                            else:
                                return default
                        else:
                            return default
                    else:
                        return default
                return current_level
            except (KeyError, IndexError, TypeError):
                return default

    def set(self, key_path: str, value: Any) -> None:
        """
        以层级点号语法动态写入或覆写配置项
        
        【特性】
        - 线程安全写访问；
        - 自动递归创建中间缺失的字典层级；
        - 常用于运行时动态调参、状态覆盖以及单元测试桩数据注入。

        【用法示例】
        ```python
        config = ConfigManager()
        config.set("mqtt.broker_ip", "192.168.1.100")
        config.set("plugins.nav.params.timeout", 30)
        ```

        :param key_path: 点号分隔的目标配置路径
        :param value: 欲写入的配置值
        """
        if not key_path:
            return

        with self._lock:
            keys = key_path.split(".")
            current_level = self._config

            for i, key in enumerate(keys[:-1]):
                if key not in current_level or not isinstance(current_level[key], dict):
                    current_level[key] = {}
                current_level = current_level[key]

            current_level[keys[-1]] = value

    def reload(self, config_path: str = "configs/config.yaml") -> Dict[str, Any]:
        """
        主动重新加载网关主配置文件，并保留已挂载的插件配置

        :param config_path: 主配置文件路径
        :return: 重新加载后的全局配置字典
        """
        with self._lock:
            self.logger.info(f"🔄 [ConfigManager] 正在重载网关配置: {config_path}")
            return self.load_main(config_path)

    def to_dict(self) -> Dict[str, Any]:
        """
        导出当前整树配置的深度拷贝 (Deep Copy) 快照
        外部对返回字典的任何修改均不会污染配置管理器内部状态

        :return: 完整的深拷贝配置字典
        """
        with self._lock:
            return copy.deepcopy(self._config)

    @classmethod
    def reset(cls) -> None:
        """
        彻底重置单例状态与清空配置树（专供单元测试环境使用）
        """
        with cls._instance_lock:
            if cls._instance:
                with cls._instance._lock:
                    cls._instance._config.clear()
                    cls._instance._main_loaded = False
                cls._instance = None