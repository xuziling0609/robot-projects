#!/usr/bin/env python3
"""
睿尔曼 RM65 机械臂手眼标定工具 (眼在手上 Eye-in-Hand 模式)
参考睿尔曼官方开发指南: https://develop.realman-robotics.com/AI/developerGuide/hand/

主要功能:
1. 数据采集 (collect_data): 同步采集 D435 相机图像与机械臂末端位姿 (支持 GUI 与无头 Headless 终端模式)
2. 相机标定 (calibrateCamera): 标定相机内参及每张图在相机系下的位姿 (rvecs, tvecs)
3. 机械臂位姿转换 (poses_main): 将末端位姿转换为末端相对于基座的旋转矩阵与平移向量 (Z-Y-X 欧拉角)
4. 手眼标定求解 (cv2.calibrateHandEye): 求解相机相对于末端的变换关系 T_cam2end
5. 精度验证与自检: 检查旋转充分度 (≥30°) 与标定板基座重构一致性误差
6. 自动写回配置文件: 将标定结果同步至 config/settings.yaml
7. 坐标转换验证 (convert): 提供相机坐标系目标点/位姿到基座坐标系的换算验证
"""

import os
import sys
import glob
import json
import csv
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Tuple, List, Optional, Union

# 确保项目根目录在 sys.path 中，支持在任意工作目录下运行
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import cv2
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("calibrate_hand_eye")


# ==============================================================================
# 1. 睿尔曼官方数学转换函数 (对齐官方文档标准)
# ==============================================================================

def euler_angles_to_rotation_matrix(rx: float, ry: float, rz: float) -> np.ndarray:
    """
    计算欧拉角对应的旋转矩阵 (对齐睿尔曼开发文档标准: R = Rz @ Ry @ Rx)
    旋转顺序为内旋 Z-Y-X 或外旋 X-Y-Z。
    
    :param rx, ry, rz: 绕 X, Y, Z 轴的旋转角度 (弧度 rad)
    :return: 3x3 旋转矩阵
    """
    Rx = np.array([
        [1.0, 0.0, 0.0],
        [0.0, np.cos(rx), -np.sin(rx)],
        [0.0, np.sin(rx), np.cos(rx)]
    ], dtype=np.float64)

    Ry = np.array([
        [np.cos(ry), 0.0, np.sin(ry)],
        [0.0, 1.0, 0.0],
        [-np.sin(ry), 0.0, np.cos(ry)]
    ], dtype=np.float64)

    Rz = np.array([
        [np.cos(rz), -np.sin(rz), 0.0],
        [np.sin(rz), np.cos(rz), 0.0],
        [0.0, 0.0, 1.0]
    ], dtype=np.float64)

    return Rz @ Ry @ Rx


def pose_to_homogeneous_matrix(pose: Union[list, np.ndarray]) -> np.ndarray:
    """
    将机械臂末端位姿 [x, y, z, rx, ry, rz] 转换为 4x4 齐次变换矩阵。
    
    :param pose: [x, y, z, rx, ry, rz]，其中平移单位为 mm (或 m)，旋转为弧度
    :return: 4x4 齐次矩阵
    """
    x, y, z, rx, ry, rz = pose
    R = euler_angles_to_rotation_matrix(rx, ry, rz)
    t = np.array([x, y, z], dtype=np.float64).reshape(3, 1)

    H = np.eye(4, dtype=np.float64)
    H[:3, :3] = R
    H[:3, 3] = t[:, 0]
    return H


# 保留别名兼容原有接口
pose_to_matrix = pose_to_homogeneous_matrix


def decompose_transform(matrix: np.ndarray) -> Tuple[np.ndarray, float, float, float]:
    """
    将 4x4 齐次矩阵分解为平移向量与欧拉角 (rx, ry, rz)，完全对齐睿尔曼开发文档。
    
    :param matrix: 4x4 齐次变换矩阵
    :return: (translation, rx, ry, rz)，rx, ry, rz 为弧度
    """
    translation = matrix[:3, 3]
    rotation = matrix[:3, :3]

    sy = np.sqrt(rotation[0, 0] * rotation[0, 0] + rotation[1, 0] * rotation[1, 0])
    singular = sy < 1e-6

    if not singular:
        rx = np.arctan2(rotation[2, 1], rotation[2, 2])
        ry = np.arctan2(-rotation[2, 0], sy)
        rz = np.arctan2(rotation[1, 0], rotation[0, 0])
    else:
        rx = np.arctan2(-rotation[1, 2], rotation[1, 1])
        ry = np.arctan2(-rotation[2, 0], sy)
        rz = 0.0

    return translation, float(rx), float(ry), float(rz)


def matrix_to_list(T: np.ndarray) -> list:
    """将矩阵转换为嵌套列表以保存至 YAML"""
    return T.tolist()


def convert_camera_to_base(
    obj_camera_coords: Union[list, np.ndarray],
    end_effector_pose: Union[list, np.ndarray],
    T_camera_to_end: np.ndarray
) -> Union[list, Tuple[np.ndarray, float, float, float]]:
    """
    对齐睿尔曼开发文档中的 convert() 函数:
    通过手眼外参矩阵，将相机坐标系下的点/位姿转换到机械臂基坐标系。
    
    公式:
      P_end = T_camera_to_end @ P_camera
      P_base = T_base_to_end @ P_end
    
    :param obj_camera_coords: 相机系下的 3D 坐标 [x, y, z] 或 6D 位姿 [x, y, z, rx, ry, rz]
    :param end_effector_pose: 当前机械臂末端在基座系的位姿 [x, y, z, rx, ry, rz]
    :param T_camera_to_end: 标定得到的 4x4 相机相对于末端的变换矩阵
    :return: 基座坐标系下的坐标 [x, y, z] 或分解位姿 (translation, rx, ry, rz)
    """
    T_base_to_end = pose_to_homogeneous_matrix(end_effector_pose)

    if len(obj_camera_coords) == 3:
        # 单个 3D 点齐次坐标转换
        obj_cam_homo = np.append(obj_camera_coords, [1.0])
        obj_end_homo = T_camera_to_end.dot(obj_cam_homo)
        obj_base_homo = T_base_to_end.dot(obj_end_homo)
        return list(obj_base_homo[:3])
    elif len(obj_camera_coords) == 6:
        # 6D 完整位姿转换
        T_obj_to_cam = pose_to_homogeneous_matrix(obj_camera_coords)
        T_obj_to_end = T_camera_to_end.dot(T_obj_to_cam)
        T_obj_to_base = T_base_to_end.dot(T_obj_to_end)
        return decompose_transform(T_obj_to_base)
    else:
        raise ValueError(f"目标坐标维度必须为 3 或 6，当前输入长度为: {len(obj_camera_coords)}")


# ==============================================================================
# 2. 睿尔曼手眼标定核心算法 (Eye-in-Hand / 眼在手上)
# ==============================================================================

METHOD_DICT = {
    "tsai": cv2.CALIB_HAND_EYE_TSAI,
    "park": cv2.CALIB_HAND_EYE_PARK,
    "horaud": cv2.CALIB_HAND_EYE_HORAUD,
    "andreff": cv2.CALIB_HAND_EYE_ANDREFF,
    "daniilidis": cv2.CALIB_HAND_EYE_DANIILIDIS,
}


def load_pose_data(img_path: str) -> Optional[list]:
    """
    灵活读取图像对应的机械臂末端位姿数据。
    支持:
    1. 同名 json 文件: frame_01.png -> frame_01.json
    2. pose_XX.json: frame_01.png -> pose_01.json
    3. 同目录下 poses.json 或 poses.csv
    """
    base_name = os.path.splitext(img_path)[0]
    dir_name = os.path.dirname(img_path)
    file_stem = os.path.basename(base_name)

    # 尝试 1: 直接对应同名 .json
    json_path = base_name + ".json"
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and "pose" in data:
                    return data["pose"]
                elif isinstance(data, list) and len(data) == 6:
                    return data
        except Exception as e:
            logger.warning(f"解析 {json_path} 出错: {e}")

    # 尝试 2: pose_XX.json
    digits = "".join([c for c in file_stem if c.isdigit()])
    if digits:
        pose_json = os.path.join(dir_name, f"pose_{digits}.json")
        if os.path.exists(pose_json):
            try:
                with open(pose_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("pose", data)
            except Exception:
                pass

    return None


def calibrate_hand_eye(
    data_dir: str = "data/calibration_samples",
    pattern_size: Tuple[int, int] = (11, 8),
    square_size: float = 20.0,
    unit: str = "mm",
    method_name: str = "tsai",
    config_path: str = "config/settings.yaml"
) -> Optional[np.ndarray]:
    """
    手眼标定核心处理流程 (完全对齐睿尔曼官方标准):
    1. 遍历采集图片检测标定板角点 (findChessboardCorners + cornerSubPix)
    2. 运行 cv2.calibrateCamera 计算真实相机内参 (mtx, dist) 及标定板外参 (rvecs, tvecs)
    3. 处理机械臂末端位姿 (poses_main): 计算 R_tool, t_tool，并自检旋转充分度
    4. 运行 cv2.calibrateHandEye 计算相机相对于末端的旋转与平移 (R_cam2end, t_cam2end)
    5. 计算基座系下重投影与手眼一致性误差评估
    6. 将标定结果同步保存至全局配置文件 config/settings.yaml
    """
    if not os.path.exists(data_dir):
        logger.error(f"标定数据目录不存在: {data_dir}")
        return None

    # 1. 查找所有标定图片
    img_files = []
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.bmp"):
        img_files.extend(glob.glob(os.path.join(data_dir, ext)))
    img_files = sorted(img_files)

    if not img_files:
        logger.error(f"在目录 {data_dir} 中未找到任何标定图像！")
        return None

    logger.info(f"找到 {len(img_files)} 张标定图像，开始提取角点 (规格: {pattern_size[0]}x{pattern_size[1]}, 单格尺寸: {square_size}{unit})...")

    # 准备标定板 3D 物理点
    # 对齐官方: L * np.mgrid[0:XX, 0:YY]
    cols, rows = pattern_size
    objp = np.zeros((cols * rows, 3), np.float32)
    objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)
    objp = objp * square_size

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    obj_points = []   # 3D 物理点列表
    img_points = []   # 2D 像平面像素点列表
    valid_poses = []  # 成功检测角点对应的机械臂位姿
    valid_img_paths = []
    img_shape = None

    # 2. 遍历图像获取角点
    for img_path in img_files:
        pose = load_pose_data(img_path)
        if pose is None or len(pose) != 6:
            logger.warning(f"跳过 {os.path.basename(img_path)}: 未找到有效对应的 6 自由度位姿数据")
            continue

        img = cv2.imread(img_path)
        if img is None:
            continue

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if img_shape is None:
            img_shape = gray.shape[::-1]  # (width, height)

        ret, corners = cv2.findChessboardCorners(
            gray, (cols, rows),
            cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
        )

        if ret:
            corners2 = cv2.cornerSubPix(gray, corners, (5, 5), (-1, -1), criteria)
            obj_points.append(objp)
            img_points.append(corners2)
            valid_poses.append(pose)
            valid_img_paths.append(img_path)
            logger.info(f"  [✓] 成功识别角点: {os.path.basename(img_path)}")
        else:
            logger.warning(f"  [✗] 未能检测到完整棋盘格角点: {os.path.basename(img_path)}")

    valid_count = len(obj_points)
    logger.info(f"成功提取有效位姿/图像对: {valid_count} 组")

    if valid_count < 4:
        logger.error(f"有效数据仅 {valid_count} 组 (至少需要 4 组，官方推荐 15~20 组)，无法进行手眼标定求解！")
        return None

    # 3. 相机内参标定 (对齐官方教程 compute_in_hand.py 第 2 步)
    logger.info("正在执行相机内参标定 (cv2.calibrateCamera)...")
    ret_cam, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
        obj_points, img_points, img_shape, None, None
    )
    logger.info(f"相机标定重投影均方误差 (RMS): {ret_cam:.4f} 像素")
    logger.info(f"计算所得相机内参矩阵:\n{np.array_str(mtx, precision=2)}")

    # 4. 处理机械臂末端位姿 (对齐官方教程第 3 步 poses_main)
    R_tool = []
    t_tool = []
    rotations_deg = []

    for pose in valid_poses:
        # 统一单位检查: 若 pose 平移为米 (绝对值 < 2.0) 且用户单位为 mm，则自动放大为 mm；反之亦然
        p_xyz = np.array(pose[:3], dtype=np.float64)
        if unit == "mm" and np.max(np.abs(p_xyz)) < 2.0:
            p_xyz *= 1000.0  # 自动换算为 mm
        elif unit == "m" and np.max(np.abs(p_xyz)) > 20.0:
            p_xyz /= 1000.0  # 自动换算为 m

        H = pose_to_homogeneous_matrix([p_xyz[0], p_xyz[1], p_xyz[2], pose[3], pose[4], pose[5]])
        R_tool.append(H[:3, :3])
        t_tool.append(H[:3, 3].reshape(3, 1))

        # 记录角度用于旋转充分度检查
        rotations_deg.append(np.degrees(pose[3:6]))

    # 旋转充分度自检 (对齐官方《常见问题 1: Not enough informative motions》)
    rot_arr = np.array(rotations_deg)
    rot_range = np.max(rot_arr, axis=0) - np.min(rot_arr, axis=0)
    logger.info(f"采集样本姿态角度覆盖范围: Rx={rot_range[0]:.1f}°, Ry={rot_range[1]:.1f}°, Rz={rot_range[2]:.1f}°")

    if np.any(rot_range < 30.0):
        insufficient_axes = [axis for axis, r in zip(["X", "Y", "Z"], rot_range) if r < 30.0]
        logger.warning(
            f"⚠️ 提示 (参考睿尔曼官方 FAQ): 轴向 [{','.join(insufficient_axes)}] 旋转角度变化小于 30°！"
            f" 若手眼标定求解精度不理想，请在采集时绕各轴执行更大幅度的倾斜/旋转旋转姿态。"
        )

    # 5. 手眼标定计算 (对齐官方教程第 4 步)
    method_enum = METHOD_DICT.get(method_name.lower(), cv2.CALIB_HAND_EYE_TSAI)
    logger.info(f"正在调用 OpenCV 手眼标定算法 (算法: {method_name.upper()})...")

    try:
        R_cam2end, t_cam2end = cv2.calibrateHandEye(
            R_tool, t_tool,
            rvecs, tvecs,
            method=method_enum
        )
    except cv2.error as e:
        logger.error(f"cv2.calibrateHandEye 求解失败: {e}")
        logger.error("失败原因通常为位姿旋转变化不足，请参考官方文档补充大角度旋转数据重新标定。")
        return None

    T_camera_to_end = np.eye(4, dtype=np.float64)
    T_camera_to_end[:3, :3] = R_cam2end
    T_camera_to_end[:3, 3] = t_cam2end.flatten()

    # 6. 手眼一致性误差评估 (检验基座系下标定板 3D 位置一致性)
    board_positions_in_base = []
    for i in range(valid_count):
        # 标定板在相机系下的齐次变换
        R_b2c, _ = cv2.Rodrigues(rvecs[i])
        t_b2c = tvecs[i].reshape(3, 1)
        T_board_to_cam = np.eye(4)
        T_board_to_cam[:3, :3] = R_b2c
        T_board_to_cam[:3, 3] = t_b2c[:, 0]

        # 机械臂末端在基座系下的齐次变换
        T_base_to_end = np.eye(4)
        T_base_to_end[:3, :3] = R_tool[i]
        T_base_to_end[:3, 3] = t_tool[i][:, 0]

        # T_board_to_base = T_base_to_end @ T_cam_to_end @ T_board_to_cam
        T_board_to_base = T_base_to_end @ T_camera_to_end @ T_board_to_cam
        board_positions_in_base.append(T_board_to_base[:3, 3])

    board_pos_arr = np.array(board_positions_in_base)
    pos_mean = np.mean(board_pos_arr, axis=0)
    pos_std = np.std(board_pos_arr, axis=0)
    pos_max_err = np.max(np.linalg.norm(board_pos_arr - pos_mean, axis=1))

    logger.info("==================================================")
    logger.info("🎉 睿尔曼 RM65 手眼标定 (Eye-in-Hand) 求解成功！")
    logger.info(f"平移向量 translation_vector ({unit}): [{t_cam2end[0,0]:.4f}, {t_cam2end[1,0]:.4f}, {t_cam2end[2,0]:.4f}]")
    logger.info(f"旋转矩阵 rotation_matrix:\n{np.array_str(R_cam2end, precision=4)}")
    logger.info(f"4x4 齐次矩阵 T_camera_to_end (P_end = T * P_cam):\n{np.array_str(T_camera_to_end, precision=4)}")
    logger.info("--------------------------------------------------")
    logger.info("标定精度自检报告:")
    logger.info(f"  • 相机标定 RMS 误差: {ret_cam:.3f} px")
    logger.info(f"  • 标定板基座位置标准差: X={pos_std[0]:.2f}{unit}, Y={pos_std[1]:.2f}{unit}, Z={pos_std[2]:.2f}{unit}")
    logger.info(f"  • 空间三维一致性最大偏差: {pos_max_err:.2f}{unit} (官方标准推荐 < 10.0mm)")
    logger.info("==================================================")

    # 7. 写回配置文件 config/settings.yaml
    if config_path and os.path.exists(config_path):
        try:
            use_ruamel = False
            try:
                from ruamel.yaml import YAML
                ryaml = YAML()
                ryaml.preserve_quotes = True
                with open(config_path, 'r', encoding='utf-8') as f:
                    cfg = ryaml.load(f) or {}
                use_ruamel = True
            except Exception:
                with open(config_path, 'r', encoding='utf-8') as f:
                    cfg = yaml.safe_load(f) or {}

            if use_ruamel:
                from ruamel.yaml.comments import CommentedSeq
                def to_flow(seq):
                    cs = CommentedSeq(seq)
                    cs.fa.set_flow_style()
                    return cs

                def matrix_to_flow(T):
                    return CommentedSeq([to_flow([float(x) for x in row]) for row in T])

                cfg['calibration']['T_end_to_camera'] = matrix_to_flow(T_camera_to_end)
                cfg['calibration']['rotation_matrix'] = matrix_to_flow(R_cam2end)
                cfg['calibration']['translation_vector'] = to_flow([float(x) for x in t_cam2end.flatten()])
                cfg['calibration']['camera_matrix'] = matrix_to_flow(mtx)
                cfg['calibration']['dist_coeffs'] = to_flow([float(x) for x in dist.flatten()])
            else:
                cfg['calibration']['T_end_to_camera'] = matrix_to_list(T_camera_to_end)
                cfg['calibration']['rotation_matrix'] = matrix_to_list(R_cam2end)
                cfg['calibration']['translation_vector'] = [float(x) for x in t_cam2end.flatten()]
                cfg['calibration']['camera_matrix'] = matrix_to_list(mtx)
                cfg['calibration']['dist_coeffs'] = [float(x) for x in dist.flatten()]

            cfg['calibration']['unit'] = unit
            cfg['calibration']['method'] = method_name
            cfg['calibration']['rms_error'] = float(ret_cam)
            cfg['calibration']['max_spatial_error'] = float(pos_max_err)
            cfg['calibration']['updated_at'] = datetime.now().isoformat()

            with open(config_path, 'w', encoding='utf-8') as f:
                if use_ruamel:
                    ryaml.dump(cfg, f)
                else:
                    yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)

            logger.info(f"✅ 标定结果与内参已同步持久化到: {config_path}")
        except Exception as e:
            logger.error(f"写入配置文件失败: {e}")

    return T_camera_to_end


# ==============================================================================
# 3. 睿尔曼数据采集模块 (对齐 collect_data.py)
# ==============================================================================

def collect_calibration_data(
    save_dir: str = "data/calibration_samples",
    pattern_size: Tuple[int, int] = (11, 8),
    camera_id: int = 0,
    headless: bool = False
):
    """
    采集手眼标定数据 (对齐官方 collect_data.py 流程):
    实时获取 D435 彩色画面与机械臂末端位姿。
    快捷键:
      's' / Enter: 记录当前画面与位姿
      'c': 完成采集并立即计算标定
      'q' / ESC: 退出
    """
    os.makedirs(save_dir, exist_ok=True)

    # 尝试连接机械臂
    arm_ctrl = None
    try:
        from src.control.rm65_api import RM65Controller
        arm_ctrl = RM65Controller()
        arm_ctrl.connect()
        if arm_ctrl.is_connected:
            logger.info("已连接 RM65 机械臂控制器。")
        else:
            logger.warning("无法建立机械臂网络连接 (请检查控制器IP与网线连接)，将以模拟位姿模式运行。")
            arm_ctrl = None
    except Exception as e:
        logger.warning(f"无法建立机械臂硬件连接 ({e})，将以模拟位姿模式运行。")

    # 尝试连接 RealSense 或 OpenCV 相机
    pipeline = None
    cap = None
    try:
        import pyrealsense2 as rs
        pipeline = rs.pipeline()
        config = rs.config()
        config.enable_stream(rs.stream.color, 1280, 720, rs.format.bgr8, 30)
        pipeline.start(config)
        logger.info("已启动 RealSense D435 硬件视频流。")
    except Exception as e:
        logger.warning(f"无法启动 RealSense 流 ({e})，回退到标准 OpenCV VideoCapture({camera_id})...")
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            logger.error("无法打开任何可用摄像头设备！")
            return

    count = len(glob.glob(os.path.join(save_dir, "*.png")))
    logger.info(f"数据采集已就绪！当前已有样本: {count} 组。保存路径: {save_dir}")
    logger.info("操作提示: 保证相机视野内标定板清晰完整，并保持倾角变化；按 's' 记录，按 'c' 计算，按 'q' 退出。")

    cols, rows = pattern_size

    try:
        while True:
            # 获取画面
            if pipeline:
                frames = pipeline.wait_for_frames()
                color_frame = frames.get_color_frame()
                if not color_frame:
                    continue
                frame = np.asanyarray(color_frame.get_data())
            else:
                ret, frame = cap.read()
                if not ret:
                    continue

            display_img = frame.copy()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            found, corners = cv2.findChessboardCorners(gray, (cols, rows), None)

            # 绘制角点指示
            if found:
                cv2.drawChessboardCorners(display_img, (cols, rows), corners, found)
                cv2.putText(display_img, "Chessboard DETECTED [OK]", (30, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            else:
                cv2.putText(display_img, "Chessboard NOT Found", (30, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)

            # 获取当前位姿
            current_pose = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            if arm_ctrl and arm_ctrl.is_connected:
                current_pose = arm_ctrl.get_current_pose()

            cv2.putText(display_img, f"Samples: {count} | Pose: {[round(x, 1) for x in current_pose[:3]]}",
                        (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

            key = -1
            if not headless:
                cv2.imshow("RealMan Hand-Eye Calibration Data Collector", display_img)
                key = cv2.waitKey(30) & 0xFF
            else:
                # 无头模式使用终端输入
                cmd = input(f"样本 {count} -> 输入 's' 保存, 'c' 标定, 'q' 退出: ").strip().lower()
                if cmd == 's':
                    key = ord('s')
                elif cmd == 'c':
                    key = ord('c')
                elif cmd == 'q':
                    key = ord('q')

            if key == ord('s'):
                count += 1
                img_path = os.path.join(save_dir, f"{count}.jpg")
                json_path = os.path.join(save_dir, f"{count}.json")

                cv2.imwrite(img_path, frame)
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump({"pose": current_pose, "timestamp": datetime.now().isoformat()}, f, indent=2)

                logger.info(f"✅ 成功记录第 {count} 组数据: {img_path} (Pose: {current_pose})")

            elif key == ord('c'):
                logger.info("采集结束，开始执行手眼标定求解...")
                break
            elif key in (ord('q'), 27):
                logger.info("用户中止数据采集。")
                break

    finally:
        if pipeline:
            pipeline.stop()
        if cap:
            cap.release()
        if not headless:
            cv2.destroyAllWindows()
        if arm_ctrl and arm_ctrl.is_connected:
            arm_ctrl.disconnect()


# ==============================================================================
# 4. 主程序命令行入口
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="睿尔曼 RM65 机械臂手眼标定工具 (Eye-in-Hand / 眼在手上)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--data-dir", type=str, default="data/calibration_samples",
                        help="包含标定图像与位姿 json 的数据目录")
    parser.add_argument("--pattern-width", type=int, default=11,
                        help="标定板横向角点数 (长边格子数减1，官方推荐 11)")
    parser.add_argument("--pattern-height", type=int, default=8,
                        help="标定板纵向角点数 (短边格子数减1，官方推荐 8)")
    parser.add_argument("--square-size", type=float, default=30.0,
                        help="标定板单个方格边长数值 (默认 30.0mm 或 0.03m)")
    parser.add_argument("--unit", type=str, choices=["mm", "m"], default="mm",
                        help="空间尺寸与平移向量单位")
    parser.add_argument("--method", type=str, choices=["tsai", "park", "horaud", "andreff", "daniilidis"],
                        default="tsai", help="OpenCV 手眼标定求解算法")
    parser.add_argument("--config-path", type=str, default="config/settings.yaml",
                        help="结果自动写回的配置文件路径")
    parser.add_argument("--collect", action="store_true",
                        help="启动实时相机与机械臂数据采集流程")
    parser.add_argument("--camera-id", type=int, default=0,
                        help="USB/RealSense 摄像头索引")
    parser.add_argument("--headless", action="store_true",
                        help="无头无界面终端采集模式 (适用于远程 SSH)")
    parser.add_argument("--verify", action="store_true",
                        help="使用标定结果进行坐标转换验证测试")
    args = parser.parse_args()

    if args.collect:
        collect_calibration_data(
            save_dir=args.data_dir,
            pattern_size=(args.pattern_width, args.pattern_height),
            camera_id=args.camera_id,
            headless=args.headless
        )

    T_res = calibrate_hand_eye(
        data_dir=args.data_dir,
        pattern_size=(args.pattern_width, args.pattern_height),
        square_size=args.square_size,
        unit=args.unit,
        method_name=args.method,
        config_path=args.config_path
    )

    if args.verify and T_res is not None:
        logger.info("\n--- 执行坐标转换验证 (convert_camera_to_base) ---")
        test_cam_pt = [0.0, 0.0, 300.0]  # 相机正前方 300mm
        test_robot_pose = [400.0, 0.0, 300.0, 0.0, 0.0, 0.0]
        base_pt = convert_camera_to_base(test_cam_pt, test_robot_pose, T_res)
        logger.info(f"相机点 {test_cam_pt} 在位姿 {test_robot_pose} 下的基座坐标: {base_pt}")


if __name__ == "__main__":
    main()
