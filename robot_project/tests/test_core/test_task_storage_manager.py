# -*- coding: utf-8 -*-
import os
import shutil
import tempfile
import threading
import time
from unittest.mock import MagicMock
import pytest
from core.task_storage_manager import TaskStorageManager

class TestTaskStorageManager:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mock_config = MagicMock()
        self.mock_config._config = {}
        
        self.tsm = TaskStorageManager(config_loader=self.mock_config)
        self.tsm.storage_dir = self.temp_dir # override to temp dir

    def teardown_method(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_save_and_get_task(self):
        """验证基础保存与读取"""
        steps = [{"action": "move"}]
        success = self.tsm.save_task_to_disk("T1", steps, "Test Task")
        assert success is True
        
        # 应该能回读 steps
        retrieved_steps = self.tsm.get_task_steps("T1")
        assert retrieved_steps == steps
        
        # 检查物理文件是否存在
        target_file = os.path.join(self.temp_dir, "T1.json")
        assert os.path.exists(target_file)
        assert self.tsm.has_task("T1") is True

    def test_save_and_get_task_data_with_rth_point(self):
        """验证带 metadata (如 rth_point) 的保存与全量回读"""
        steps = [{"action": "start_nav", "params": {"goal_point": 10}}]
        metadata = {"rth_point": 100, "task_type": "patrol"}
        success = self.tsm.save_task_to_disk("T_RTH", steps, "RTH Task", metadata=metadata)
        assert success is True
        
        task_data = self.tsm.get_task_data("T_RTH")
        assert task_data is not None
        assert task_data["task_id"] == "T_RTH"
        assert task_data["rth_point"] == 100
        assert task_data["task_type"] == "patrol"
        assert task_data["steps"] == steps
        assert task_data["total_steps"] == 1
        assert "updated_at" in task_data

    def test_list_tasks(self):
        """验证任务列表汇总功能"""
        self.tsm.save_task_to_disk("T1", [{"action": "move"}], "Task 1")
        self.tsm.save_task_to_disk("T2", [{"action": "stop"}], "Task 2")
        
        res = self.tsm.list_tasks()
        assert res["status"] == "success"
        assert res["total_count"] == 2
        task_ids = [t["task_id"] for t in res["tasks"]]
        assert "T1" in task_ids
        assert "T2" in task_ids

    def test_delete_task(self):
        """验证删除任务物理文件与缓存"""
        self.tsm.save_task_to_disk("T1", [{"action": "move"}])
        assert self.tsm.has_task("T1") is True

        res = self.tsm.delete_task("T1")
        assert res["status"] == "success"
        
        assert self.tsm.get_task_steps("T1") is None
        assert self.tsm.has_task("T1") is False
        assert not os.path.exists(os.path.join(self.temp_dir, "T1.json"))

    def test_clear_tasks(self):
        """验证清空所有任务"""
        self.tsm.save_task_to_disk("T1", [{"action": "move"}])
        self.tsm.save_task_to_disk("T2", [{"action": "stop"}])
        
        res = self.tsm.clear_tasks()
        assert res["cleared_count"] == 2
        assert self.tsm.list_tasks()["total_count"] == 0

    def test_invalid_inputs_rejected(self):
        """验证防御性校验：非法入参拒绝落盘"""
        # 空 task_id
        assert self.tsm.save_task_to_disk("", [{"action": "move"}]) is False
        # 非字符串 task_id
        assert self.tsm.save_task_to_disk(None, [{"action": "move"}]) is False
        # 空 steps
        assert self.tsm.save_task_to_disk("T_EMPTY", []) is False
        # 非列表 steps
        assert self.tsm.save_task_to_disk("T_INVALID", "not_a_list") is False

        assert self.tsm.get_task_data("NON_EXISTENT") is None
        assert self.tsm.has_task("") is False

    def test_cleanup_orphan_tmp_files(self):
        """验证孤儿临时文件的自动清理机制"""
        # 手工创建一个遗留的孤儿临时文件
        orphan_tmp = os.path.join(self.temp_dir, ".tmp_T_ORPHAN_123.json")
        with open(orphan_tmp, "w", encoding="utf-8") as f:
            f.write("{}")
        assert os.path.exists(orphan_tmp)

        # 触发清理
        self.tsm._cleanup_orphan_tmp_files()
        assert not os.path.exists(orphan_tmp)

    def test_concurrent_save_and_read(self):
        """验证多线程并发读写安全性"""
        stop_event = threading.Event()
        errors = []

        def writer():
            for i in range(20):
                if stop_event.is_set():
                    break
                try:
                    self.tsm.save_task_to_disk(f"T_CONCURRENT_{i}", [{"action": "ping"}], f"Name_{i}")
                except Exception as e:
                    errors.append(e)

        def reader():
            for i in range(20):
                if stop_event.is_set():
                    break
                try:
                    self.tsm.get_task_data(f"T_CONCURRENT_{i}")
                    self.tsm.list_tasks()
                except Exception as e:
                    errors.append(e)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"并发读写出现异常: {errors}"
