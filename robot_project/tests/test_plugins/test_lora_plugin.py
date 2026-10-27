from unittest.mock import MagicMock, patch, call
import pytest
from plugins.lora.lora_plugin import LoraPlugin

class TestLoraPlugin:
    @pytest.fixture(autouse=True)
    def setup_plugin(self, mocker):
        mocker.patch("plugins.lora.lora_driver.LoraTCPDriver.start")
        self.config = {
            "host": "127.0.0.1",
            "port": 10024,
            "robot_id": "test_robot_888",
            "delay_seconds": 0.1
        }
        self.plugin = LoraPlugin(config=self.config)

    def teardown_method(self):
        if hasattr(self.plugin, "driver"):
            self.plugin.driver.stop()

    def test_get_capabilities(self):
        caps = self.plugin.get_capabilities()
        assert caps["plugin_type"] == "LoraPlugin"

    def test_reconnect_action(self):
        res = self.plugin.execute("reconnect", {})
        assert res["status"] == "success"

    def test_unsupported_action(self):
        res = self.plugin.execute("fly", {})
        assert res["status"] == "error"

    def test_task_status_mapping(self):
        from plugins.lora.lora_driver import LoraProtocol
        test_cases = [
            ("IDLE", "0"),
            ("idle", "0"),
            ("RUNNING", "1"),
            ("running", "1"),
            ("PAUSED", "2"),
            ("paused", "2"),
            ("FINISH", "3"),
            ("finished", "3"),
            ("FAILED", "4"),
            ("error", "4"),
            ("ABORTED", "5"),
            ("aborted", "5"),
            ("UNKNOWN", "0"),
        ]
        status_json = {
            "mode": "AUTO",
            "localization": {"x": 1.234, "y": 5.678, "status": "OK"},
            "battery": {"power": 88.0}
        }
        for task_state, expected_code in test_cases:
            res = LoraProtocol.parse_robot_status_to_list(
                status_json=status_json,
                task_json={"status": task_state},
                default_robot_id="robot888"
            )
            assert len(res) == 7
            assert res[0] == "robot888"
            assert res[1] == "1.234"
            assert res[2] == "5.678"
            assert res[3] == "88.00"
            assert res[4] == "0"  # AUTO
            assert res[5] == "0"  # OK
            assert res[6] == expected_code  # task_status


