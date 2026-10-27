from unittest.mock import MagicMock, patch
import pytest
from plugins.camera.camera_plugin import CameraPlugin

class TestCameraPlugin:
    def setup_method(self):
        self.config = {
            "cameras": [
                {
                    "camera_id": 1,
                    "name": "HM-TD5567T-7_W双光相机",
                    "ip": "127.0.0.1",
                    "port": 80
                }
            ]
        }
        self.plugin = CameraPlugin(config=self.config)

    def test_get_capabilities(self):
        caps = self.plugin.get_capabilities()
        assert caps["plugin_type"] == "CameraPlugin"
        assert caps["plugin_name"] == "摄像头插件"
        assert len(caps["supported_actions"]) == 8
        actions = {a["action"]: a for a in caps["supported_actions"]}
        assert "cycle" in actions
        assert "capture" in actions
        assert "ptz" in actions
        assert "thermometry" in actions
        assert actions["thermometry"]["params"] == []

    @patch("plugins.camera.camera_driver.CameraDriver.get_thermometry_info")
    def test_thermometry_action_default_channel(self, mock_temp):
        mock_temp.return_value = {
            "status": "success",
            "data": {
                "highestTemperature": 45.0,
                "lowestTemperature": 22.0,
                "averageTemperature": 30.0,
                "alarmStatus": "NORMAL"
            }
        }
        res = self.plugin.execute("thermometry", {})
        assert res["status"] == "success"
        mock_temp.assert_called_once_with(channel=2)
        assert res["data"]["max_temp"] == 45.0

    @patch("plugins.camera.camera_driver.CameraDriver.capture_picture")
    def test_capture_action(self, mock_capture):
        mock_capture.return_value = {
            "status": "success",
            "message": "抓图成功",
            "data": {
                "base64": "data:image/jpeg;base64,/9j/4AAQSkZJRg==",
                "resolution": "1920x1080"
            }
        }
        res = self.plugin.execute("capture", {"camera_id": 1, "channel": 1})
        assert res["status"] == "success"
        mock_capture.assert_called_once_with(channel=1, return_base64=True)

    @patch("plugins.camera.camera_driver.CameraDriver.get_thermometry_info")
    def test_cycle_start_stop_action(self, mock_temp):
        mock_temp.return_value = {
            "status": "success",
            "data": {
                "highestTemperature": 42.5,
                "lowestTemperature": 20.1,
                "averageTemperature": 31.0,
                "alarmStatus": "NORMAL"
            }
        }
        res_start = self.plugin.execute("cycle", {"action": "start", "interval": 1})
        assert res_start["status"] == "success"
        assert "已成功启动双光热成像相机循环测温" in res_start["message"]
        assert self.plugin._cycle_thread is not None

        res_stop = self.plugin.execute("cycle", {"action": "stop"})
        assert res_stop["status"] == "success"
        assert "已停止双光热成像相机循环测温" in res_stop["message"]
        assert self.plugin.latest_telemetry is None

    def test_parse_thermal_metrics_nested(self):
        # 模拟海康 XML 解析后的嵌套结构以及普通结构
        raw_xml_dict = {
            "ThermalThermometry": {
                "highestPoint": {"temperature": "55.6", "position": {"x": 100, "y": 200}},
                "lowestPoint": {"temperature": "23.4"},
                "averagePoint": {"temperature": "35.8"},
                "alarmStatus": "ALARM"
            }
        }
        max_t, min_t, avg_t, status = self.plugin._parse_thermal_metrics(raw_xml_dict)
        assert max_t == 55.6
        assert min_t == 23.4
        assert avg_t == 35.8
        assert status == "ALARM"

    @patch("requests.Session.request")
    def test_camera_driver_xml_request_and_response(self, mock_request):
        driver = self.plugin.drivers[1]
        
        # 模拟海康原生 XML 返回
        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.headers = {"Content-Type": "application/xml"}
        resp_200.text = """<?xml version="1.0" encoding="UTF-8"?>
<ThermalThermometry>
    <highestPoint><temperature>48.2</temperature></highestPoint>
    <lowestPoint><temperature>21.0</temperature></lowestPoint>
    <averagePoint><temperature>32.5</temperature></averagePoint>
    <alarmStatus>NORMAL</alarmStatus>
</ThermalThermometry>"""

        mock_request.return_value = resp_200

        res = driver.get_thermometry_info(channel=2)
        assert res["status"] == "success"
        data = res["data"]
        assert "ThermalThermometry" in data
        assert data["ThermalThermometry"]["highestPoint"]["temperature"] == "48.2"

        # 验证请求绝不携带 format=json，并且采用 XML 请求
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args.kwargs
        params = call_kwargs.get("params")
        assert params is None or "format" not in params

    @patch("requests.Session.request")
    def test_camera_driver_xml_ptz_payload(self, mock_request):
        driver = self.plugin.drivers[1]
        
        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.headers = {"Content-Type": "application/xml"}
        resp_200.text = """<?xml version="1.0" encoding="UTF-8"?>
<ResponseStatus version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">
    <statusCode>1</statusCode>
    <statusString>OK</statusString>
</ResponseStatus>"""
        mock_request.return_value = resp_200

        res = driver.ptz_control(pan=15.0, tilt=-5.0, zoom=0.0, channel=1)
        assert res["status"] == "success"

        call_kwargs = mock_request.call_args.kwargs
        headers = call_kwargs.get("headers", {})
        assert "application/xml" in headers.get("Content-Type", "")

        sent_data = call_kwargs.get("data", b"").decode("utf-8")
        assert "<PTZData" in sent_data
        assert "<pan>15</pan>" in sent_data
        assert "<tilt>-5</tilt>" in sent_data
        assert "<rotate" not in sent_data

    @patch("requests.Session.request")
    def test_camera_driver_xml_ptz_ignores_rotate(self, mock_request):
        driver = self.plugin.drivers[1]
        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.headers = {"Content-Type": "application/xml"}
        resp_200.text = "<ResponseStatus><statusCode>1</statusCode></ResponseStatus>"
        mock_request.return_value = resp_200

        # 模拟前端或上层传递 rotate 字段
        res = driver.ptz_control(pan=1.0, tilt=0.0, zoom=0.0, rotate=0.0, channel=1)
        assert res["status"] == "success"

        sent_data = mock_request.call_args.kwargs.get("data", b"").decode("utf-8")
        assert "<pan>1</pan>" in sent_data
        assert "<tilt>0</tilt>" in sent_data
        assert "<zoom>0</zoom>" in sent_data
        assert "rotate" not in sent_data

    def test_dict_to_xml_utility(self):
        xml_str = self.plugin.drivers[1]._dict_to_xml({
            "PTZData": {
                "pan": 10.0,
                "tilt": 0.0
            }
        })
        assert "<?xml version=" in xml_str
        assert "<PTZData" in xml_str
        assert "<pan>10</pan>" in xml_str
        assert "<tilt>0</tilt>" in xml_str

    def teardown_method(self):
        self.plugin._stop_cycle_thread()


