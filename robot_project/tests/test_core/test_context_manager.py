import pytest
import threading
from core.context_manager import ContextManager

class TestContextManager:
    def setup_method(self):
        # 使用生命周期接口进行标准化初始化
        ContextManager.reset_status()
        ContextManager.reset_task()

    def test_update_and_get_robot_status(self):
        ContextManager.update_robot_status({"battery": 90, "speed": 1.5})
        status = ContextManager.get_robot_status()
        assert status["battery"] == 90
        assert status["speed"] == 1.5
        
        # 确保返回的是副本拷贝，外部修改不影响共享池
        status["battery"] = 50
        assert ContextManager.get_robot_status()["battery"] == 90

    def test_update_and_get_robot_task(self):
        ContextManager.update_robot_task({"status": "running", "task_id": "T123"})
        task = ContextManager.get_robot_task()
        assert task["status"] == "running"
        assert task["task_id"] == "T123"

    def test_get_field_and_convenience_getters(self):
        # 初始默认值测试
        assert ContextManager.get_task_status() == "idle"
        assert ContextManager.get_task_id() is None
        assert ContextManager.get_rth_point() is None
        assert ContextManager.get_status_field("battery", 100) == 100

        # 更新并测试单字段读取
        ContextManager.update_robot_task({
            "status": "RUNNING",
            "task_id": "TASK_001",
            "task_name": "巡检任务",
            "rth_point": 105,
            "custom_metadata": "special_val"
        })
        ContextManager.update_robot_status({"battery": 88})

        assert ContextManager.get_task_status() == "running"
        assert ContextManager.get_task_id() == "TASK_001"
        assert ContextManager.get_rth_point() == 105
        assert ContextManager.get_task_field("custom_metadata") == "special_val"
        assert ContextManager.get_task_field("non_existent", "default_val") == "default_val"
        assert ContextManager.get_status_field("battery") == 88

    def test_is_task_active(self):
        ContextManager.update_robot_task({"status": "idle"})
        assert not ContextManager.is_task_active()

        ContextManager.update_robot_task({"status": "running"})
        assert ContextManager.is_task_active()

        ContextManager.update_robot_task({"status": "paused"})
        assert ContextManager.is_task_active()

        ContextManager.update_robot_task({"status": "finish"})
        assert not ContextManager.is_task_active()

        ContextManager.update_robot_task({"status": "aborted"})
        assert not ContextManager.is_task_active()

    def test_reset_task_and_reset_status(self):
        ContextManager.update_robot_task({"status": "running", "task_id": "T_DEL", "rth_point": 50})
        ContextManager.update_robot_status({"battery": 20})

        ContextManager.reset_status()
        assert ContextManager.get_robot_status() == {}

        ContextManager.reset_task()
        task = ContextManager.get_robot_task()
        assert task["status"] == "idle"
        assert task["task_id"] is None
        assert task["rth_point"] is None

    def test_concurrent_updates(self):
        # 压力测试：并发 10 个线程同时更新和读取
        errors = []
        def worker(thread_id):
            try:
                for i in range(50):
                    ContextManager.update_robot_status({f"key_{thread_id}": i})
                    ContextManager.update_robot_task({"status": "running", "step": i})
                    _ = ContextManager.get_robot_status()
                    _ = ContextManager.get_task_status()
                    _ = ContextManager.get_task_field("step")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
