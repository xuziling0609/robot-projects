"""
GDPD-63-TEV-T-A 局部放电检测插件包 (Partial Discharge Detection Plugin Package)
"""
from .gdpd_plugin import GdpdPlugin
from .gdpd_driver import GdpdDriver

__all__ = ['GdpdPlugin', 'GdpdDriver']
