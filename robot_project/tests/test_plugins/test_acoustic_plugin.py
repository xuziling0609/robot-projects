from unittest.mock import MagicMock, patch, call
import pytest
import struct
from plugins.acoustic.acoustic_driver import AcousticDriver
from plugins.acoustic.acoustic_plugin import AcousticPlugin

class TestAcousticDriver:
    def setup_method(self):
        self.driver = AcousticDriver("127.0.0.1", port=80, tcp_port=13052)
        
    @patch('requests.get')
    def test_get_spl(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"spl": 65.5}
        mock_get.return_value = mock_resp
        
        assert self.driver.get_spl() == 65.5
        mock_get.assert_called_with("http://127.0.0.1:80/spl", timeout=3.0)

    @patch('requests.post')
    def test_set_threshold(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "success"}
        mock_post.return_value = mock_resp
        
        res = self.driver.set_threshold(80.0)
        assert res == {"status": "success"}
        mock_post.assert_called_with("http://127.0.0.1:80/threshold", json={"value": 80.0}, timeout=3.0)

    def test_parse_frame(self):
        # 构造一帧合法的 TCP Payload 结构
        frame_no = 1
        spl = 85.0
        sound_len = 0
        filter_len = 0
        grid_len = 2  # 用极小长度测试
        prpd_len = 0
        v_type = 1
        v_len = 4
        
        payload_parts = [
            struct.pack('<If', frame_no, spl),
            struct.pack('<I', sound_len),
            struct.pack('<I', filter_len),
            struct.pack('<I', grid_len),
            struct.pack('<2f', 1.0, 2.0),
            struct.pack('<I', prpd_len),
            struct.pack('<I', v_type),
            struct.pack('<I', v_len),
            b'abcd'
        ]
        payload = b''.join(payload_parts)
        
        # 定义回调
        callback_mock = MagicMock()
        self.driver.on_frame_callback = callback_mock
        
        self.driver._parse_frame(payload)
        
        # 验证解析是否准确调用回调
        callback_mock.assert_called_once()
        args, _ = callback_mock.call_args
        assert args[0] == pytest.approx(85.0)  # spl
        assert len(args[1]) == 2      # grid_data
        assert args[1][0] == 1.0
        assert args[2] == 0           # prpd_len
        assert args[3] == b'abcd'     # video_data
        assert args[4] == 1           # v_type


class TestAcousticPlugin:
    @pytest.fixture(autouse=True)
    def setup_plugin(self, mocker):
        # 模拟配置读取
        def mock_config_get(key, default=None):
            if key == "plugins.acoustic.params.ip": return "127.0.0.1"
            if key == "plugins.acoustic.params.http_port": return 80
            if key == "plugins.acoustic.params.tcp_port": return 13052
            return default
            
        mocker.patch('core.config_manager.ConfigManager.get', side_effect=mock_config_get)
        self.plugin = AcousticPlugin(config={})
        
    def test_determine_alarm_level_default(self):
        self.plugin.alarm_rules = []
        level, msg = self.plugin._determine_alarm_level(85.5)
        assert level == "warning"
        assert "异常声压" in msg
        
    def test_determine_alarm_level_custom(self):
        self.plugin.alarm_rules = [{
            "metric_name": "SPL",
            "thresholds": {
                "warning": {"operator": "between", "value": [75.0, 85.0], "message": "WARN"},
                "error": {"operator": "between", "value": [85.0, 100.0], "message": "ERR"},
                "fatal": {"operator": "gte", "value": 100.0, "message": "FATAL"}
            }
        }]
        
        l1, m1 = self.plugin._determine_alarm_level(80.0)
        assert l1 == "warning"
        assert m1 == "WARN"
        
        l2, m2 = self.plugin._determine_alarm_level(90.0)
        assert l2 == "error"
        assert m2 == "ERR"
        
        l3, m3 = self.plugin._determine_alarm_level(105.0)
        assert l3 == "fatal"
        assert m3 == "FATAL"

    def test_get_capabilities(self):
        caps = self.plugin.get_capabilities()
        assert caps["plugin_type"] == "AcousticPlugin"
        actions = [a["action"] for a in caps.get("supported_actions", caps.get("capabilities", []))]
        assert "query_spl" in actions
        assert "cycle" in actions
        assert "query_fault" in actions
        assert "get_status" in actions
        assert "status" in actions

    @patch('plugins.acoustic.acoustic_driver.AcousticDriver.get_spl')
    def test_execute_query_spl(self, mock_get_spl):
        mock_get_spl.return_value = 78.5
        res = self.plugin.execute("query_spl", {})
        assert res["status"] == "success"
        assert res["data"]["spl"] == 78.5

    def test_execute_cyclic_detection(self):
        res = self.plugin.execute("cycle", {"enable": False})
        assert res["status"] == "success"
        assert not self.plugin.cycle_enabled

    @patch("core.alarm_manager.AlarmManager.report_alarm")
    def test_trigger_spl_alarm_with_real_h264(self, mock_report):
        from simulator.acousticSimulator import load_and_encode_h264_frame, generate_gaussian_grid, SCENE_IMAGE_PATH
        
        # 1. 获取合法的单帧 H.264 IDR 裸流
        h264_bytes = load_and_encode_h264_frame(SCENE_IMAGE_PATH)
        assert len(h264_bytes) > 100
        
        # 2. 生成高斯声像矩阵与局放数据
        grid_data = tuple(generate_gaussian_grid(spl=95.0, has_fault=True))
        assert len(grid_data) == 768
        
        # 3. 触发声纹告警合成
        with patch.object(self.plugin.driver, "get_prpd", return_value={"discharge_acceptance": 98.5}):
            self.plugin._trigger_spl_alarm(
                spl=95.0,
                grid_data=grid_data,
                prpd_len=2,
                video_data=h264_bytes,
                v_type=1
            )
            
        # 4. 验证 AlarmManager 是否上报了包含真实融合图像的 Base64
        mock_report.assert_called_once()
        _, kwargs = mock_report.call_args
        assert kwargs["code"] == 6001
        assert kwargs["source_plugin"] == "AcousticPlugin"
        alarm_data = kwargs["data"]
        assert alarm_data["spl"] == 95.0
        assert "image_base64" in alarm_data
        assert alarm_data["image_base64"].startswith("data:image/jpeg;base64,")
        assert len(alarm_data["image_base64"]) > 1000  # 确保是真正解码融合出的有效 JPEG

    @patch("core.alarm_manager.AlarmManager.report_alarm")
    def test_trigger_spl_alarm_with_no_video_data_fallback(self, mock_report):
        # 验证在探头未提供任何视频数据时，依然能够保底合成工业背景声纹融合图并上报告警 (无需 RTSP 拉流)
        self.plugin._latest_frame_bgr = None
        self.plugin._trigger_spl_alarm(
            spl=92.0,
            grid_data=tuple([50.0] * 768),
            prpd_len=0,
            video_data=b"",
            v_type=0
        )
        mock_report.assert_called_once()
        alarm_data = mock_report.call_args[1]["data"]
        assert "image_base64" in alarm_data
        assert alarm_data["image_base64"].startswith("data:image/jpeg;base64,")
        assert len(alarm_data["image_base64"]) > 1000

    @patch("core.alarm_manager.AlarmManager.report_alarm")
    def test_trigger_spl_alarm_with_cached_tcp_frame(self, mock_report):
        # 验证当后续帧无视频数据时，优先使用前序 TCP 帧缓存底图进行融合
        import numpy as np
        fake_cached_frame = np.full((720, 1280, 3), 120, dtype=np.uint8)
        self.plugin._latest_frame_bgr = fake_cached_frame
        
        self.plugin._trigger_spl_alarm(
            spl=93.5,
            grid_data=tuple([55.0] * 768),
            prpd_len=0,
            video_data=b"",
            v_type=0
        )
        mock_report.assert_called_once()
        alarm_data = mock_report.call_args[1]["data"]
        assert "image_base64" in alarm_data
        assert alarm_data["image_base64"].startswith("data:image/jpeg;base64,")

    @patch("plugins.acoustic.acoustic_driver.AcousticDriver.get_spl", return_value=60.0)
    def test_execute_capture(self, mock_spl):
        # 验证主动 capture 动作支持
        res = self.plugin.execute("capture", {})
        assert res["status"] == "success"
        assert "data" in res
        assert "image_base64" in res["data"]
        assert res["data"]["image_base64"].startswith("data:image/jpeg;base64,")


