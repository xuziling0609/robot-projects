"""
边缘网关能力插件包 (Plugins Package)

向 Python 解释器声明当前目录为标准包，暴露 BasePlugin 基类。
"""
from .base import BasePlugin

__all__ = ['BasePlugin']