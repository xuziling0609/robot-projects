from unittest.mock import MagicMock, patch, call
import pytest
from plugins.station.station_plugin import StationPlugin

class TestStationPlugin:
    def setup_method(self):
        self.plugin = StationPlugin({"uptime_success": 0.01})
        self.params = {"ips": ["192.168.1.101"]}

    @patch("plugins.station.station_plugin.Tasio211Driver")
    def test_open_success(self, MockDriver):
        mock_driver_instance = MagicMock()
        mock_driver_instance.execute_door_action.return_value = (True, "OK")
        self.plugin.driver = mock_driver_instance

        with patch("plugins.station.station_plugin.time.sleep", return_value=None):
            result = self.plugin.execute(action="open", params=self.params)

        assert result["status"] == "success"
        assert "开门成功" in result["message"]

    @patch("plugins.station.station_plugin.Tasio211Driver")
    def test_close_success(self, MockDriver):
        mock_driver_instance = MagicMock()
        mock_driver_instance.execute_door_action.return_value = (True, "OK")
        self.plugin.driver = mock_driver_instance

        result = self.plugin.execute(action="close", params=self.params)

        assert result["status"] == "success"
        assert "关门成功" in result["message"]

    def test_missing_ips(self):
        result = self.plugin.execute(action="open", params={})
        assert result["status"] == "error"

    def test_unsupported_action(self):
        result = self.plugin.execute(action="jump", params=self.params)
        assert result["status"] == "error"

    def test_abort_and_capabilities(self):
        assert self.plugin.abort()["status"] == "success"
        caps = self.plugin.get_capabilities()
        assert caps["plugin_type"] == "StationPlugin"

    def test_execute_status(self):
        result = self.plugin.execute(action="status", params={"ips": ["192.168.1.101"]})
        assert result["status"] == "success"
        assert result["data"]["online"] is True

    @patch("core.tcp_manager.TCPManager")
    def test_get_status_idle_does_not_connect_tcp(self, mock_pool_cls):
        mock_pool = MagicMock()
        mock_pool_cls.return_value = mock_pool

        assert self.plugin.get_status() is True
        assert self.plugin.status() is True
        mock_pool.get_connection.assert_not_called()
        mock_pool.release_connection.assert_not_called()

