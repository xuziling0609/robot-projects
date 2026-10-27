from unittest.mock import MagicMock, patch, call
import pytest
from components.station_component import StationComponent

class TestStationComponent:
    def setup_method(self):
        self.mock_pm = MagicMock()
        self.mock_station = MagicMock()
        self.mock_nav = MagicMock()
        
        self.mock_pm.get_plugin_by_capability.side_effect = lambda cap: {
            "station_control": self.mock_station,
            "navigation": self.mock_nav
        }.get(cap)
        
        self.comp = StationComponent(self.mock_pm)
        
        self.mock_station.execute.return_value = {"status": "success"}
        self.mock_nav.execute.return_value = {"status": "success"}

    def test_execute_leave_success(self):
        params = {
            "direction": "leave",
            "inner_point": 1,
            "outer_point": 2,
            "ips": ["192.168.1.200"]
        }
        res = self.comp.execute(params)
        
        assert res["status"] == "success"
        self.mock_nav.execute.assert_called_with(action="start_nav", params={"goal_point": 2})
        assert self.mock_station.execute.call_count == 2 # open, close

    def test_execute_enter_success(self):
        params = {
            "direction": "enter",
            "inner_point": 1,
            "outer_point": 2,
            "ips": ["192.168.1.200"]
        }
        res = self.comp.execute(params)
        
        assert res["status"] == "success"
        assert self.mock_nav.execute.call_count == 3 # start_nav * 2, motion_cmd * 1
        assert self.mock_station.execute.call_count == 2 # open, close

    def test_missing_params(self):
        res = self.comp.execute({})
        assert res["status"] == "error"
