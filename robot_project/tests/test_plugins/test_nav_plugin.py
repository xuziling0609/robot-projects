from unittest.mock import MagicMock, patch, call
import time
import threading
import pytest
from plugins.navigation.nav_plugin import NavPlugin

class TestNavPlugin:
    def setup_method(self):
        self.config = {
            "ip": "192.168.100.178",
            "port": 17808,
            "push_port": 17899,
            "app_code": "test_app_code",
            "robot_type": 513
        }
        # 拦截测试环境下的 HTTP 初始化请求，加快测试速度
        with patch("plugins.navigation.kecong_webapi_driver.KecongWebAPIDriver.set_push_settings", return_value={"result": 0}):
            self.plugin = NavPlugin(self.config)

    def teardown_method(self):
        if hasattr(self.plugin, "push_server") and self.plugin.push_server:
            self.plugin.push_server.stop()

    @patch("plugins.navigation.nav_plugin.KecongWebAPIDriver")
    def test_start_nav_pushed_finish(self, MockDriver):
        mock_driver = MagicMock()
        mock_driver.start_nav.return_value = {"result": 0, "error": ""}
        self.plugin.driver = mock_driver

        result_holder = {}
        def run_start_nav():
            result_holder["res"] = self.plugin.execute(action="start_nav", params={"goal_point": 15})

        t = threading.Thread(target=run_start_nav)
        t.start()

        # 模拟 0.05s 后控制器通过 HTTP POST 极速推过来 FINISH 状态 (按照文档 4.2.1)
        time.sleep(0.05)
        self.plugin._on_robot_status_pushed({
            "result": 0,
            "navigation": {"status": "FINISH", "goal": 15}
        })

        t.join(timeout=2.0)
        assert "res" in result_holder
        assert result_holder["res"]["status"] == "success"
        assert "成功到达" in result_holder["res"]["message"]

    @patch("plugins.navigation.nav_plugin.KecongWebAPIDriver")
    def test_start_nav_pushed_failed(self, MockDriver):
        mock_driver = MagicMock()
        mock_driver.start_nav.return_value = {"result": 0, "error": ""}
        self.plugin.driver = mock_driver

        result_holder = {}
        def run_start_nav():
            result_holder["res"] = self.plugin.execute(action="start_nav", params={"goal_point": 15})

        t = threading.Thread(target=run_start_nav)
        t.start()

        time.sleep(0.05)
        self.plugin._on_robot_status_pushed({
            "result": 0,
            "navigation": {"status": "FAILED", "goal": 15}
        })

        t.join(timeout=2.0)
        assert "res" in result_holder
        assert result_holder["res"]["status"] == "error"
        assert "未完成" in result_holder["res"]["message"]

    @patch("plugins.navigation.nav_plugin.KecongWebAPIDriver")
    def test_set_mode_and_gait(self, MockDriver):
        mock_driver = MagicMock()
        mock_driver.set_mode.return_value = {"result": 0}
        mock_driver.set_gait.return_value = {"result": 0}
        self.plugin.driver = mock_driver

        res_mode = self.plugin.execute(action="set_mode", params={"mode": "AUTO"})
        assert res_mode["status"] == "success"

        res_gait = self.plugin.execute(action="set_gait", params={"gait_index": 2})
        assert res_gait["status"] == "success"

    @patch("plugins.navigation.nav_plugin.KecongWebAPIDriver")
    def test_execute_motion_and_jerk(self, MockDriver):
        mock_driver = MagicMock()
        mock_driver.execute_motion.return_value = {"result": 0}
        mock_driver.jerk_stop.return_value = {"result": 0}
        self.plugin.driver = mock_driver

        res_motion = self.plugin.execute(action="execute_motion", params={"motion_cmd": 1})
        assert res_motion["status"] == "success"

        res_jerk = self.plugin.execute(action="jerk_stop", params={"jerk": True})
        assert res_jerk["status"] == "success"

    def test_unsupported_action(self):
        result = self.plugin.execute(action="dance_ballet", params={})
        assert result["status"] == "error"
        assert "不支持的导航动作" in result["message"]

    @patch("plugins.navigation.nav_plugin.KecongWebAPIDriver")
    def test_abort_and_capabilities(self, MockDriver):
        mock_driver = MagicMock()
        self.plugin.driver = mock_driver

        res = self.plugin.abort()
        assert res["status"] == "success"
        mock_driver.abort_nav.assert_called_once()

        caps = self.plugin.get_capabilities()
        assert caps["plugin_type"] == "NavPlugin"
        assert "supported_actions" in caps

    def test_status_push_telemetry_blocked_and_battery(self):
        # 1. 模拟推送正常状态 (未受阻，电量 85%)
        status_normal = {
            "result": 0,
            "chassis": {"velocity": 0.5, "blocked": False},
            "battery": {"percentage": 85.0}
        }
        self.plugin._on_robot_status_pushed(status_normal)
        telemetry = self.plugin.latest_telemetry
        metrics = {item["metric_name"]: item["value"] for item in telemetry}
        assert metrics.get("BATTERY") == 85.0
        assert metrics.get("BLOCKED") == 0

        # 2. 模拟推送受阻状态 (blocked: True)
        status_blocked = {
            "result": 0,
            "chassis": {"velocity": 0.0, "blocked": True},
            "battery": {"percentage": 82.0}
        }
        self.plugin._on_robot_status_pushed(status_blocked)
        telemetry = self.plugin.latest_telemetry
        metrics = {item["metric_name"]: item["value"] for item in telemetry}
        assert metrics.get("BATTERY") == 82.0
        assert metrics.get("BLOCKED") == 1

    def test_capabilities_config_metrics(self):
        caps = self.plugin.get_capabilities()
        metrics = {m["metric_name"]: m for m in caps.get("config_metrics", [])}
        assert "BATTERY" in metrics
        assert "BLOCKED" in metrics
        assert metrics["BLOCKED"]["unit"] == "bool"
        assert metrics["BLOCKED"]["operator"] == ["eq"]

    @patch("plugins.navigation.nav_plugin.KecongWebAPIDriver")
    def test_manual_control(self, MockDriver):
        mock_driver = MagicMock()
        mock_driver.manual_control.return_value = {"result": 0, "error": ""}
        self.plugin.driver = mock_driver

        # 1. 当前处于 AUTO 模式时，应直接拦截报错，不调用底层驱动
        self.plugin.latest_status = {"mode": "AUTO"}
        res_fail = self.plugin.execute(action="manual_control", params={"speed_x": 0.5, "speed_y": 0.0, "speed_theta": 0.2})
        assert res_fail["status"] == "error"
        assert "MANU" in res_fail["message"]
        mock_driver.manual_control.assert_not_called()

        # 2. 当前处于 MANU 手动模式时，应正常下发底层遥控
        self.plugin.latest_status = {"mode": "MANU"}
        res_ok = self.plugin.execute(action="manual_control", params={"speed_x": 0.5, "speed_y": 0.0, "speed_theta": 0.2})
        assert res_ok["status"] == "success"
        mock_driver.manual_control.assert_called_once_with(speed_x=0.5, speed_y=0.0, speed_theta=0.2)




