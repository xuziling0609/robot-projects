from unittest.mock import MagicMock, patch, call
import time
import pytest
from core.telemetry_manager import TelemetryManager
from core.event_manager import EventType


class TestTelemetryManager:
    def setup_method(self):
        self.mock_pm = MagicMock()
        self.mock_mqtt = MagicMock()
        self.mock_task = MagicMock()
        self.mock_task.get_task_state.return_value = "IDLE"

        # 构造 Mock NavPlugin 接口
        self.mock_nav = MagicMock()
        self.mock_nav.status = MagicMock(return_value=True)
        self.mock_nav.get_status.return_value = {
            "mode": "AUTO",
            "chassis": {"vx": 0.0},
            "battery": {"soc": 90.0}
        }

        # 构造 Mock GasPlugin (带 latest_telemetry)
        self.mock_gas = MagicMock()
        self.mock_gas.latest_telemetry = [
            {"sensor_id": 1, "channel_code": 1, "name": "CO", "value": 12.5, "unit": "PPM", "status": "NORMAL"}
        ]

        self.mock_pm.plugins = {
            "NavPlugin": self.mock_nav,
            "GasPlugin": self.mock_gas
        }

        self.telemetry_mgr = TelemetryManager(
            plugin_manager=self.mock_pm,
            mqtt_manager=self.mock_mqtt,
            task_manager=self.mock_task,
            interval=1.0
        )

    def teardown_method(self):
        # 确保每个测试用例结束后线程安全退出
        if hasattr(self, "telemetry_mgr") and self.telemetry_mgr.is_running():
            self.telemetry_mgr.stop(timeout=1.0)

    def test_collect_plugin_telemetry(self):
        """测试正常收集全量插件遥测数据与事件发布"""
        data = self.telemetry_mgr.collect_plugin_telemetry()
        assert "NavPlugin" in data
        assert "GasPlugin" in data
        assert data["NavPlugin"]["mode"] == "AUTO"
        assert len(data["GasPlugin"]) == 1
        assert data["GasPlugin"][0]["name"] == "CO"

    def test_auto_cleanup_when_telemetry_is_none(self):
        """测试插件无数据时自动清理剔除"""
        # 模拟 GasPlugin 关泵停止采集 -> latest_telemetry 置为 None
        self.mock_gas.latest_telemetry = None

        data = self.telemetry_mgr.collect_plugin_telemetry()
        assert "NavPlugin" in data
        assert "GasPlugin" not in data  # GasPlugin 被自动清理剔除

    def test_publish_status_once(self):
        """测试单次发布状态心跳"""
        self.telemetry_mgr.publish_status_once()
        self.mock_mqtt.publish_status.assert_called_once()
        args, kwargs = self.mock_mqtt.publish_status.call_args
        assert kwargs["task_state"] == "IDLE"
        assert "plugins" in kwargs["robot_status"]
        plugins = kwargs["robot_status"]["plugins"]
        assert "NavPlugin" in plugins
        assert "GasPlugin" in plugins

    def test_single_plugin_failure_isolated(self):
        """核心断言：单个插件异常隔离，不影响其他健康插件收集"""
        # 模拟一个崩溃故障的传感器插件
        mock_faulty = MagicMock()
        mock_faulty.status.side_effect = RuntimeError("硬件串口读取超时")
        
        # 模拟另一个抛出异常的插件
        mock_faulty2 = MagicMock()
        mock_faulty2.status.return_value = True
        mock_faulty2.get_status.side_effect = ValueError("数据校验非法")

        self.mock_pm.plugins["FaultySensor"] = mock_faulty
        self.mock_pm.plugins["CrashPlugin"] = mock_faulty2

        # 收集遥测，验证即使有两个故障插件，系统不崩溃，NavPlugin 和 GasPlugin 依然正常收取
        data = self.telemetry_mgr.collect_plugin_telemetry()
        assert "NavPlugin" in data
        assert "GasPlugin" in data
        assert "FaultySensor" not in data
        assert "CrashPlugin" not in data

    def test_get_latest_telemetry_snapshot_and_timestamp(self):
        """测试状态快照与时间戳自省接口"""
        assert self.telemetry_mgr.get_latest_sweep_timestamp() == 0.0
        assert self.telemetry_mgr.get_latest_telemetry() == {}

        # 触发一次收集
        data = self.telemetry_mgr.collect_plugin_telemetry()
        snapshot = self.telemetry_mgr.get_latest_telemetry()
        timestamp = self.telemetry_mgr.get_latest_sweep_timestamp()

        assert snapshot == data
        assert timestamp > 0.0

        # 修改返回的深拷贝快照，内部缓存不受污染
        snapshot["TestHack"] = True
        assert "TestHack" not in self.telemetry_mgr.get_latest_telemetry()

    def test_trigger_sweep(self):
        """测试外部手动强制触发一次上报"""
        self.telemetry_mgr.trigger_sweep()
        self.mock_mqtt.publish_status.assert_called_once()

    def test_lifecycle_start_and_stop(self):
        """测试线程生命周期控制与毫秒级即时平滑退出"""
        assert not self.telemetry_mgr.is_running()

        self.telemetry_mgr.start()
        assert self.telemetry_mgr.is_running()

        # 重复调用 start 安全忽略
        self.telemetry_mgr.start()
        assert self.telemetry_mgr.is_running()

        # 停止线程
        start_time = time.time()
        self.telemetry_mgr.stop(timeout=1.0)
        stop_duration = time.time() - start_time

        assert not self.telemetry_mgr.is_running()
        # 应该在极短时间内 (远小于 1 秒) 响应退出
        assert stop_duration < 1.0

        # 重复调用 stop 安全忽略
        self.telemetry_mgr.stop()
        assert not self.telemetry_mgr.is_running()
