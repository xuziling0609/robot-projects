# -*- coding: utf-8 -*-
"""
================================================================================
Pytest 全局测试沙箱隔离配置 (Test Sandbox Fixtures)
================================================================================
核心职责：
1. 【物理目录绝对隔离】：
   自动拦截测试套件中所有初始化的 TaskStorageManager 实例，将其默认存储路径
   强制重定向至 pytest 独立的临时沙箱目录 (tmp_path)；
2. 【杜绝误删与脏数据泄漏】：
   测试期间发生的任何 save、delete 以及危险的 clear 动作，100% 在临时沙箱中执行，
   测试结束后随临时目录自动销毁，彻底保护工程真实生产目录 `data/tasks/` 下的
   平台下发任务文件不受任何篡改、污染或删除！
================================================================================
"""

import os
import pytest
from core.task_storage_manager import TaskStorageManager
from core.mqtt_manager import DiskQueue

@pytest.fixture(autouse=True)
def isolate_task_storage_sandbox(tmp_path, monkeypatch):
    """
    全局自动生效 Fixture：
    1. 拦截 TaskStorageManager.__init__，重定向至当前用例独占的 tmp_path 临时目录；
    2. 拦截 DiskQueue.__init__，重定向至 tmp_path，彻底杜绝测试读写 data/mqtt_offline.db。
    """
    sandbox_tasks_dir = str(tmp_path / "sandbox_tasks")
    os.makedirs(sandbox_tasks_dir, exist_ok=True)

    original_init = TaskStorageManager.__init__
    def sandboxed_init(self, config_loader=None, storage_dir=None):
        target_dir = storage_dir or sandbox_tasks_dir
        original_init(self, config_loader=config_loader, storage_dir=target_dir)

    monkeypatch.setattr(TaskStorageManager, "__init__", sandboxed_init)

    # 隔离 MQTT 离线磁盘队列数据库
    sandbox_db_path = str(tmp_path / "sandbox_mqtt_offline.db")
    original_dq_init = DiskQueue.__init__
    def sandboxed_dq_init(self, db_path=None, max_size=10000):
        target_db = db_path or sandbox_db_path
        original_dq_init(self, db_path=target_db, max_size=max_size)

    monkeypatch.setattr(DiskQueue, "__init__", sandboxed_dq_init)

    yield
