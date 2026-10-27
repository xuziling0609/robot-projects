import numpy as np
import yaml
from scipy.spatial.transform import Rotation as R
from src.core.logger import logger
from src.core.config_loader import get_config

class HandEyeCalibrator:
    """
    手眼标定与坐标转换工具 (Eye-in-Hand 架构)。
    负责将相机坐标系下的 3D 点映射到机械臂基座坐标系。
    """
    def __init__(self):
        # 默认的 T_end_to_camera (4x4 齐次变换矩阵)
        # 实际开发中，应通过 OpenCV 的 cv2.calibrateHandEye 算法离线计算后填入此处，或写入配置
        self.T_end_to_camera = np.eye(4)
        
        # 尝试从全局配置加载
        cfg = get_config()
        if 'calibration' in cfg and 'T_end_to_camera' in cfg['calibration']:
            matrix_list = cfg['calibration']['T_end_to_camera']
            self.T_end_to_camera = np.array(matrix_list).reshape(4, 4)
            logger.info("已加载手眼标定矩阵 (T_end_to_camera)")
        else:
            logger.warning("未配置手眼标定矩阵，当前使用单位矩阵(无任何偏移)。")

    def pose_to_matrix(self, pose: list) -> np.ndarray:
        """
        将机械臂位姿 [x, y, z, rx, ry, rz] 转换为 4x4 齐次变换矩阵 T_base_to_end。
        假设: 
        1. 睿尔曼位姿中平移(x, y, z)单位为毫米 (mm)。(如果是米，需要在此处 * 1000)
        2. 旋转(rx, ry, rz)为欧拉角 (Euler Angles)，默认通常为 XYZ 或 ZYX 顺序，单位为弧度 (rad)。
           （如果是角度，需要 np.radians 转换）。
           这里默认睿尔曼的 Euler 为 XYZ (弧度)。
        """
        if len(pose) != 6:
            logger.error(f"位姿格式错误: {pose}")
            return np.eye(4)

        x, y, z, rx, ry, rz = pose
        
        # 构建旋转矩阵
        # 根据睿尔曼文档，其末端姿态通常表示为 XYZ 轴旋转 (固有或者外在)
        # 具体顺序需视 SDK 文档，一般采用 'xyz'
        r = R.from_euler('xyz', [rx, ry, rz], degrees=False)
        rot_mat = r.as_matrix()

        # 构建 4x4 齐次矩阵
        T = np.eye(4)
        T[:3, :3] = rot_mat
        
        # 如果从 SDK 获取的是米(m)，请解除下方的注释，本项目统一用 mm 计算
        # x, y, z = x * 1000.0, y * 1000.0, z * 1000.0
        T[0, 3] = x
        T[1, 3] = y
        T[2, 3] = z

        return T

    def transform_camera_to_base(self, point_camera: np.ndarray, current_robot_pose: list) -> np.ndarray:
        """
        将相机坐标系下的 3D 点转化为机械臂基座坐标系。
        
        公式: P_base = T_base_to_end * T_end_to_camera * P_camera
        
        Args:
            point_camera: (3,) 数组, 包含 [x, y, z] 相机系坐标，单位毫米
            current_robot_pose: (6,) 列表, 机械臂当前法兰端位姿 [x, y, z, rx, ry, rz]
            
        Returns:
            np.ndarray: (3,) 基座坐标系下的绝对物理坐标 (x, y, z)，单位毫米
        """
        # 1. 获取 T_base_to_end
        T_base_to_end = self.pose_to_matrix(current_robot_pose)
        
        # 2. 将 3D 点转化为齐次坐标 [x, y, z, 1]^T
        P_cam_homo = np.array([point_camera[0], point_camera[1], point_camera[2], 1.0])
        
        # 3. 级联矩阵乘法
        # 先转为法兰端坐标系：P_end = T_end_to_camera * P_camera
        P_end_homo = np.dot(self.T_end_to_camera, P_cam_homo)
        
        # 再转为基座坐标系：P_base = T_base_to_end * P_end
        P_base_homo = np.dot(T_base_to_end, P_end_homo)
        
        # 4. 返回前 3 维 [x, y, z]
        return P_base_homo[:3]

    def rotate_vector_camera_to_base(self, vector_camera: np.ndarray, current_robot_pose: list) -> np.ndarray:
        """
        仅旋转一个向量(如移动增量、速度等)，而不考虑平移。
        公式: V_base = R_base_to_end * R_end_to_camera * V_camera
        """
        T_base_to_end = self.pose_to_matrix(current_robot_pose)
        
        # 提取 3x3 旋转矩阵
        R_base_to_end = T_base_to_end[:3, :3]
        R_end_to_camera = self.T_end_to_camera[:3, :3]
        
        # V_end = R_end_to_camera * V_camera
        V_end = np.dot(R_end_to_camera, vector_camera)
        
        # V_base = R_base_to_end * V_end
        V_base = np.dot(R_base_to_end, V_end)
        
        return V_base

    def transform_base_to_camera(self, point_base: np.ndarray, current_robot_pose: list) -> np.ndarray:
        """
        将机械臂基座坐标系下的 3D 点逆变换到当前相机坐标系。
        公式: P_camera = (T_base_to_end * T_end_to_camera)^(-1) * P_base
                     = T_camera_to_end * T_end_to_base * P_base
        
        Args:
            point_base: (3,) 数组, 包含 [x, y, z] 基座坐标，单位毫米
            current_robot_pose: (6,) 列表, 机械臂当前法兰端位姿 [x, y, z, rx, ry, rz]
            
        Returns:
            np.ndarray: (3,) 相机坐标系下的物理坐标 (x, y, z)，单位毫米
        """
        T_base_to_end = self.pose_to_matrix(current_robot_pose)
        T_end_to_base = np.linalg.inv(T_base_to_end)
        T_camera_to_end = np.linalg.inv(self.T_end_to_camera)
        
        P_base_homo = np.array([point_base[0], point_base[1], point_base[2], 1.0])
        P_end_homo = np.dot(T_end_to_base, P_base_homo)
        P_cam_homo = np.dot(T_camera_to_end, P_end_homo)
        return P_cam_homo[:3]

