from unittest.mock import MagicMock, patch, call
import socket
import pytest
from utils.net_utils import get_local_ip

class TestNetUtils:
    def test_get_local_ip_normal(self):
        ip = get_local_ip()
        assert isinstance(ip, str)
        assert len(ip.split(".")) > 3

    @patch("socket.socket")
    def test_get_local_ip_udp_success(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_sock.getsockname.return_value = ("192.168.1.100", 54321)
        mock_socket_cls.return_value = mock_sock

        ip = get_local_ip("192.168.1.1")
        assert ip == "192.168.1.100"
        mock_sock.connect.assert_called_once_with(("192.168.1.1", 80))
        mock_sock.close.assert_called_once()

    @patch("socket.socket")
    @patch("socket.gethostbyname")
    def test_get_local_ip_fallback_hostname(self, mock_gethostbyname, mock_socket_cls):
        mock_socket_cls.side_effect = Exception("UDP failed")
        mock_gethostbyname.return_value = "10.0.0.50"

        ip = get_local_ip()
        assert ip == "10.0.0.50"

    @patch("socket.socket")
    @patch("socket.gethostbyname")
    def test_get_local_ip_double_fallback_loopback(self, mock_gethostbyname, mock_socket_cls):
        mock_socket_cls.side_effect = Exception("UDP failed")
        mock_gethostbyname.side_effect = Exception("DNS failed")

        ip = get_local_ip()
        assert ip == "127.0.0.1"

