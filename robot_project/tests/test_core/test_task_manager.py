import os
import json
import shutil
import time
import threading
import pytest
from unittest.mock import MagicMock, patch, call
from core.task_manager import TaskManager

class TestTaskManager:
    def setup_method(self):
        # 单元测试不擦除/删除 data/ 下的任何目录与预设文件
        pass

    def teardown_method(self):
        # 清理具体的测试用中间生成文件（不删整体 data/ 目录）
        test_wf = "data/tasks/WF_TEST_DELETE.json"
        if os.path.exists(test_wf):
            try:
                os.remove(test_wf)
            except Exception as e:
                logger.error('操作引发异常:', exc_info=True)
                pass

    def test_single_step_execution_with_ack(self):
        mock_pm = MagicMock()
        mock_plugin = MagicMock()
        mock_plugin.execute.return_value = {"status": "success", "message": "开门成功"}
        mock_pm.get_plugin.return_value = mock_plugin

        mock_config = MagicMock()
        mock_ack = MagicMock()

        engine = TaskManager(plugin_manager=mock_pm, config_loader=mock_config, response_callback=mock_ack)
        payload = {
            "msg_id": "CMD_DOOR_001",
            "cmd_type": "action",
            "plugin_type": "DoorPlugin",
            "action": "open",
            "params": {"ips": ["192.168.1.100"]}
        }

        engine._process_payload(payload)

        import time; time.sleep(0.5)
        mock_pm.get_plugin.assert_called_once_with("DoorPlugin")
        mock_plugin.execute.assert_called_once_with(action="open", params={"ips": ["192.168.1.100"]})
        
        import time; time.sleep(0.5)
        mock_ack.assert_called_once()
        args, kwargs = mock_ack.call_args
        assert kwargs.get("msg_id") == "CMD_DOOR_001"
        assert kwargs.get("reply_type") == "ACK_EXECUTE"
        assert kwargs.get("code") == 0

    def test_direct_dynamic_steps_rejected(self):
        """测试禁止直接透传 steps 执行动态任务链，必须先保存再执行"""
        mock_pm = MagicMock()
        mock_config = MagicMock()
        mock_ack = MagicMock()

        engine = TaskManager(plugin_manager=mock_pm, config_loader=mock_config, response_callback=mock_ack)
        payload = {
            "msg_id": "TASK_MULTI_003",
            "cmd_type": "task",
            "task_name": "巡检测试",
            "steps": [
                {"step": 1, "plugin_type": "DoorPlugin", "action": "open", "params": {"ips": ["192.168.1.100"]}},
                {"step": 2, "plugin_type": "ElevatorPlugin", "action": "goToFloor", "params": {"addr": 1, "floor": 3}}
            ]
        }

        engine._process_payload(payload)

        mock_ack.assert_called_once()
        args, kwargs = mock_ack.call_args
        assert kwargs.get("reply_type") == "ACK_EXECUTE"
        assert kwargs.get("code") == 4000
        assert "不支持直接下发动态任务链执行" in kwargs.get("message")

    def test_task_execution(self):
        """测试按顺序调度执行 plugin/component 步骤"""
        mock_pm = MagicMock()
        mock_plugin = MagicMock()
        mock_pm.get_plugin.return_value = mock_plugin
        mock_plugin.execute.return_value = {"status": "success", "message": "OK"}
        
        mock_config = MagicMock()
        mock_config.get.return_value = {
            "TASK_PASS_DOOR": [
                {"step": 1, "plugin_type": "DoorPlugin", "action": "open", "params": {}},
                {"step": 2, "plugin_type": "DoorPlugin", "action": "close", "params": {}}
            ]
        }
        mock_ack = MagicMock()

        engine = TaskManager(plugin_manager=mock_pm, config_loader=mock_config, response_callback=mock_ack)
        payload = {
            "msg_id": "MSG_002",
            "cmd_type": "task",
            "task_id": "TASK_PASS_DOOR"
        }

        engine._process_payload(payload)

        import time; time.sleep(0.5)
        assert mock_pm.get_plugin.call_count == 2
        assert mock_ack.call_args[1].get("reply_type") == "ACK_EXECUTE"
        assert mock_ack.call_args[1].get("code") == 0

    def test_offline_task_persistence(self):
        """测试下发带 steps 的离线任务，自动原子落盘保存至 data/tasks/ 并可成功调度执行"""
        mock_pm = MagicMock()
        mock_plugin = MagicMock()
        mock_plugin.execute.return_value = {"status": "success"}
        mock_pm.get_plugin.return_value = mock_plugin

        mock_config = MagicMock()
        mock_config.get.return_value = {}
        mock_ack = MagicMock()

        engine = TaskManager(plugin_manager=mock_pm, config_loader=mock_config, response_callback=mock_ack)
        
        payload_save = {
            "msg_id": "MSG_SAVE_01",
            "cmd_type": "task",
            "action": "save",
            "task_id": "TASK_OFFLINE_TEST",
            "task_name": "离线测试剧本",
            "steps": [
                {"step": 1, "plugin_type": "DoorPlugin", "action": "open", "params": {"ips": ["192.168.1.100"]}}
            ]
        }
        engine._process_payload(payload_save)

        saved_file = os.path.join(engine.storage_manager.storage_dir, "TASK_OFFLINE_TEST.json")
        assert os.path.exists(saved_file)
        with open(saved_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["task_id"] == "TASK_OFFLINE_TEST"
            assert len(data["steps"]) == 1

        engine2 = TaskManager(plugin_manager=mock_pm, config_loader=mock_config, response_callback=mock_ack)
        payload_exec = {
            "msg_id": "MSG_RUN_01",
            "cmd_type": "task",
            "task_id": "TASK_OFFLINE_TEST"
        }
        engine2._process_payload(payload_exec)
        import time; time.sleep(0.5)
        assert mock_plugin.execute.call_count == 1

    def test_task_delete_list_clear_actions(self):
        """测试统一使用 cmd_type: task 模式下的 delete, list, clear 操作"""
        mock_pm = MagicMock()
        mock_config = MagicMock()
        mock_config.get.return_value = {}
        mock_ack = MagicMock()

        engine = TaskManager(plugin_manager=mock_pm, config_loader=mock_config, response_callback=mock_ack)

        # 1. 创建测试任务
        test_file = os.path.join(engine.storage_manager.storage_dir, "WF_TEST_DELETE.json")
        engine.storage_manager.save_task_to_disk("WF_TEST_DELETE", [{"step": 1, "plugin_type": "DoorPlugin", "action": "open"}])
        assert os.path.exists(test_file)

        # 2. list 测试
        engine._process_payload({"msg_id": "MSG_LIST", "cmd_type": "task", "action": "list"})
        import time; time.sleep(0.5)
        mock_ack.assert_called_once()
        args, kwargs = mock_ack.call_args
        assert kwargs["code"] == 0
        assert kwargs["data"]["total_count"] >= 1

        # 3. delete 测试
        mock_ack.reset_mock()
        engine._process_payload({"msg_id": "MSG_DEL", "cmd_type": "task", "action": "delete", "task_id": "WF_TEST_DELETE"})
        import time; time.sleep(0.5)
        mock_ack.assert_called_once()
        assert mock_ack.call_args[1]["code"] == 0
        assert not os.path.exists(test_file)

        # 4. clear 测试
        engine.storage_manager.save_task_to_disk("WF_A", [{"step": 1, "plugin_type": "DoorPlugin", "action": "open"}])
        engine.storage_manager.save_task_to_disk("WF_B", [{"step": 1, "plugin_type": "DoorPlugin", "action": "open"}])
        mock_ack.reset_mock()
        engine._process_payload({"msg_id": "MSG_CLEAR", "cmd_type": "task", "action": "clear"})
        import time; time.sleep(0.5)
        mock_ack.assert_called_once()
        assert mock_ack.call_args[1]["code"] == 0
        assert mock_ack.call_args[1]["data"]["cleared_count"] >= 2

    def test_task_pause_cancel_actions(self):
        """测试使用控制类指令 action 改变引擎状态"""
        mock_pm = MagicMock()
        mock_config = MagicMock()
        mock_ack = MagicMock()

        engine = TaskManager(plugin_manager=mock_pm, config_loader=mock_config, response_callback=mock_ack)
        engine.task_state = "RUNNING"

        # 1. pause 测试
        engine._process_payload({"msg_id": "20260728-092443-471-250", "cmd_type": "task", "action": "pause", "task_id": "WF_PATROL_F3_01"})
        import time; time.sleep(0.5)
        mock_ack.assert_called_once()
        assert mock_ack.call_args[1]["code"] == 0
        assert engine.get_task_state() == "PAUSED"

        # 2. resume 测试
        mock_ack.reset_mock()
        engine._process_payload({"msg_id": "20260728-092443-471-250", "cmd_type": "task", "action": "resume", "task_id": "WF_PATROL_F3_01"})
        import time; time.sleep(0.5)
        mock_ack.assert_called_once()
        assert mock_ack.call_args[1]["code"] == 0
        assert engine.get_task_state() == "RUNNING"

        # 3. abort 测试
        mock_ack.reset_mock()
        engine._process_payload({"msg_id": "20260728-092443-471-250", "cmd_type": "task", "action": "abort", "task_id": "WF_PATROL_F3_01"})
        import time; time.sleep(0.5)
        mock_ack.assert_called_once()
        assert mock_ack.call_args[1]["code"] == 0
        assert engine.get_task_state() == "ABORTED"

    def test_task_cmd_type_pause_resume_cancel(self):
        """测试动态任务链 (cmd_type=task) 运行中下发 pause, resume 与 abort 动作及状态切换"""
        mock_pm = MagicMock()
        mock_config = MagicMock()
        mock_ack = MagicMock()

        engine = TaskManager(plugin_manager=mock_pm, config_loader=mock_config, response_callback=mock_ack)
        engine.task_state = "RUNNING"

        # 1. pause 测试 (cmd_type=task)
        engine._process_payload({"msg_id": "MSG_TASK_P", "cmd_type": "task", "task_name": "动态过门任务", "action": "pause"})
        import time; time.sleep(0.5)
        mock_ack.assert_called_once()
        assert mock_ack.call_args[1]["code"] == 0
        assert engine.get_task_state() == "PAUSED"

        # 2. resume 测试 (cmd_type=task)
        mock_ack.reset_mock()
        engine._process_payload({"msg_id": "MSG_TASK_R", "cmd_type": "task", "task_name": "动态过门任务", "action": "resume"})
        import time; time.sleep(0.5)
        mock_ack.assert_called_once()
        assert mock_ack.call_args[1]["code"] == 0
        assert engine.get_task_state() == "RUNNING"

        # 3. abort 测试 (cmd_type=task)
        mock_ack.reset_mock()
        engine._process_payload({"msg_id": "MSG_TASK_C", "cmd_type": "task", "task_name": "动态过门任务", "action": "abort"})
        import time; time.sleep(0.5)
        mock_ack.assert_called_once()
        assert mock_ack.call_args[1]["code"] == 0
        assert engine.get_task_state() == "ABORTED"

    def test_resume_without_paused_task_ignored(self):
        """测试在未处于 PAUSED 状态下下发 resume，会被直接忽略并返回 '当前没有可恢复的任务'"""
        mock_pm = MagicMock()
        mock_config = MagicMock()
        mock_ack = MagicMock()

        engine = TaskManager(plugin_manager=mock_pm, config_loader=mock_config, response_callback=mock_ack)

        # 初始 IDLE 状态下下发 resume
        engine._process_payload({"msg_id": "MSG_RESUME_IDLE", "cmd_type": "task", "action": "resume"})
        import time; time.sleep(0.5)
        mock_ack.assert_called_once()
        assert mock_ack.call_args[1]["code"] == 4000
        assert mock_ack.call_args[1]["message"] == "当前没有可恢复的任务"
        assert engine.get_task_state() == "IDLE"

    def test_abort_without_active_task_ignored(self):
        """测试在未处于 RUNNING/PAUSED 状态下下发 abort/cancel，会被直接忽略并返回 '当前没有可取消的任务'"""
        mock_pm = MagicMock()
        mock_config = MagicMock()
        mock_ack = MagicMock()

        engine = TaskManager(plugin_manager=mock_pm, config_loader=mock_config, response_callback=mock_ack)

        # 初始 IDLE 状态下下发 abort
        engine._process_payload({"msg_id": "MSG_ABORT_IDLE", "cmd_type": "task", "action": "abort"})
        import time; time.sleep(0.5)
        mock_ack.assert_called_once()
        assert mock_ack.call_args[1]["code"] == 4000
        assert mock_ack.call_args[1]["message"] == "当前没有可取消的任务"
        assert engine.get_task_state() == "IDLE"

    def test_pause_in_middle_and_resume_recovery(self):
        """测试在子任务执行中途下发 pause，任务进入挂起，下发 resume 后自动无缝恢复并执行完成"""
        import threading
        import time

        mock_pm = MagicMock()
        mock_plugin = MagicMock()

        call_count = 0
        def side_effect_execute(action, params):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # 模拟第一次执行时被 pause 打断，返回 error
                engine.task_state = "PAUSED"
                return {"status": "error", "message": "任务被打断暂停"}
            else:
                # 恢复后的重新尝试，执行成功
                return {"status": "success", "message": "开门成功"}

        mock_plugin.execute.side_effect = side_effect_execute
        mock_pm.get_plugin.return_value = mock_plugin

        mock_config = MagicMock()
        mock_ack = MagicMock()

        engine = TaskManager(plugin_manager=mock_pm, config_loader=mock_config, response_callback=mock_ack)
        payload_save = {
            "msg_id": "TASK_SAVE_REC_001",
            "cmd_type": "task",
            "action": "save",
            "task_id": "TASK_RECOVER_001",
            "task_name": "恢复测试",
            "steps": [
                {"step": 1, "plugin_type": "DoorPlugin", "action": "open", "params": {"ips": ["192.168.1.100"]}}
            ]
        }
        engine._process_payload(payload_save)

        payload_run = {
            "msg_id": "TASK_RECOVER_001",
            "cmd_type": "task",
            "action": "run",
            "task_id": "TASK_RECOVER_001"
        }

        # 后台多线程启动任务
        t = threading.Thread(target=engine._process_payload, args=(payload_run,))
        t.start()

        # 等待 0.2s 确保任务执行进入 pause 挂起状态
        time.sleep(0.2)
        assert engine.get_task_state() == "PAUSED"

        # 下发 resume 指令
        engine._process_payload({"msg_id": "RESUME_001", "cmd_type": "task", "action": "resume"})
        t.join(timeout=3.0)

        # 校验：任务最终成功完成，execute 被调用了 2 次 (第一次被打断，第二次成功)
        import time; time.sleep(0.5)
        assert engine.get_task_state() == "FINISH"
        assert mock_plugin.execute.call_count == 2

    def test_single_action_pause_execution(self):
        mock_pm = MagicMock()
        mock_plugin = MagicMock()
        mock_plugin.execute.return_value = {"status": "success", "message": "1 部开门机已成功下发暂停"}
        mock_pm.get_plugin.return_value = mock_plugin

        mock_config = MagicMock()
        mock_ack = MagicMock()

        engine = TaskManager(plugin_manager=mock_pm, config_loader=mock_config, response_callback=mock_ack)
        payload = {
            "msg_id": "20260728-092443-471-262",
            "cmd_type": "action",
            "plugin_type": "DoorPlugin",
            "action": "pause",
            "params": {"ips": ["127.0.0.1"]}
        }

        engine._process_payload(payload)

        import time; time.sleep(0.5)
        mock_pm.get_plugin.assert_called_once_with("DoorPlugin")
        mock_plugin.execute.assert_called_once_with(action="pause", params={"ips": ["127.0.0.1"]})
        import time; time.sleep(0.5)
        mock_ack.assert_called_once()
        args, kwargs = mock_ack.call_args
        assert kwargs.get("code") == 0

    def test_task_save_with_rth_point(self):
        """测试保存带有 rth_point 的任务时，元数据被完整透传给 storage_manager"""
        mock_pm = MagicMock()
        mock_config = MagicMock()
        mock_ack = MagicMock()

        engine = TaskManager(plugin_manager=mock_pm, config_loader=mock_config, response_callback=mock_ack)
        engine.storage_manager = MagicMock()

        payload = {
            "msg_id": "MSG_SAVE_RTH",
            "cmd_type": "task",
            "action": "save",
            "task_id": "TASK_WITH_RTH",
            "task_name": "带返航点巡检任务",
            "rth_point": 100,
            "steps": [
                {"step": 1, "plugin_type": "NavPlugin", "action": "start_nav", "params": {"goal_point": 10}}
            ]
        }
        engine._process_payload(payload)

        engine.storage_manager.save_task_to_disk.assert_called_once()
        call_kwargs = engine.storage_manager.save_task_to_disk.call_args[1]
        assert call_kwargs["task_id"] == "TASK_WITH_RTH"
        assert call_kwargs["metadata"].get("rth_point") == 100

    def test_task_rth_execution(self):
        """测试在任务运行中下发 rth 指令，成功终止当前动作并编译启动返航流水线"""
        mock_pm = MagicMock()
        mock_plugin = MagicMock()
        mock_plugin.execute.return_value = {"status": "success"}
        mock_pm.get_plugin.return_value = mock_plugin

        mock_config = MagicMock()
        mock_ack = MagicMock()

        engine = TaskManager(plugin_manager=mock_pm, config_loader=mock_config, response_callback=mock_ack)
        engine.task_state = "RUNNING"
        engine.current_execution_queue = [
            {"step": 1, "plugin_type": "NavPlugin", "action": "start_nav", "params": {"goal_point": 10}},
            {"step": 2, "plugin_type": "NavPlugin", "action": "start_nav", "params": {"goal_point": 15}}
        ]
        engine._current_step_index = 1
        engine._current_plugin = mock_plugin

        rth_payload = {
            "msg_id": "MSG_RTH_001",
            "cmd_type": "task",
            "action": "rth",
            "task_id": "TASK_PATROL",
            "task_name": "巡检任务",
            "rth_point": 100
        }

        with patch("core.task_manager.RthManager") as MockRthManager:
            mock_builder = MagicMock()
            mock_builder.build.return_value = [
                {"step": 1, "plugin_type": "NavPlugin", "action": "start_nav", "params": {"goal_point": 10}},
                {"step": 2, "plugin_type": "NavPlugin", "action": "start_nav", "params": {"goal_point": 100}}
            ]
            MockRthManager.return_value = mock_builder

            engine._process_payload(rth_payload)

            mock_plugin.abort.assert_called_once()
            mock_builder.build.assert_called_once()
            args, kwargs = mock_builder.build.call_args
            assert args[2].get("rth_point") == 100

    def test_rth_permanently_cancels_original_paused_task(self):
        """
        核心防御验证：
        当原任务处于 PAUSED 暂停状态时，平台下发 rth 返航指令，
        原任务必须被永久且彻底终止，绝不能在返航流水线启动后被意外唤醒继续执行原后续步骤！
        """
        mock_pm = MagicMock()
        executed_steps = []
        step1_done = threading.Event()
        step2_started = threading.Event()
        step2_unblock = threading.Event()

        def fake_execute(action, params):
            step_id = params.get("step_id")
            executed_steps.append(step_id)
            if step_id == "original_step_1":
                step1_done.set()
                return {"status": "success"}
            elif step_id == "original_step_2":
                step2_started.set()
                # 阻塞直到下发 pause 指令唤醒
                step2_unblock.wait(timeout=5.0)
                return {"status": "paused", "message": "步骤2主动挂起"}
            return {"status": "success"}

        mock_plugin = MagicMock()
        mock_plugin.execute.side_effect = fake_execute

        def fake_pause():
            step2_unblock.set()

        mock_plugin.pause.side_effect = fake_pause
        mock_pm.get_plugin.return_value = mock_plugin

        mock_config = MagicMock()
        mock_config.get.return_value = {
            "TASK_ORIGINAL": [
                {"step": 1, "plugin_type": "NavPlugin", "action": "start_nav", "params": {"step_id": "original_step_1"}},
                {"step": 2, "plugin_type": "NavPlugin", "action": "start_nav", "params": {"step_id": "original_step_2"}},
                {"step": 3, "plugin_type": "NavPlugin", "action": "start_nav", "params": {"step_id": "original_step_3"}}
            ]
        }
        mock_ack = MagicMock()

        engine = TaskManager(plugin_manager=mock_pm, config_loader=mock_config, response_callback=mock_ack)

        # 1. 启动原任务 (共 3 个步骤，通过合规配置任务库触发)
        original_payload = {
            "msg_id": "MSG_ORIGINAL_001",
            "cmd_type": "task",
            "action": "run",
            "task_id": "TASK_ORIGINAL",
            "task_name": "原始多步巡检任务"
        }

        engine._process_payload(original_payload)
        assert step1_done.wait(timeout=2.0)
        assert step2_started.wait(timeout=2.0)

        # 2. 模拟平台在步骤 2 运行期间下发 pause 暂停任务
        pause_payload = {
            "msg_id": "MSG_PAUSE_001",
            "cmd_type": "control",
            "action": "pause",
            "task_id": "TASK_ORIGINAL"
        }
        engine._process_payload(pause_payload)
        # 等待任务状态进入 PAUSED
        time.sleep(0.1)
        assert engine.task_state == "PAUSED"

        # 3. 在 PAUSED 状态下下发 rth 返航指令
        rth_payload = {
            "msg_id": "MSG_RTH_002",
            "cmd_type": "task",
            "action": "rth",
            "task_id": "TASK_ORIGINAL",
            "task_name": "原始多步巡检任务"
        }

        with patch("core.task_manager.RthManager") as MockRthManager:
            mock_builder = MagicMock()
            mock_builder.build.return_value = [
                {"step": 1, "plugin_type": "NavPlugin", "action": "start_nav", "params": {"step_id": "rth_step_1"}}
            ]
            MockRthManager.return_value = mock_builder

            engine._process_payload(rth_payload)

        # 等待返航执行完成
        time.sleep(0.5)

        # 4. 核心断言：
        # - rth_step_1 必须成功执行
        # - 原任务在步骤 2 暂停后收到 RTH，原任务工作线程彻底退出，original_step_3 绝对不能被执行！
        # - original_step_2 绝不会在返航启动后被意外唤醒重试！
        assert "original_step_1" in executed_steps
        assert "original_step_2" in executed_steps
        assert "rth_step_1" in executed_steps
        assert executed_steps.count("original_step_2") == 1
        assert "original_step_3" not in executed_steps

        # 核心验证：平台必须收到原任务 (MSG_ORIGINAL_001) 的 ACK_EXECUTE 取消回复 (code=4009)！
        orig_aborted_acks = [
            c for c in mock_ack.call_args_list 
            if c.kwargs.get("msg_id") == "MSG_ORIGINAL_001" and c.kwargs.get("reply_type") == "ACK_EXECUTE"
        ]
        assert len(orig_aborted_acks) == 1
        assert orig_aborted_acks[0].kwargs.get("code") == 4009
        assert "终止取消" in orig_aborted_acks[0].kwargs.get("message")

    def test_rth_preempts_running_task(self):
        """
        验证原任务正在运行过程中，下发 RTH 指令能瞬间打断当前正在运行的插件，
        且原任务后续步骤绝不再被执行，返航独立安全执行完成。
        """
        mock_pm = MagicMock()
        executed_steps = []
        step1_started = threading.Event()
        step1_aborted = threading.Event()

        def fake_execute(action, params):
            step_id = params.get("step_id")
            executed_steps.append(step_id)
            if step_id == "long_step_1":
                step1_started.set()
                # 模拟长耗时阻塞动作，等待 abort
                while not step1_aborted.is_set():
                    time.sleep(0.05)
                return {"status": "aborted", "message": "被打断"}
            return {"status": "success"}

        mock_plugin = MagicMock()
        mock_plugin.execute.side_effect = fake_execute

        def fake_abort():
            step1_aborted.set()

        mock_plugin.abort.side_effect = fake_abort
        mock_pm.get_plugin.return_value = mock_plugin

        mock_config = MagicMock()
        mock_config.get.return_value = {
            "TASK_LONG": [
                {"step": 1, "plugin_type": "NavPlugin", "action": "start_nav", "params": {"step_id": "long_step_1"}},
                {"step": 2, "plugin_type": "NavPlugin", "action": "start_nav", "params": {"step_id": "long_step_2"}}
            ]
        }
        mock_ack = MagicMock()

        engine = TaskManager(plugin_manager=mock_pm, config_loader=mock_config, response_callback=mock_ack)

        # 启动长任务
        run_payload = {
            "msg_id": "MSG_RUN_LONG",
            "cmd_type": "task",
            "action": "run",
            "task_id": "TASK_LONG",
            "task_name": "长巡检任务"
        }

        engine._process_payload(run_payload)
        assert step1_started.wait(timeout=2.0)

        # 此时任务处于 RUNNING 且正在阻塞执行 long_step_1，下发 RTH
        rth_payload = {
            "msg_id": "MSG_RTH_INTERRUPT",
            "cmd_type": "task",
            "action": "rth",
            "task_id": "TASK_LONG",
            "task_name": "长巡检任务"
        }

        with patch("core.task_manager.RthManager") as MockRthManager:
            mock_builder = MagicMock()
            mock_builder.build.return_value = [
                {"step": 1, "plugin_type": "NavPlugin", "action": "start_nav", "params": {"step_id": "rth_nav_home"}}
            ]
            MockRthManager.return_value = mock_builder

            engine._process_payload(rth_payload)

        # 等待返航执行完成
        time.sleep(0.5)

        # 断言插件 abort 被调用
        assert step1_aborted.is_set()
        # 断言返航步骤执行
        assert "rth_nav_home" in executed_steps
        # 原任务后续步骤 long_step_2 绝不能被执行
        assert "long_step_2" not in executed_steps

        # 核心验证：平台必须收到长任务 (MSG_RUN_LONG) 的 ACK_EXECUTE 取消回复 (code=4009)！
        long_aborted_acks = [
            c for c in mock_ack.call_args_list 
            if c.kwargs.get("msg_id") == "MSG_RUN_LONG" and c.kwargs.get("reply_type") == "ACK_EXECUTE"
        ]
        assert len(long_aborted_acks) == 1
        assert long_aborted_acks[0].kwargs.get("code") == 4009

