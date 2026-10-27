import threading
from typing import Dict, Any, Optional, Union, List

class BaseComponent:
    """
    业务宏组件基类
    封装跨插件的复杂业务流，提供正向执行、中断回滚和逆向映射标准契约。
    """
    def __init__(self, plugin_manager):
        self.plugin_manager = plugin_manager
        self._is_aborted = False
        self.component_type = self.__class__.__name__

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        主执行逻辑：协调多个原子插件，必须阻塞执行，返回最终结果。
        内部应定期检查 self._is_aborted 以响应急停/打断。
        """
        raise NotImplementedError

    def abort(self) -> None:
        """
        触发打断标志位，由 execute 内部循环检测并执行 _rollback。
        可以子类重写以直接打断底层阻塞事件，但必须调用 _rollback。
        """
        self._is_aborted = True

    def _rollback(self) -> None:
        """
        内聚回滚：根据子状态机清理现场，防止物理伤害（如门夹车）。
        """
        pass

    @classmethod
    def get_capability(cls) -> Dict[str, Any]:
        """
        上报组件能力 (API JSON Schema)
        提供给前端渲染的扁平化结构，不含 reverse_mapping。
        """
        raise NotImplementedError
