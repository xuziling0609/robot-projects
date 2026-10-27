from unittest.mock import MagicMock, patch, call
import pytest

from plugins.door.door_plugin import DoorPlugin

class TestDoorPlugin:
    """
    DoorPlugin 业务逻辑自动化测试集
    通过 Mock 底层驱动，验证多线程下发、超时控制、多模式处理是否正确。
    """
    def setup_method(self):
        self.plugin = DoorPlugin({"port": 1030, "timeout": 3})
        self.params = {
            "ips": ["192.168.1.100", "192.168.1.101"]
        }

    @patch("plugins.door.door_plugin.FMK02Driver")
    def test_execute_success(self, MockDriver):
        mock_instance = MagicMock()
        mock_instance.send_command.return_value = True
        mock_instance.get_sensor_status.side_effect = ["MIDDLE", "MIDDLE", "FULLY_OPENED", "FULLY_OPENED"]
        MockDriver.return_value = mock_instance

        with patch("plugins.door.door_plugin.time.sleep", return_value=None):
            result = self.plugin.execute(action="open", params=self.params)

        assert result["status"] == "success"
        assert "完成" in result["message"]
        assert mock_instance.get_sensor_status.call_count == 4

    @patch("plugins.door.door_plugin.FMK02Driver")
    def test_execute_network_error(self, MockDriver):
        mock_instance = MagicMock()
        mock_instance.send_command.return_value = True
        mock_instance.get_sensor_status.return_value = "NETWORK_ERROR"
        MockDriver.return_value = mock_instance

        with patch("plugins.door.door_plugin.time.sleep", return_value=None):
            result = self.plugin.execute(action="open", params=self.params)

        assert result["status"] == "error"
        assert "断开" in result["message"]

    @patch("plugins.door.door_plugin.FMK02Driver")
    def test_execute_timeout(self, MockDriver):
        mock_instance = MagicMock()
        mock_instance.send_command.return_value = True
        mock_instance.get_sensor_status.return_value = "MIDDLE"
        MockDriver.return_value = mock_instance

        # 模拟连续递增时间触发 30s 超时
        times = [100.0 + i * 10 for i in range(100)]
        with patch("plugins.door.door_plugin.time.time", side_effect=times):
            with patch("plugins.door.door_plugin.time.sleep", return_value=None):
                result = self.plugin.execute(action="open", params=self.params)

        assert result["status"] == "error"
        assert "超时" in result["message"]

    def test_missing_ips_param(self):
        result = self.plugin.execute(action="open", params={})
        assert result["status"] == "error"
        assert "未提取到门控 IPs" in result["message"]

    def test_unsupported_action(self):
        result = self.plugin.execute(action="fly", params=self.params)
        assert result["status"] == "error"
        assert "不支持的动作" in result["message"]

    def test_get_capabilities(self):
        caps = self.plugin.get_capabilities()
        assert caps["plugin_type"] == "DoorPlugin"
        assert "supported_actions" in caps

    @patch("plugins.door.door_plugin.FMK02Driver")
    def test_pause_stops_polling(self, MockDriver):
        mock_instance = MagicMock()
        mock_instance.send_command.return_value = True
        mock_instance.get_sensor_status.return_value = "MIDDLE"
        MockDriver.return_value = mock_instance

        # 模拟执行中途触发 pause
        self.plugin._is_paused = True
        result = self.plugin.execute(action="open", params=self.params)

        assert result["status"] == "paused"
        assert "开门机动作因暂停被中断" in result["message"]

