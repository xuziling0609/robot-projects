from unittest.mock import MagicMock, patch, call
import pytest
from components.elevator_component import ElevatorComponent

class TestElevatorComponent:
    def setup_method(self):
        self.mock_pm = MagicMock()
        self.mock_elevator = MagicMock()
        self.mock_nav = MagicMock()
        
        self.mock_pm.get_plugin_by_capability.side_effect = lambda cap: {
            "elevator_control": self.mock_elevator,
            "navigation": self.mock_nav
        }.get(cap)
        
        self.comp = ElevatorComponent(self.mock_pm)
        
        self.mock_elevator.execute.return_value = {"status": "success"}
        self.mock_nav.execute.return_value = {"status": "success"}

    def test_execute_success(self):
        params = {
            "addr": 1,
            "start_floor": 1,
            "start_point": 10,
            "start_ele_point": 11,
            "target_floor": 2,
            "target_point": 12,
            "target_ele_point": 13
        }
        res = self.comp.execute(params)
        
        assert res["status"] == "success"
        assert self.mock_nav.execute.call_count == 3
        assert self.mock_elevator.execute.call_count == 6 # goToFloor * 2, open * 2, close * 2

    def test_missing_params(self):
        res = self.comp.execute({})
        assert res["status"] == "error"
