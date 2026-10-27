import pytest
from unittest.mock import MagicMock
from src.control.rm65_api import RM65Controller, RoboticArm

# Mock 配置加载器，防止依赖 yaml 文件
@pytest.fixture(autouse=True)
def mock_config(mocker):
    mocker.patch('src.control.rm65_api.get_config', return_value={
        'robot': {
            'controller_ip': '127.0.0.1',
            'controller_port': 8080,
            'home_pose': [88.24, 92.059, -165.194, 4.255, 163.162, 4.689],
            'scan_pose': [0.56, 82.227, -158.141, 2.79, 156.001, 94.176],
            'soft_limits': {
                'x_min': -100, 'x_max': 500,
                'y_min': -500, 'y_max': 500,
                'z_min': -100, 'z_max': 800
            },
            'self_collision': {
                'enabled': True,
                'tool_envelope': {
                    'enabled': True,
                    'radius_m': 0.050,
                    'center_m': [0.033, 0.050, 0.050]
                }
            },
            'joint_limits': {
                'j2_max_deg': 75.0,
                'directional_constraint': True
            }
        }
    })

@pytest.fixture
def rm65_controller(mocker):
    # Mock RoboticArm 的导入与实例化
    mock_arm_class = mocker.patch('src.control.rm65_api.RoboticArm')
    
    # 建立一个模拟的 SDK 实例
    mock_instance = MagicMock()
    # 模拟句柄正常返回
    mock_handle = MagicMock()
    mock_handle.contents.id = 1
    mock_instance.rm_create_robot_arm.return_value = mock_handle
    
    # 模拟获取当前位姿返回 code=0，且有数据
    mock_instance.rm_get_current_arm_state.return_value = (0, {
        'pose': [10, 20, 30, 0.1, 0.2, 0.3],
        'joint': [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
    })
    
    # 模拟 API 方法成功返回 0
    mock_instance.rm_movel.return_value = 0
    mock_instance.rm_movej.return_value = 0
    mock_instance.rm_movej_p.return_value = 0
    mock_instance.rm_set_collision_stage.return_value = 0
    mock_instance.rm_set_collision_state.return_value = 0
    mock_instance.rm_set_self_collision_enable.return_value = 0
    mock_instance.rm_algo_set_tool_envelope.return_value = None
    mock_instance.rm_algo_safety_robot_self_collision_detection.return_value = 0
    mock_instance.rm_algo_inverse_kinematics.return_value = (0, [10.0, 20.0, 30.0, 40.0, 50.0, 60.0])
    mock_instance.rm_set_arm_pause.return_value = 0
    mock_instance.rm_set_arm_slow_stop.return_value = 0
    mock_instance.rm_set_arm_stop.return_value = 0
    mock_instance.rm_set_arm_resume.return_value = 0
    mock_instance.rm_set_arm_continue.return_value = 0
    mock_instance.rm_set_tool_coordinate.return_value = 0
    mock_instance.rm_set_manual_tool_frame.return_value = 0
    mock_instance.rm_change_tool_frame.return_value = 0
    
    mock_arm_class.return_value = mock_instance
    
    controller = RM65Controller()
    return controller

def test_connect_success(rm65_controller):
    rm65_controller.connect()
    assert rm65_controller.is_connected == True
    rm65_controller.arm.rm_create_robot_arm.assert_called_once_with('127.0.0.1', 8080)

def test_move_l_within_fence(rm65_controller):
    rm65_controller.connect()
    
    # [100, 100, 100] mm 在虚拟围栏内，SDK 接收米制 [0.1, 0.1, 0.1]
    result = rm65_controller.move_l(100, 100, 100, 0, 0, 0, speed=20, r=0, connect=0, block=0)
    assert result == True
    rm65_controller.arm.rm_movel.assert_called_once_with([0.1, 0.1, 0.1, 0, 0, 0], 20, 0, 0, 0)

def test_move_j_p_within_fence(rm65_controller):
    rm65_controller.connect()
    
    # [100, 100, 100] mm 在虚拟围栏内，SDK 接收米制 [0.1, 0.1, 0.1]
    result = rm65_controller.move_j_p(100, 100, 100, 0, 0, 0, speed=20, r=0, connect=0, block=0)
    assert result == True
    rm65_controller.arm.rm_movej_p.assert_called_once_with([0.1, 0.1, 0.1, 0, 0, 0], 20, 0, 0, 0)

def test_move_l_out_of_fence(rm65_controller):
    rm65_controller.connect()
    
    # [1000, 100, 100] x 超出了 500
    result = rm65_controller.move_l(1000, 100, 100, 0, 0, 0)
    assert result == False
    rm65_controller.arm.rm_movel.assert_not_called()

def test_set_collision_stage(rm65_controller):
    rm65_controller.connect()
    rm65_controller.arm.rm_set_collision_state.return_value = 0
    res = rm65_controller.set_collision_stage(level=1)
    assert res == True
    rm65_controller.arm.rm_set_collision_state.assert_called_with(1)

def test_pause_resume(rm65_controller):
    rm65_controller.connect()
    rm65_controller.arm.rm_set_arm_pause.return_value = 0
    rm65_controller.arm.rm_set_arm_continue.return_value = 0
    
    assert rm65_controller.pause() == True
    assert rm65_controller.resume() == True

def test_pause_fallback_to_slow_stop(rm65_controller):
    """测试 rm_set_arm_pause 失败时自动降级调用 rm_set_arm_slow_stop 缓停成功"""
    rm65_controller.connect()
    rm65_controller.arm.rm_set_arm_pause.return_value = 1
    rm65_controller.arm.rm_set_arm_slow_stop.return_value = 0
    assert rm65_controller.pause() == True
    rm65_controller.arm.rm_set_arm_slow_stop.assert_called_once()

def test_set_tool_coordinate(rm65_controller):
    rm65_controller.connect()
    rm65_controller.arm.rm_set_tool_coordinate.return_value = 0
    
    tool_pose = [0, 0, 150, 0, 0, 0]
    assert rm65_controller.set_tool_coordinate(tool_pose) == True
    rm65_controller.arm.rm_set_tool_coordinate.assert_called_with(tool_pose)

def test_get_joint_degrees(rm65_controller):
    rm65_controller.connect()
    rm65_controller.arm.rm_get_current_arm_state.return_value = (0, {'joint': [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]})
    joints = rm65_controller.get_joint_degrees()
    assert joints == [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]

def test_get_current_pose(rm65_controller):
    rm65_controller.connect()
    # SDK 返回米制数据 [0.01, 0.02, 0.03, 0.1, 0.2, 0.3]
    rm65_controller.arm.rm_get_current_arm_state.return_value = (0, {'pose': [0.01, 0.02, 0.03, 0.1, 0.2, 0.3]})
    pose_mm = rm65_controller.get_current_pose(unit="mm")
    assert pytest.approx(pose_mm[:3]) == [10.0, 20.0, 30.0]
    assert pose_mm[3:] == [0.1, 0.2, 0.3]

    pose_m = rm65_controller.get_current_pose(unit="m")
    assert pose_m == [0.01, 0.02, 0.03, 0.1, 0.2, 0.3]

def test_is_busy_idle(rm65_controller):
    rm65_controller.connect()
    rm65_controller._last_cmd_time = 0.0
    rm65_controller.arm.rm_get_arm_current_trajectory.return_value = {
        'return_code': 0,
        'trajectory_type': 0,  # RM_NO_PLANNING_E
        'data': [0.0] * 6
    }
    assert rm65_controller.is_busy() is False

def test_is_busy_moving(rm65_controller):
    rm65_controller.connect()
    rm65_controller._last_cmd_time = 0.0
    rm65_controller.arm.rm_get_arm_current_trajectory.return_value = {
        'return_code': 0,
        'trajectory_type': 2,  # RM_CARTESIAN_LINEAR_PLANNING_E
        'data': [0.0] * 6
    }
    assert rm65_controller.is_busy() is True

def test_connect_configures_self_collision(rm65_controller):
    """测试连接机械臂时自动下发自碰撞使能和末端 D435i 工具包络球"""
    rm65_controller.connect()
    rm65_controller.arm.rm_set_self_collision_enable.assert_called_once_with(True)
    rm65_controller.arm.rm_algo_set_tool_envelope.assert_called_once()

def test_set_self_collision_enable(rm65_controller):
    rm65_controller.connect()
    rm65_controller.arm.rm_set_self_collision_enable.return_value = 0
    assert rm65_controller.set_self_collision_enable(True) is True
    assert rm65_controller.set_self_collision_enable(False) is True

def test_set_tool_envelope(rm65_controller):
    rm65_controller.connect()
    res = rm65_controller.set_tool_envelope(0, radius_m=0.050, center_m=[0.033, 0.050, 0.050])
    assert res is True
    rm65_controller.arm.rm_algo_set_tool_envelope.assert_called()

def test_move_j_self_collision_rejected(rm65_controller):
    """测试当关节角度触发自碰撞危险 (返回 1) 时，move_j 自动拦截并拒绝下发"""
    rm65_controller.connect()
    rm65_controller.arm.rm_algo_safety_robot_self_collision_detection.return_value = 1
    
    collide_joints = [0.0, 70.0, -175.0, 0.0, 175.0, 0.0]
    result = rm65_controller.move_j(collide_joints, speed=20)
    assert result is False
    rm65_controller.arm.rm_movej.assert_not_called()

def test_move_l_self_collision_rejected(rm65_controller):
    """测试当笛卡尔直线目标位姿逆解存在自碰撞干涉时，move_l 自动拦截并拒绝下发"""
    rm65_controller.connect()
    # 模拟逆解成功，但碰撞检测算法判定为 1 (发生本体干涉)
    rm65_controller.arm.rm_algo_inverse_kinematics.return_value = (0, [0.0, 70.0, -175.0, 0.0, 175.0, 0.0])
    rm65_controller.arm.rm_algo_safety_robot_self_collision_detection.return_value = 1
    
    result = rm65_controller.move_l(100, 100, 100, 0, 0, 0, speed=20)
    assert result is False
    rm65_controller.arm.rm_movel.assert_not_called()

def test_move_j_p_self_collision_rejected(rm65_controller):
    """测试当 MoveJ_P 目标位姿逆解存在自碰撞干涉时自动拦截"""
    rm65_controller.connect()
    rm65_controller.arm.rm_algo_inverse_kinematics.return_value = (0, [0.0, 70.0, -175.0, 0.0, 175.0, 0.0])
    rm65_controller.arm.rm_algo_safety_robot_self_collision_detection.return_value = 1
    
    result = rm65_controller.move_j_p(100, 100, 100, 0, 0, 0, speed=20)
    assert result is False
    rm65_controller.arm.rm_movej_p.assert_not_called()


def test_set_joint_limits_hardware_and_algo(rm65_controller):
    """测试连接时自动向硬件控制器和算法库下发关节2最大限位 (75度)"""
    rm65_controller.connect()
    rm65_controller.arm.rm_get_joint_max_pos.return_value = (0, [178.0, 178.0, 145.0, 178.0, 178.0, 360.0])
    rm65_controller.set_joint_limits(75.0)

    # 验证硬件底层设置 API 调用
    rm65_controller.arm.rm_set_joint_max_pos.assert_called_with(2, 75.0)
    # 验证算法库设置 API 调用
    rm65_controller.arm.rm_algo_set_joint_max_limit.assert_called_with([178.0, 75.0, 145.0, 178.0, 178.0, 360.0])


def test_move_j_joint2_limit_rejected(rm65_controller):
    """测试当关节2目标角度超过 75度 时 (如 78度)，move_j 自动拦截拒绝下发，防止撞击后方声纹模块"""
    rm65_controller.connect()
    
    # 关节2为 78.0° > 75.0°
    exceeded_joints = [0.0, 78.0, -150.0, 0.0, 150.0, 0.0]
    result = rm65_controller.move_j(exceeded_joints, speed=20)
    assert result is False
    rm65_controller.arm.rm_movej.assert_not_called()


def test_move_l_joint2_limit_rejected(rm65_controller):
    """测试当笛卡尔直线目标位姿逆解得到的关节2角度超过 75度 时，move_l 自动拦截拒绝下发"""
    rm65_controller.connect()
    # 模拟逆解得到的关节2为 82.5° > 75.0°
    rm65_controller.arm.rm_algo_inverse_kinematics.return_value = (0, [0.0, 82.5, -150.0, 0.0, 150.0, 0.0])
    rm65_controller.arm.rm_algo_safety_robot_self_collision_detection.return_value = 0

    result = rm65_controller.move_l(100, 100, 100, 0, 0, 0, speed=20)
    assert result is False
    rm65_controller.arm.rm_movel.assert_not_called()


def test_joint_limits_disabled_allows_scan_pose(rm65_controller):
    """测试当未配置或取消 j2_max_deg 限制时，允许执行 scan_pose (J2=82.227度) 并不做限位拦截"""
    rm65_controller.connect()
    rm65_controller.j2_max_deg = None  # 模拟未配置/取消限制

    scan_pose = [0.56, 82.227, -158.141, 2.79, 156.001, 94.176]
    # check_joint_limits 应该返回 True
    assert rm65_controller.check_joint_limits(scan_pose) is True

    # move_j 应该成功下发至底层
    result = rm65_controller.move_j(scan_pose, speed=20)
    assert result is True
    rm65_controller.arm.rm_movej.assert_called_once_with(scan_pose, 20, 0, 0, 0)


def test_set_joint_limits_default_when_none(rm65_controller):
    """测试当 j2_max_deg 为 None 时，set_joint_limits 自动恢复默认限位 178.0 度"""
    rm65_controller.connect()
    rm65_controller.arm.rm_get_joint_max_pos.return_value = (0, [178.0, 178.0, 145.0, 178.0, 178.0, 360.0])
    rm65_controller.j2_max_deg = None
    rm65_controller.set_joint_limits()

    # 验证向底层和算法库恢复 178.0° 默认最大限位
    rm65_controller.arm.rm_set_joint_max_pos.assert_called_with(2, 178.0)
    rm65_controller.arm.rm_algo_set_joint_max_limit.assert_called_with([178.0, 178.0, 145.0, 178.0, 178.0, 360.0])


def test_plan_a_allows_waypoint_scan_pose(rm65_controller):
    """方案A测试：配置了 j2_max_deg: 75.0 时，预设安全路点 scan_pose (J2=82.227°) 能够正常被放行并成功执行 MoveJ"""
    rm65_controller.connect()
    scan_pose = [0.56, 82.227, -158.141, 2.79, 156.001, 94.176]
    
    # 确认为安全路点
    assert rm65_controller._is_known_waypoint(scan_pose) is True
    assert rm65_controller.check_joint_limits(scan_pose) is True

    result = rm65_controller.move_j(scan_pose, speed=20)
    assert result is True
    rm65_controller.arm.rm_movej.assert_called_once_with(scan_pose, 20, 0, 0, 0)


def test_plan_a_directional_constraint_during_planning(rm65_controller):
    """方案A测试：在轨迹规划逼近阶段（当前在 scan_pose J2=82.227°），允许向前俯下 (J2减小)，严禁向后摆动 (J2增大)"""
    rm65_controller.connect()
    scan_pose_joints = [0.56, 82.227, -158.141, 2.79, 156.001, 94.176]
    # 设置当前机械臂关节状态为 scan_pose
    rm65_controller.arm.rm_get_current_arm_state.return_value = (0, {
        'pose': [100, 200, 300, 0.0, 0.0, 0.0],
        'joint': scan_pose_joints
    })
    rm65_controller.arm.rm_algo_safety_robot_self_collision_detection.return_value = 0

    # 1. 轨迹向前微调，逆解 J2 减小 (如 80.5° <= 82.227°) -> 允许执行
    forward_joints = [0.56, 80.5, -158.0, 2.79, 156.0, 94.1]
    rm65_controller.arm.rm_algo_inverse_kinematics.return_value = (0, forward_joints)
    assert rm65_controller.check_joint_limits(forward_joints, current_joints=scan_pose_joints) is True
    ok = rm65_controller.move_l(100, 100, 100, 0, 0, 0, speed=20)
    assert ok is True

    # 2. 轨迹异常后摆，逆解 J2 增大 (如 84.5° > 82.227°) -> 拦截拒绝
    backward_joints = [0.56, 84.5, -158.0, 2.79, 156.0, 94.1]
    rm65_controller.arm.rm_algo_inverse_kinematics.return_value = (0, backward_joints)
    assert rm65_controller.check_joint_limits(backward_joints, current_joints=scan_pose_joints) is False




