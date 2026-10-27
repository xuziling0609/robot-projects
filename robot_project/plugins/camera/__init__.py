"""
海康威视双光热成像云台相机插件包 (Camera Plugin Package)
"""
from .camera_plugin import CameraPlugin
from .camera_driver import CameraDriver

__all__ = ['CameraPlugin', 'CameraDriver']
