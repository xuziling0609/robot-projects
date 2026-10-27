# -*- coding: utf-8 -*-
"""
业务宏组件管理器 (ComponentManager) 单元测试套件
验证多实例工厂、弱引用活跃实例追踪、联动急停 abort_all、编程式注册/注销、能力缓存与并发安全性。
"""

import gc
import threading
from typing import Dict, Any
from unittest.mock import MagicMock
import pytest

from core.component_manager import ComponentManager
from components.base_component import BaseComponent


class DummyNormalComponent(BaseComponent):
    """测试用普通合规宏组件"""
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "SUCCESS", "echo": params}

    @classmethod
    def get_capability(cls) -> Dict[str, Any]:
        return {
            "component_type": "DummyNormalComponent",
            "name": "测试普通宏组件",
            "description": "供单测使用的标准宏组件"
        }


class DummyFaultyComponent(BaseComponent):
    """测试用故障宏组件（abort 和 get_capability 抛异常）"""
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "FAILED"}

    def abort(self) -> None:
        super().abort()
        raise RuntimeError("硬件通信中断，abort 故障模拟")

    @classmethod
    def get_capability(cls) -> Dict[str, Any]:
        raise RuntimeError("能力元数据解析失败模拟")


class NonComponentClass:
    """非 BaseComponent 子类"""
    pass


class TestComponentManager:
    """ComponentManager 核心测试套件"""

    def setup_method(self):
        self.mock_plugin_manager = MagicMock()
        self.manager = ComponentManager(self.mock_plugin_manager)

    def teardown_method(self):
        self.manager.reset()

    def test_load_components(self):
        """测试目录自动加载能力"""
        assert isinstance(self.manager.components, dict)
        # 默认 components 目录下包含 DoorComponent, ElevatorComponent, StationComponent 等
        assert self.manager.has_component("DoorComponent")
        assert self.manager.has_component("ElevatorComponent")
        assert self.manager.has_component("StationComponent")

    def test_get_component_instance_invalid(self):
        """测试获取未知组件实例时正确抛出 ValueError"""
        with pytest.raises(ValueError, match="未知业务宏组件类型: InvalidComponent"):
            self.manager.get_component_instance("InvalidComponent")

    def test_get_component_instance_success_and_isolation(self):
        """测试多次获取组件实例为独立对象（多实例隔离模式）"""
        inst1 = self.manager.get_component_instance("DoorComponent")
        inst2 = self.manager.get_component_instance("DoorComponent")
        assert inst1 is not inst2
        assert isinstance(inst1, BaseComponent)
        assert inst1.plugin_manager == self.mock_plugin_manager

    def test_register_and_unregister_component(self):
        """测试编程式动态注册与注销"""
        # 1. 成功注册
        self.manager.register_component(DummyNormalComponent)
        assert self.manager.has_component("DummyNormalComponent")
        assert "DummyNormalComponent" in self.manager.list_components()

        # 2. 重复注册抛出异常
        with pytest.raises(ValueError, match="已存在，禁止重复注册"):
            self.manager.register_component(DummyNormalComponent)

        # 3. 允许显式覆盖
        self.manager.register_component(DummyNormalComponent, override=True)

        # 4. 非法类型校验
        with pytest.raises(TypeError, match="有效具体子类"):
            self.manager.register_component(NonComponentClass)  # type: ignore

        with pytest.raises(TypeError, match="有效具体子类"):
            self.manager.register_component(BaseComponent)  # 基类本身不允许

        # 5. 实例化注册的自定义组件
        dummy_inst = self.manager.get_component_instance("DummyNormalComponent")
        assert isinstance(dummy_inst, DummyNormalComponent)

        # 6. 注销组件
        assert self.manager.unregister_component("DummyNormalComponent") is True
        assert self.manager.has_component("DummyNormalComponent") is False
        assert self.manager.unregister_component("DummyNormalComponent") is False

    def test_active_instances_tracking_and_abort_all(self):
        """测试弱引用活跃实例追踪与联动急停 (abort_all_active_components)"""
        self.manager.register_component(DummyNormalComponent)
        self.manager.register_component(DummyFaultyComponent)

        # 实例化组件
        inst1 = self.manager.get_component_instance("DummyNormalComponent")
        inst2 = self.manager.get_component_instance("DummyNormalComponent")
        faulty_inst = self.manager.get_component_instance("DummyFaultyComponent")

        # 验证活跃集合
        assert self.manager.get_active_component_count() >= 3
        assert inst1._is_aborted is False
        assert inst2._is_aborted is False
        assert faulty_inst._is_aborted is False

        # 触发全局联动急停（包含故障组件的异常隔离）
        # 3 个活跃实例中，2 个正常成功打断返回计数 2，1 个故障组件抛出异常被安全隔离
        aborted_count = self.manager.abort_all_active_components()
        assert aborted_count == 2
        assert inst1._is_aborted is True
        assert inst2._is_aborted is True
        assert faulty_inst._is_aborted is True

    def test_weakref_gc_cleanup(self):
        """测试弱引用追踪在外部引用释放后自动 GC 回收，无内存泄漏"""
        self.manager.register_component(DummyNormalComponent)
        initial_active = self.manager.get_active_component_count()

        # 创建局部作用域实例
        def create_temporary_instance():
            temp_inst = self.manager.get_component_instance("DummyNormalComponent")
            assert self.manager.get_active_component_count() == initial_active + 1
            return None

        create_temporary_instance()
        gc.collect()

        # 局部变量释放后，WeakSet 应自动将其清理
        assert self.manager.get_active_component_count() == initial_active

    def test_get_all_capabilities_caching_and_fault_isolation(self):
        """测试能力元数据聚合、缓存机制与单组件故障隔离"""
        self.manager.register_component(DummyNormalComponent)
        self.manager.register_component(DummyFaultyComponent)

        # 1. 首次计算并缓存
        caps1 = self.manager.get_all_capabilities()
        assert isinstance(caps1, list)
        # DummyNormalComponent 能力必须在其中
        dummy_caps = [c for c in caps1 if c.get("component_type") == "DummyNormalComponent"]
        assert len(dummy_caps) == 1
        # DummyFaultyComponent 抛出异常被隔离，不影响整体结果
        faulty_caps = [c for c in caps1 if c.get("component_type") == "DummyFaultyComponent"]
        assert len(faulty_caps) == 0

        # 2. 第二次调用直接命中缓存
        caps2 = self.manager.get_all_capabilities()
        assert caps1 == caps2

        # 3. 强制穿透刷新
        caps3 = self.manager.get_all_capabilities(force_refresh=True)
        assert caps1 == caps3

        # 4. 注销后缓存自动失效
        self.manager.unregister_component("DummyNormalComponent")
        caps4 = self.manager.get_all_capabilities()
        assert not any(c.get("component_type") == "DummyNormalComponent" for c in caps4)

    def test_concurrent_get_instances(self):
        """测试高并发多线程获取组件实例与弱引用登记的安全性"""
        self.manager.register_component(DummyNormalComponent)
        instances = []
        lock = threading.Lock()

        def worker():
            for _ in range(30):
                inst = self.manager.get_component_instance("DummyNormalComponent")
                with lock:
                    instances.append(inst)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 总计创建 150 个实例
        assert len(instances) == 150
        assert self.manager.get_active_component_count() >= 150

        # 联动急停
        aborted = self.manager.abort_all_active_components()
        assert aborted >= 150
        assert all(i._is_aborted for i in instances)

    def test_stats_and_reload(self):
        """测试自省统计接口与重新加载"""
        stats = self.manager.get_stats()
        assert "registered_components_count" in stats
        assert "registered_components" in stats
        assert "active_components_count" in stats
        assert stats["registered_components_count"] >= 3

        # 测试 reload_components
        reloaded_count = self.manager.reload_components()
        assert reloaded_count >= 3
        assert self.manager.has_component("DoorComponent")
