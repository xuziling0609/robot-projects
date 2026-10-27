import numpy as np
from src.core.logger import logger
from src.core.config_loader import get_config

class APFPlanner:
    """
    人工势场法 (Artificial Potential Field) 局部避障规划器。
    结合目标引力与深度图非目标区域的斥力，计算柔顺避障的移动增量。
    """
    def __init__(self):
        self.cfg = get_config()['vision']['apf']
        # 最大感知距离(mm)，超出此距离的障碍物不产生斥力
        self.max_z = self.cfg.get('max_z_mm', 300) 
        # 绝对安全距离(mm)，一旦有物体逼近此距离，斥力将呈指数级甚至无限大增长
        self.safe_dist = self.cfg.get('safe_distance_mm', 150)
        
        # 势场系数
        self.k_att = 1.0  # 引力增益系数
        self.k_rep = 5000.0 # 动态点云斥力增益系数

        # 海康双光云台静态包围球配置 (方案一)
        self.ptz_cfg = self.cfg.get('ptz_obstacle', {})
        self.ptz_enabled = self.ptz_cfg.get('enabled', True)
        self.ptz_center_base = np.array(self.ptz_cfg.get('center_base_mm', [450.0, 0.0, 150.0]))
        self.ptz_radius = self.ptz_cfg.get('radius_mm', 250.0)
        self.k_rep_ptz = self.ptz_cfg.get('k_rep_ptz', 10000.0)

    def calculate_ptz_repulsive_force(self, current_pos_base: np.ndarray) -> np.ndarray:
        """
        方案一：计算狗头海康双光云台静态包围球的强斥力向量。
        当机械臂末端/手臂逼近云台包围球 250mm 半径范围时，产生强力推离开云台。
        
        Args:
            current_pos_base: 机械臂当前位置 (Base Frame, 单位 mm)
        """
        if not self.ptz_enabled or current_pos_base is None:
            return np.zeros(3)

        diff = current_pos_base - self.ptz_center_base
        dist = np.linalg.norm(diff)

        # 处于云台包围球保护半径内
        if dist < self.ptz_radius:
            dist = max(dist, 1.0) # 避开 0 除
            # 强斥力公式
            magnitude = self.k_rep_ptz * (1.0 / dist - 1.0 / self.ptz_radius) * (1.0 / (dist ** 2))
            direction = diff / dist
            logger.warning(f"触发云台保护斥力！距离海康云台中心: {dist:.1f}mm，推力大小: {magnitude:.1f}")
            return magnitude * direction

        return np.zeros(3)

    def calculate_attractive_force(self, current_pos: np.ndarray, target_pos: np.ndarray) -> np.ndarray:
        """
        计算引力向量。
        引力大小与距离成正比，方向指向目标。
        """
        diff = target_pos - current_pos
        dist = np.linalg.norm(diff)
        if dist < 1.0: # 到达目标容差范围
            return np.zeros(3)
            
        force = self.k_att * diff
        return force

    def calculate_repulsive_force(self, current_pos: np.ndarray, depth_cloud: np.ndarray, target_pos: np.ndarray = None, target_exclusion_radius: float = 60.0) -> np.ndarray:
        """
        计算障碍物点云斥力向量。
        对输入的局部点云 (仅保留接近相机的危险点) 计算合成斥力。
        若传入目标点坐标 target_pos，则排除目标表面周围 target_exclusion_radius 内的点云，
        防止目标自身作为障碍物排斥机械臂导致无法逼近或震荡死锁。
        """
        if depth_cloud is None or len(depth_cloud) == 0:
            return np.zeros(3)

        rep_force = np.zeros(3)
        for point in depth_cloud:
            # 排除目标自身周围的点云 (避免目标自身斥力推斥机械臂)
            if target_pos is not None:
                if np.linalg.norm(point - target_pos) < target_exclusion_radius:
                    continue

            diff = current_pos - point
            dist = np.linalg.norm(diff)
            
            if dist < self.safe_dist:
                dist = max(dist, 1.0)
                magnitude = self.k_rep * (1.0 / dist - 1.0 / self.safe_dist) * (1.0 / (dist ** 2))
                direction = diff / dist
                rep_force += magnitude * direction

        return rep_force

    def downsample_and_crop_depth(self, depth_img: np.ndarray, intrinsics, downsample_rate: int = 10) -> np.ndarray:
        """
        深度图近场裁剪与降采样优化算力。
        返回 (N, 3) 的三维点云坐标 (相机坐标系下)。
        """
        sampled = depth_img[::downsample_rate, ::downsample_rate]
        mask = (sampled > 0) & (sampled < self.max_z)
        
        v_idx, u_idx = np.where(mask)
        if len(v_idx) == 0:
            return np.array([])
            
        z_values = sampled[v_idx, u_idx]
        
        cx, cy = intrinsics.ppx, intrinsics.ppy
        fx, fy = intrinsics.fx, intrinsics.fy
        
        x_values = (u_idx * downsample_rate - cx) * z_values / fx
        y_values = (v_idx * downsample_rate - cy) * z_values / fy
        
        cloud = np.vstack((x_values, y_values, z_values)).T
        return cloud

    def plan_next_step(self, current_pos: np.ndarray, target_pos: np.ndarray, depth_img: np.ndarray, intrinsics, current_pos_base: np.ndarray = None) -> np.ndarray:
        """
        总控方法：输入当前位置、目标位置和当前深度图，输出经过避障校正后的下一个位置增量 (相机坐标系下)。
        """
        if intrinsics is None:
            logger.error("缺少相机内参，无法计算势场！")
            return np.zeros(3)

        # 1. 计算目标引力 (相机坐标系)
        F_att = self.calculate_attractive_force(current_pos, target_pos)
        
        # 2. 获取周围障碍物的三维危险点云 (相机坐标系)
        cloud = self.downsample_and_crop_depth(depth_img, intrinsics)
        
        # 3. 计算来自动态点云的斥力 (相机坐标系，排除目标物体自身)
        target_ex_radius = float(self.cfg.get('target_exclusion_radius_mm', 60.0))
        F_rep = self.calculate_repulsive_force(
            current_pos, cloud, target_pos=target_pos, target_exclusion_radius=target_ex_radius
        )
        
        # 4. 相机系合成力 (引力 + 点云斥力)
        F_cam = F_att + F_rep
        
        # 5. 限制单步最大移动量，防止突变
        max_step = 50.0 # 毫米
        norm = np.linalg.norm(F_cam)
        if norm > max_step:
            F_cam = (F_cam / norm) * max_step
            
        logger.debug(f"APF相机系合成力向量: {F_cam}")
        return F_cam
