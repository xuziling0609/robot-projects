from unittest.mock import MagicMock, patch, call
import pytest
from plugins.elevator.elevator_plugin import ElevatorPlugin

class TestElevatorPlugin:
    def setup_method(self):
        self.config = {
            "host_api": "http://mock.api",
            "appname": "test_app",
            "secret": "test_sec",
            "fixed_place_id": "test_place"
        }
        self.plugin = ElevatorPlugin(self.config)

    @patch.object(ElevatorPlugin, "_is_lora_online", return_value=False)
    def test_missing_addr(self, mock_lora):
        result = self.plugin.execute(action="goToFloor", params={"floor": 3})
        assert result["status"] == "error"
        assert "缺少必要的 addr 参数" in result["message"]

    @patch.object(ElevatorPlugin, "_is_lora_online", return_value=False)
    def test_missing_floor(self, mock_lora):
        result = self.plugin.execute(action="goToFloor", params={"addr": 18191})
        assert result["status"] == "error"
        assert "缺少 floor 参数" in result["message"]

    @patch.object(ElevatorPlugin, "_is_lora_online", return_value=False)
    def test_call_lift_failure(self, mock_lora):
        self.plugin.yunji_driver.call_lift = MagicMock(return_value=False)
        result = self.plugin.execute(action="goToFloor", params={"addr": 18191, "floor": 3})
        assert result["status"] == "error"
        assert "调用失败" in result["message"]

    @patch.object(ElevatorPlugin, "_is_lora_online", return_value=False)
    def test_go_to_floor_success(self, mock_lora):
        self.plugin.yunji_driver.call_lift = MagicMock(return_value=True)
        self.plugin.yunji_driver.query_status = MagicMock(return_value={"floor": 3})

        with patch("plugins.elevator.elevator_plugin.time.sleep", return_value=None):
            result = self.plugin.execute(action="goToFloor", params={"addr": 18191, "floor": 3})

        assert result["status"] == "success"
        assert "到达 3 层" in result["message"]

    @patch.object(ElevatorPlugin, "_is_lora_online", return_value=False)
    def test_open_and_close_door(self, mock_lora):
        self.plugin.yunji_driver.delay_close = MagicMock(return_value=True)

        res_open = self.plugin.execute(action="openDoor", params={"addr": 18191})
        assert res_open["status"] == "success"

        res_close = self.plugin.execute(action="closeDoor", params={"addr": 18191})
        assert res_close["status"] == "success"

    def test_abort(self):
        res = self.plugin.abort()
        assert res["status"] == "success"

    def test_get_capabilities(self):
        caps = self.plugin.get_capabilities()
        assert caps["plugin_type"] == "ElevatorPlugin"
        assert "supported_actions" in caps

