from unittest.mock import MagicMock, patch, call
import threading
import pytest
from core.plugin_manager import PluginManager


class TestPluginManager:
    def setup_method(self):
        self.pm = PluginManager()
        self.pm.reset()

    def teardown_method(self):
        self.pm.reset()

    def test_singleton(self):
        """测试单例唯一性"""
        pm2 = PluginManager()
        assert self.pm is pm2

    def test_get_plugin_not_registered(self):
        """测试获取未注册插件抛出 KeyError"""
        with pytest.raises(KeyError):
            self.pm.get_plugin("NonExistentPlugin")

    def test_get_plugin_by_capability_not_registered(self):
        """测试获取未注册能力抛出 KeyError"""
        with pytest.raises(KeyError):
            self.pm.get_plugin_by_capability("unregistered_capability")

    def test_programmatic_register_and_unregister(self):
        """测试编程式注册、查询、能力映射与注销完整流程"""
        mock_door = MagicMock()
        mock_door.get_capabilities.return_value = {
            "plugin_type": "MockDoorPlugin",
            "supported_actions": [{"action": "open", "action_name": "开门"}]
        }

        # 1. 注册
        self.pm.register_plugin("MockDoorPlugin", mock_door, capabilities=["door_control", "rfid_scan"])
        assert self.pm.has_plugin("MockDoorPlugin")
        assert "MockDoorPlugin" in self.pm.list_plugins()
        assert self.pm.get_plugin("MockDoorPlugin") is mock_door
        assert self.pm.get_plugin_by_capability("door_control") is mock_door
        assert self.pm.get_plugin_by_capability("rfid_scan") is mock_door

        # 2. 注销
        unregistered = self.pm.unregister_plugin("MockDoorPlugin")
        assert unregistered is mock_door
        assert not self.pm.has_plugin("MockDoorPlugin")
        assert "MockDoorPlugin" not in self.pm.list_plugins()

        # 能力映射也应被同步清理
        with pytest.raises(KeyError):
            self.pm.get_plugin_by_capability("door_control")

        # 重复注销返回 None
        assert self.pm.unregister_plugin("MockDoorPlugin") is None

    def test_invalid_register_inputs(self):
        """测试非法入参校验"""
        with pytest.raises(ValueError):
            self.pm.register_plugin("", MagicMock())
        with pytest.raises(ValueError):
            self.pm.register_plugin("ValidName", None)

    def test_trigger_global_abort(self):
        """测试整机全局急停联动：成功通知所有注册插件调用 abort/stop"""
        mock_arm = MagicMock()
        mock_nav = MagicMock()
        mock_door = MagicMock()
        # mock_door 仅实现 stop，未实现 abort
        del mock_door.abort

        self.pm.register_plugin("ArmPlugin", mock_arm)
        self.pm.register_plugin("NavPlugin", mock_nav)
        self.pm.register_plugin("DoorPlugin", mock_door)

        aborted_count = self.pm.trigger_global_abort()
        assert aborted_count == 3
        mock_arm.abort.assert_called_once()
        mock_nav.abort.assert_called_once()
        mock_door.stop.assert_called_once()

    def test_reset_clears_plugins(self):
        """测试 reset 清空所有已注册插件"""
        self.pm.register_plugin("PluginA", MagicMock())
        self.pm.register_plugin("PluginB", MagicMock(), capabilities=["cap_b"])
        assert len(self.pm.list_plugins()) == 2

        self.pm.reset()
        assert len(self.pm.list_plugins()) == 0
        assert not self.pm.has_plugin("PluginA")
        with pytest.raises(KeyError):
            self.pm.get_plugin_by_capability("cap_b")

    def test_get_all_capabilities(self):
        """测试获取物模型能力描述"""
        mock_plugin = MagicMock()
        mock_plugin.get_capabilities.return_value = {
            "plugin_type": "MockPlugin",
            "supported_actions": [{"action": "open", "action_name": "开门"}]
        }
        self.pm.register_plugin("MockPlugin", mock_plugin)

        caps = self.pm.get_all_capabilities()
        assert any(c["plugin_type"] == "MockPlugin" for c in caps)
        mock_cap = next(c for c in caps if c["plugin_type"] == "MockPlugin")
        assert mock_cap["supported_actions"][0]["action_name"] == "开门"

    def test_get_all_plugin_states(self):
        """测试搜集全量插件实时状态"""
        mock_online = MagicMock()
        mock_online.status.return_value = True
        mock_dict_status = MagicMock()
        mock_dict_status.get_status.return_value = {"mode": "AUTO", "battery": 95}

        self.pm.register_plugin("OnlinePlugin", mock_online)
        self.pm.register_plugin("DictPlugin", mock_dict_status)

        states = self.pm.get_all_plugin_states()
        assert states["OnlinePlugin"]["status"] == "ONLINE"
        assert states["DictPlugin"]["mode"] == "AUTO"

    def test_concurrent_multithreaded_access(self):
        """测试多线程并发获取单例并注册查询插件"""
        errors = []

        def worker(idx):
            try:
                local_pm = PluginManager()
                plugin_name = f"ConcurrentPlugin_{idx}"
                mock_inst = MagicMock()
                local_pm.register_plugin(plugin_name, mock_inst, capabilities=[f"cap_{idx}"])
                assert local_pm.has_plugin(plugin_name)
                assert local_pm.get_plugin_by_capability(f"cap_{idx}") is mock_inst
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(self.pm.list_plugins()) == 10

    def test_real_plugins_have_action_name(self):
        """测试所有已实现的实际能力插件上报中均包含 action_name 字段"""
        self.pm.discover_plugins("plugins")
        all_caps = self.pm.get_all_capabilities()
        assert len(all_caps) > 0
        for cap in all_caps:
            supported = cap.get("supported_actions", [])
            for act in supported:
                assert "action_name" in act, f"插件 [{cap.get('plugin_type')}] 的动作 [{act.get('action')}] 缺少 action_name 字段"
                assert len(act["action_name"]) > 0, f"插件 [{cap.get('plugin_type')}] 的 action_name 不能为空"
