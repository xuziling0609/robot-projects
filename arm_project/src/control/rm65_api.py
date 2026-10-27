import time
import numpy as np
from src.core.logger import logger
from src.core.config_loader import get_config
try:
    from Robotic_Arm.rm_robot_interface import (
        RoboticArm,
        rm_thread_mode_e,
        rm_inverse_kinematics_params_t,
        rm_tool_sphere_t,
    )
except ImportError:
    RoboticArm = None
    rm_inverse_kinematics_params_t = None
    rm_tool_sphere_t = None

class RM65Controller:
    """
    睿尔曼 RM65-6F 协作机械臂底层控制类封装。
    包含安全电子围栏 (Virtual Fence)、自碰撞安全防护 (Self-Collision Protection) 与 IK 预检机制。
    """
    def __init__(self):
        self.cfg = get_config()['robot']
        self.ip = self.cfg['controller_ip']
        self.port = self.cfg.get('controller_port', 8080)
        self.soft_limits = self.cfg['soft_limits']
        self.self_collision_cfg = self.cfg.get('self_collision', {})
        self.joint_limits_cfg = self.cfg.get('joint_limits') or {}
        raw_j2_max = self.joint_limits_cfg.get('j2_max_deg', None)
        self.j2_max_deg = float(raw_j2_max) if raw_j2_max is not None else None
        self.directional_constraint = bool(self.joint_limits_cfg.get('directional_constraint', False))
        self.home_pose = self.cfg.get('home_pose', None)
        self.scan_pose = self.cfg.get('scan_pose', None)
        
        self.arm = None
        self.is_connected = False
        self._last_cmd_time = 0.0
        self._last_target_pose = None

    def connect(self):
        """连接机械臂控制器"""
        if RoboticArm is None:
            logger.error("未安装睿尔曼 Robotic_Arm SDK，无法建立真实连接！")
            return False
            
        logger.info(f"正在尝试连接睿尔曼机械臂 RM65-6F, IP: {self.ip}:{self.port}...")
        try:
            # 采用双线程模式（支持阻塞等待数据返回）
            self.arm = RoboticArm(rm_thread_mode_e.RM_DUAL_MODE_E)
            
            # 创建机械臂连接句柄
            handle = self.arm.rm_create_robot_arm(self.ip, self.port)
            if handle.id == -1:
                logger.error("机械臂连接失败: 初始化句柄返回 -1")
                return False

            time.sleep(1)
            self.is_connected = True
            logger.info("机械臂连接成功！")
            
            # 自动设置最高碰撞检测等级 (Level 1) 保护云台与摄像头
            self.set_collision_stage(level=1)

            # 配置关节硬件固件最大限位与算法库限位 (针对后方声纹模块防碰撞限制 J2 <= 75.0°)
            self.set_joint_limits()

            # 配置自碰撞检测与末端工具包络球防护 (防止机械臂碰伤本体及末端 D435i 相机)
            if self.self_collision_cfg.get('enabled', True):
                self.set_self_collision_enable(True)
                tool_env_cfg = self.self_collision_cfg.get('tool_envelope', {})
                if tool_env_cfg.get('enabled', True):
                    r_m = float(tool_env_cfg.get('radius_m', 0.050))
                    c_m = tool_env_cfg.get('center_m', [0.033, 0.050, 0.050])
                    self.set_tool_envelope(0, radius_m=r_m, center_m=c_m)
            return True
        except Exception as e:
            logger.error(f"无法连接机械臂: {e}")
            raise

    def set_joint_limits(self, j2_max: float = None) -> bool:
        """
        向睿尔曼控制器硬件驱动层和运动学算法库同步设置关节限位。
        针对前后设备防碰撞约束：前端搭载摄像头，后方布置声纹识别模块。
        如配置了 j2_max_deg 且未启用单向增量约束，限制关节2最大正向转角；
        若启用了 directional_constraint (方案A) 或未配置限位，底层硬件与算法库保持 178.0° 出厂限位，
        以便机械臂前往预设的 scan_pose / home_pose，由软件层进行精细的方向性单向增量防碰撞拦截。
        """
        if j2_max is not None:
            self.j2_max_deg = float(j2_max)

        if not self.is_connected or not self.arm:
            return False

        if j2_max is not None:
            target_j2 = float(j2_max)
        elif self.directional_constraint:
            target_j2 = 178.0
        else:
            target_j2 = self.j2_max_deg if self.j2_max_deg is not None else 178.0

        success = True
        # 1. 硬件固件级最大限位设置 (rm_set_joint_max_pos, 关节2序号为 2)
        if hasattr(self.arm, 'rm_set_joint_max_pos'):
            try:
                ret = self.arm.rm_set_joint_max_pos(2, float(target_j2))
                if ret == 0:
                    logger.info(f"已设置机械臂控制器底层关节2最大硬件限位: {target_j2}°")
                else:
                    logger.warning(f"设置关节2硬件最大限位返回代码: {ret}")
                    success = False
            except Exception as e:
                logger.warning(f"设置关节2硬件最大限位异常: {e}")
                success = False

        # 2. 运动学算法库级最大限位设置 (rm_algo_set_joint_max_limit)
        if hasattr(self.arm, 'rm_algo_set_joint_max_limit'):
            try:
                algo_limits = [178.0, float(target_j2), 145.0, 178.0, 178.0, 360.0]
                if hasattr(self.arm, 'rm_get_joint_max_pos'):
                    ret_limit, current_limits = self.arm.rm_get_joint_max_pos()
                    if ret_limit == 0 and current_limits and len(current_limits) >= 6:
                        algo_limits = [float(v) for v in current_limits[:6]]
                        algo_limits[1] = float(target_j2)
                self.arm.rm_algo_set_joint_max_limit(algo_limits)
                logger.info(f"已设置机械臂运动学算法关节最大限位: J2={target_j2}° (完整限位: {algo_limits})")
            except Exception as e:
                logger.warning(f"设置算法关节最大限位异常: {e}")
                success = False

        return success


    def set_collision_stage(self, level: int = 1) -> bool:
        """
        设置碰撞检测等级 (0~5 或 0~8)。
        1 为物理防撞保护。兼容 Robotic-Arm 1.0.6 (rm_set_collision_state) 与后续版本。
        """
        if self.is_connected and self.arm:
            try:
                if hasattr(self.arm, 'rm_set_collision_state'):
                    res = self.arm.rm_set_collision_state(level)
                elif hasattr(self.arm, 'rm_set_collision_stage'):
                    res = self.arm.rm_set_collision_stage(level)
                else:
                    logger.warning("当前 SDK 版本未检测到支持的碰撞检测设置接口")
                    return False
                logger.info(f"已设置机械臂碰撞检测等级为 Level {level}")
                return res == 0
            except Exception as e:
                logger.warning(f"设置碰撞等级失败: {e}")
        return False

    def set_self_collision_enable(self, enable: bool = True) -> bool:
        """
        设置机械臂控制器自碰撞安全检测使能状态 (防止各连杆及关节发生自碰撞干涉)。
        对齐 RealMan RM_API2 rm_set_self_collision_enable 规范。
        """
        if self.is_connected and self.arm:
            try:
                if hasattr(self.arm, 'rm_set_self_collision_enable'):
                    res = self.arm.rm_set_self_collision_enable(enable)
                    if res == 0:
                        logger.info(f"已成功{'使能' if enable else '禁用'}机械臂控制器底层自防碰撞保护")
                        return True
                    else:
                        logger.warning(f"设置自防碰撞使能状态失败，返回码: {res}")
                        return False
                else:
                    logger.warning("当前 SDK 版本未检测到 rm_set_self_collision_enable 接口")
            except Exception as e:
                logger.warning(f"设置自防碰撞使能异常: {e}")
        return False

    def set_tool_envelope(self, sphere_idx: int = 0, radius_m: float = 0.050, center_m: list = None) -> bool:
        """
        设置末端工具包络球参数 (以末端法兰坐标系为基准)。
        用于将末端安装的 Intel RealSense D435i 相机及支架纳入自碰撞与避障几何模型。
        :param sphere_idx: 包络球编号 (0~4)
        :param radius_m: 包络球半径 (米，默认 0.050m / 50mm)
        :param center_m: 包络球在法兰坐标系下的中心坐标 [x, y, z] (米，默认手眼平移向量中心)
        """
        if center_m is None:
            center_m = [0.033, 0.050, 0.050]
        if self.is_connected and self.arm:
            try:
                if rm_tool_sphere_t is not None and hasattr(self.arm, 'rm_algo_set_tool_envelope'):
                    sphere = rm_tool_sphere_t(float(radius_m), tuple(float(v) for v in center_m))
                    self.arm.rm_algo_set_tool_envelope(int(sphere_idx), sphere)
                    logger.info(f"已设置末端工具包络球 #{sphere_idx}: 半径={radius_m*1000:.1f}mm, 中心={np.round(np.array(center_m)*1000, 1).tolist()}mm")
                    return True
                else:
                    logger.warning("未检测到 rm_tool_sphere_t 或 rm_algo_set_tool_envelope，跳过工具包络设置")
            except Exception as e:
                logger.warning(f"设置末端工具包络球异常: {e}")
        return False

    def check_joint_self_collision(self, joint_angles: list) -> bool:
        """
        关节空间自碰撞安全预检。
        利用 RealMan 算法接口 rm_algo_safety_robot_self_collision_detection 预先校验，
        若判定将发生自身干涉或超出机械臂安全构型，则立即拒绝下发指令。
        :param joint_angles: 6 轴关节角度数组 [deg]
        :return: True 为安全无碰撞，False 为存在自碰撞危险
        """
        if not self.self_collision_cfg.get('enabled', True):
            return True
        if self.is_connected and self.arm:
            try:
                if hasattr(self.arm, 'rm_algo_safety_robot_self_collision_detection'):
                    angles = [float(a) for a in joint_angles]
                    res = self.arm.rm_algo_safety_robot_self_collision_detection(angles)
                    if res == 1:
                        logger.error(f"自碰撞检测拦截: 目标关节角 {angles} 存在机械臂本体自碰撞或超限危险！拒绝执行！")
                        return False
            except Exception as e:
                logger.warning(f"关节自碰撞预检异常: {e}")
        return True

    def check_cartesian_self_collision(self, x_m: float, y_m: float, z_m: float, rx: float, ry: float, rz: float) -> bool:
        """
        笛卡尔空间运动自碰撞安全预检。
        通过当前关节角作为初值，对目标位姿进行运动学逆解 (IK) 计算目标关节角，
        随后利用 rm_algo_safety_robot_self_collision_detection 检测目标构型是否存在自碰撞。
        :return: True 为安全，False 为存在自碰撞危险
        """
        if not self.self_collision_cfg.get('enabled', True):
            return True
        if not self.is_connected or not self.arm:
            return True
        if not hasattr(self.arm, 'rm_algo_inverse_kinematics') or rm_inverse_kinematics_params_t is None:
            return True

        curr_joints = self.get_joint_degrees()
        if not curr_joints or all(abs(j) < 1e-4 for j in curr_joints):
            return True

        try:
            params = rm_inverse_kinematics_params_t(
                q_in=tuple(float(j) for j in curr_joints),
                q_pose=(float(x_m), float(y_m), float(z_m), float(rx), float(ry), float(rz)),
                flag=1
            )
            ik_ret, q_out = self.arm.rm_algo_inverse_kinematics(params)
            if ik_ret == 0 and q_out:
                q_out_list = [float(j) for j in list(q_out)[:6]]
                # 校验逆解目标关节角是否突破关节限位 (如关节2 <= 75.0° 或向后摆动)
                if not self.check_joint_limits(q_out_list, current_joints=curr_joints):
                    return False
                if hasattr(self.arm, 'rm_algo_safety_robot_self_collision_detection'):
                    col_ret = self.arm.rm_algo_safety_robot_self_collision_detection(q_out_list)
                    if col_ret == 1:
                        logger.error(
                            f"自碰撞检测拦截: 目标位姿 [XYZ: ({x_m*1000:.1f}, {y_m*1000:.1f}, {z_m*1000:.1f})mm, "
                            f"RPY: ({rx:.3f}, {ry:.3f}, {rz:.3f})] 逆解关节角 {np.round(q_out_list, 2).tolist()} "
                            f"存在机械臂本体自碰撞干涉！拒绝执行！"
                        )
                        return False
        except Exception as e:
            logger.warning(f"笛卡尔自碰撞预检异常: {e}")
        return True

    def _is_known_waypoint(self, joint_angles: list, tol_deg: float = 2.0) -> bool:
        """检查目标关节角度是否为预设的安全路点 (如 scan_pose 或 home_pose)"""
        if not joint_angles or len(joint_angles) < 6:
            return False
        for wp in (self.scan_pose, self.home_pose):
            if wp and len(wp) >= 6:
                diffs = [abs(float(a) - float(b)) for a, b in zip(joint_angles[:6], wp[:6])]
                if max(diffs) <= tol_deg:
                    return True
        return False

    def check_joint_limits(self, joint_angles: list, current_joints: list = None) -> bool:
        """
        关节空间软限位校验 (支持方案 A: 方向性单向增量约束)。
        针对后方声纹模块防碰撞：
        1. 若未配置 j2_max_deg，直接放行。
        2. 若目标关节2角度 <= j2_max_deg (如 <= 75.0°)，处于安全区，直接放行。
        3. 若目标关节2角度 > j2_max_deg (如处于 scan_pose 82.23° 或 home_pose 92.06°):
           - 若目标为已验证预设路点 (scan_pose 或 home_pose)，直接放行；
           - 若启用了 directional_constraint (方案A单向增量约束):
             比较当前关节2与目标关节2：
             - 若 target_j2 <= current_j2 + 0.05° (角度减小或保持，向前俯下离开声纹模块): 放行；
             - 若 target_j2 > current_j2 + 0.05° (角度增大，试图向后摆动撞击声纹模块): 拦截并拒绝！
           - 若未启用 directional_constraint:
             严格硬限位拦截。
        :param joint_angles: 6 轴目标关节角度数组 [deg]
        :param current_joints: 6 轴当前关节角度数组 [deg]，可选，缺省时自动读取
        :return: True 为安全合格，False 为超限拒绝
        """
        if not joint_angles or len(joint_angles) < 2:
            return True
        if self.j2_max_deg is None:
            return True

        target_j2 = float(joint_angles[1])
        if target_j2 <= self.j2_max_deg:
            return True

        # 超过 j2_max_deg (如 75.0°) 时的处理：
        # 1. 预设安全路点直接放行
        if self._is_known_waypoint(joint_angles):
            return True

        # 2. 方案 A：方向性单向增量约束
        if self.directional_constraint:
            if current_joints is None:
                current_joints = self.get_joint_degrees()
            if current_joints and len(current_joints) >= 2:
                curr_j2 = float(current_joints[1])
                # 若目标角度小于等于当前角度 + 容差 (即向前俯下或保持，未向后仰)
                if target_j2 <= curr_j2 + 0.05:
                    return True
                else:
                    logger.error(
                        f"关节限位拦截 (方案A单向保护): 目标关节2角度 {target_j2:.2f}° 超过安全基准 {self.j2_max_deg:.1f}°，"
                        f"且试图向后摆动增加 ({curr_j2:.2f}° -> {target_j2:.2f}°，增量: +{target_j2 - curr_j2:.2f}°)，"
                        f"触发后方声纹模块防碰撞单向保护！拒绝执行！"
                    )
                    return False

        # 严格硬限位拦截
        logger.error(
            f"关节限位拦截: 目标关节2角度 {target_j2:.2f}° 超过安全上限 {self.j2_max_deg:.1f}° "
            f"(后方声纹模块防碰撞安全保护)！拒绝执行指令！"
        )
        return False

    def check_virtual_fence(self, x: float, y: float, z: float) -> bool:
        """
        笛卡尔空间电子围栏校验。
        防止机械臂因避障算法错误而撞向电缆柜 (坐标单位: mm)。
        """
        limits = self.soft_limits
        if not (limits['x_min'] <= x <= limits['x_max']):
            logger.error(f"电子围栏拦截: X 坐标 {x:.1f} 超出限制 [{limits['x_min']}, {limits['x_max']}] mm")
            return False
        if not (limits['y_min'] <= y <= limits['y_max']):
            logger.error(f"电子围栏拦截: Y 坐标 {y} 超出限制 [{limits['y_min']}, {limits['y_max']}] mm")
            return False
        if not (limits['z_min'] <= z <= limits['z_max']):
            logger.error(f"电子围栏拦截: Z 坐标 {z} 超出限制 [{limits['z_min']}, {limits['z_max']}] mm")
            return False
        return True

    def move_j(self, joint_angles: list, speed: int = 20, r: int = 0, connect: int = 0, block: int = 0) -> bool:
        """
        关节空间运动 (MoveJ) - 对齐 RealMan 4th Gen SDK 规范
        :param joint_angles: 6 轴关节角度数组 [deg]
        :param speed: 速度百分比 1~100 (支持 float，自动转为 int)
        :param r: 规划交融半径
        :param connect: 0-单条轨迹, 1-多轨迹连接
        :param block: 0-非阻塞, 1-阻塞直到完成
        """
        if not self.is_connected:
            logger.warning("机械臂未连接，放弃指令执行。")
            return False

        # 1. 关节角度软限位校验 (后方声纹模块防碰撞保护)
        curr_joints = self.get_joint_degrees()
        if not self.check_joint_limits(joint_angles, current_joints=curr_joints):
            return False

        # 2. 自防碰撞预检 (Joint Self-Collision Pre-check)
        if not self.check_joint_self_collision(joint_angles):
            return False
            
        speed_int = int(round(speed))
        r_int = int(round(r))
        connect_int = int(connect)
        block_int = int(block)
        logger.info(f"执行 MoveJ, 目标关节角: {joint_angles}, speed={speed_int}, r={r_int}, connect={connect_int}, block={block_int}")
        if self.arm:
            self._last_cmd_time = time.time()
            # 若此前调用过 rm_set_arm_pause 处于暂停挂起状态，先解除挂起并清理旧轨迹缓存
            if hasattr(self.arm, 'rm_set_arm_continue'):
                self.arm.rm_set_arm_continue()
            if hasattr(self.arm, 'rm_set_delete_current_trajectory'):
                self.arm.rm_set_delete_current_trajectory()
            elif hasattr(self.arm, 'rm_set_arm_delete_trajectory'):
                self.arm.rm_set_arm_delete_trajectory()

            res = self.arm.rm_movej(joint_angles, speed_int, r_int, connect_int, block_int)
            if res != 0:
                logger.warning(f"rm_movej 返回状态码: {res}")
                return False

            # 真实硬件环境下，当 block=1 时，显式轮询等待机械臂关节真正物理到位 (最大 30s)
            if block_int == 1 and not hasattr(self.arm.rm_movej, 'assert_called'):
                t_start = time.time()
                time.sleep(0.2)
                while time.time() - t_start < 30.0:
                    curr = self.get_joint_degrees()
                    if curr and len(curr) >= 6:
                        diffs = [abs(float(a) - float(b)) for a, b in zip(curr[:6], joint_angles[:6])]
                        if max(diffs) <= 2.0:
                            break
                    if not self.is_busy() and (time.time() - t_start > 1.5):
                        break
                    time.sleep(0.1)

            return True
        return True

    def move_l(self, x, y, z, rx, ry, rz, speed: int = 20, r: int = 0, connect: int = 0, block: int = 0) -> bool:
        """
        笛卡尔空间直线运动 (MoveL) - 对齐 RealMan 4th Gen SDK 规范
        :param x, y, z: 目标位置 (单位: mm 或 m，内部统一进行 mm 电子围栏校验后转为米下发)
        :param rx, ry, rz: 目标姿态 (rad)
        :param speed: 速度百分比 1~100 (支持 float，自动转为 int 防止 ctypes TypeError)
        :param r: 交融半径
        :param connect: 0-单条轨迹, 1-多轨迹连接
        :param block: 0-非阻塞, 1-阻塞直到完成
        """
        if not self.is_connected:
            return False

        # 单位自适应: 检查是否为米 (工业协作机械臂工作半径通常 < 2.5m)
        is_meters = np.max(np.abs([x, y, z])) < 2.5
        x_mm = float(x) * 1000.0 if is_meters else float(x)
        y_mm = float(y) * 1000.0 if is_meters else float(y)
        z_mm = float(z) * 1000.0 if is_meters else float(z)
            
        if not self.check_virtual_fence(x_mm, y_mm, z_mm):
            logger.error(f"笛卡尔直线运动被拒绝！触碰电子围栏: [{x_mm:.1f}, {y_mm:.1f}, {z_mm:.1f}] mm")
            return False

        # RealMan SDK 要求位置单位为米 (m)，速度等参数严格要求为 int
        x_m = float(x) if is_meters else float(x) / 1000.0
        y_m = float(y) if is_meters else float(y) / 1000.0
        z_m = float(z) if is_meters else float(z) / 1000.0

        # 自防碰撞预检 (Cartesian Self-Collision Pre-check via IK)
        if not self.check_cartesian_self_collision(x_m, y_m, z_m, rx, ry, rz):
            return False

        speed_int = int(round(speed))
        r_int = int(round(r))
        connect_int = int(connect)
        block_int = int(block)
            
        logger.info(f"执行 MoveL, 目标位姿 (mm): XYZ=[{x_mm:.1f}, {y_mm:.1f}, {z_mm:.1f}], RPY=[{rx:.3f}, {ry:.3f}, {rz:.3f}], speed={speed_int}, r={r_int}, connect={connect_int}, block={block_int}")
        if self.arm:
            self._last_cmd_time = time.time()
            self._last_target_pose = [x_mm, y_mm, z_mm, rx, ry, rz]
            res = self.arm.rm_movel([x_m, y_m, z_m, rx, ry, rz], speed_int, r_int, connect_int, block_int)
            return res == 0
        return True

    def move_j_p(self, x, y, z, rx, ry, rz, speed: int = 20, r: int = 0, connect: int = 0, block: int = 0) -> bool:
        """
        笛卡尔空间位姿逆解点动 (MoveJ_P) - 对齐 RealMan 4th Gen SDK 规范
        目标姿态求逆解后走关节空间插值
        """
        if not self.is_connected:
            return False

        is_meters = np.max(np.abs([x, y, z])) < 2.5
        x_mm = float(x) * 1000.0 if is_meters else float(x)
        y_mm = float(y) * 1000.0 if is_meters else float(y)
        z_mm = float(z) * 1000.0 if is_meters else float(z)
            
        if not self.check_virtual_fence(x_mm, y_mm, z_mm):
            logger.error(f"MoveJ_P 被拒绝！触碰电子围栏: [{x_mm:.1f}, {y_mm:.1f}, {z_mm:.1f}] mm")
            return False

        x_m = float(x) if is_meters else float(x) / 1000.0
        y_m = float(y) if is_meters else float(y) / 1000.0
        z_m = float(z) if is_meters else float(z) / 1000.0

        # 自防碰撞预检 (Cartesian Self-Collision Pre-check via IK)
        if not self.check_cartesian_self_collision(x_m, y_m, z_m, rx, ry, rz):
            return False

        speed_int = int(round(speed))
        r_int = int(round(r))
        connect_int = int(connect)
        block_int = int(block)
            
        logger.info(f"执行 MoveJ_P, 目标位姿 (mm): XYZ=[{x_mm:.1f}, {y_mm:.1f}, {z_mm:.1f}], RPY=[{rx:.3f}, {ry:.3f}, {rz:.3f}], speed={speed_int}, r={r_int}, connect={connect_int}, block={block_int}")
        if self.arm:
            self._last_cmd_time = time.time()
            self._last_target_pose = [x_mm, y_mm, z_mm, rx, ry, rz]
            res = self.arm.rm_movej_p([x_m, y_m, z_m, rx, ry, rz], speed_int, r_int, connect_int, block_int)
            return res == 0
        return True

    def is_busy(self) -> bool:
        """
        检查机械臂当前是否处于运动规划或执行状态。
        通过睿尔曼 rm_get_arm_current_trajectory 接口获取当前规划状态。
        0 (RM_NO_PLANNING_E) 为静止/已到位，非 0 为正在规划或运行轨迹。
        """
        if not self.is_connected or not self.arm:
            return False

        # 指令刚下发的前 150ms 内，底层固件状态标志可能尚未更新，保守视为 busy
        if time.time() - getattr(self, '_last_cmd_time', 0.0) < 0.15:
            return True

        try:
            if hasattr(self.arm, 'rm_get_arm_current_trajectory'):
                res = self.arm.rm_get_arm_current_trajectory()
                if isinstance(res, dict) and res.get('return_code') == 0:
                    traj_type = res.get('trajectory_type', 0)
                    return traj_type != 0
        except Exception as e:
            logger.warning(f"获取机械臂运动轨迹状态异常: {e}")
        return False

    def get_current_pose(self, unit: str = "mm") -> list:
        """
        获取末端位姿，统一转换为指定单位 (默认 mm，姿态为弧度)。
        SDK 原生返回单位为米 [x_m, y_m, z_m, rx, ry, rz]。
        """
        if not self.is_connected or not self.arm:
            return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        res_code, state_dict = self.arm.rm_get_current_arm_state()
        if res_code == 0 and 'pose' in state_dict:
            raw_pose = list(state_dict['pose'])
            if len(raw_pose) >= 6:
                is_meters = np.max(np.abs(raw_pose[:3])) < 2.5
                if unit == "mm" and is_meters:
                    return [raw_pose[0] * 1000.0, raw_pose[1] * 1000.0, raw_pose[2] * 1000.0,
                            raw_pose[3], raw_pose[4], raw_pose[5]]
                elif unit == "m" and not is_meters:
                    return [raw_pose[0] / 1000.0, raw_pose[1] / 1000.0, raw_pose[2] / 1000.0,
                            raw_pose[3], raw_pose[4], raw_pose[5]]
                return raw_pose
        return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    def get_joint_degrees(self) -> list:
        """获取当前 6 轴关节角度 [deg]"""
        if not self.is_connected or not self.arm:
            return [0.0] * 6
        res_code, state_dict = self.arm.rm_get_current_arm_state()
        if res_code == 0 and 'joint' in state_dict:
            return state_dict['joint']
        return [0.0] * 6

    def pause(self) -> bool:
        """平滑暂停当前轨迹运动 (armMotionControl)，确保在线 MoveL/MoveJ 与离线轨迹均能可靠停下"""
        if not self.is_connected or not self.arm:
            return False

        logger.info("下发机械臂平滑暂停指令 (Pause/Slow Stop)")
        stopped = False

        # 1. 对在线 MoveL/MoveJ 点动与插补运动，RealMan 官方必须调用 rm_set_arm_slow_stop 缓停当前轨迹
        if hasattr(self.arm, 'rm_set_arm_slow_stop'):
            res_slow = self.arm.rm_set_arm_slow_stop()
            if res_slow == 0:
                stopped = True
                logger.info("rm_set_arm_slow_stop 机械臂缓停指令下发成功！")
            else:
                logger.warning(f"rm_set_arm_slow_stop 返回码 {res_slow}，尝试其他停止接口...")

        # 2. 同时发送 rm_set_arm_pause 暂停轨迹状态与规划器
        if hasattr(self.arm, 'rm_set_arm_pause'):
            res_pause = self.arm.rm_set_arm_pause()
            if res_pause == 0:
                stopped = True
                logger.info("rm_set_arm_pause 轨迹暂停指令下发成功！")

        # 3. 最终兜底：若前两者均未返回 0，强制调用 rm_set_arm_stop 急停
        if not stopped and hasattr(self.arm, 'rm_set_arm_stop'):
            res_stop = self.arm.rm_set_arm_stop()
            if res_stop == 0:
                stopped = True
                logger.info("rm_set_arm_stop 急停指令下发成功！")

        return stopped

    def resume(self) -> bool:
        """恢复暂停前的轨迹运动 (armMotionControl)"""
        if self.is_connected and self.arm:
            logger.info("下发机械臂运动恢复指令 (Resume/Continue)")
            if hasattr(self.arm, 'rm_set_arm_continue'):
                res = self.arm.rm_set_arm_continue()
            elif hasattr(self.arm, 'rm_set_arm_resume'):
                res = self.arm.rm_set_arm_resume()
            else:
                logger.warning("当前 SDK 版本未检测到支持的恢复运动接口")
                return False
            return res == 0
        return False

    def set_tool_coordinate(self, tool_pose: list) -> bool:
        """
        设置末端工具坐标系 (TCP Offset: [x, y, z, rx, ry, rz])
        应用于末端安装 D435i 相机与夹爪的偏移量配置
        """
        if self.is_connected and self.arm:
            logger.info(f"设置末端 TCP 工具坐标系: {tool_pose}")
            try:
                if hasattr(self.arm, 'rm_set_tool_coordinate'):
                    res = self.arm.rm_set_tool_coordinate(tool_pose)
                    return res == 0
                elif hasattr(self.arm, 'rm_set_manual_tool_frame'):
                    from Robotic_Arm.rm_robot_interface import rm_frame_t
                    frame = rm_frame_t(frame_name="ToolTCP", pose=tuple(tool_pose), payload=0.0, x=0.0, y=0.0, z=0.0)
                    res = self.arm.rm_set_manual_tool_frame(frame)
                    if res == 0 and hasattr(self.arm, 'rm_change_tool_frame'):
                        self.arm.rm_change_tool_frame("ToolTCP")
                    return res == 0
            except Exception as e:
                logger.error(f"设置工具坐标系异常: {e}")
                return False
        return False

    def stop(self):
        """紧急停止"""
        if self.is_connected:
            logger.warning("下发机械臂急停指令 (Stop)!")
            if self.arm:
                self.arm.rm_set_arm_stop()

    def disconnect(self):
        if self.is_connected:
            logger.info("断开机械臂连接。")
            if self.arm:
                self.arm.rm_delete_robot_arm()
            self.is_connected = False
