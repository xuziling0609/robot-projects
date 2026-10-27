from abc import ABC, abstractmethod

class BasePlugin(ABC):
    def __init__(self, config: dict = None):
        self.config = config or {}

    @abstractmethod
    def execute(self, action: str, params: dict) -> dict:
        pass

    def pause(self) -> None:
        """暂停插件当前动作 (预留方法)"""
        pass

    def resume(self) -> None:
        """恢复插件暂停动作 (预留方法)"""
        pass

    def abort(self) -> None:
        """终止/打断插件当前动作 (预留方法)"""
        pass

    @abstractmethod
    def get_capabilities(self) -> dict:
        pass

    def status(self) -> bool:
        """获取当前插件在线状态 (默认返回 True)"""
        return True