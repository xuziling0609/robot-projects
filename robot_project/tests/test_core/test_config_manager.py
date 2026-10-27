import os
import copy
import threading
import tempfile
import yaml
import pytest
from core.config_manager import ConfigManager


class TestConfigManager:
    """ConfigManager 核心能力与多线程并发完整单测套件"""

    def setup_method(self):
        ConfigManager.reset()
        self.loader = ConfigManager()

    def teardown_method(self):
        ConfigManager.reset()

    def test_singleton(self):
        """验证全局单例唯一性"""
        loader2 = ConfigManager()
        assert self.loader is loader2

    def test_get_nested_key(self):
        """验证深层点号字典检索与默认回退机制"""
        with self.loader._lock:
            self.loader._config = {
                "gateway": {"version": "1.0.0"},
                "mqtt": {"broker_ip": "127.0.0.1", "port": 1883}
            }

        assert self.loader.get("gateway.version") == "1.0.0"
        assert self.loader.get("mqtt.port") == 1883
        assert self.loader.get("non_existent.key", "DEFAULT") == "DEFAULT"
        assert self.loader.get("", "DEFAULT") == "DEFAULT"

    def test_set_nested_key_and_auto_hierarchy(self):
        """验证点号 set 语法支持自动递归建层与覆写"""
        self.loader.set("mqtt.broker_ip", "10.0.0.1")
        self.loader.set("mqtt.auth.username", "admin")
        self.loader.set("plugins.nav.params.speed", 1.5)

        assert self.loader.get("mqtt.broker_ip") == "10.0.0.1"
        assert self.loader.get("mqtt.auth.username") == "admin"
        assert self.loader.get("plugins.nav.params.speed") == 1.5

    def test_list_indexing_in_path(self):
        """验证点号路径中支持使用数字索引遍历列表元素"""
        with self.loader._lock:
            self.loader._config = {
                "routes": [
                    {"id": "route_1", "ip": "192.168.1.10"},
                    {"id": "route_2", "ip": "192.168.1.20"}
                ],
                "tags": ["alpha", "beta", "gamma"]
            }

        assert self.loader.get("routes.0.ip") == "192.168.1.10"
        assert self.loader.get("routes.1.id") == "route_2"
        assert self.loader.get("tags.2") == "gamma"
        # 越界或非法索引回退
        assert self.loader.get("routes.5.ip", "FALLBACK") == "FALLBACK"
        assert self.loader.get("tags.abc", "FALLBACK") == "FALLBACK"

    def test_to_dict_deep_copy_isolation(self):
        """验证 to_dict 导出深拷贝快照，外部修改绝不污染配置中枢"""
        self.loader.set("device.meta.sn", "SN-99999")
        snapshot = self.loader.to_dict()

        assert snapshot["device"]["meta"]["sn"] == "SN-99999"
        # 尝试外部污染篡改
        snapshot["device"]["meta"]["sn"] = "TAMPERED"

        assert self.loader.get("device.meta.sn") == "SN-99999"

    def test_load_plugin_and_main_config_merge(self):
        """验证插件配置动态挂载至 plugins 节点，且与主配置平滑合并"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            plugin_cfg_path = os.path.join(tmp_dir, "plugin_nav.yaml")
            with open(plugin_cfg_path, "w", encoding="utf-8") as f:
                yaml.dump({"timeout": 25, "planner": "astar"}, f)

            main_cfg_path = os.path.join(tmp_dir, "main_cfg.yaml")
            with open(main_cfg_path, "w", encoding="utf-8") as f:
                yaml.dump({"gateway": {"id": "GW-001"}, "log_level": "DEBUG"}, f)

            # 1. 先挂载插件
            loaded_plugin = self.loader.load_plugin("nav", plugin_cfg_path)
            assert loaded_plugin["planner"] == "astar"
            assert self.loader.get("plugins.nav.timeout") == 25

            # 2. 再加载主配置，验证插件挂载不会被冲掉
            self.loader.load_main(main_cfg_path)
            assert self.loader.get("gateway.id") == "GW-001"
            assert self.loader.get("plugins.nav.planner") == "astar"

    def test_concurrent_read_write(self):
        """验证 20 个工作线程高频并发进行 get 与 set 操作时的绝对线程安全"""
        errors = []

        def writer(thread_id: int):
            try:
                for i in range(50):
                    self.loader.set(f"thread_{thread_id}.var_{i}", i)
            except Exception as e:
                errors.append(e)

        def reader(thread_id: int):
            try:
                for i in range(50):
                    _ = self.loader.get(f"thread_{thread_id}.var_{i}", None)
            except Exception as e:
                errors.append(e)

        threads = []
        for tid in range(10):
            threads.append(threading.Thread(target=writer, args=(tid,)))
            threads.append(threading.Thread(target=reader, args=(tid,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_reset_isolation(self):
        """验证 reset 能够彻底清空配置树并清理单例实例"""
        self.loader.set("test.key", "val")
        assert self.loader.get("test.key") == "val"

        ConfigManager.reset()
        assert ConfigManager._instance is None

        new_instance = ConfigManager()
        # 由于 reset 之后是全新实例且主配置未加载或为空，应当检索不到旧 key
        assert new_instance.get("test.key") is None


