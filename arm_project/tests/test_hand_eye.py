import pytest
import numpy as np
from scipy.spatial.transform import Rotation as R
from src.calibration.hand_eye import HandEyeCalibrator

@pytest.fixture
def calibrator():
    calc = HandEyeCalibrator()
    # 强制设置一个简单的 T_end_to_camera 矩阵，假设相机只在 Z 轴上向前平移了 100mm，无旋转
    calc.T_end_to_camera = np.eye(4)
    calc.T_end_to_camera[2, 3] = 100.0
    return calc

def test_pose_to_matrix(calibrator):
    # 测试位姿转换，机械臂处于原点，绕 X 轴旋转 90 度 (pi/2)
    pose = [10.0, 20.0, 30.0, np.pi/2, 0.0, 0.0]
    matrix = calibrator.pose_to_matrix(pose)
    
    # 平移向量
    assert np.allclose(matrix[:3, 3], [10.0, 20.0, 30.0])
    
    # 旋转矩阵，绕 X 旋转 pi/2，即 [1, 0, 0; 0, 0, -1; 0, 1, 0]
    expected_rot = R.from_euler('xyz', [np.pi/2, 0.0, 0.0]).as_matrix()
    assert np.allclose(matrix[:3, :3], expected_rot)

def test_transform_camera_to_base(calibrator):
    # 相机观测到目标点 [0, 0, 50] (正前方 50mm)
    point_camera = np.array([0.0, 0.0, 50.0])
    
    # 机械臂处于 [0, 0, 0, 0, 0, 0]
    robot_pose = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    
    # 由于相机位于法兰前方 100mm (Z轴)，相机正前方 50mm 即法兰正前方 150mm
    p_base = calibrator.transform_camera_to_base(point_camera, robot_pose)
    assert np.allclose(p_base, [0.0, 0.0, 150.0])

def test_rotate_vector_camera_to_base(calibrator):
    # 假设 APF 输出需要我们在相机坐标系下往 X 轴移动 10mm
    vector_cam = np.array([10.0, 0.0, 0.0])
    
    # 机械臂绕 Z 轴旋转了 90 度 (pi/2)
    robot_pose = [100.0, 200.0, 300.0, 0.0, 0.0, np.pi/2]
    
    # 旋转向量时不考虑平移，由于机械臂绕 Z 转了 90 度，相机的 X 轴应对应基座的 Y 轴
    vector_base = calibrator.rotate_vector_camera_to_base(vector_cam, robot_pose)
    
    # np.cos(pi/2) ~ 0, np.sin(pi/2) = 1, 所以 [10, 0, 0] 转后应为 [0, 10, 0]
    assert np.allclose(vector_base, [0.0, 10.0, 0.0], atol=1e-6)

def test_realman_math_and_conversions():
    from tools.calibrate_hand_eye import (
        euler_angles_to_rotation_matrix,
        pose_to_homogeneous_matrix,
        decompose_transform,
        convert_camera_to_base,
    )

    rx, ry, rz = 0.1, 0.2, 0.3
    R_rm = euler_angles_to_rotation_matrix(rx, ry, rz)
    expected_rot = R.from_euler('xyz', [rx, ry, rz], degrees=False).as_matrix()
    assert np.allclose(R_rm, expected_rot)

    pose = [100.0, 200.0, 300.0, 0.1, 0.2, 0.3]
    H = pose_to_homogeneous_matrix(pose)
    assert np.allclose(H[:3, 3], [100.0, 200.0, 300.0])
    assert np.allclose(H[:3, :3], expected_rot)

    # 测试分解逆算
    t_out, rx_out, ry_out, rz_out = decompose_transform(H)
    assert np.allclose(t_out, [100.0, 200.0, 300.0])
    assert np.isclose(rx_out, 0.1, atol=1e-5)
    assert np.isclose(ry_out, 0.2, atol=1e-5)
    assert np.isclose(rz_out, 0.3, atol=1e-5)

    # 测试官方 convert 函数 3D 点转换
    T_cam2end = np.eye(4)
    T_cam2end[2, 3] = 50.0  # 相机在末端前方 50mm
    cam_pt = [0.0, 0.0, 100.0]  # 物体在相机前方 100mm
    robot_pose = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    base_pt = convert_camera_to_base(cam_pt, robot_pose, T_cam2end)
    assert np.allclose(base_pt, [0.0, 0.0, 150.0])


def test_transform_base_to_camera(calibrator):
    # 相机观测到目标点 [10.0, -20.0, 50.0]
    point_camera = np.array([10.0, -20.0, 50.0])
    robot_pose = [50.0, -30.0, 100.0, 0.1, -0.2, 0.3]

    # 变换到基座坐标系
    p_base = calibrator.transform_camera_to_base(point_camera, robot_pose)

    # 逆变换回相机坐标系
    p_cam_recovered = calibrator.transform_base_to_camera(p_base, robot_pose)

    assert np.allclose(p_cam_recovered, point_camera, atol=1e-5)


