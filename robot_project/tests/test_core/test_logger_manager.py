from unittest.mock import MagicMock, patch, call
import os
import shutil
import logging
import threading
import pytest
from core.logger_manager import LoggerManager, get_logger


class TestLoggerManager:
    """LoggerManager 核心能力与边界场景全量单测套件"""

    def setup_method(self):
        LoggerManager.reset()
        self.test_log_dir = "test_logs_tmp"
        if os.path.exists(self.test_log_dir):
            shutil.rmtree(self.test_log_dir)

    def teardown_method(self):
        LoggerManager.reset()
        if os.path.exists(self.test_log_dir):
            shutil.rmtree(self.test_log_dir)

    def test_singleton_instance(self):
        """验证 LoggerManager 无论以何种参数调用，始终保持全局单例唯一性"""
        logger_inst1 = LoggerManager(name="TestLogger1", log_dir=self.test_log_dir)
        logger_inst2 = LoggerManager(name="TestLogger2", log_dir=self.test_log_dir)
        assert logger_inst1 is logger_inst2

    def test_get_logger_function(self):
        """验证全局便捷函数 get_logger 返回规范的 logging.Logger 实例"""
        log_obj = get_logger("TestModule")
        assert isinstance(log_obj, logging.Logger)
        assert "TestModule" in log_obj.name

    @patch("core.config_manager.ConfigManager.load_main")
    def test_level_from_config_mapping(self, mock_load_main):
        """验证 ConfigManager 配置的各级别字符串映射"""
        mock_load_main.return_value = {"log_level": "DEBUG"}
        level = LoggerManager()._get_level_from_config()
        assert level == logging.DEBUG

        mock_load_main.return_value = {"log_level": "ERROR"}
        level = LoggerManager()._get_level_from_config()
        assert level == logging.ERROR

    @patch("core.config_manager.ConfigManager.load_main")
    def test_level_from_config_fallback(self, mock_load_main):
        """验证当配置加载抛出异常时，平滑降级为 INFO 级别"""
        mock_load_main.side_effect = Exception("Config load failed")
        level = LoggerManager()._get_level_from_config()
        assert level == logging.INFO

    def test_logger_directory_creation(self):
        """验证首次初始化时能自动创建日志存储目录"""
        inst = LoggerManager(name="DirTestLogger", log_dir=self.test_log_dir)
        assert os.path.exists(self.test_log_dir)
        assert isinstance(inst.logger, logging.Logger)

    def test_child_logger_namespace_and_caching(self):
        """验证子模块派生 Logger 拥有独立命名空间且具备内部缓存一致性"""
        manager = LoggerManager(name="GatewayRoot", log_dir=self.test_log_dir)
        
        # 1. 根 Logger 命名验证
        root_log = manager.logger
        assert root_log.name == "GatewayRoot"
        
        # 2. 派生子 Logger 验证
        nav_log1 = manager.get_child_logger("NavPlugin")
        nav_log2 = manager.get_child_logger("NavPlugin")
        door_log = manager.get_child_logger("DoorPlugin")
        
        assert nav_log1 is nav_log2  # 验证内部缓存复用
        assert nav_log1.name == "GatewayRoot.NavPlugin"
        assert door_log.name == "GatewayRoot.DoorPlugin"
        assert nav_log1 is not door_log

        # 3. get_logger 便捷函数与 get_child_logger 互通
        helper_log = get_logger("NavPlugin")
        assert helper_log is nav_log1

        # 4. 传入根名称时返回根 Logger
        root_via_child = manager.get_child_logger("GatewayRoot")
        assert root_via_child is root_log

    def test_dynamic_level_adjustment(self):
        """验证 set_level 针对全局以及针对特定子模块的动态调级机制"""
        manager = LoggerManager(name="DynTestRoot", log_dir=self.test_log_dir)
        
        # 1. 动态调整特定子模块级别
        nav_log = manager.get_child_logger("NavPlugin")
        manager.set_level("DEBUG", module_name="NavPlugin")
        assert nav_log.level == logging.DEBUG
        
        manager.set_level(logging.WARNING, module_name="NavPlugin")
        assert nav_log.level == logging.WARNING
        
        # 2. 动态调整全局根级别
        manager.set_level("ERROR")
        assert manager.get_level() == logging.ERROR
        assert manager.logger.level == logging.ERROR
        for handler in manager.logger.handlers:
            assert handler.level == logging.ERROR

    def test_list_loggers_introspection(self):
        """验证 list_loggers 可观测自省接口能够准确列出所有派生的子模块"""
        manager = LoggerManager(name="ListTest", log_dir=self.test_log_dir)
        initial_loggers = manager.list_loggers()

        manager.get_child_logger("ModuleA")
        manager.get_child_logger("ModuleB")
        
        loggers = manager.list_loggers()
        assert "ModuleA" in loggers
        assert "ModuleB" in loggers
        assert len(loggers) == len(initial_loggers) + 2

    def test_concurrent_singleton_initialization(self):
        """验证多线程高并发下同时获取 LoggerManager 单例，实例完全一致且无竞态报错"""
        instances = []
        errors = []

        def worker():
            try:
                inst = LoggerManager(name="ConcurrentTest", log_dir=self.test_log_dir)
                instances.append(inst)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(instances) == 20
        first = instances[0]
        for inst in instances[1:]:
            assert inst is first

    def test_close_and_reset(self):
        """验证 close 释放 handlers 与 reset 销毁单例能力"""
        manager = LoggerManager(name="ResetTest", log_dir=self.test_log_dir)
        assert len(manager.logger.handlers) > 0

        # close 应该清理 handlers
        manager.close()
        assert len(manager.logger.handlers) == 0

        # reset 应该重置 _instance
        LoggerManager.reset()
        assert LoggerManager._instance is None

