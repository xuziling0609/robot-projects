from typing import Optional
from pathlib import Path
import yaml

class ConfigManager:
    """
    单例模式的全局配置加载器。
    用于加载并缓存 config/settings.yaml 中的所有配置。
    """
    _instance = None
    _config = None

    def __new__(cls, config_path: Optional[str] = None):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            # 如果未提供路径，默认寻找根目录下的 config/settings.yaml
            if config_path is None:
                # 定位到 src/core 的上两级目录，即 arm_project 根目录
                base_dir = Path(__file__).resolve().parent.parent.parent
                config_path = base_dir / "config" / "settings.yaml"
            
            with open(config_path, 'r', encoding='utf-8') as f:
                cls._instance._config = yaml.safe_load(f)
        return cls._instance

    @property
    def config(self) -> dict:
        return self._config

# 全局快捷访问实例
def get_config() -> dict:
    return ConfigManager().config
