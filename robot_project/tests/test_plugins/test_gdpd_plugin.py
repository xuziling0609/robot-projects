from unittest.mock import MagicMock, patch, call
import pytest
from plugins.gdpd.gdpd_plugin import GdpdPlugin

class TestGdpdPlugin:
    def setup_method(self):
        self.config = {
            "conn_type": "tcp",
            "ip": "127.0.0.1",
            "port": "8080",
            "sample_count": 2,
            "sample_interval": 0.01
        }
        self.plugin = GdpdPlugin(config=self.config)

    def test_get_capabilities(self):
        caps = self.plugin.get_capabilities()
        assert caps["plugin_type"] == "GdpdPlugin"
        assert "supported_actions" in caps
        actions = [a["action"] for a in caps["supported_actions"]]
        assert "get_config" in actions
        assert "set_config" in actions
        assert "config_metrics" in caps
        assert len(caps["config_metrics"]) == 1
        assert caps["config_metrics"][0]["metric_name"] == "PEAK"
        assert caps["config_metrics"][0]["unit"] == "dBm"

    @patch("plugins.gdpd.gdpd_driver.GdpdDriver.acquire_data")
    def test_acquire_action(self, mock_acquire):
        mock_acquire.return_value = {"peak": 10.0, "average": 5.0, "frequency": 12}
        res = self.plugin.execute("acquire", {"sample_count": 2, "sample_interval": 0.01})
        assert res["status"] == "success"
        assert res["data"] == {"peak": 10.0, "mean": 5.0, "frequency": 12}
        assert not hasattr(self.plugin, "latest_telemetry")

    @patch("plugins.gdpd.gdpd_driver.GdpdDriver.stop_acquisition")
    @patch("plugins.gdpd.gdpd_driver.GdpdDriver.acquire_data")
    @patch("plugins.gdpd.gdpd_driver.GdpdDriver.start_acquisition")
    def test_start_monitor_action(self, mock_start, mock_acquire, mock_stop):
        mock_start.return_value = True
        mock_stop.return_value = True
        mock_acquire.return_value = {"peak": 24.5, "average": 18.2, "frequency": 71}
        res = self.plugin.execute("monitor", {"sample_count": 2, "sample_interval": 0.001})
        assert res["status"] == "success"
        assert res["data"] == {"peak": 24.5, "mean": 18.2, "frequency": 142}
        assert not hasattr(self.plugin, "latest_telemetry")

    def test_get_and_set_config(self, tmp_path):
        test_file = str(tmp_path / "GdpdPlugin_alarm.json")
        self.plugin.alarm_config_path = test_file

        # 初始文件不存在时 get_config
        res_get_empty = self.plugin.execute("get_config", {})
        assert res_get_empty["status"] == "success"
        assert res_get_empty["data"] == []

        # 下发 set_config 配置
        sample_rules = [
            {
                "metric_name": "PEAK",
                "unit": "dBm",
                "thresholds": {
                    "warning": {
                        "operator": "gte",
                        "value": 25.0,
                        "message": "局放峰值过高"
                    }
                }
            }
        ]
        res_set = self.plugin.execute("set_config", {"config": sample_rules})
        assert res_set["status"] == "success"
        assert res_set["data"] == sample_rules

        # 再次 get_config 验证读取
        res_get = self.plugin.execute("get_config", {})
        assert res_get["status"] == "success"
        assert res_get["data"] == sample_rules
        assert res_get["data"][0]["metric_name"] == "PEAK"

    def test_unsupported_action(self):
        res = self.plugin.execute("fly", {})
        assert res["status"] == "error"

