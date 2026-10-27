import pytest
import numpy as np
from src.control.motion_plan import APFPlanner

@pytest.fixture
def planner():
    # 使用 fixture 提供规划器实例，这里我们可以配置一些默认的安全距离参数用于测试
    p = APFPlanner()
    p.safe_dist = 150.0
    p.k_att = 1.0
    p.k_rep = 5000.0
    p.max_z = 300.0
    return p

def test_attractive_force(planner):
    current_pos = np.array([0.0, 0.0, 0.0])
    target_pos = np.array([10.0, 0.0, 0.0])
    
    force = planner.calculate_attractive_force(current_pos, target_pos)
    
    # 因为 k_att = 1.0, 距离为 10, 方向在 x 轴正向
    assert np.allclose(force, [10.0, 0.0, 0.0])

def test_attractive_force_arrived(planner):
    current_pos = np.array([0.0, 0.0, 0.0])
    target_pos = np.array([0.5, 0.0, 0.0])
    
    force = planner.calculate_attractive_force(current_pos, target_pos)
    
    # 距离小于 1.0，应视为到达，引力为 0
    assert np.allclose(force, [0.0, 0.0, 0.0])

def test_repulsive_force_far(planner):
    current_pos = np.array([0.0, 0.0, 0.0])
    # 障碍物距离 200 > safe_dist(150)，应该不产生斥力
    depth_cloud = np.array([[200.0, 0.0, 0.0]])
    
    force = planner.calculate_repulsive_force(current_pos, depth_cloud)
    assert np.allclose(force, [0.0, 0.0, 0.0])

def test_repulsive_force_near(planner):
    current_pos = np.array([0.0, 0.0, 0.0])
    # 障碍物距离 100 < safe_dist(150)
    # 计算应该有远离方向（负 X）的斥力
    depth_cloud = np.array([[100.0, 0.0, 0.0]])
    
    force = planner.calculate_repulsive_force(current_pos, depth_cloud)
    # 因为 current - point = [-100, 0, 0], 所以 direction 是 [-1, 0, 0]
    # 应当在 X 轴上有一个负向斥力
    assert force[0] < 0.0
    assert force[1] == 0.0
    assert force[2] == 0.0

def test_repulsive_force_multiple_points(planner):
    current_pos = np.array([0.0, 0.0, 0.0])
    # 两个障碍物，一个在正前方，一个在正下方
    depth_cloud = np.array([
        [100.0, 0.0, 0.0],
        [0.0, 100.0, 0.0]
    ])
    
    force = planner.calculate_repulsive_force(current_pos, depth_cloud)
    # 综合斥力应该指向负 X 和负 Y
    assert force[0] < 0.0
    assert force[1] < 0.0
    assert force[2] == 0.0

def test_ptz_repulsive_force(planner):
    # 云台中心设为 [450, 0, 150]，半径 250
    planner.ptz_enabled = True
    planner.ptz_center_base = np.array([450.0, 0.0, 150.0])
    planner.ptz_radius = 250.0

    # 机械臂位置 [300, 0, 150]，距离云台中心 150mm < 250mm
    current_pos_base = np.array([300.0, 0.0, 150.0])
    force = planner.calculate_ptz_repulsive_force(current_pos_base)

    # 应当在 X 轴向后推（负 X 方向）
    assert force[0] < 0.0
    assert force[1] == 0.0
    assert force[2] == 0.0


def test_repulsive_force_target_exclusion(planner):
    current_pos = np.array([0.0, 0.0, 0.0])
    target_pos = np.array([0.0, 0.0, 80.0])

    # 障碍物点位于目标点附近 (距离目标 5mm < exclusion_radius 60mm)
    depth_cloud_target = np.array([[0.0, 0.0, 85.0]])

    # 当指定 target_pos 时，目标附近的点被排除，不产生斥力
    force_excluded = planner.calculate_repulsive_force(
        current_pos, depth_cloud_target, target_pos=target_pos, target_exclusion_radius=60.0
    )
    assert np.allclose(force_excluded, [0.0, 0.0, 0.0])

    # 若障碍物不在目标排除半径内 (距离目标 60mm > 20mm)，应当产生斥力
    depth_cloud_obstacle = np.array([[0.0, 0.0, 20.0]])
    force_included = planner.calculate_repulsive_force(
        current_pos, depth_cloud_obstacle, target_pos=target_pos, target_exclusion_radius=20.0
    )
    assert force_included[2] < 0.0  # 沿负 Z 轴推开

