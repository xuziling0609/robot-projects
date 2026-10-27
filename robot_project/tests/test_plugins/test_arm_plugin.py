from unittest.mock import MagicMock, patch, call
import json
import pytest
from plugins.arm.arm_plugin import ArmPlugin

class TestArmPlugin:
    def setup_method(self):
        self.config = {
            "ip": "127.0.0.1",
            "port": 2000,
            "connect_timeout": 1.0,
            "start_timeout": 1.0,
            "exec_timeout": 1.0
        }
        self.plugin = ArmPlugin(config=self.config)

    @patch("plugins.arm.arm_plugin.TCPManager")
    def test_goto_success(self, mock_pool_cls):
        mock_pool = MagicMock()
        mock_socket = MagicMock()
        mock_pool.get_connection.return_value = mock_socket
        mock_pool_cls.return_value = mock_pool

        # 模拟 TCP 服务器相继返回 {"result": "start"} 与 {"result": "success"}
        mock_socket.recv.side_effect = [
            b'{"result": "start"}\n',
            b'{"result": "success"}\n'
        ]

        res = self.plugin.execute("goto", {"point": 0})

        assert res["status"] == "success"
        assert "data" not in res

        # 校验发出的 TCP 指令为 {"action": "goto", "point": 0}
        mock_socket.sendall.assert_called_once()
        sent_bytes = mock_socket.sendall.call_args[0][0]
        sent_json = json.loads(sent_bytes.decode('utf-8').strip())
        assert sent_json == {"action": "goto", "point": 0}

        # 校验最后关闭 TCP 连接
        mock_pool.release_connection.assert_called_once_with("127.0.0.1", 2000)

    @patch("plugins.arm.arm_plugin.TCPManager")
    def test_pause_success(self, mock_pool_cls):
        mock_pool = MagicMock()
        mock_socket = MagicMock()
        mock_pool.get_connection.return_value = mock_socket
        mock_pool_cls.return_value = mock_pool

        mock_socket.recv.side_effect = [
            b'{"result": "start"}\n',
            b'{"result": "success"}\n'
        ]

        res = self.plugin.execute("pause", {})

        assert res["status"] == "success"
        sent_bytes = mock_socket.sendall.call_args[0][0]
        sent_json = json.loads(sent_bytes.decode('utf-8').strip())
        assert sent_json == {"action": "pause"}
        mock_pool.release_connection.assert_called_once()

    @patch("plugins.arm.arm_plugin.TCPManager")
    def test_goback_success(self, mock_pool_cls):
        mock_pool = MagicMock()
        mock_socket = MagicMock()
        mock_pool.get_connection.return_value = mock_socket
        mock_pool_cls.return_value = mock_pool

        mock_socket.recv.side_effect = [
            b'{"result": "start"}\n',
            b'{"result": "success"}\n'
        ]

        res = self.plugin.execute("goback", {})

        assert res["status"] == "success"
        sent_bytes = mock_socket.sendall.call_args[0][0]
        sent_json = json.loads(sent_bytes.decode('utf-8').strip())
        assert sent_json == {"action": "goback"}
        mock_pool.release_connection.assert_called_once()

    def test_unsupported_action(self):
        res = self.plugin.execute("fly", {})
        assert res["status"] == "error"
        assert "不支持的机械臂动作" in res["message"]

    @patch("plugins.arm.arm_plugin.TCPManager")
    def test_start_fail_response(self, mock_pool_cls):
        mock_pool = MagicMock()
        mock_socket = MagicMock()
        mock_pool.get_connection.return_value = mock_socket
        mock_pool_cls.return_value = mock_pool

        mock_socket.recv.return_value = b'{"result": "fail"}\n'

        res = self.plugin.execute("goto", {"point": 0})

        assert res["status"] == "error"
        assert "机械臂启动回应异常" in res["message"]
        mock_pool.release_connection.assert_called_once()

    @patch("plugins.arm.arm_plugin.TCPManager")
    def test_plugin_lifecycle_methods(self, mock_pool_cls):
        mock_pool = MagicMock()
        mock_socket = MagicMock()
        mock_pool.get_connection.return_value = mock_socket
        mock_pool_cls.return_value = mock_pool

        mock_socket.recv.side_effect = [
            b'{"result": "start"}\n',
            b'{"result": "success"}\n'
        ]

        res_pause = self.plugin.pause()
        assert res_pause["status"] == "success"

    def test_capabilities(self):
        caps = self.plugin.get_capabilities()
        assert caps["plugin_type"] == "ArmPlugin"
        assert caps["plugin_name"] == "机械臂插件"
        assert len(caps["supported_actions"]) == 4
        actions = [a["action"] for a in caps["supported_actions"]]
        assert actions == ["goto", "pause", "goback", "status"]

    def test_execute_status(self):
        res = self.plugin.execute("status", {})
        assert res["status"] == "success"
        assert res["data"]["online"] is True

    @patch("plugins.arm.arm_plugin.TCPManager")
    def test_get_status_idle_does_not_connect_tcp(self, mock_pool_cls):
        # 核心断言：后台健康轮询 get_status / status 严禁主动发起 TCP 连接
        mock_pool = MagicMock()
        mock_pool_cls.return_value = mock_pool

        assert self.plugin.get_status() is True
        assert self.plugin.status() is True
        mock_pool.get_connection.assert_not_called()
        mock_pool.release_connection.assert_not_called()

