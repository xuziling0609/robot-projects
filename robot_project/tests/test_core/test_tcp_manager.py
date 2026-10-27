# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch, call
import socket
import threading
import time
import pytest
import logging
from core.tcp_manager import TCPManager, TCPPoolManager

logger = logging.getLogger(__name__)

class TestTCPManager:
    def setup_method(self):
        TCPManager._instance = None
        self.pool = TCPManager()

        # 启动本地 Mock TCP Server
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind(("127.0.0.1", 0))
        self.server_port = self.server_sock.getsockname()[1]
        self.server_sock.listen(10)
        self.server_running = True

        def server_accept():
            while self.server_running:
                try:
                    self.server_sock.settimeout(0.5)
                    client, _ = self.server_sock.accept()
                    client.settimeout(1.0)
                except socket.timeout:
                    continue
                except Exception as e:
                    break

        self.server_thread = threading.Thread(target=server_accept, daemon=True)
        self.server_thread.start()

    def teardown_method(self):
        self.pool.close_all()
        self.server_running = False
        try:
            self.server_sock.close()
        except Exception:
            pass

    def test_singleton(self):
        """验证单例唯一性与别名兼容"""
        pool2 = TCPManager()
        pool3 = TCPPoolManager()
        assert self.pool is pool2
        assert self.pool is pool3

    def test_get_and_reuse_connection(self):
        """验证同一 IP 和端口的连接复用"""
        sock1 = self.pool.get_connection("127.0.0.1", self.server_port, timeout=2.0)
        assert isinstance(sock1, socket.socket)

        # 再次获取相同目标应复用同一实例
        sock2 = self.pool.get_connection("127.0.0.1", self.server_port, timeout=2.0)
        assert sock1 is sock2

    def test_release_connection(self):
        """验证主动释放并关闭链路"""
        sock = self.pool.get_connection("127.0.0.1", self.server_port, timeout=2.0)
        assert self.pool.is_connected("127.0.0.1", self.server_port) is True

        self.pool.release_connection("127.0.0.1", self.server_port)
        assert self.pool.is_connected("127.0.0.1", self.server_port) is False
        assert f"127.0.0.1:{self.server_port}" not in self.pool.list_connections()

    def test_close_all(self):
        """验证一键关闭全部链路"""
        self.pool.get_connection("127.0.0.1", self.server_port, timeout=2.0)
        assert self.pool.get_pool_size() == 1

        self.pool.close_all()
        assert self.pool.get_pool_size() == 0

    def test_connection_refused_exception(self):
        """验证目标端口未监听时正确抛出异常"""
        unused_port = 59876
        with pytest.raises(Exception):
            self.pool.get_connection("127.0.0.1", unused_port, timeout=0.5)

    def test_is_socket_alive_detection(self):
        """验证存活检测算法的正确性"""
        sock = self.pool.get_connection("127.0.0.1", self.server_port, timeout=2.0)
        assert self.pool._is_socket_alive(sock)

        # 模拟 getsockopt 报告错误
        mock_sock = MagicMock()
        mock_sock.getsockopt.return_value = 1
        assert not self.pool._is_socket_alive(mock_sock)

    def test_socket_timeout_not_corrupted_by_alive_check(self):
        """
        核心防线验证：存活探测后，Socket 的 timeout 属性绝不能被篡改为 0.001s，
        必须严格恢复为调用方初始设定的原始超时时间 (如 2.5s)。
        """
        original_timeout = 2.5
        sock = self.pool.get_connection("127.0.0.1", self.server_port, timeout=original_timeout)
        assert sock.gettimeout() == original_timeout

        # 执行存活探测
        alive = self.pool._is_socket_alive(sock)
        assert alive is True

        # 核心断言：timeout 绝未被篡改为 0.001
        assert sock.gettimeout() == original_timeout

        # 再次通过 get_connection 复用时，超时时间依然保持
        sock_reused = self.pool.get_connection("127.0.0.1", self.server_port, timeout=original_timeout)
        assert sock_reused.gettimeout() == original_timeout

    def test_observability_apis(self):
        """验证可观测性自省 API"""
        assert self.pool.get_pool_size() == 0
        assert self.pool.list_connections() == []
        assert self.pool.is_connected("127.0.0.1", self.server_port) is False

        self.pool.get_connection("127.0.0.1", self.server_port, timeout=2.0)

        assert self.pool.get_pool_size() == 1
        assert self.pool.list_connections() == [f"127.0.0.1:{self.server_port}"]
        assert self.pool.is_connected("127.0.0.1", self.server_port) is True

    def test_concurrent_get_connections(self):
        """高并发建连测试：多线程同时请求连接，验证无死锁且正常合并复用"""
        sockets = []
        errors = []

        def worker():
            try:
                s = self.pool.get_connection("127.0.0.1", self.server_port, timeout=2.0)
                sockets.append(s)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"并发获取连接产生异常: {errors}"
        assert len(sockets) == 8
        # 所有线程拿到的应该是同一个 Socket 复用实例
        first = sockets[0]
        for s in sockets:
            assert s is first
