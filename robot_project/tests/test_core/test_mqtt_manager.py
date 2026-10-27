from unittest.mock import MagicMock, patch, call
import json
import os
import time
import pytest
from core.mqtt_manager import MQTTManager, DiskQueue


class TestMQTTManager:
    def setup_method(self):
        MQTTManager._instance = None
        self.robot_id = "test_robot_01"
        self.mqtt_cli = MQTTManager(
            robot_id=self.robot_id,
            broker_ip="127.0.0.1",
            port=1883
        )
        self.mqtt_cli._is_running = False
        self.mqtt_cli.client = MagicMock()
        # 清理由于持久化引起的脏数据
        self.mqtt_cli._offline_disk_queue.clear()

    def teardown_method(self):
        if hasattr(self, "mqtt_cli"):
            self.mqtt_cli.stop(timeout=1.0)
        MQTTManager._instance = None

    def test_topic_formatting(self):
        """测试 5 大 Topic 命名空间规约格式"""
        assert self.mqtt_cli.topic_cmd_down == "/edge/gateway/test_robot_01/cmd/down"
        assert self.mqtt_cli.topic_response_up == "/edge/gateway/test_robot_01/response/up"
        assert self.mqtt_cli.topic_status_up == "/edge/gateway/test_robot_01/status/up"
        assert self.mqtt_cli.topic_alarm_up == "/edge/gateway/test_robot_01/alarm/up"
        assert self.mqtt_cli.topic_caps_up == "/edge/gateway/test_robot_01/capability/up"

    def test_publish_response(self):
        """测试正常连接状态下向云端发送 ACK"""
        self.mqtt_cli.client.is_connected.return_value = True
        res_mock = MagicMock()
        res_mock.rc = 0
        self.mqtt_cli.client.publish.return_value = res_mock
        self.mqtt_cli.publish_response(
            msg_id="20260728-092443-471-250",
            reply_type="ACK_EXECUTE",
            code=0,
            message="OK",
            data={"test": 123}
        )

        self.mqtt_cli.client.publish.assert_called_once()
        args, kwargs = self.mqtt_cli.client.publish.call_args
        topic = args[0]
        payload = json.loads(args[1])
        assert topic == "/edge/gateway/test_robot_01/response/up"
        assert payload["msg_id"] == "20260728-092443-471-250"
        assert payload["robot_id"] == "test_robot_01"
        assert payload["reply_type"] == "ACK_EXECUTE"
        assert payload["code"] == 0

    def test_offline_response_caching_and_retransmission(self):
        """测试断网/未连接时 ACK 进入离线缓存队列，网络恢复后以 0.5s 频率自动补发"""
        # 1. 模拟网络未连接
        self.mqtt_cli.client.is_connected.return_value = False
        self.mqtt_cli.publish_response(
            msg_id="MSG_OFFLINE_001",
            reply_type="ACK_PROGRESS",
            code=0,
            message="离线测试"
        )

        # 校验：已转入离线队列积压 >= 1 条
        assert self.mqtt_cli._offline_disk_queue.qsize() >= 1

        # 2. 模拟网络恢复正常，开启补发守护
        self.mqtt_cli.client.is_connected.return_value = True
        res_mock = MagicMock()
        res_mock.rc = 0
        self.mqtt_cli.client.publish.return_value = res_mock

        self.mqtt_cli._is_running = True
        
        # 3. 直接同步触发一次单步补发逻辑，消灭由于 time.sleep 带来的异步不确定性 (Flaky Test)
        self.mqtt_cli._retransmit_once()
        
        self.mqtt_cli._is_running = False

        # 校验：重传成功，缓存队列清空
        assert self.mqtt_cli._offline_disk_queue.qsize() == 0
        self.mqtt_cli.client.publish.assert_called_once()
        args, _ = self.mqtt_cli.client.publish.call_args
        payload = json.loads(args[1])
        assert payload["msg_id"] == "MSG_OFFLINE_001"

    def test_publish_alarm(self):
        """测试正常连接状态下上报告警"""
        self.mqtt_cli.client.is_connected.return_value = True
        res_mock = MagicMock()
        res_mock.rc = 0
        self.mqtt_cli.client.publish.return_value = res_mock

        self.mqtt_cli.publish_alarm(
            msg_id="20260728-092443-471-250",
            level="error",
            code=5001,
            message="开门机 [192.168.1.100] 状态轮询超时 (连续 3 次网络错误)",
            data={"plugin_type": "DoorPlugin", "ip": "192.168.1.100"}
        )

        self.mqtt_cli.client.publish.assert_called_once()
        args, kwargs = self.mqtt_cli.client.publish.call_args
        payload = json.loads(args[1])
        assert payload["msg_id"] == "20260728-092443-471-250"
        assert payload["robot_id"] == "test_robot_01"
        assert payload["level"] == "error"
        assert payload["code"] == 5001

    def test_normalized_alarm_parameters(self):
        """测试多态历史入参归一化清洗兼容"""
        self.mqtt_cli.client.is_connected.return_value = True
        res_mock = MagicMock()
        res_mock.rc = 0
        self.mqtt_cli.client.publish.return_value = res_mock

        # 使用历史兼容参数名：error_code, description, params, alarm_id
        self.mqtt_cli.publish_alarm(
            level="WARN",
            error_code=4002,
            description="兼容告警描述",
            params={"custom_key": "val"},
            alarm_id="ALARM_COMPAT_001",
            source_plugin="CameraPlugin"
        )

        args, kwargs = self.mqtt_cli.client.publish.call_args
        payload = json.loads(args[1])
        assert payload["level"] == "warning"  # 大写 WARN 自动规范化为 warning
        assert payload["code"] == 4002
        assert payload["message"] == "兼容告警描述"
        assert payload["msg_id"] == "ALARM_COMPAT_001"
        assert payload["data"]["plugin_type"] == "CameraPlugin"
        assert payload["data"]["custom_key"] == "val"

    def test_publish_status(self):
        """测试发布整机状态"""
        self.mqtt_cli.client.is_connected.return_value = True
        res_mock = MagicMock()
        res_mock.rc = 0
        self.mqtt_cli.client.publish.return_value = res_mock

        self.mqtt_cli.publish_status(
            msg_id="20260728-092443-471-250",
            task_state="RUNNING",
            robot_status={
                "plugins": {
                    "NavPlugin": {"mode": "AUTO"}
                }
            },
            force=True
        )

        self.mqtt_cli.client.publish.assert_called_once()
        args, kwargs = self.mqtt_cli.client.publish.call_args
        topic = args[0]
        payload = json.loads(args[1])
        assert topic == "/edge/gateway/test_robot_01/status/up"
        assert payload["robot_id"] == "test_robot_01"
        assert payload["task_state"] == "RUNNING"
        assert "NavPlugin" in payload["robot_status"]["plugins"]

    def test_on_message_dispatch(self):
        """测试收到下行报文后自动发送 ACK_RECEIVE 并向线程池派发"""
        mock_callback = MagicMock()
        self.mqtt_cli.register_task_callback(mock_callback)
        self.mqtt_cli.publish_response = MagicMock()

        msg = MagicMock()
        msg.topic = "/edge/gateway/test_robot_01/cmd/down"
        msg.payload = json.dumps({"msg_id": "20260728-092443-471-250", "cmd_type": "action"}).encode('utf-8')

        with patch.object(self.mqtt_cli._executor, "submit") as mock_submit:
            self.mqtt_cli._on_message(None, None, msg)
            mock_submit.assert_called_once()
            self.mqtt_cli.publish_response.assert_called_once()
            args, kwargs = self.mqtt_cli.publish_response.call_args
            assert kwargs.get("reply_type") == "ACK_RECEIVE"

    def test_disk_queue_wal_and_fifo(self, tmp_path):
        """测试 DiskQueue WAL 模式、FIFO 顺序与 CRUD 完整流程"""
        custom_db = str(tmp_path / "test_wal_dq.db")
        dq = DiskQueue(db_path=custom_db, max_size=100)

        # 验证 WAL 模式已生效
        cursor = dq.conn.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        assert mode.upper() == "WAL"

        # 写入 3 条数据
        dq.put("/topic/1", {"step": 1}, qos=1)
        dq.put("/topic/2", {"step": 2}, qos=0)
        dq.put("/topic/3", {"step": 3}, qos=1)
        assert dq.qsize() == 3

        # 先进先出顺序验证
        item1 = dq.get()
        assert item1["topic"] == "/topic/1"
        assert item1["payload"]["step"] == 1
        dq.delete(item1["id"])
        assert dq.qsize() == 2

        item2 = dq.get()
        assert item2["topic"] == "/topic/2"
        assert item2["payload"]["step"] == 2
        dq.delete(item2["id"])

        dq.clear()
        assert dq.qsize() == 0
        dq.close()

    def test_disk_queue_max_size_overflow(self, tmp_path):
        """测试 DiskQueue 队列达到上限自动淘汰最旧消息"""
        custom_db = str(tmp_path / "test_overflow_dq.db")
        dq = DiskQueue(db_path=custom_db, max_size=3)

        dq.put("/topic/1", {"msg": 1})
        dq.put("/topic/2", {"msg": 2})
        dq.put("/topic/3", {"msg": 3})
        assert dq.qsize() == 3

        # 写入第 4 条，应淘汰第 1 条，保持总数为 3
        dq.put("/topic/4", {"msg": 4})
        assert dq.qsize() == 3

        item = dq.get()
        assert item["payload"]["msg"] == 2  # msg: 1 已被淘汰，现在头部是 msg: 2
        dq.close()

    def test_observability_and_connection_state(self):
        """测试连接状态自省与统计指标接口"""
        self.mqtt_cli.client.is_connected.return_value = True
        assert self.mqtt_cli.is_connected() is True

        stats = self.mqtt_cli.get_stats()
        assert "is_connected" in stats
        assert stats["is_connected"] is True
        assert "offline_disk_queue_size" in stats
        assert "messages_received" in stats

    def test_stop_graceful_shutdown(self):
        """测试 stop 毫秒级优雅平滑停止与资源回收"""
        start_time = time.time()
        self.mqtt_cli.stop(timeout=1.0)
        duration = time.time() - start_time
        assert duration < 1.0  # 远小于 1 秒退出
        assert not self.mqtt_cli._is_running
