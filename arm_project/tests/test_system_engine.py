import time
import pytest
import numpy as np
from unittest.mock import MagicMock
from src.core.system_engine import SystemEngine
from src.communication.host_server import command_queue

@pytest.fixture
def mock_engine(mocker):
    # Mock config
    mock_cfg = {
        'network': {'tcp_server': {'host': '127.0.0.1', 'port': 9000}},
        'robot': {
            'controller_ip': '127.0.0.1',
            'controller_port': 8080,
            'home_pose': [88.0, 92.0, -165.0, 4.0, 163.0, 4.0],
            'scan_pose': [0.5, 77.8, -129.4, 3.6, 132.7, 94.2],
            'soft_limits': {'x_min': -500, 'x_max': 700, 'y_min': -500, 'y_max': 500, 'z_min': 0, 'z_max': 800},
            'active_scanning': {
                'amplitude_z_mm': 50.0,
                'frequency': 1.0,
                'speed': 15.0,
                'z_min': 50.0,
                'z_max': 750.0
            }
        },
        'vision': {
            'camera': {'color_width': 1280, 'color_height': 720, 'depth_width': 848, 'depth_height': 480, 'fps': 30},
            'model_path': 'dummy.engine',
            'apf': {'max_z_mm': 300, 'safe_distance_mm': 150}
        },
        'calibration': {'T_end_to_camera': np.eye(4).tolist()}
    }
    mocker.patch('src.core.system_engine.get_config', return_value=mock_cfg)
    mocker.patch('src.control.rm65_api.get_config', return_value=mock_cfg)
    mocker.patch('src.control.motion_plan.get_config', return_value=mock_cfg)
    mocker.patch('src.vision.camera.get_config', return_value=mock_cfg)
    mocker.patch('src.calibration.hand_eye.get_config', return_value=mock_cfg)

    # Mock hardware and IO
    mocker.patch('src.control.rm65_api.RoboticArm')
    mocker.patch('src.vision.camera.rs')
    mocker.patch('src.vision.detector.YOLO')

    engine = SystemEngine()
    engine.arm = MagicMock()
    engine.arm.move_j.return_value = True
    engine.arm.move_l.return_value = True
    engine.arm.pause.return_value = True
    engine.arm.is_busy.return_value = False
    engine.arm.get_current_pose.return_value = [100.0, 200.0, 300.0, 0.0, 0.0, 0.0]

    engine.cam = MagicMock()
    engine.cam.get_frames.return_value = (np.ones((480, 848), dtype=np.uint16), np.zeros((720, 1280, 3), dtype=np.uint8), None)
    engine.cam.intrinsics = MagicMock()

    engine.detector = MagicMock()
    return engine

def test_goto_moves_to_scan_pose_first(mock_engine):
    """测试收到 goto 指令后，机械臂先执行 move_j 前往 scan_pose 位姿，然后开启扫描状态"""
    while not command_queue.empty():
        command_queue.get()

    handler = MagicMock()
    command_queue.put({"action": "goto", "point": 1, "handler": handler})

    mock_engine.process_tcp_commands()

    # 验证机械臂先调用 move_j 前往 scan_pose，且带有 block=1 确保完全就位
    expected_scan_pose = [0.5, 77.8, -129.4, 3.6, 132.7, 94.2]
    mock_engine.arm.move_j.assert_called_once_with(expected_scan_pose, speed=20, block=1)

    # 验证扫描状态变量已设置
    assert mock_engine.is_approaching is True
    assert mock_engine.current_target_index == 0
    assert mock_engine.current_handler == handler
    assert mock_engine.scan_baseline_pose_base == [100.0, 200.0, 300.0, 0.0, 0.0, 0.0]
    assert mock_engine.scan_start_time is not None

def test_goto_scan_pose_failure(mock_engine):
    """测试若前往 scan_pose 失败，系统发送 fail 响应并不启动扫描"""
    while not command_queue.empty():
        command_queue.get()

    mock_engine.arm.move_j.return_value = False
    handler = MagicMock()
    command_queue.put({"action": "goto", "point": 2, "handler": handler})

    mock_engine.process_tcp_commands()

    mock_engine.arm.move_j.assert_called_once()
    assert mock_engine.is_approaching is False
    handler.send_fail.assert_called_once_with("移动至初始扫描位姿失败")

def test_goto_point_4_indexing(mock_engine):
    """测试上位机下发 point=4 时，系统正确映射为 index=3 (从上至下第 4 根电缆)"""
    while not command_queue.empty():
        command_queue.get()

    handler = MagicMock()
    command_queue.put({"action": "goto", "point": 4, "handler": handler})
    mock_engine.process_tcp_commands()
    assert mock_engine.current_target_index == 3

def test_active_scanning_around_scan_baseline(mock_engine):
    """测试视野不完整时，系统沿相机垂直轴微调扫描，严禁左右摆臂且末端姿态保持恒定"""
    from scipy.spatial.transform import Rotation as R
    # 设定到达 scan_pose 时的基准位姿
    baseline = [150.0, 250.0, 350.0, 0.1, 0.2, 0.3]
    mock_engine.scan_baseline_pose_base = baseline
    mock_engine.scan_start_time = time.time() - 0.5
    mock_engine.is_approaching = True

    # 模拟视野不完整状态 (INCOMPLETE)
    mock_engine.detector.process_frame.return_value = {"status": "INCOMPLETE", "cables": []}

    mock_engine.run_control_step()

    # 验证 move_l 被调用
    mock_engine.arm.move_l.assert_called_once()
    args, kwargs = mock_engine.arm.move_l.call_args
    x, y, z, rx, ry, rz = args[:6]

    # 1. 验证旋转姿态保持与 scan_baseline_pose_base 完全一致
    assert rx == baseline[3]
    assert ry == baseline[4]
    assert rz == baseline[5]

    # 2. 验证水平左右位移严格为 0 (严禁左右摆臂)
    R_base_end = R.from_euler('xyz', baseline[3:]).as_matrix()
    T_end_cam = np.array(mock_engine.cfg.get('calibration', {}).get('T_end_to_camera', np.eye(4)))
    R_base_cam = R_base_end @ T_end_cam[:3, :3]
    u_horizontal = R_base_cam[:, 0]
    
    delta_pos = np.array([x, y, z]) - np.array(baseline[:3])
    horizontal_displacement = np.dot(delta_pos, u_horizontal)
    assert abs(horizontal_displacement) < 1e-3

def test_goback_resets_scan_state(mock_engine):
    """测试 goback 指令复位至 home_pose 并清空扫描基准状态"""
    while not command_queue.empty():
        command_queue.get()

    mock_engine.is_approaching = True
    mock_engine.scan_baseline_pose_base = [100.0, 200.0, 300.0, 0.0, 0.0, 0.0]
    mock_engine.scan_start_time = time.time()

    handler = MagicMock()
    command_queue.put({"action": "goback", "handler": handler})

    mock_engine.process_tcp_commands()

    expected_home_pose = [88.0, 92.0, -165.0, 4.0, 163.0, 4.0]
    mock_engine.arm.move_j.assert_called_once_with(expected_home_pose, speed=20, block=1)
    assert mock_engine.is_approaching is False
    assert mock_engine.scan_baseline_pose_base is None
    assert mock_engine.scan_start_time is None
    handler.send_success.assert_called_once_with("机械臂复位成功")

def test_active_scanning_timeout_and_reset(mock_engine):
    """测试 Active Scanning 超时未识别到电缆时停止扫描、复位机械臂，并向上位机返回 fail"""
    mock_engine.cfg['robot']['active_scanning']['max_scan_time_sec'] = 10.0
    mock_engine.is_approaching = True
    # 模拟主动扫描已耗时 12 秒 (超过 10 秒限制)
    mock_engine.active_scan_start_time = time.time() - 12.0
    mock_engine.scan_baseline_pose_base = [100.0, 200.0, 300.0, 0.0, 0.0, 0.0]

    handler = MagicMock()
    mock_engine.current_handler = handler

    # 视觉识别返回未识别/不完整
    mock_engine.detector.process_frame.return_value = {"status": "INCOMPLETE", "cables": []}

    mock_engine.run_control_step()

    # 1. 验证扫描状态已终止
    assert mock_engine.is_approaching is False
    assert mock_engine.active_scan_start_time is None
    assert mock_engine.scan_baseline_pose_base is None

    # 2. 验证机械臂执行暂停并复位至 home_pose
    mock_engine.arm.pause.assert_called_once()
    expected_home_pose = [88.0, 92.0, -165.0, 4.0, 163.0, 4.0]
    mock_engine.arm.move_j.assert_called_once_with(expected_home_pose, speed=20, block=1)

    # 3. 验证复位成功后向上位机发送 fail: 没有识别到电缆
    handler.send_fail.assert_called_once_with("没有识别到电缆")
    assert mock_engine.current_handler is None

def test_pause_during_active_scanning(mock_engine):
    """测试 Active Scanning 期间上位机发送 pause 指令时，能平滑暂停并成功响应上位机"""
    while not command_queue.empty():
        command_queue.get()

    handler = MagicMock()
    mock_engine.is_approaching = True
    mock_engine.current_handler = handler
    mock_engine.active_scan_start_time = time.time()
    mock_engine.scan_baseline_pose_base = [100.0, 200.0, 300.0, 0.0, 0.0, 0.0]

    # 上位机在同一连接下发 pause 指令
    command_queue.put({"action": "pause", "handler": handler})

    mock_engine.process_tcp_commands()

    # 验证扫描状态已被打断且未误向当前 handler 发送 fail
    assert mock_engine.is_approaching is False
    assert mock_engine.active_scan_start_time is None
    assert mock_engine.scan_baseline_pose_base is None
    mock_engine.arm.pause.assert_called_once()
    handler.send_fail.assert_not_called()
    handler.send_success.assert_called_once_with("机械臂暂停成功")
    assert mock_engine.current_handler is None

def test_emergency_pause_hook_immediate_halt(mock_engine):
    """测试 TCP 线程直接触发的即时急停钩子能瞬间重置扫描状态并下发硬件缓停"""
    mock_engine.is_approaching = True
    mock_engine.active_scan_start_time = time.time()
    mock_engine.scan_baseline_pose_base = [100.0, 200.0, 300.0, 0.0, 0.0, 0.0]

    mock_engine._on_emergency_pause()

    assert mock_engine.is_approaching is False
    assert mock_engine.active_scan_start_time is None
    assert mock_engine.scan_baseline_pose_base is None
    mock_engine.arm.pause.assert_called_once()

def test_control_step_bypassed_when_not_approaching(mock_engine):
    """测试当 is_approaching=False (暂停或待机) 时，run_control_step 立即跳过不执行任何动作"""
    mock_engine.is_approaching = False
    mock_engine.run_control_step()

    # 验证未获取相机帧，也未调用探测器与机械臂
    mock_engine.cam.get_frames.assert_not_called()
    mock_engine.detector.process_frame.assert_not_called()
    mock_engine.arm.move_l.assert_not_called()

def test_cable_locked_after_complete_detection(mock_engine):
    """测试识别并剔除最上方备用电缆 (status=COMPLETE) 后，系统锁定目标状态 (cable_locked=True)"""
    mock_engine.is_approaching = True
    mock_engine.current_target_index = 0
    mock_engine.cable_locked = False

    fake_cables = [
        {"bbox": [100, 200, 400, 250], "pos_camera": np.array([100.0, 50.0, 300.0])},
        {"bbox": [100, 300, 400, 350], "pos_camera": np.array([100.0, 100.0, 300.0])},
        {"bbox": [100, 400, 400, 450], "pos_camera": np.array([100.0, 150.0, 300.0])}
    ]
    mock_engine.detector.process_frame.return_value = {"status": "COMPLETE", "cables": fake_cables}
    mock_engine.planner = MagicMock()
    mock_engine.planner.plan_next_step.return_value = np.array([10.0, 5.0, 20.0])
    mock_engine.calibrator = MagicMock()
    mock_engine.calibrator.rotate_vector_camera_to_base.return_value = np.array([10.0, 5.0, 20.0])

    mock_engine.run_control_step()

    assert mock_engine.cable_locked is True
    assert mock_engine.last_move_vector_base is not None
    assert mock_engine.last_target_pos_camera is not None
    mock_engine.arm.move_l.assert_called_once()

def test_locked_target_does_not_timeout_on_incomplete_view(mock_engine):
    """测试已锁定目标后 (cable_locked=True)，后续偶发视野不完整时不进行上下微调，沿当前位姿保持逼近，不触发超时复位，不发送 fail"""
    mock_engine.cfg['robot']['active_scanning']['max_scan_time_sec'] = 10.0
    mock_engine.is_approaching = True
    mock_engine.cable_locked = True
    mock_engine.last_move_vector_base = np.array([5.0, 0.0, 10.0])
    # 模拟过去的时间早已超过 10s
    mock_engine.active_scan_start_time = time.time() - 30.0

    handler = MagicMock()
    mock_engine.current_handler = handler

    # 视觉识别返回未识别/不完整 (如逼近过程中局部遮挡或未达4层)
    mock_engine.detector.process_frame.return_value = {"status": "INCOMPLETE", "cables": []}

    mock_engine.run_control_step()

    # 1. 验证目标依然保持锁定与逼近，未被中断
    assert mock_engine.is_approaching is True
    assert mock_engine.cable_locked is True

    # 2. 验证未触发超时复位 (未调用 move_j 复位到 home_pose)
    mock_engine.arm.move_j.assert_not_called()

    # 3. 验证未向上位机发送 fail
    handler.send_fail.assert_not_called()

    # 4. 验证执行了沿当前位姿与逼近方向平稳推进的 move_l (无上下微调振荡)
    mock_engine.arm.move_l.assert_called_once()
    args, kwargs = mock_engine.arm.move_l.call_args
    # 验证推进增量方向与 last_move_vector_base 严格共线 (不含垂直正弦摆动分量)
    delta_pos = np.array([args[0] - 100.0, args[1] - 200.0, args[2] - 300.0])
    unit_delta = delta_pos / np.linalg.norm(delta_pos)
    unit_expected = mock_engine.last_move_vector_base / np.linalg.norm(mock_engine.last_move_vector_base)
    np.testing.assert_allclose(unit_delta, unit_expected, atol=1e-4)

def test_approaching_waits_for_busy_step(mock_engine):
    """测试当机械臂正在执行上一步轨迹时，系统平滑等待到位，不重复下发 move_l 指令打断运动"""
    mock_engine.is_approaching = True
    mock_engine.current_target_index = 0
    mock_engine.cable_locked = True
    mock_engine._last_cmd_target_base = np.array([200.0, 200.0, 300.0])
    mock_engine._last_step_start_time = time.time()
    mock_engine.arm.get_current_pose.return_value = [100.0, 200.0, 300.0, 0.0, 0.0, 0.0]
    mock_engine.arm.is_busy.return_value = True

    fake_cables = [
        {"bbox": [100, 200, 400, 250], "pos_camera": np.array([100.0, 50.0, 300.0])},
        {"bbox": [100, 300, 400, 350], "pos_camera": np.array([100.0, 100.0, 300.0])},
        {"bbox": [100, 400, 400, 450], "pos_camera": np.array([100.0, 150.0, 300.0])}
    ]
    mock_engine.detector.process_frame.return_value = {"status": "COMPLETE", "cables": fake_cables}

    mock_engine.run_control_step()

    # 机械臂处于忙碌状态且未到位，move_l 不应被重复调用
    mock_engine.arm.move_l.assert_not_called()


def test_target_approach_stages_and_damping(mock_engine):
    """测试多阶段逼近状态机：粗逼近、姿态对齐、精细下潜贴近与到达判定 (RealMan verticalGrab 规范)"""
    mock_engine.cfg['robot']['target_approach'] = {
        'enabled': True,
        'staged_approach': True,
        'pre_approach_distance_mm': 100.0,
        'final_target_distance_mm': 45.0,
        'reach_tolerance_mm': 50.0,
        'speed_coarse': 12.0,
        'speed_fine': 6.0,
        'target_align_rpy': [1.398, -0.025, 1.605]
    }
    mock_engine.is_approaching = True
    mock_engine.current_target_index = 0
    handler = MagicMock()
    mock_engine.current_handler = handler

    mock_engine.planner = MagicMock()
    mock_engine.calibrator = MagicMock()
    # 模拟 APF 输出向前 100mm (大于限值)
    mock_engine.planner.plan_next_step.return_value = np.array([0.0, 0.0, 100.0])
    mock_engine.calibrator.rotate_vector_camera_to_base.return_value = np.array([0.0, 0.0, 100.0])

    # 阶段 1: 距离 150mm > 100mm (PRE_APPROACH)
    fake_cables = [{"bbox": [0,0,1,1], "pos_camera": np.array([0.0, 0.0, 150.0])}]
    mock_engine.detector.process_frame.return_value = {"status": "COMPLETE", "cables": fake_cables}
    mock_engine.run_control_step()

    assert mock_engine.approach_stage == "PRE_APPROACH"
    mock_engine.arm.move_l.assert_called_once()
    args, kwargs = mock_engine.arm.move_l.call_args
    assert kwargs.get('speed') == 12
    # 验证末端姿态严格锁定对齐为 target_align_rpy
    assert args[3] == pytest.approx(1.398)
    assert args[4] == pytest.approx(-0.025)
    assert args[5] == pytest.approx(1.605)
    # 验证单步限值限制在 50mm
    delta_z = args[2] - 300.0  # current pose z is 300.0
    assert delta_z == pytest.approx(50.0)

    # 阶段 2: 距离 85mm (75mm < 85mm <= 100mm) -> ALIGN_ORIENTATION
    mock_engine.arm.move_l.reset_mock()
    mock_engine._last_cmd_target_base = None
    mock_engine._smoothed_target_cam = None
    fake_cables[0]["pos_camera"] = np.array([0.0, 0.0, 85.0])
    mock_engine.run_control_step()

    assert mock_engine.approach_stage == "ALIGN_ORIENTATION"
    mock_engine.arm.move_l.assert_called_once()
    args, kwargs = mock_engine.arm.move_l.call_args
    assert kwargs.get('speed') == 9  # int(max(6, 12 * 0.8)) = 9
    delta_z = args[2] - 300.0
    assert delta_z == pytest.approx(30.0)  # max_step=30.0

    # 阶段 3: 距离 60mm (50mm < 60mm <= 75mm) -> FINAL_APPROACH
    mock_engine.arm.move_l.reset_mock()
    mock_engine._last_cmd_target_base = None
    mock_engine._smoothed_target_cam = None
    fake_cables[0]["pos_camera"] = np.array([0.0, 0.0, 60.0])
    mock_engine.run_control_step()

    assert mock_engine.approach_stage == "FINAL_APPROACH"
    mock_engine.arm.move_l.assert_called_once()
    args, kwargs = mock_engine.arm.move_l.call_args
    assert kwargs.get('speed') == 6  # speed_fine
    delta_z = args[2] - 300.0
    # remaining = 60 - 50 = 10mm, step = clip(10 * 0.8, 8, 20) = 8.0mm
    assert delta_z == pytest.approx(8.0)

    # 阶段 4: 距离 45mm <= 50mm -> REACHED
    mock_engine.arm.move_l.reset_mock()
    mock_engine._last_cmd_target_base = None
    mock_engine._smoothed_target_cam = None
    fake_cables[0]["pos_camera"] = np.array([0.0, 0.0, 45.0])
    mock_engine.run_control_step()

    # 到达后重置运动状态并向上位机发送成功
    assert mock_engine.is_approaching is False
    handler.send_success.assert_called_once_with("已成功到达目标电缆位置")
    mock_engine.arm.move_l.assert_not_called()


def test_target_ema_smoothing(mock_engine):
    """测试视觉检测目标点在相机系下的 EMA 指数平滑滤波"""
    mock_engine.cfg['robot']['target_approach'] = {'enabled': True, 'reach_tolerance_mm': 10.0}
    mock_engine.is_approaching = True
    mock_engine.current_target_index = 0

    mock_engine.planner = MagicMock()
    mock_engine.planner.plan_next_step.return_value = np.array([0.0, 0.0, 10.0])
    mock_engine.calibrator = MagicMock()
    mock_engine.calibrator.rotate_vector_camera_to_base.return_value = np.array([0.0, 0.0, 10.0])

    # 第一次检测: [100.0, 0.0, 200.0]
    fake_cables = [{"bbox": [0,0,1,1], "pos_camera": np.array([100.0, 0.0, 200.0])}]
    mock_engine.detector.process_frame.return_value = {"status": "COMPLETE", "cables": fake_cables}
    mock_engine.run_control_step()
    np.testing.assert_allclose(mock_engine._smoothed_target_cam, [100.0, 0.0, 200.0])

    # 第二次检测 (有轻微抖动跳变到 [120.0, 10.0, 210.0])
    mock_engine._last_cmd_target_base = None
    fake_cables = [{"bbox": [0,0,1,1], "pos_camera": np.array([120.0, 10.0, 210.0])}]
    mock_engine.detector.process_frame.return_value = {"status": "COMPLETE", "cables": fake_cables}
    mock_engine.run_control_step()
    # 期望值: 0.7 * [120, 10, 210] + 0.3 * [100, 0, 200] = [84+30, 7+0, 147+60] = [114.0, 7.0, 207.0]
    np.testing.assert_allclose(mock_engine._smoothed_target_cam, [114.0, 7.0, 207.0])


def test_partial_view_continuous_approach_and_reach(mock_engine):
    """测试在近景特写局部视野 (PARTIAL) 下，系统能持续基于基座坐标匹配追踪目标并成功判定到达"""
    mock_engine.cfg['robot']['target_approach'] = {
        'enabled': True,
        'staged_approach': True,
        'reach_tolerance_mm': 50.0,
        'pre_approach_distance_mm': 100.0,
        'final_target_distance_mm': 45.0,
        'speed_coarse': 12.0,
        'speed_fine': 6.0,
        'target_align_rpy': [0.0, 0.0, 0.0]
    }
    mock_engine.is_approaching = True
    mock_engine.current_target_index = 0
    handler = MagicMock()
    mock_engine.current_handler = handler

    mock_engine.planner = MagicMock()
    mock_engine.planner.plan_next_step.return_value = np.array([0.0, 0.0, 10.0])
    mock_engine.calibrator = MagicMock()
    mock_engine.calibrator.rotate_vector_camera_to_base.return_value = np.array([0.0, 0.0, 10.0])
    # 让 transform_camera_to_base 随机械臂当前位姿动态映射 (真实手眼齐次变换)
    mock_engine.calibrator.transform_camera_to_base.side_effect = lambda pt, pose: np.array([pose[0] + pt[0], pose[1] + pt[1], pose[2] + pt[2]])
    mock_engine.calibrator.transform_base_to_camera.side_effect = lambda pt, pose: np.array([pt[0] - pose[0], pt[1] - pose[1], pt[2] - pose[2]])

    # 1. 远景完整视野下锁定目标
    cables_step1 = [
        {"bbox": [10, 20, 30, 40], "pos_camera": np.array([0.0, 0.0, 200.0])},
        {"bbox": [10, 50, 30, 70], "pos_camera": np.array([0.0, 50.0, 200.0])}
    ]
    mock_engine.detector.process_frame.return_value = {"status": "COMPLETE", "cables": cables_step1}
    mock_engine.run_control_step()

    assert mock_engine.cable_locked is True
    assert mock_engine.target_pos_base is not None
    assert mock_engine.is_approaching is True

    # 2. 逼近过程中局部视野 (PARTIAL)，例如上位备用线缆出画，仅能看到 2 根
    # 模拟机械臂向前移动 120mm，法兰位姿 Z 变为 420.0
    mock_engine.arm.get_current_pose.return_value = [100.0, 200.0, 420.0, 0.0, 0.0, 0.0]
    mock_engine.arm.move_l.reset_mock()
    mock_engine._last_cmd_target_base = None
    mock_engine._smoothed_target_cam = None
    cables_step2 = [
        {"bbox": [10, 50, 30, 70], "pos_camera": np.array([0.0, 0.0, 80.0])}  # 目标电缆在局部视野中持续跟踪
    ]
    mock_engine.detector.process_frame.return_value = {"status": "PARTIAL", "cables": cables_step2}
    mock_engine.run_control_step()

    # 验证在 PARTIAL 下正常执行了逼近运动，没有退回扫描状态
    assert mock_engine.cable_locked is True
    assert mock_engine.is_approaching is True
    mock_engine.arm.move_l.assert_called_once()

    # 3. 逼近到到达容差以内 (机械臂推进至 460.0，距离 40mm <= 50mm)
    mock_engine.arm.get_current_pose.return_value = [100.0, 200.0, 460.0, 0.0, 0.0, 0.0]
    mock_engine.arm.move_l.reset_mock()
    mock_engine._last_cmd_target_base = None
    mock_engine._smoothed_target_cam = None
    cables_step3 = [
        {"bbox": [10, 50, 30, 70], "pos_camera": np.array([0.0, 0.0, 40.0])}
    ]
    mock_engine.detector.process_frame.return_value = {"status": "PARTIAL", "cables": cables_step3}
    mock_engine.run_control_step()

    assert mock_engine.is_approaching is False
    handler.send_success.assert_called_once_with("已成功到达目标电缆位置")
    mock_engine.arm.move_l.assert_not_called()



def test_fallback_branch_reach_tolerance(mock_engine):
    """测试分支 B1 (纯运动学追踪兜底) 下，若机械臂到达目标容差内，能够正确触发到达退出"""
    mock_engine.cfg['robot']['target_approach'] = {
        'enabled': True,
        'reach_tolerance_mm': 40.0,
        'speed_fine': 5.0,
    }
    mock_engine.is_approaching = True
    mock_engine.cable_locked = True
    mock_engine.target_pos_base = np.array([100.0, 200.0, 330.0])  # 距离当前 pose [100, 200, 300] 30mm
    handler = MagicMock()
    mock_engine.current_handler = handler

    mock_engine.calibrator = MagicMock()
    # 逆投影到相机系，距离为 30mm <= reach_tolerance (40mm)
    mock_engine.calibrator.transform_base_to_camera.return_value = np.array([0.0, 0.0, 30.0])

    # 模拟未检测到电缆 (触发分支 B1)
    mock_engine.detector.process_frame.return_value = {"status": "INCOMPLETE", "cables": []}
    mock_engine.run_control_step()

    # 验证到达判定生效，结束逼近并发送成功
    assert mock_engine.is_approaching is False
    handler.send_success.assert_called_once_with("已成功到达目标电缆位置")
    mock_engine.arm.move_l.assert_not_called()


def test_soft_limits_x_boundary_and_warning(mock_engine):
    """测试笛卡尔软限位放宽至 700mm 后允许机械臂伸向电缆柜深处 (X > 500mm)，并对超限指令发出警告拦截"""
    mock_engine.cfg['robot']['target_approach'] = {
        'enabled': True,
        'reach_tolerance_mm': 50.0,
        'pre_approach_distance_mm': 100.0,
        'speed_coarse': 12.0
    }
    mock_engine.is_approaching = True
    mock_engine.current_target_index = 0
    mock_engine.cable_locked = True
    mock_engine.target_pos_base = np.array([690.0, 200.0, 300.0])

    # 1. 机械臂当前 X=500mm，朝向目标前移 40mm 至 X=540mm
    mock_engine.arm.get_current_pose.return_value = [500.0, 200.0, 300.0, 0.0, 0.0, 0.0]
    mock_engine.planner = MagicMock()
    mock_engine.planner.plan_next_step.return_value = np.array([40.0, 0.0, 0.0])
    mock_engine.calibrator = MagicMock()
    mock_engine.calibrator.rotate_vector_camera_to_base.return_value = np.array([40.0, 0.0, 0.0])
    mock_engine.calibrator.transform_base_to_camera.return_value = np.array([150.0, 0.0, 0.0])

    mock_engine.detector.process_frame.return_value = {"status": "PARTIAL", "cables": []}
    mock_engine.run_control_step()

    # 验证 MoveL 下发的目标 X 为 540.0mm (不再被卡在 500mm)
    mock_engine.arm.move_l.assert_called_once()
    args, _ = mock_engine.arm.move_l.call_args
    assert args[0] == pytest.approx(540.0)

    # 2. 模拟超限尝试 (目标期望 X=750mm > x_max 700mm)
    mock_engine.arm.move_l.reset_mock()
    mock_engine._last_cmd_target_base = None
    mock_engine._smoothed_target_cam = None
    mock_engine.arm.get_current_pose.return_value = [680.0, 200.0, 300.0, 0.0, 0.0, 0.0]
    mock_engine.planner.plan_next_step.return_value = np.array([50.0, 0.0, 0.0])
    mock_engine.calibrator.rotate_vector_camera_to_base.return_value = np.array([50.0, 0.0, 0.0])
    mock_engine.calibrator.transform_base_to_camera.return_value = np.array([100.0, 0.0, 0.0])

    mock_engine.run_control_step()

    # 验证截断至 700.0mm
    mock_engine.arm.move_l.assert_called_once()
    args, _ = mock_engine.arm.move_l.call_args
    assert args[0] == pytest.approx(700.0)


def test_point_1_locked_target_does_not_jump_to_adjacent_layer(mock_engine):
    """测试核心防呆机制：下发 point=1 (上工作电缆) 锁定后，
    在靠近电缆、顶层备用电缆出画并检测到局部多层时，
    系统利用 40mm 空间门限牢牢锚定目标，绝对不会跳变漂移至第 3 层 (中工作电缆)"""
    mock_engine.cfg['robot']['target_approach'] = {
        'enabled': True,
        'staged_approach': True,
        'reach_tolerance_mm': 200.0,
        'pre_approach_distance_mm': 350.0,
        'speed_coarse': 12.0,
        'speed_fine': 6.0,
        'target_align_rpy': [1.398, -0.025, 1.605]
    }
    mock_engine.is_approaching = True
    mock_engine.current_target_index = 0  # point=1 -> index 0 (上工作电缆)
    handler = MagicMock()
    mock_engine.current_handler = handler

    mock_engine.planner = MagicMock()
    mock_engine.planner.plan_next_step.return_value = np.array([30.0, 0.0, 0.0])
    mock_engine.calibrator = MagicMock()
    mock_engine.calibrator.rotate_vector_camera_to_base.return_value = np.array([30.0, 0.0, 0.0])
    mock_engine.calibrator.transform_camera_to_base.side_effect = lambda pt, pose: np.array([pose[0] + pt[0], pose[1] + pt[1], pose[2] + pt[2]])
    mock_engine.calibrator.transform_base_to_camera.side_effect = lambda pt, pose: np.array([pt[0] - pose[0], pt[1] - pose[1], pt[2] - pose[2]])

    # 1. 在 scan_pose (位姿 [45, 0, 400]) 首次检测到 3 根工作电缆 (备用已在 detector 中剔除)
    # 上工作电缆 (index 0, point 1): Camera坐标 [600, 0, 600]，对应 Base坐标 [645, 0, 1000]
    # 中工作电缆 (index 1, point 2): Camera坐标 [600, -100, 600]，对应 Base坐标 [645, -100, 1000] (层间距 100mm)
    # 下工作电缆 (index 2, point 3): Camera坐标 [600, -200, 600]，对应 Base坐标 [645, -200, 1000]
    mock_engine.arm.get_current_pose.return_value = [45.0, 0.0, 400.0, 1.398, -0.025, 1.605]
    scan_cables = [
        {"bbox": [100, 200, 400, 250], "pos_camera": np.array([600.0, 0.0, 600.0])},     # 上工作电缆
        {"bbox": [100, 300, 400, 350], "pos_camera": np.array([600.0, -100.0, 600.0])},  # 中工作电缆 (第3层)
        {"bbox": [100, 400, 400, 450], "pos_camera": np.array([600.0, -200.0, 600.0])}   # 下工作电缆
    ]
    mock_engine.detector.process_frame.return_value = {"status": "COMPLETE", "cables": scan_cables}
    mock_engine.run_control_step()

    # 验证目标正确锁定为上工作电缆 [645.0, 0.0, 1000.0]
    assert mock_engine.cable_locked is True
    np.testing.assert_allclose(mock_engine.target_pos_base, [645.0, 0.0, 1000.0])
    np.testing.assert_allclose(mock_engine.locked_target_base, [645.0, 0.0, 1000.0])

    # 2. 模拟逼近过程中，机械臂前推至 [300, 0, 400]，最上方备用已出画，
    # 视野中出现了中工作电缆 (第3层，间距 100mm) 与其他候选
    mock_engine.arm.get_current_pose.return_value = [300.0, 0.0, 400.0, 1.398, -0.025, 1.605]
    mock_engine.arm.move_l.reset_mock()
    mock_engine._last_cmd_target_base = None
    mock_engine._smoothed_target_cam = None

    # 此时局部视野中上电缆在 [345, 0, 600]，而第3层中电缆在 [345, -100, 600]
    partial_cables = [
        {"bbox": [100, 120, 400, 170], "pos_camera": np.array([345.0, 0.0, 600.0])},    # 真实的目标上电缆
        {"bbox": [100, 300, 400, 350], "pos_camera": np.array([345.0, -100.0, 600.0])} # 第3层中电缆
    ]
    mock_engine.detector.process_frame.return_value = {"status": "PARTIAL", "cables": partial_cables}
    mock_engine.run_control_step()

    # 验证目标依然牢固锁定在 Y=0 的上电缆，绝对没有跳变漂移至 Y=-100 的第3层中电缆
    assert abs(mock_engine.target_pos_base[1]) < 5.0
    assert abs(mock_engine.target_pos_base[1] - (-100.0)) > 90.0







