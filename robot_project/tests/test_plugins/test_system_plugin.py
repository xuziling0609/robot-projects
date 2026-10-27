from unittest.mock import MagicMock, patch, call
import pytest
from plugins.system.system_plugin import SystemPlugin

class TestSystemPlugin:
    def setup_method(self):
        self.plugin = SystemPlugin()

    def test_delay_action(self):
        with patch("plugins.system.system_plugin.time.sleep", return_value=None):
            result = self.plugin.execute(action="delay", params={"seconds": 1.5})
        assert result["status"] == "success"
        assert "1.5 秒完成" in result["message"]

    def test_unsupported_action(self):
        result = self.plugin.execute(action="invalid_sys_cmd", params={})
        assert result["status"] == "error"
        assert "不支持的系统动作" in result["message"]

    def test_restart_service_success(self):
        with patch.object(self.plugin, "_schedule_restart_service") as mock_sched:
            with patch("core.context_manager.ContextManager.get_robot_task", return_value={"status": "idle"}):
                result = self.plugin.execute(action="restart_service", params={"delay_s": 1.5})
                assert result["status"] == "success"
                assert result["data"]["target"] == "service"
                assert result["data"]["delay_s"] == 1.5
                mock_sched.assert_called_once_with(delay_s=1.5)

    def test_reboot_system_success(self):
        with patch.object(self.plugin, "_schedule_reboot_system") as mock_sched:
            with patch("core.context_manager.ContextManager.get_robot_task", return_value={"status": "idle"}):
                result = self.plugin.execute(action="reboot_system", params={"delay_s": 3.0})
                assert result["status"] == "success"
                assert result["data"]["target"] == "system"
                assert result["data"]["delay_s"] == 3.0
                mock_sched.assert_called_once_with(delay_s=3.0)

    def test_restart_service_safety_interlock_blocked(self):
        with patch.object(self.plugin, "_schedule_restart_service") as mock_sched:
            with patch("core.context_manager.ContextManager.get_robot_task", return_value={"status": "running", "task_id": "TASK_001"}):
                result = self.plugin.execute(action="restart_service", params={"force": False})
                assert result["status"] == "error"
                assert "拒绝" in result["message"]
                mock_sched.assert_not_called()

    def test_restart_service_safety_interlock_forced(self):
        with patch.object(self.plugin, "_schedule_restart_service") as mock_sched:
            with patch("core.context_manager.ContextManager.get_robot_task", return_value={"status": "running", "task_id": "TASK_001"}):
                result = self.plugin.execute(action="restart_service", params={"force": True})
                assert result["status"] == "success"
                mock_sched.assert_called_once()

    def test_reboot_system_safety_interlock_blocked(self):
        with patch.object(self.plugin, "_schedule_reboot_system") as mock_sched:
            with patch("core.context_manager.ContextManager.get_robot_task", return_value={"status": "paused", "task_id": "TASK_002"}):
                result = self.plugin.execute(action="reboot_system", params={"force": False})
                assert result["status"] == "error"
                assert "拒绝" in result["message"]
                mock_sched.assert_not_called()

    def test_restart_service_pdm_execv(self):
        with patch("plugins.system.system_plugin.subprocess.run", side_effect=Exception("not systemd")), \
             patch("plugins.system.system_plugin.os.execv") as mock_execv, \
             patch("plugins.system.system_plugin.time.sleep", return_value=None), \
             patch("threading.Thread") as mock_thread:
            def fake_init(target, daemon=None, name=None):
                mock_t = MagicMock()
                mock_t.start.side_effect = target
                return mock_t
            mock_thread.side_effect = fake_init
            self.plugin._schedule_restart_service(delay_s=0.01)
            mock_execv.assert_called_once()

    def test_get_capabilities(self):
        caps = self.plugin.get_capabilities()
        assert caps["plugin_type"] == "SystemPlugin"
        actions = [a["action"] for a in caps.get("supported_actions", [])]
        assert "delay" in actions
        assert "status" in actions
        assert "restart_service" in actions
        assert "reboot_system" in actions

    def test_pause_and_resume_delay(self):
        import threading
        import time

        res = []
        def run_delay():
            r = self.plugin.execute(action="delay", params={"seconds": 2.0})
            res.append(r)

        t = threading.Thread(target=run_delay)
        t.start()
        time.sleep(0.1)
        self.plugin.pause()
        t.join(timeout=2.0)

        assert len(res) == 1
        assert res[0]["status"] == "paused"

        self.plugin.resume()
        res2 = self.plugin.execute(action="delay", params={"seconds": 0.05})
        assert res2["status"] == "success"

    def test_system_plugin_task_engine_recovery(self):
        import time
        from core.task_manager import TaskManager

        mock_pm = MagicMock()
        mock_pm.get_plugin.return_value = self.plugin
        mock_pm.pause_all.side_effect = self.plugin.pause
        mock_pm.resume_all.side_effect = self.plugin.resume
        mock_config = MagicMock()
        mock_ack = MagicMock()

        engine = TaskManager(plugin_manager=mock_pm, config_loader=mock_config, response_callback=mock_ack)
        # 1. 先保存离线任务
        payload_save = {
            "msg_id": "SYS_TASK_SAVE_001",
            "cmd_type": "task",
            "action": "save",
            "task_id": "SYS_TASK_RECOVER_001",
            "task_name": "系统插件恢复测试",
            "steps": [
                {"step": 1, "plugin_type": "SystemPlugin", "action": "delay", "params": {"seconds": 0.3}}
            ]
        }
        engine._process_payload(payload_save)

        # 2. 触发执行离线任务
        payload_run = {
            "msg_id": "SYS_TASK_RUN_001",
            "cmd_type": "task",
            "action": "run",
            "task_id": "SYS_TASK_RECOVER_001"
        }
        engine.handle_task(payload_run)

        time.sleep(0.1)
        engine.handle_task({"msg_id": "PAUSE_001", "cmd_type": "task", "action": "pause"})
        time.sleep(0.15)
        assert engine.get_task_state() == "PAUSED"

        engine.handle_task({"msg_id": "RESUME_001", "cmd_type": "task", "action": "resume"})
        for _ in range(20):
            if engine.get_task_state() == "FINISH":
                break
            time.sleep(0.1)

        assert engine.get_task_state() == "FINISH"



