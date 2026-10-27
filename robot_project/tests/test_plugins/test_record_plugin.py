import os
import shutil
import tempfile
import time
from unittest.mock import MagicMock, patch
import pytest

from core.context_manager import ContextManager
from core.event_manager import TaskEvent
from plugins.record.record_plugin import RecordPlugin
from plugins.record.video_recorder import FFmpegResolver, MultiChannelRecorder, DualChannelRecorder
from plugins.record.seaweed_sync_worker import VideoSyncDatabase, SeaweedSyncWorker


class TestRecordPlugin:
    def setup_method(self):
        self.config = {
            "recording": {
                "segment_duration_sec": 60,
                "save_dir": "data/videos",
                "channels": {
                    "vis": {"label": "可见光通道 (vis)", "url": "rtsp://127.0.0.1:554/vis"},
                    "thm": {"label": "热成像通道 (thm)", "url": "rtsp://127.0.0.1:554/thm"},
                    "arm": {"label": "自定义机械臂 (arm)", "url": "rtsp://127.0.0.1:554/arm"}
                }
            },
            "server_sync": {
                "enabled": True,
                "delete_after_sync": True,
                "seaweedfs": {
                    "filer_url": "http://127.0.0.1:8888",
                    "base_dir": "test_surveillance"
                }
            }
        }
        self.plugin = RecordPlugin(config=self.config)

    def teardown_method(self):
        self.plugin.sync_worker.stop()
        self.plugin.recorder.stop_recording()

    def test_get_capabilities_dynamic_aliases(self):
        """核心验证：start_record 的 channel 选项自动读取 config 中的别名与自定义 label"""
        caps = self.plugin.get_capabilities()
        assert caps["plugin_type"] == "RecordPlugin"
        assert caps["plugin_name"] == "录像插件"

        actions = {a["action"]: a for a in caps["supported_actions"]}
        assert "start_record" in actions
        assert "stop_record" in actions
        assert "record_status" in actions
        assert "sync_control" in actions
        assert "status" in actions

        # 检查 stop_record 无参数
        stop_act = actions["stop_record"]
        assert stop_act["params"] == []

        # 检查 status 无参数与结构
        status_act = actions["status"]
        assert status_act["params"] == []
        assert status_act["scopes"] == ["config"]

        # 检查 start_record 的 channel 参数配置
        start_act = actions["start_record"]
        channel_param = next(p for p in start_act["params"] if p["name"] == "channel")
        assert channel_param["type"] == "string"
        assert channel_param["default"] == "all"

        options = channel_param["options"]
        option_map = {opt["value"]: opt["name"] for opt in options}

        # 验证动态生成的别名选项与其配置的 label
        assert option_map["all"] == "全部通道"
        assert option_map["vis"] == "可见光通道 (vis)"
        assert option_map["thm"] == "热成像通道 (thm)"
        assert option_map["arm"] == "自定义机械臂 (arm)"

    def test_record_actions_and_status(self):
        # 1. 查询状态
        status_res = self.plugin.execute("record_status", {})
        assert status_res["status"] == "success"
        assert "recording" in status_res["data"]
        assert "sync" in status_res["data"]
        assert status_res["data"]["recording"]["is_recording"] is False

        # 2. 停止录像 (验证无参调用，默认停止全部)
        with patch.object(self.plugin.recorder, "stop_recording") as mock_stop:
            mock_stop.return_value = {"status": "success", "message": "all stopped"}
            stop_res = self.plugin.execute("stop_record", {})
            assert stop_res["status"] == "success"
            mock_stop.assert_called_once_with()

        # 3. 开启录像
        with patch.object(self.plugin.recorder, "start_recording") as mock_start:
            mock_start.return_value = {"status": "success", "message": "started"}
            res = self.plugin.execute("start_record", {"channel": "vis", "task_id": "t_01"})
            assert res["status"] == "success"
            mock_start.assert_called_once_with(channels="vis", segment_duration=None, task_id="t_01")

    def test_status_action(self):
        """测试 status 动作与在线查询能力 (对齐 SystemPlugin 规范)"""
        # 1. 基础 status 动作查询
        res = self.plugin.execute("status")
        assert res["status"] == "success"
        assert res["message"] == "录像插件在线"
        assert res["data"]["online"] is True

        # 2. 忽略大小写
        res_upper = self.plugin.execute("STATUS", {})
        assert res_upper["status"] == "success"
        assert res_upper["data"]["online"] is True

        # 3. get_status 与 status 方法
        assert self.plugin.get_status() is True
        assert self.plugin.status() is True

    def test_task_id_resolution_from_msg_id(self):
        # 1. 模拟平台执行离线任务：msg_id 存在于 ContextManager 中
        ContextManager.update_robot_task({"task_id": "TASK_OFFLINE_01", "msg_id": "20260914-123000-001"})
        with patch.object(self.plugin.recorder, "start_recording") as mock_start:
            mock_start.return_value = {"status": "success"}
            self.plugin.execute("start_record", {})
            mock_start.assert_called_once()
            call_kwargs = mock_start.call_args[1]
            assert call_kwargs["task_id"] == "20260914-123000-001"
            assert call_kwargs["channels"] == "all"

        # 2. 模拟单能力调试：params 中带有 msg_id
        ContextManager.update_robot_task({"task_id": None, "msg_id": None})
        with patch.object(self.plugin.recorder, "start_recording") as mock_start:
            mock_start.return_value = {"status": "success"}
            self.plugin.execute("start_record", {"msg_id": "CMD_DEBUG_888", "channel": "arm"})
            call_kwargs = mock_start.call_args[1]
            assert call_kwargs["task_id"] == "CMD_DEBUG_888"
            assert call_kwargs["channels"] == "arm"

        # 3. 模拟含有特殊字符的 msg_id 安全过滤
        with patch.object(self.plugin.recorder, "start_recording") as mock_start:
            mock_start.return_value = {"status": "success"}
            self.plugin.execute("start_record", {"msg_id": "2026/09/14:12-00"})
            call_kwargs = mock_start.call_args[1]
            assert call_kwargs["task_id"] == "2026_09_14_12-00"

        # 4. 模拟无上下文时的本地单能力调试 (自动兜底 debug_ 前缀)
        with patch.object(self.plugin.recorder, "start_recording") as mock_start:
            mock_start.return_value = {"status": "success"}
            self.plugin.execute("start_record", {})
            call_kwargs = mock_start.call_args[1]
            assert call_kwargs["task_id"].startswith("debug_")

    def test_sync_control_action(self):
        # 暂停同步
        res_pause = self.plugin.execute("sync_control", {"control": "pause"})
        assert res_pause["status"] == "success"
        assert self.plugin.sync_worker._paused_by_event is True

        # 恢复同步
        res_resume = self.plugin.execute("sync_control", {"control": "resume"})
        assert res_resume["status"] == "success"
        assert self.plugin.sync_worker._paused_by_event is False

        # 非法控制命令返回错误
        res_invalid = self.plugin.execute("sync_control", {"control": "invalid_cmd"})
        assert res_invalid["status"] == "error"

    def test_state_change_sync_gate(self):
        # 模拟任务变更为 RUNNING -> 同步挂起让出带宽
        fake_event_running = {"state": "RUNNING"}
        self.plugin._on_state_changed(fake_event_running)
        assert self.plugin.sync_worker._paused_by_event is True

        # 模拟任务变更为 FINISHED -> 唤醒全速视频同步
        fake_event_finished = {"state": "FINISHED"}
        self.plugin._on_state_changed(fake_event_finished)
        assert self.plugin.sync_worker._paused_by_event is False

    def test_state_change_auto_stop_recording(self):
        """核心验证：任务完成、取消或失败时，若录像在运行，自动停止录像"""
        for term_state in ["FINISHED", "FINISH", "ABORTED", "FAILED"]:
            with patch.object(self.plugin.recorder, "get_status", return_value={"is_recording": True}), \
                 patch.object(self.plugin.recorder, "stop_recording") as mock_stop:
                self.plugin._on_state_changed({"state": term_state})
                mock_stop.assert_called_once()

        # 当未在录像时，不会多余调用 stop_recording
        with patch.object(self.plugin.recorder, "get_status", return_value={"is_recording": False}), \
             patch.object(self.plugin.recorder, "stop_recording") as mock_stop:
            self.plugin._on_state_changed({"state": "FINISHED"})
            mock_stop.assert_not_called()

    def test_state_change_with_task_event(self):
        """核心验证：接收真实 EventManager 广播的 TaskEvent 对象，不报 'TaskEvent' object has no attribute 'get'"""
        event_running = TaskEvent(
            event_type="global_state_changed",
            task_id="system",
            extra_data={"state": "RUNNING"}
        )
        self.plugin._on_state_changed(event_running)
        assert self.plugin.sync_worker._paused_by_event is True

        event_finished = TaskEvent(
            event_type="global_state_changed",
            task_id="system",
            extra_data={"state": "FINISHED"}
        )
        self.plugin._on_state_changed(event_finished)
        assert self.plugin.sync_worker._paused_by_event is False

    def test_abort_stops_recording(self):
        """核心验证：收到 abort 信号时停止所有录像"""
        with patch.object(self.plugin.recorder, "stop_recording") as mock_stop:
            self.plugin.abort()
            mock_stop.assert_called_once()

    def test_unsupported_action(self):
        res = self.plugin.execute("invalid_action", {})
        assert res["status"] == "error"


class TestFFmpegResolver:
    def test_custom_path_resolution(self, tmp_path):
        fake_ffmpeg = tmp_path / "my_ffmpeg"
        fake_ffmpeg.write_text("#!/bin/sh\nexit 0")
        os.chmod(str(fake_ffmpeg), 0o644)

        resolved = FFmpegResolver.get_binary_path(str(fake_ffmpeg))
        assert resolved == str(fake_ffmpeg)
        # 验证自动赋予 755 执行权限
        assert os.access(resolved, os.X_OK)

    def test_missing_binary_fallback(self):
        # 传入不存在的自定义路径
        res = FFmpegResolver.get_binary_path("/nonexistent/path/to/ffmpeg")
        # 若环境没有全局 ffmpeg，则返回 None 并输出友好日志
        assert res is None or os.path.exists(res)


class TestVideoSyncDatabase:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_video_sync.db")
        self.db = VideoSyncDatabase(db_path=self.db_path)

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_crud_and_purge(self):
        record = {
            "task_id": "task_101",
            "channel": "vis",
            "filename": "vis_0001.mp4",
            "file_path": "/fake/vis_0001.mp4",
            "file_size": 1048576,
            "duration_sec": 60.0,
            "checksum_md5": "abc123md5",
            "created_at": int(time.time())
        }
        # 1. 注册新分片
        self.db.register_segment(record)

        # 2. 查询待同步列表
        pending = self.db.get_pending_records(limit=10)
        assert len(pending) == 1
        assert pending[0]["filename"] == "vis_0001.mp4"
        assert pending[0]["status"] == "PENDING"

        # 3. 标记同步并上云即焚 (local_deleted=1, file_path=NULL)
        rec_id = pending[0]["id"]
        self.db.mark_synced_and_purge(rec_id, remote_url="/robot/task_101/vis_0001.mp4")

        # 4. 再次查询待同步列表应为空
        pending_after = self.db.get_pending_records(limit=10)
        assert len(pending_after) == 0

        # 5. 检查任务是否全部同步完毕
        assert self.db.is_task_all_synced("task_101") is True

        # 6. 统计数据
        stats = self.db.get_stats()
        assert stats["synced_count"] == 1
        assert stats["pending_count"] == 0

    def test_reset_failed_records(self):
        record = {
            "task_id": "task_fail_1",
            "channel": "vis",
            "filename": "fail_0001.mp4",
            "file_path": "/fake/fail_0001.mp4",
            "file_size": 1024,
            "duration_sec": 60.0,
            "created_at": int(time.time())
        }
        self.db.register_segment(record)
        pending = self.db.get_pending_records()
        rec_id = pending[0]["id"]

        # 模拟上传失败多次达到限制
        for _ in range(3):
            self.db.mark_failed(rec_id)
            
        # 达到限制后，普通的 get_pending_records 不会再返回它
        assert len(self.db.get_pending_records(max_retries=3)) == 0
        
        # 调用重置机制
        self.db.reset_failed_records()
        
        # 重置后应该重新被查询出来补传
        pending_after = self.db.get_pending_records(max_retries=3)
        assert len(pending_after) == 1
        assert pending_after[0]["retry_count"] == 0
        assert pending_after[0]["status"] == "FAILED"


class TestSeaweedSyncWorker:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_sync.db")
        self.worker = SeaweedSyncWorker(
            config={
                "enabled": True,
                "delete_after_sync": True,
                "seaweedfs": {
                    "filer_url": "http://127.0.0.1:8888",
                    "base_dir": "robot_test"
                }
            },
            check_idle_fn=lambda: True
        )
        self.worker.db = VideoSyncDatabase(db_path=self.db_path)

    def teardown_method(self):
        self.worker.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch.object(VideoSyncDatabase, "reset_failed_records")
    def test_start_resets_failed_records(self, mock_reset):
        """验证 worker 启动时自动触发失败记录的重置 (补传)"""
        self.worker.start()
        mock_reset.assert_called_once()
        self.worker.stop()

    @patch("requests.head")
    def test_head_check_exists(self, mock_head):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Length": "1000"}
        mock_head.return_value = mock_resp

        # 文件大小匹配 -> 触发秒传
        assert self.worker._head_check_exists("/test/video.mp4", 1000) is True
        # 文件大小不匹配 -> 不触发秒传
        assert self.worker._head_check_exists("/test/video.mp4", 2000) is False

    @patch("requests.put")
    @patch("requests.head")
    def test_upload_and_immediate_local_delete(self, mock_head, mock_put):
        # 创建真实物理测试视频文件
        task_dir = os.path.join(self.temp_dir, "task_202")
        os.makedirs(task_dir, exist_ok=True)
        video_file = os.path.join(task_dir, "vis_test.mp4")
        with open(video_file, "wb") as f:
            f.write(b"0" * 1024)

        # 同时生成录制过程日志文件 (.ffmpeg_vis.log)
        log_file = os.path.join(task_dir, ".ffmpeg_vis.log")
        with open(log_file, "w") as f:
            f.write("ffmpeg log...")

        record = {
            "task_id": "task_202",
            "channel": "vis",
            "filename": "vis_test.mp4",
            "file_path": video_file,
            "file_size": 1024,
            "checksum_md5": "testmd5"
        }
        self.worker.db.register_segment(record)
        rec_in_db = self.worker.db.get_pending_records()[0]

        # 模拟 HEAD 首次不存在，PUT 返回 201 成功，PUT 之后 HEAD 确认存在
        mock_head_not_exist = MagicMock(status_code=404)
        mock_head_exist = MagicMock(status_code=200, headers={"Content-Length": "1024"})
        mock_head.side_effect = [mock_head_not_exist, mock_head_exist]

        mock_put.return_value = MagicMock(status_code=201)

        success = self.worker._upload_file(rec_in_db)
        assert success is True

        # 核心验证 1：本地实体视频文件已被立刻安全删除 (上云即焚，零积压)
        assert not os.path.exists(video_file)

        # 核心验证 2：录制生成的日志文件已被彻底清理
        assert not os.path.exists(log_file)

        # 核心验证 3：任务目录 task_id 文件夹已彻底被清理移除
        assert not os.path.exists(task_dir)

        # 核心验证：SQLite 数据库状态已变更为 SYNCED
        stats = self.worker.db.get_stats()
        assert stats["synced_count"] == 1
        assert stats["pending_count"] == 0


class TestMultiChannelRecorderAliasResolution:
    def test_alias_mapping(self):
        # 验证结构化 channels 别名映射与 label 解析
        recorder = MultiChannelRecorder(
            config={
                "channels": {
                    "vis": {
                        "label": "可见光通道 (vis)",
                        "url": "rtsp://test_server:554/vis"
                    },
                    "thm": {
                        "label": "热成像通道 (thm)",
                        "url": "rtsp://test_server:554/thm"
                    },
                    "arm": {
                        "label": "机械臂相机 (arm)",
                        "url": "rtsp://test_server:554/arm"
                    },
                    "rear": {
                        # 未显式配置 label 时测试兜底
                        "url": "rtsp://test_server:554/rear"
                    }
                }
            }
        )
        assert recorder.get_configured_aliases() == ["vis", "thm", "arm", "rear"]
        assert recorder._resolve_target_aliases("all") == ["vis", "thm", "arm", "rear"]
        assert recorder._resolve_target_aliases("vis") == ["vis"]
        assert recorder._resolve_target_aliases(1) == ["vis"]
        assert recorder._resolve_target_aliases("arm") == ["arm"]
        assert recorder._resolve_target_aliases(3) == ["arm"]

        # 验证 label 读取及未配置时的兜底
        assert recorder.get_channel_label("vis") == "可见光通道 (vis)"
        assert recorder.get_channel_label("arm") == "机械臂相机 (arm)"
        assert recorder.get_channel_label("rear") == "rear 通道"
        assert recorder.get_channel_label("unknown") == "unknown 通道"
