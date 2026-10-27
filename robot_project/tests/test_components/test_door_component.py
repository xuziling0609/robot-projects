from unittest.mock import MagicMock, patch, call
import pytest
from components.door_component import DoorComponent

class TestDoorComponent:
    def setup_method(self):
        self.mock_pm = MagicMock()
        self.mock_door = MagicMock()
        self.mock_nav = MagicMock()
        
        self.mock_pm.get_plugin_by_capability.side_effect = lambda cap: {
            "door_control": self.mock_door,
            "navigation": self.mock_nav
        }.get(cap)
        
        self.comp = DoorComponent(self.mock_pm)
        
        # 默认全部返回成功
        self.mock_door.execute.return_value = {"status": "success"}
        self.mock_nav.execute.return_value = {"status": "success"}

    def test_execute_success(self):
        params = {
            "door_ips": ["192.168.1.100"],
            "entry_point": 1,
            "exit_point": 2
        }
        res = self.comp.execute(params)
        
        assert res["status"] == "success"
        assert self.mock_nav.execute.call_count == 2
        assert self.mock_door.execute.call_count == 3

    def test_missing_params(self):
        res = self.comp.execute({})
        assert res["status"] == "error"

    def test_abort_during_execution(self):
        params = {
            "door_ips": ["192.168.1.100"],
            "entry_point": 1,
            "exit_point": 2
        }
        
        def side_effect(action, params):
            if action == "open":
                self.comp.abort()
                return {"status": "success"}
            return {"status": "success"}
            
        self.mock_door.execute.side_effect = side_effect
        
        res = self.comp.execute(params)
        assert res["status"] == "aborted"
        self.mock_door.execute.assert_called_with(action="close", params={"ips": ["192.168.1.100"]})
