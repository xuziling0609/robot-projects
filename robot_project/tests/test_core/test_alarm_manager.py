from unittest.mock import MagicMock, patch, call
import os
import json
import time
import tempfile
import threading
import yaml
import pytest

from core.alarm_manager import AlarmManager, PLUGINS_DATA_DIR
from core.event_manager import TaskEvent
from plugins.gas.gas_plugin import GasPlugin


class TestAlarmManagerSolutionA:
    def setup_method(self):
        AlarmManager.reset()
        self.alarm_mgr = AlarmManager()
        self.alarm_mgr.rules_cfg = {}
        self.alarm_mgr._file_mtimes = {}
        self.alarm_mgr._last_alarm_state = {}

        self.test_alarm_file = os.path.join(PLUGINS_DATA_DIR, "GasPlugin_alarm.json")
        self.backup_content = None
        if os.path.exists(self.test_alarm_file):
            try:
                with open(self.test_alarm_file, "r", encoding="utf-8") as f:
                    self.backup_content = f.read()
            except Exception:
                pass

    def teardown_method(self):
        if self.backup_content is not None and os.path.exists(self.test_alarm_file):
            try:
                with open(self.test_alarm_file, "w", encoding="utf-8") as f:
                    f.write(self.backup_content)
            except Exception:
                pass
        AlarmManager.reset()

    def test_mtime_auto_reload_from_plugin(self):
        """测试能力插件直接保存至 data/plugins/GasPlugin_alarm.json，AlarmManager 自动通过 mtime 热重载规则"""
        gas_plugin = GasPlugin()
        rule = [
            {
                "gasType": "CO2",
                "unit": "PPM",
                "thresholds": {
                    "warning": {"operator": "between", "value": [400, 1000], "message": "CO2浓度偏高"}
                }
            }
        ]

        # 1. 气体插件单独执行 set_config 指令，写入文件
        res = gas_plugin.execute("set_config", {"config": rule})
        assert res["status"] == "success"

        # 2. AlarmManager 执行 check_and_reload_configs() 自动检测 mtime 并重载
        self.alarm_mgr.check_and_reload_configs()
        assert "CO2" in self.alarm_mgr.rules_cfg
        assert self.alarm_mgr.rules_cfg["CO2"]["thresholds"]["warning"]["message"] == "CO2浓度偏高"

        # 3. 模拟插件更新配置文件 (mtime 改变)
        time.sleep(1.1)
        updated_rule = [
            {
                "gasType": "CO2",
                "unit": "PPM",
                "thresholds": {
                    "error": {"operator": "gt", "value": 1500, "message": "CO2严重超标"}
                }
            }
        ]
        gas_plugin.execute("set_config", {"config": updated_rule})

        # 4. AlarmManager 自动感知 mtime 变更并更新内存中的规则
        self.alarm_mgr.check_and_reload_configs()
        assert "error" in self.alarm_mgr.rules_cfg["CO2"]["thresholds"]
        assert self.alarm_mgr.rules_cfg["CO2"]["thresholds"]["error"]["message"] == "CO2严重超标"

    @patch("core.mqtt_manager.MQTTManager.send_alarm")
    def test_sweep_and_evaluate_with_mtime(self, mock_send_alarm):
        """测试扫盘加 mtime 自动感知的集成流程"""
        gas_plugin = GasPlugin()
        rule = [{
            "gasType": "CO2",
            "unit": "PPM",
            "thresholds": {
                "warning": {"operator": "gt", "value": 500, "message": "CO2偏高"}
            }
        }]
        gas_plugin.execute("set_config", {"config": rule})

        mock_plugin = MagicMock()
        mock_plugin.latest_telemetry = [
            {"sensor_id": 1, "channel_code": 5, "name": "CO2", "value": 800.0, "unit": "PPM"}
        ]
        mock_pm = MagicMock()
        mock_pm.plugins = {"GasPlugin": mock_plugin}

        self.alarm_mgr.sweep_and_evaluate(mock_pm)
        mock_send_alarm.assert_called_once()
        call_args = mock_send_alarm.call_args[1]
        assert call_args["level"] == "warning"
        assert call_args["data"]["metric_name"] == "CO2"


class TestAlarmManagerAdvanced:
    """全面覆盖重构后的工业级特性：沙箱隔离、算子引擎、防抖抑制、自省与多线程并发"""

    def setup_method(self):
        AlarmManager.reset()

    def teardown_method(self):
        AlarmManager.reset()

    def test_singleton_and_reset(self):
        """验证单例唯一性与 reset 清理能力"""
        mgr1 = AlarmManager()
        mgr2 = AlarmManager()
        assert mgr1 is mgr2

        AlarmManager.reset()
        assert AlarmManager._instance is None

    def test_operator_evaluations(self):
        """验证算子引擎各类条件与异常输入容错"""
        mgr = AlarmManager()
        # 比较数值
        assert mgr._check_operator(10, "gt", 5) is True
        assert mgr._check_operator(5, "gte", 5) is True
        assert mgr._check_operator(3, "lt", 5) is True
        assert mgr._check_operator(5, "lte", 5) is True
        assert mgr._check_operator(5, "between", [1, 10]) is True
        assert mgr._check_operator(15, "between", [1, 10]) is False

        # 离散值 / 等值
        assert mgr._check_operator("ALARM", "eq", "ALARM") is True
        assert mgr._check_operator("ALARM", "neq", "NORMAL") is True
        assert mgr._check_operator("ERR_01", "in", ["ERR_01", "ERR_02"]) is True

        # 非法输入容错（杜绝抛错崩溃）
        assert mgr._check_operator(None, "gt", 5) is False
        assert mgr._check_operator("not_a_number", "gt", 5) is False
        assert mgr._check_operator(10, "unknown_op", 5) is False

    @patch("core.mqtt_manager.MQTTManager.send_alarm")
    def test_parametric_sandbox_and_task_event_debounce(self, mock_send_alarm):
        """验证参数化沙箱目录注入与任务事件防抖抑制机制"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 1. 构造独立的任务告警配置文件
            custom_alarm_yaml = os.path.join(tmp_dir, "custom_alarm.yaml")
            yaml_content = {
                "task_alarms": {
                    "subtask_failed": {
                        "enabled": True,
                        "level": "error",
                        "code": 5001,
                        "suppress_seconds": 2.0,
                        "message_template": "任务[{task_id}] 步骤{step} 失败: {reason}"
                    }
                }
            }
            with open(custom_alarm_yaml, "w", encoding="utf-8") as f:
                yaml.dump(yaml_content, f)

            mgr = AlarmManager(
                plugins_data_dir=tmp_dir,
                task_alarm_config_path=custom_alarm_yaml
            )

            event = TaskEvent(
                event_type="subtask_failed",
                task_id="TASK_001",
                step=2,
                reason="电机驱动失联"
            )

            # 首次触发：应正常上报
            mgr.handle_task_event(event)
            assert mock_send_alarm.call_count == 1
            args = mock_send_alarm.call_args[1]
            assert args["level"] == "error"
            assert args["code"] == 5001
            assert "电机驱动失联" in args["message"]

            # 立即再次触发相同 task_id 事件：处于 2.0s 防抖窗口内，应被抑制拦截
            mgr.handle_task_event(event)
            assert mock_send_alarm.call_count == 1  # 仍为 1，说明成功防抖抑制！

    @patch("core.mqtt_manager.MQTTManager.send_alarm")
    def test_channel_state_machine_transition_and_recovery(self, mock_send_alarm):
        """验证通道告警级别跳变上报与恢复正常机制"""
        mgr = AlarmManager()
        with mgr._lock:
            mgr.rules_cfg = {
                "TEMP": {
                    "unit": "℃",
                    "thresholds": {
                        "error": {"operator": "gt", "value": 70, "message": "温度过高"},
                        "warning": {"operator": "gt", "value": 50, "message": "温度偏高"}
                    }
                }
            }

        # 1. 温度 55 -> 触发 warning
        readings_1 = [{"sensor_id": 1, "channel_code": 1, "name": "TEMP", "value": 55.0}]
        mgr.evaluate_plugin_telemetry("TempPlugin", readings_1)
        assert mock_send_alarm.call_count == 1
        assert mock_send_alarm.call_args[1]["level"] == "warning"

        # 2. 温度持续为 58 -> 同为 warning，不重复刷屏上报
        readings_2 = [{"sensor_id": 1, "channel_code": 1, "name": "TEMP", "value": 58.0}]
        mgr.evaluate_plugin_telemetry("TempPlugin", readings_2)
        assert mock_send_alarm.call_count == 1

        # 3. 温度飙升到 75 -> 跳变至 error，再次上报
        readings_3 = [{"sensor_id": 1, "channel_code": 1, "name": "TEMP", "value": 75.0}]
        mgr.evaluate_plugin_telemetry("TempPlugin", readings_3)
        assert mock_send_alarm.call_count == 2
        assert mock_send_alarm.call_args[1]["level"] == "error"

        # 4. 温度降至 40 -> 恢复正常，检查活跃告警消除
        readings_4 = [{"sensor_id": 1, "channel_code": 1, "name": "TEMP", "value": 40.0}]
        mgr.evaluate_plugin_telemetry("TempPlugin", readings_4)
        active_alarms = mgr.get_active_alarms()
        assert len(active_alarms) == 0

    def test_active_alarms_and_clear_apis(self):
        """验证 get_active_alarms、clear_alarm_state 与 get_stats 自省 API"""
        mgr = AlarmManager()
        with mgr._lock:
            mgr._last_alarm_state["Ch1"] = "warning"
            mgr._last_alarm_state["Ch2"] = "error"
            mgr._last_alarm_state["Ch3"] = "NORMAL"

        active = mgr.get_active_alarms()
        assert active == {"Ch1": "warning", "Ch2": "error"}

        stats = mgr.get_stats()
        assert stats["active_alarm_count"] == 2
        assert stats["event_bus_bound"] is True

        # 手动重置单个通道
        mgr.clear_alarm_state("Ch1")
        assert "Ch1" not in mgr.get_active_alarms()

        # 手动清空全量
        mgr.clear_alarm_state()
        assert len(mgr.get_active_alarms()) == 0

    def test_concurrent_sweep_and_task_event(self):
        """验证多线程高并发下同时执行 sweep 与 handle_task_event 的线程安全性"""
        mgr = AlarmManager()
        errors = []

        mock_plugin = MagicMock()
        mock_plugin.latest_telemetry = [{"name": "MOCK", "value": 10}]
        mock_pm = MagicMock()
        mock_pm.plugins = {"P1": mock_plugin}

        def worker_sweep():
            try:
                for _ in range(30):
                    mgr.sweep_and_evaluate(mock_pm)
            except Exception as e:
                errors.append(e)

        def worker_event(tid: int):
            try:
                for i in range(30):
                    ev = TaskEvent(
                        event_type="subtask_failed",
                        task_id=f"T_{tid}_{i}",
                        step=1,
                        reason="Err"
                    )
                    mgr.handle_task_event(ev)
            except Exception as e:
                errors.append(e)

        threads = []
        for tid in range(5):
            threads.append(threading.Thread(target=worker_sweep))
            threads.append(threading.Thread(target=worker_event, args=(tid,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


