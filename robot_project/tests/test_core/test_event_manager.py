# -*- coding: utf-8 -*-
import time
import threading
from unittest.mock import MagicMock
import pytest
from core.event_manager import EventManager, EventBus, TaskEvent, EventType

class TestEventManager:
    def setup_method(self):
        self.em = EventManager()
        self.em.reset()

    def teardown_method(self):
        self.em.reset()

    def test_singleton(self):
        """验证双重检测锁单例唯一性及别名一致性"""
        em2 = EventManager()
        em_bus = EventBus()
        assert self.em is em2
        assert self.em is em_bus

    def test_event_type_enum_compatibility(self):
        """验证 EventType 枚举与字符串的 100% 互操作性"""
        assert EventType.GLOBAL_STATE_CHANGED == "global_state_changed"
        assert EventType.TASK_PAUSED == "task_paused"
        assert EventType.TASK_RESUMED == "task_resumed"
        assert EventType.TASK_CANCELLED == "task_cancelled"
        assert EventType.SUBTASK_FAILED == "subtask_failed"
        assert EventType.ALARM_AUTO_ACTION == "alarm_auto_action"
        assert EventType.TELEMETRY_SWEEP_READY == "telemetry_sweep_ready"
        assert EventType.ALL == "*"
        assert isinstance(EventType.TASK_PAUSED, str)

    def test_subscribe_and_publish_async(self):
        """验证标准异步非阻塞推入与守护线程派发"""
        handler_mock = MagicMock()
        self.em.subscribe(EventType.SUBTASK_FAILED, handler_mock)
        assert self.em.get_listener_count(EventType.SUBTASK_FAILED) == 1

        event = TaskEvent(event_type=EventType.SUBTASK_FAILED, task_id="T1", reason="timeout")
        self.em.publish(event)
        
        # 守护线程未启动，队列中积压 1 项
        assert self.em.get_queue_size() == 1
        assert not self.em.is_running()

        self.em.start()
        assert self.em.is_running()
        time.sleep(0.1) # 等待后台线程处理
        
        handler_mock.assert_called_once_with(event)
        assert self.em.get_queue_size() == 0
        self.em.stop()
        assert not self.em.is_running()

    def test_wildcard_subscribe(self):
        """验证通配符 '*' 订阅能够接收所有事件"""
        handler_mock = MagicMock()
        self.em.subscribe("*", handler_mock)
        
        event = TaskEvent(event_type="any_custom_event", task_id="T2")
        self.em.publish(event)
        
        self.em.start()
        time.sleep(0.1)
        
        handler_mock.assert_called_once_with(event)
        self.em.stop()

    def test_publish_sync(self):
        """验证同步直接派发，无需启动后台线程即可即时响应"""
        handler_mock = MagicMock()
        self.em.subscribe(EventType.GLOBAL_STATE_CHANGED, handler_mock)

        event = TaskEvent(
            event_type=EventType.GLOBAL_STATE_CHANGED,
            task_id="sys",
            extra_data={"state": "PAUSED"}
        )
        self.em.publish_sync(event)

        # 立即被调用，且队列中无积压
        handler_mock.assert_called_once_with(event)
        assert self.em.get_queue_size() == 0

    def test_unsubscribe(self):
        """验证注销监听器"""
        h1 = MagicMock()
        h2 = MagicMock()

        self.em.subscribe("evt_a", h1)
        self.em.subscribe("evt_a", h2)
        assert self.em.get_listener_count("evt_a") == 2

        # 移除 h1
        assert self.em.unsubscribe("evt_a", h1) is True
        assert self.em.get_listener_count("evt_a") == 1

        # 重复移除返回 False
        assert self.em.unsubscribe("evt_a", h1) is False

        # 测试派发只触发 h2
        event = TaskEvent(event_type="evt_a", task_id="T3")
        self.em.publish_sync(event)
        h1.assert_not_called()
        h2.assert_called_once_with(event)

        # 移除 h2 后该 key 完全清理
        assert self.em.unsubscribe("evt_a", h2) is True
        assert self.em.get_listener_count("evt_a") == 0

    def test_clear_listeners(self):
        """验证清空单类型或全部类型监听器"""
        self.em.subscribe("type1", lambda e: None)
        self.em.subscribe("type2", lambda e: None)
        assert self.em.get_listener_count() == 2

        # 仅清空 type1
        self.em.clear_listeners("type1")
        assert self.em.get_listener_count("type1") == 0
        assert self.em.get_listener_count("type2") == 1

        # 清空全部
        self.em.clear_listeners()
        assert self.em.get_listener_count() == 0

    def test_handler_exception_isolation(self):
        """验证单个监听器抛出异常不会中断其他监听器"""
        def bad_handler(e):
            raise RuntimeError("Handler crash!")

        good_handler = MagicMock()

        self.em.subscribe("test_crash", bad_handler)
        self.em.subscribe("test_crash", good_handler)

        event = TaskEvent(event_type="test_crash", task_id="T4")
        self.em.publish_sync(event)

        good_handler.assert_called_once_with(event)

    def test_concurrent_subscription_and_dispatch(self):
        """高并发场景：多线程并发注册、注销与派发，验证无迭代竞态冲突 (RuntimeError)"""
        stop_event = threading.Event()
        errors = []

        def worker_subscribe():
            while not stop_event.is_set():
                try:
                    def dummy(e): pass
                    self.em.subscribe("stress_event", dummy)
                    self.em.unsubscribe("stress_event", dummy)
                except Exception as e:
                    errors.append(e)

        def worker_publish():
            while not stop_event.is_set():
                try:
                    event = TaskEvent(event_type="stress_event", task_id="stress")
                    self.em.publish_sync(event)
                except Exception as e:
                    errors.append(e)

        threads = [
            threading.Thread(target=worker_subscribe),
            threading.Thread(target=worker_subscribe),
            threading.Thread(target=worker_publish),
            threading.Thread(target=worker_publish),
        ]
        for t in threads:
            t.start()

        time.sleep(0.3)
        stop_event.set()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"并发订阅派发产生异常: {errors}"

    def test_task_event_repr_and_compat(self):
        """验证 TaskEvent 的 get() 兼容性与 repr"""
        event = TaskEvent(
            event_type="global_state_changed",
            task_id="system",
            extra_data={"state": "RUNNING", "custom": 123}
        )
        assert event.get("event_type") == "global_state_changed"
        assert event.get("task_id") == "system"
        assert event.get("state") == "RUNNING"
        assert event.get("custom") == 123
        assert event.get("nonexistent") is None
        assert event.get("nonexistent", "default_val") == "default_val"
        assert "global_state_changed" in repr(event)
