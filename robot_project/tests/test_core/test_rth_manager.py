import pytest
import os
import yaml
from core.rth_manager import RthManager

@pytest.fixture
def temp_config_file(tmp_path):
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    config_file = config_dir / "rth_hooks.yaml"
    
    config_data = {
        "pre_rth_resets": [
            {"plugin_type": "ArmPlugin", "action": "goback", "params": {}},
            {"plugin_type": "CameraPlugin", "action": "ptz_goto_preset", "params": {"preset_id": 1}}
        ],
        "edge_actions": {
            "15_14": [
                {"plugin_type": "DoorPlugin", "action": "open", "params": {"ips": ["192.168.1.100"]}},
                {"plugin_type": "NavPlugin", "action": "start_nav", "params": {"goal_point": 14}},
                {"plugin_type": "DoorPlugin", "action": "close", "params": {"ips": ["192.168.1.100"]}}
            ]
        }
    }
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(config_data, f)
        
    return str(config_file)

@pytest.fixture
def rth_manager(temp_config_file, monkeypatch):
    mgr = RthManager()
    mgr.config_path = temp_config_file
    return mgr

def test_build_rth_with_edge_and_rth_point(rth_manager):
    current_queue = [
        {"step": 1, "plugin_type": "NavPlugin", "action": "start_nav", "params": {"goal_point": 10}},
        {"step": 2, "plugin_type": "CameraPlugin", "action": "ptz_goto_preset", "params": {"preset_id": 2}},
        {"step": 3, "plugin_type": "NavPlugin", "action": "start_nav", "params": {"goal_point": 14}},
        {"step": 4, "plugin_type": "NavPlugin", "action": "start_nav", "params": {"goal_point": 15}},
        {"step": 5, "plugin_type": "ArmPlugin", "action": "do_something", "params": {}}
    ]
    # 中断在 step 5
    current_step_index = 4
    
    task_metadata = {"rth_point": 100}
    
    res = rth_manager.build(current_queue, current_step_index, task_metadata)
    
    # 期望生成的步骤集分析：
    # 提取出的原始 Nav 点：[10, 14, 15]
    # 逆序后：[15, 14, 10]
    #
    # pre_resets: ArmPlugin, CameraPlugin
    # edge 15_14: 命中！插入 open_door, start_nav(14), close_door
    # edge 14_10: 未命中，单纯插入 start_nav(10)
    # 追加 rth_point: start_nav(100)
    
    # 所以一共 2 (pre) + 3 (edge 15_14) + 1 (nav 10) + 1 (rth) = 7 steps
    assert len(res) == 7
    
    assert res[0]["plugin_type"] == "ArmPlugin"
    assert res[1]["plugin_type"] == "CameraPlugin"
    
    assert res[2]["plugin_type"] == "DoorPlugin"
    assert res[2]["action"] == "open"
    
    assert res[3]["plugin_type"] == "NavPlugin"
    assert res[3]["params"]["goal_point"] == 14
    
    assert res[4]["plugin_type"] == "DoorPlugin"
    assert res[4]["action"] == "close"
    
    assert res[5]["plugin_type"] == "NavPlugin"
    assert res[5]["params"]["goal_point"] == 10
    
    assert res[6]["plugin_type"] == "NavPlugin"
    assert res[6]["params"]["goal_point"] == 100
    
    # 检查重置 step id
    for i, r in enumerate(res):
        assert r["step"] == i + 1

def test_build_rth_fallback_no_rth_point(rth_manager):
    current_queue = [
        {"step": 1, "plugin_type": "NavPlugin", "action": "start_nav", "params": {"goal_point": 10}},
        {"step": 2, "plugin_type": "NavPlugin", "action": "start_nav", "params": {"goal_point": 11}}
    ]
    # 没有 rth_point
    res = rth_manager.build(current_queue, 1, {})
    
    # 逆序 [11, 10]
    # 2 (pre) + 1 (nav 10) = 3 steps
    assert len(res) == 3
    assert res[-1]["plugin_type"] == "NavPlugin"
    assert res[-1]["params"]["goal_point"] == 10

def test_build_rth_no_nav_points(rth_manager):
    current_queue = [
        {"step": 1, "plugin_type": "CameraPlugin", "action": "ptz_goto_preset", "params": {"preset_id": 2}}
    ]
    res = rth_manager.build(current_queue, 0, {"rth_point": 99})
    
    # 2 (pre) + 1 (rth 99) = 3 steps
    assert len(res) == 3
    assert res[2]["plugin_type"] == "NavPlugin"
    assert res[2]["params"]["goal_point"] == 99

def test_build_rth_with_edge_to_rth_point(rth_manager):
    current_queue = [
        {"step": 1, "plugin_type": "NavPlugin", "action": "start_nav", "params": {"goal_point": 15}}
    ]
    # 假设此时 rth_point 是 14
    # 退回到起点 15 后，去往 14 构成了边 "15_14"
    res = rth_manager.build(current_queue, 0, {"rth_point": 14})
    
    # 2 (pre) + 3 (edge 15_14 which has 3 actions: Door open, Nav 14, Door close)
    # wait, edge_actions in temp config for 15_14 is:
    # Door open, Nav 14, Door close.
    # Total = 5 steps
    assert len(res) == 5
    assert res[2]["plugin_type"] == "DoorPlugin"
    assert res[3]["plugin_type"] == "NavPlugin"
    assert res[3]["params"]["goal_point"] == 14
    assert res[4]["plugin_type"] == "DoorPlugin"
