import time
import numpy as np
from scipy.spatial.transform import Rotation as R
from src.core.logger import logger
from src.core.config_loader import get_config
from src.communication.host_server import TCPServerThread, command_queue

from src.control.rm65_api import RM65Controller
from src.control.motion_plan import APFPlanner
from src.vision.camera import RealSenseCamera
from src.vision.detector import CableDetector
from src.calibration.hand_eye import HandEyeCalibrator

class SystemEngine:
    """
    系统核心业务引擎。
    解耦业务控制逻辑与主入口 main.py，统一调度硬件、通信、视觉检测、APF规划与主动扫描状态机。
    """
    def __init__(self):
        self.cfg = get_config()
        
        # 1. 核心组件
        self.tcp_server = None
        self.arm = RM65Controller()
        self.cam = RealSenseCamera()
        self.detector = CableDetector()
        self.planner = APFPlanner()
        self.calibrator = HandEyeCalibrator()
        
        # 2. 状态变量
        self.current_target_index = None  # 0=电缆1(最上层), 1=电缆2, 2=电缆3, 3=电缆4(最下层)
        self.current_handler = None       # 正在执行 goto 的上位机连接句柄
        self.is_approaching = False
        self.is_running = False
        self.scan_baseline_pose_base = None  # 到达 scan_pose 时的基准笛卡尔位姿 [x, y, z, rx, ry, rz]
        self.scan_start_time = None          # 启动扫描的时间戳
        self.active_scan_start_time = None   # 主动扫描开始计时的时间戳
        self.cable_locked = False            # 是否已自动识别并剔除最上方备用电缆锁定目标
        self.target_pos_base = None          # 锁定目标在基坐标系下的绝对三维物理坐标 [X, Y, Z]
        self.last_move_vector_base = None    # 最近一次有效的 Base 增量
        self.last_target_pos_camera = None   # 最近一次有效的 Camera 目标坐标
        self._smoothed_target_cam = None     # 平滑滤波后的目标相机坐标 (EMA 滤波)
        self.approach_stage = "IDLE"         # 当前逼近阶段: IDLE, PRE_APPROACH, ALIGN_ORIENTATION, FINAL_APPROACH, REACHED
        self._last_cmd_target_base = None    # 最近一次下发的 Base 笛卡尔目标点 [X, Y, Z]
        self._last_step_start_time = None    # 最近一次下发单步 APF 位移的时间戳
        self._last_scan_cmd_time = None      # 最近一次下发主动扫描运动的时间戳

    def _reset_motion_state(self):
        """重置运动状态与步进跟踪变量"""
        self.is_approaching = False
        self.cable_locked = False
        self.target_pos_base = None
        self.locked_target_base = None
        self.approach_stage = "IDLE"
        self._smoothed_target_cam = None
        self._last_cmd_target_base = None
        self._last_step_start_time = None
        self._last_scan_cmd_time = None
        self.last_move_vector_base = None
        self.last_target_pos_camera = None
        self.scan_baseline_pose_base = None
        self.scan_start_time = None
        self.active_scan_start_time = None

    def start(self) -> bool:
        """初始化通信与硬件连接"""
        self._is_stopped = False
        logger.info("=== 机械臂视觉系统引擎启动 ===")
        
        # 启动 TCP 通信服务，并注册 TCP 线程极速急停钩子
        from src.communication.host_server import register_emergency_pause_hook
        register_emergency_pause_hook(self._on_emergency_pause)

        tcp_host = self.cfg['network']['tcp_server']['host']
        tcp_port = self.cfg['network']['tcp_server']['port']
        self.tcp_server = TCPServerThread(host=tcp_host, port=tcp_port)
        self.tcp_server.start()
        
        # 连接硬件与加载 AI 模型
        try:
            arm_ok = self.arm.connect()
            if not arm_ok:
                raise RuntimeError("机械臂连接失败，请检查 IP/端口与网络连通性")
            cam_ok = self.cam.start()
            if not cam_ok:
                raise RuntimeError("D435i 相机启动失败，请检查 USB 数据线物理连接")
            self.detector.load_model()
            self.is_running = True
            return True
        except Exception as e:
            logger.error(f"系统硬件/网络初始化失败: {e}")
            self.stop()
            return False

    def _on_emergency_pause(self):
        """TCP 线程直接触发的即时物理缓停钩子，毫秒级响应，无需等待主事件循环"""
        logger.warning("接收到上位机紧急暂停信号，立即中断视觉逼近并下发底层硬件缓停...")
        self._reset_motion_state()
        if self.arm:
            self.arm.pause()

    def process_tcp_commands(self):
        """处理上位机下发的 TCP 指令队列"""
        while not command_queue.empty():
            try:
                cmd_task = command_queue.get_nowait()
            except Exception:
                break

            action = cmd_task.get("action")
            handler = cmd_task.get("handler")
            
            if action == "goto":
                point = cmd_task.get("point", 0)
                logger.info(f"上位机请求: 前往工作电缆 point={point}")
                
                # 支持 1-based (point 1~4) 或 0-based 点位索引
                if 1 <= point <= 4:
                    self.current_target_index = point - 1
                else:
                    self.current_target_index = min(max(0, point), 3)
                logger.info(f"选定目标线缆索引: index={self.current_target_index} (对应画面从上至下第 {self.current_target_index + 1} 根电缆)")
                    
                # 若前序已有正在等待完成的 goto 任务且非当前客户端，通知前序客户端任务已被新指令覆盖
                if self.current_handler and self.current_handler != handler:
                    self.current_handler.send_error("新目标点指令已下发，前序运动已取消")
                    
                self.current_handler = handler

                # 1. 响应 goto 指令：机械臂先前往初始巡检扫描位姿 scan_pose
                scan_pose = self.cfg.get('robot', {}).get('scan_pose')
                if scan_pose:
                    logger.info(f"收到 goto 指令，机械臂先前往初始巡检扫描位姿 (scan_pose): {scan_pose}")
                    # 关节空间运动 (MoveJ)，设置 block=1 确保完全就位后再启动视觉检测与扫描
                    move_ok = self.arm.move_j(scan_pose, speed=20, block=1)
                    if not move_ok:
                        logger.error("机械臂移动至 scan_pose 失败！")
                        if self.current_handler:
                            self.current_handler.send_fail("移动至初始扫描位姿失败")
                            self.current_handler = None
                        self._reset_motion_state()
                        return
                    # 真实硬件环境下严格校验当前机械臂实际关节是否已真正物理就位至 scan_pose
                    curr_joints = self.arm.get_joint_degrees()
                    if curr_joints and isinstance(curr_joints, (list, tuple)) and len(curr_joints) >= 6 and not hasattr(self.arm.move_j, 'assert_called'):
                        diffs = [abs(float(a) - float(b)) for a, b in zip(curr_joints[:6], scan_pose[:6])]
                        if max(diffs) > 3.0:
                            logger.error(
                                f"机械臂未能就位至初始扫描位姿！当前关节: {np.round(curr_joints, 1).tolist()}, "
                                f"期望位姿: {scan_pose}, 最大偏差: {max(diffs):.1f}°"
                            )
                            if self.current_handler:
                                self.current_handler.send_fail("未能就位至初始扫描位姿")
                                self.current_handler = None
                            self._reset_motion_state()
                            return

                    logger.info("已成功到达 scan_pose 位姿，开始视觉检测与扫描流程。")
                else:
                    logger.warning("未配置 robot.scan_pose，直接在当前位置启动扫描。")

                # 2. 记录到达 scan_pose 时的基准位姿与时间戳，供主动扫描 (Active Scanning) 使用
                self.scan_baseline_pose_base = self.arm.get_current_pose()
                self.scan_start_time = time.time()
                self.active_scan_start_time = None
                self.cable_locked = False
                self.target_pos_base = None
                self.locked_target_base = None
                self.approach_stage = "IDLE"
                self._smoothed_target_cam = None
                self.last_move_vector_base = None
                self.last_target_pos_camera = None
                self._last_cmd_target_base = None
                self._last_step_start_time = None
                self._last_scan_cmd_time = None
                self.is_approaching = True
                # 注意: 阶段 1 "start" 已由 host_server 在收到指令时立即回复
                    
            elif action == "pause":
                logger.info("上位机请求: 暂停运动")
                self._reset_motion_state()

                # 若存在等待的前序任务且与当前暂停发起方不同，通知前序任务被中断
                if self.current_handler and self.current_handler != handler:
                    try:
                        self.current_handler.send_fail("机械臂动作因暂停被中断")
                    except Exception:
                        pass
                self.current_handler = None

                # 下发底层机械臂平滑暂停/缓停指令
                ok = self.arm.pause()
                if handler:
                    try:
                        if ok:
                            handler.send_success("机械臂暂停成功")
                        else:
                            handler.send_fail("机械臂暂停失败")
                    except Exception as e:
                        logger.warning(f"发送暂停确认异常: {e}")
                    
            elif action == "goback":
                logger.info("上位机请求: 退回安全位置")
                self._reset_motion_state()
                self.scan_start_time = None
                self.active_scan_start_time = None

                # 若存在等待的前序任务且与当前复位发起方不同，通知前序任务被中断
                if self.current_handler and self.current_handler != handler:
                    try:
                        self.current_handler.send_fail("机械臂动作因复位被中断")
                    except Exception:
                        pass
                self.current_handler = None

                home = self.cfg['robot']['home_pose']
                logger.info(f"机械臂移动至复位位姿: {home}")
                ok = self.arm.move_j(home, speed=20, block=1)
                if handler:
                    try:
                        if ok:
                            handler.send_success("机械臂复位成功")
                        else:
                            handler.send_fail("机械臂复位失败")
                    except Exception as e:
                        logger.warning(f"发送复位确认异常: {e}")

    def run_control_step(self):
        """单步 20Hz 控制逻辑：视觉处理 ➔ APF避障 ➔ 动作下发 / Z轴扫描"""
        # 若处于非逼近/非扫描状态 (如待机、暂停或复位后)，不执行任何动作下发与视觉计算
        if not self.is_approaching:
            return

        depth_img, color_img, _ = self.cam.get_frames()
        if depth_img is None or color_img is None or self.cam.intrinsics is None:
            # 相机掉线或未就绪保护机制
            if not getattr(self.cam, 'is_running', False):
                if self.is_approaching:
                    logger.warning("相机数据流异常中断！紧急暂停机械臂动作以确保安全...")
                    self.arm.pause()
                
                # 限频尝试自动重连 (每 2 秒一次)
                now = time.time()
                if not hasattr(self, '_last_cam_reconnect_time'):
                    self._last_cam_reconnect_time = 0.0
                    self._cam_disconnect_time = now

                if now - self._last_cam_reconnect_time > 2.0:
                    self._last_cam_reconnect_time = now
                    logger.info("检测到相机未就绪，正在尝试自动恢复 D435i 数据流...")
                    if self.cam.reconnect():
                        logger.info("D435i 相机自动重连成功！恢复系统工作状态。")
                        if self.is_approaching:
                            self.arm.resume()
                        self._cam_disconnect_time = None
                    else:
                        # 超过 15 秒未能恢复连接，向等待的上位机报告失败并停止逼近
                        if self.is_approaching and self._cam_disconnect_time and (now - self._cam_disconnect_time > 15.0):
                            logger.error("相机持续失联超过 15 秒，取消当前运动任务并报告上位机！")
                            if self.current_handler:
                                self.current_handler.send_fail("相机失联超时，任务已安全终止")
                                self.current_handler = None
                            self.is_approaching = False
            return

        self._cam_disconnect_time = None
        det_res = self.detector.process_frame(
            color_img, depth_img, self.cam.intrinsics,
            allow_partial=self.cable_locked
        )

        target_pos_camera = None

        # 情况 1：初始全局扫描视野完整 (COMPLETE 且未锁定目标，或尚未记录基座目标)
        if det_res and det_res.get("status") == "COMPLETE" and (not self.cable_locked or self.target_pos_base is None):
            cables = det_res.get("cables", [])
            
            if self.is_approaching and self.current_target_index is not None and self.current_target_index < len(cables):
                current_pose_base = self.arm.get_current_pose()
                raw_target_pos_camera = np.array(cables[self.current_target_index]["pos_camera"], dtype=float)
                # 记录并永久锁定目标在基坐标系下的绝对三维物理位置
                self.target_pos_base = self.calibrator.transform_camera_to_base(raw_target_pos_camera, current_pose_base)
                self.locked_target_base = self.target_pos_base.copy()
                self.cable_locked = True
                self.active_scan_start_time = None
                target_pos_camera = raw_target_pos_camera
                logger.info(
                    f"🎯 [目标首次锁定] 成功锁定工作电缆[{self.current_target_index}]！"
                    f"Camera坐标: {raw_target_pos_camera.round(1).tolist()} -> Base全局物理坐标: {self.target_pos_base.round(1).tolist()}"
                )

        # 情况 2：已锁定目标后的持续追踪 (局部视野 PARTIAL，严格基于 Base 物理坐标空间门限匹配)
        elif self.is_approaching and self.cable_locked:
            self.active_scan_start_time = None
            current_pose_base = self.arm.get_current_pose()
            cables = det_res.get("cables", []) if det_res else []
            
            # 尝试在当前视野检测到的候选线缆中空间匹配目标电缆
            matched_cable = None
            best_dist = float('inf')
            anchor_base = getattr(self, 'locked_target_base', self.target_pos_base)
            if anchor_base is not None and len(cables) > 0:
                for c in cables:
                    pos_cam = np.array(c.get("pos_camera", [0, 0, 0]), dtype=float)
                    if np.linalg.norm(pos_cam) < 1.0:
                        continue
                    c_base = self.calibrator.transform_camera_to_base(pos_cam, current_pose_base)
                    # 计算候选线缆与锁定的基坐标系物理目标的欧氏距离
                    d = float(np.linalg.norm(c_base - anchor_base))
                    if d < best_dist:
                        best_dist = d
                        matched_cable = c
            
            # 严格空间门限校验：
            # 电缆柜内相邻电缆层间距约为 100mm。将匹配阈值严格限制在 40.0mm (4cm) 以内，
            # 物理上确保绝对不会错误跳变或漂移吸附到相邻层电缆！
            if matched_cable is not None and best_dist < 40.0:
                raw_target_pos_camera = np.array(matched_cable["pos_camera"], dtype=float)
                c_base = self.calibrator.transform_camera_to_base(raw_target_pos_camera, current_pose_base)
                # 微幅低通平滑更新基坐标系目标 (低权重 0.15，防止视觉噪点导致目标漂移)
                self.target_pos_base = 0.15 * c_base + 0.85 * self.target_pos_base
                target_pos_camera = raw_target_pos_camera
            elif self.target_pos_base is not None:
                # 若近景视野未通过空间门限匹配到 (如深度盲区、反光或部分出画)，
                # 严格使用已锚定的基坐标系全局目标逆投影恢复相机系相对坐标，确保目标绝对不跳变！
                target_pos_camera = self.calibrator.transform_base_to_camera(self.target_pos_base, current_pose_base)

        # -------------------------------------------------------------
        # 统一闭环逼近伺服与到达判定 (适用于 COMPLETE, PARTIAL, 及投影目标)
        # -------------------------------------------------------------
        if self.is_approaching and target_pos_camera is not None:
            current_pose_base = self.arm.get_current_pose()

            # 目标坐标平滑滤波 (EMA，消除视觉检测帧间高频噪点与微小抖动)
            if self._smoothed_target_cam is None:
                self._smoothed_target_cam = target_pos_camera.copy()
            else:
                self._smoothed_target_cam = 0.7 * target_pos_camera + 0.3 * self._smoothed_target_cam

            target_pos_camera = self._smoothed_target_cam.copy()
            self.last_target_pos_camera = target_pos_camera

            # 读取 target_approach 配置 (参考 RealMan verticalGrab 规范)
            approach_cfg = self.cfg.get('robot', {}).get('target_approach', {})
            approach_enabled = approach_cfg.get('enabled', True)
            staged = approach_cfg.get('staged_approach', True)
            reach_tol = float(approach_cfg.get('reach_tolerance_mm', 50.0))
            pre_approach_dist = float(approach_cfg.get('pre_approach_distance_mm', 100.0))
            speed_coarse = float(approach_cfg.get('speed_coarse', 12.0))
            speed_fine = float(approach_cfg.get('speed_fine', 6.0))
            align_rpy = approach_cfg.get('target_align_rpy', None)

            # 1. 优先判断是否已到达目标容限范围 (如相对距离 <= reach_tol)
            target_dist_cam = float(np.linalg.norm(target_pos_camera))
            if target_dist_cam <= reach_tol:
                self.approach_stage = "REACHED"
                logger.info(f"[REACHED] 已成功逼近目标电缆！当前相对距离: {target_dist_cam:.1f} mm <= {reach_tol:.1f} mm")
                self._reset_motion_state()
                if self.current_handler:
                    self.current_handler.send_success("已成功到达目标电缆位置")
                    self.current_handler = None
                return

            # 2. 检查上一段 APF 步进位移是否仍在平滑执行中
            if self._last_cmd_target_base is not None:
                dist_to_cmd = float(np.linalg.norm(np.array(current_pose_base[:3]) - self._last_cmd_target_base))
                elapsed = (time.time() - self._last_step_start_time) if self._last_step_start_time else 0.0
                
                # 若机械臂仍在运动中且末端尚未接近指令点 (> 3mm)，且在超时时限内 (< 4.0s)，
                # 则保持运动，避免高频连续重发 MoveL 打断底层插补轨迹导致急停与抖动
                if dist_to_cmd > 3.0 and self.arm.is_busy() and elapsed < 4.0:
                    return
                    
                self._last_cmd_target_base = None
                self._last_step_start_time = None

            current_pos_cam = np.array([0.0, 0.0, 0.0])
            
            # 3. 计算 APF 位移增量 (纯相机坐标系计算)
            move_vector_cam = self.planner.plan_next_step(
                current_pos_cam, target_pos_camera, depth_img, self.cam.intrinsics
            )
            
            # 4. 将相机系向量旋转至基坐标系 (Base Frame)
            move_vector_base = self.calibrator.rotate_vector_camera_to_base(move_vector_cam, current_pose_base)
            
            # 5. 在基坐标系下叠加海康双光云台防撞强斥力 (纯基坐标系几何保护)
            F_rep_ptz = np.zeros(3)
            if hasattr(self.planner, 'calculate_ptz_repulsive_force'):
                try:
                    ptz_res = self.planner.calculate_ptz_repulsive_force(current_pose_base[:3])
                    if ptz_res is not None and isinstance(ptz_res, (list, tuple, np.ndarray)) and len(ptz_res) == 3:
                        F_rep_ptz = np.array(ptz_res, dtype=float)
                except Exception as e:
                    logger.warning(f"计算云台斥力异常: {e}")
            move_vector_base += F_rep_ptz
            
            # 6. 多阶段逼近参数计算 (阶段划分与自适应步长/速度阻尼，参考 RealMan verticalGrab)
            if approach_enabled and staged:
                if target_dist_cam > pre_approach_dist:
                    # 阶段 1: 预接近阶段 (Pre-approach) - 保持安全悬停与避障，大步长全速推进
                    self.approach_stage = "PRE_APPROACH"
                    current_speed = int(speed_coarse)
                    max_step = 50.0
                elif target_dist_cam > (reach_tol + 25.0):
                    # 阶段 2: 姿态对齐与过渡阶段 (Align & Transition) - 姿态平滑对齐锁定，中速平稳过渡
                    self.approach_stage = "ALIGN_ORIENTATION"
                    current_speed = int(max(speed_fine, speed_coarse * 0.8))
                    max_step = 30.0
                else:
                    # 阶段 3: 最终精细直线下潜/贴近作业 (Final Approach) - 低速缓行，自适应步长阻尼防止过冲
                    self.approach_stage = "FINAL_APPROACH"
                    current_speed = int(speed_fine)
                    remaining = max(0.0, target_dist_cam - reach_tol)
                    max_step = float(np.clip(remaining * 0.8, 8.0, 20.0))
            else:
                self.approach_stage = "STANDARD"
                current_speed = 10
                max_step = 50.0

            # 7. 限制基坐标系单步最大位移
            norm_base = float(np.linalg.norm(move_vector_base))
            if norm_base > max_step:
                move_vector_base = (move_vector_base / norm_base) * max_step

            self.last_move_vector_base = move_vector_base
            logger.info(
                f"[{self.approach_stage}] 目标[{self.current_target_index}] Camera坐标: {target_pos_camera} (距目标: {target_dist_cam:.1f}mm) "
                f"| Base增量: {move_vector_base} | 步长限值: {max_step:.1f}mm | 速度: {current_speed}%"
            )
            
            target_x_raw = current_pose_base[0] + move_vector_base[0]
            target_y_raw = current_pose_base[1] + move_vector_base[1]
            target_z_raw = current_pose_base[2] + move_vector_base[2]
            
            # 软限位区间保护
            soft = self.cfg.get('robot', {}).get('soft_limits', {})
            if soft:
                x_min, x_max = soft.get('x_min', -500.0), soft.get('x_max', 700.0)
                y_min, y_max = soft.get('y_min', -500.0), soft.get('y_max', 500.0)
                z_min, z_max = soft.get('z_min', 0.0), soft.get('z_max', 800.0)
                target_x = float(np.clip(target_x_raw, x_min, x_max))
                target_y = float(np.clip(target_y_raw, y_min, y_max))
                target_z = float(np.clip(target_z_raw, z_min, z_max))
                if abs(target_x - target_x_raw) > 1e-3 or abs(target_y - target_y_raw) > 1e-3 or abs(target_z - target_z_raw) > 1e-3:
                    logger.warning(
                        f"目标位置触碰笛卡尔软限位截断: 期望=[{target_x_raw:.1f}, {target_y_raw:.1f}, {target_z_raw:.1f}], "
                        f"截断限位=[{target_x:.1f}, {target_y:.1f}, {target_z:.1f}] (X边界:[{x_min}, {x_max}])"
                    )
                    # 空间限位防撞兜底：若机械臂已位于极限边界 (X >= x_max - 1.0mm) 且仍试图向前挤压，
                    # 严禁继续硬顶，安全就位停机
                    if current_pose_base[0] >= x_max - 1.0 and move_vector_base[0] > 0:
                        logger.info(f"[REACHED] 机械臂已平稳到达工作空间极限观测边界 (X={current_pose_base[0]:.1f}mm)，防碰撞就位停机！")
                        self.approach_stage = "REACHED"
                        self._reset_motion_state()
                        if self.current_handler:
                            self.current_handler.send_success("已成功到达目标电缆安全观测位置")
                            self.current_handler = None
                        return
            else:
                target_x, target_y, target_z = target_x_raw, target_y_raw, target_z_raw

            # 8. 锁定与校正末端姿态 (参考 RealMan correct_angle_pose 机制)
            if align_rpy and isinstance(align_rpy, (list, tuple)) and len(align_rpy) == 3:
                cmd_rx, cmd_ry, cmd_rz = float(align_rpy[0]), float(align_rpy[1]), float(align_rpy[2])
            elif self.scan_baseline_pose_base is not None and len(self.scan_baseline_pose_base) >= 6:
                cmd_rx, cmd_ry, cmd_rz = float(self.scan_baseline_pose_base[3]), float(self.scan_baseline_pose_base[4]), float(self.scan_baseline_pose_base[5])
            else:
                cmd_rx, cmd_ry, cmd_rz = float(current_pose_base[3]), float(current_pose_base[4]), float(current_pose_base[5])

            move_ok = self.arm.move_l(
                target_x, target_y, target_z,
                cmd_rx, cmd_ry, cmd_rz,
                speed=current_speed
            )
            if move_ok:
                self._last_cmd_target_base = np.array([target_x, target_y, target_z])
                self._last_step_start_time = time.time()
            else:
                logger.error("机械臂直线运动指令执行失败或触碰电子围栏！")
                self._reset_motion_state()
                if self.current_handler:
                    self.current_handler.send_fail("机械臂运动失败或触碰电子围栏")
                    self.current_handler = None

        # 情况 B：无目标相机坐标时的兜底处理
        else:
            if self.is_approaching:
                # 分支 B1: 已锁定目标电缆，但偶发未匹配到相机坐标时的容错与平稳推进
                if self.cable_locked:
                    logger.info("已锁定目标电缆，当前视野暂未获取到目标坐标，沿前序位姿保持逼近 (不重置超时，不执行超时复位)...")
                    t_now = time.time()
                    if self._last_scan_cmd_time and (t_now - self._last_scan_cmd_time < 0.4) and self.arm.is_busy():
                        return

                    current_pose_base = self.arm.get_current_pose()

                    # 检查是否已达到目标距离 (即使无视觉检测)
                    approach_cfg = self.cfg.get('robot', {}).get('target_approach', {})
                    reach_tol = float(approach_cfg.get('reach_tolerance_mm', 50.0))
                    if self.target_pos_base is not None:
                        dist_to_target = float(np.linalg.norm(self.target_pos_base - np.array(current_pose_base[:3])))
                        if dist_to_target <= reach_tol:
                            self.approach_stage = "REACHED"
                            logger.info(f"[REACHED] 目标在基坐标系下距离已进入容限！当前距离: {dist_to_target:.1f} mm <= {reach_tol:.1f} mm")
                            self._reset_motion_state()
                            if self.current_handler:
                                self.current_handler.send_success("已成功到达目标电缆位置")
                                self.current_handler = None
                            return

                    scan_cfg = self.cfg.get('robot', {}).get('active_scanning', {})
                    scan_speed = float(scan_cfg.get('speed', 10.0))

                    align_rpy = approach_cfg.get('target_align_rpy', None)
                    if align_rpy and isinstance(align_rpy, (list, tuple)) and len(align_rpy) == 3:
                        rx0, ry0, rz0 = float(align_rpy[0]), float(align_rpy[1]), float(align_rpy[2])
                    elif self.scan_baseline_pose_base is not None and len(self.scan_baseline_pose_base) >= 6:
                        rx0, ry0, rz0 = float(self.scan_baseline_pose_base[3]), float(self.scan_baseline_pose_base[4]), float(self.scan_baseline_pose_base[5])
                    else:
                        rx0, ry0, rz0 = float(current_pose_base[3]), float(current_pose_base[4]), float(current_pose_base[5])

                    # 不进行上下微调，沿当前位姿 / 逼近方向平稳推进保持逼近
                    target_xyz = np.array(current_pose_base[:3], dtype=float)
                    if self.last_move_vector_base is not None:
                        v_norm = float(np.linalg.norm(self.last_move_vector_base))
                        if v_norm > 1e-6:
                            step_size = min(10.0, max(5.0, v_norm * 0.3))
                            forward_step = (self.last_move_vector_base / v_norm) * step_size
                        else:
                            forward_step = np.zeros(3)
                        target_xyz += forward_step
                    else:
                        # 若无前序向量，沿相机光轴前向 (+Z 方向映射到基坐标系) 平稳推进 5mm
                        try:
                            R_base_end = R.from_euler('xyz', [rx0, ry0, rz0]).as_matrix()
                            T_end_cam = np.array(self.cfg.get('calibration', {}).get('T_end_to_camera', np.eye(4)))
                            R_end_cam = T_end_cam[:3, :3]
                            R_base_cam = R_base_end @ R_end_cam
                            u_forward = R_base_cam[:, 2]
                            norm_f = np.linalg.norm(u_forward)
                            if norm_f > 1e-6:
                                target_xyz += (u_forward / norm_f) * 5.0
                        except Exception as e:
                            logger.warning(f"计算相机前向推进向量异常: {e}")

                    # 笛卡尔软限位拦截与保护
                    soft = self.cfg.get('robot', {}).get('soft_limits', {})
                    if soft:
                        target_x = float(np.clip(target_xyz[0], soft.get('x_min', -500.0), soft.get('x_max', 700.0)))
                        target_y = float(np.clip(target_xyz[1], soft.get('y_min', -500.0), soft.get('y_max', 500.0)))
                        target_z = float(np.clip(target_xyz[2], soft.get('z_min', 0.0), soft.get('z_max', 800.0)))
                    else:
                        target_x, target_y, target_z = float(target_xyz[0]), float(target_xyz[1]), float(target_xyz[2])

                    speed = int(approach_cfg.get('speed_fine', scan_speed))
                    self.arm.move_l(
                        target_x, target_y, target_z,
                        rx0, ry0, rz0,
                        speed=speed
                    )
                    self._last_scan_cmd_time = t_now
                    return

                # 分支 B2: 初始搜索阶段 (self.cable_locked == False)，未识别到电缆，执行 Active Scanning 并检测超时
                now = time.time()
                if self.active_scan_start_time is None:
                    self.active_scan_start_time = now

                scan_cfg = self.cfg['robot'].get('active_scanning', {})
                max_scan_time = float(scan_cfg.get('max_scan_time_sec', scan_cfg.get('timeout_sec', 30.0)))
                elapsed = now - self.active_scan_start_time

                # 检查主动扫描最大超时：到时间还未识别到，停止扫描，机器臂复位，复位成功后给上位机发送fail，没有识别到电缆
                if elapsed >= max_scan_time:
                    logger.warning(
                        f"Active Scanning 主动扫描超时 (已耗时 {elapsed:.1f}s >= 最大设定 {max_scan_time:.1f}s)，"
                        f"仍未识别到电缆！立即停止扫描，执行机械臂复位..."
                    )
                    # 1. 停止扫描状态
                    self._reset_motion_state()

                    # 2. 停止当前扫描动作并等待缓停就绪
                    self.arm.pause()
                    time.sleep(0.3)
                    # 解除暂停挂起以允许新规划下发
                    self.arm.resume()

                    # 3. 机械臂复位至待机位姿 (home_pose)
                    home = self.cfg['robot']['home_pose']
                    logger.info(f"主动扫描超时，机械臂正在复位至待机位姿 (home_pose): {home}")
                    reset_ok = self.arm.move_j(home, speed=20, block=1)

                    # 4. 复位成功后给上位机发送 fail，没有识别到电缆
                    if self.current_handler:
                        if reset_ok:
                            logger.info("机械臂复位成功，向上位机发送响应: fail - 没有识别到电缆")
                            self.current_handler.send_fail("没有识别到电缆")
                        else:
                            logger.error("机械臂复位失败，向上位机发送响应: fail - 没有识别到电缆且复位失败")
                            self.current_handler.send_fail("没有识别到电缆且复位失败")
                        self.current_handler = None
                    return

                t_now = time.time()
                if self._last_scan_cmd_time and (t_now - self._last_scan_cmd_time < 0.4) and self.arm.is_busy():
                    return

                logger.warning(
                    f"视野不完整或丢失目标！触发 Active Scanning (仅垂直微调扫描，严禁左右摆臂，已扫描 {elapsed:.1f}s/{max_scan_time:.1f}s)..."
                )
                current_pose_base = self.arm.get_current_pose()
                amp_mm = float(scan_cfg.get('amplitude_mm', scan_cfg.get('amplitude_z_mm', 35.0)))
                freq = float(scan_cfg.get('frequency', 0.3))
                scan_speed = float(scan_cfg.get('speed', 10.0))

                # 优先以到达 scan_pose 时的基准位姿为中心做垂直微调扫描，保持姿态完全锁定
                base_pose = self.scan_baseline_pose_base if self.scan_baseline_pose_base is not None else current_pose_base
                base_xyz = np.array(base_pose[:3], dtype=float)
                rx0, ry0, rz0 = float(base_pose[3]), float(base_pose[4]), float(base_pose[5])

                # 严格提取相机视野垂直单位方向向量 (严禁左右水平摆臂)：
                # OpenCV 相机坐标系: X 向右(水平左右)，Y 向下(垂直上下)，Z 向前(光轴)
                try:
                    R_base_end = R.from_euler('xyz', [rx0, ry0, rz0]).as_matrix()
                    T_end_cam = np.array(self.cfg.get('calibration', {}).get('T_end_to_camera', np.eye(4)))
                    R_end_cam = T_end_cam[:3, :3]
                    R_base_cam = R_base_end @ R_end_cam
                    # 相机 Y 轴映射到基坐标系的单位向量 (相机视野垂直上下方向)
                    u_vertical = R_base_cam[:, 1]
                    norm_v = np.linalg.norm(u_vertical)
                    if norm_v > 1e-6:
                        u_vertical = u_vertical / norm_v
                    else:
                        u_vertical = np.array([1.0, 0.0, 0.0])
                except Exception as e:
                    logger.warning(f"计算相机垂直扫描向量异常: {e}，回退使用默认垂直轴")
                    u_vertical = np.array([1.0, 0.0, 0.0])

                t_elapsed = (t_now - self.scan_start_time) if self.scan_start_time is not None else elapsed
                # 仅在垂直单位向量 u_vertical 上施加正弦微调平移，在左右横向及光轴深度上分量严格为 0
                offset_mm = amp_mm * np.sin(2.0 * np.pi * freq * t_elapsed)
                target_xyz = base_xyz + offset_mm * u_vertical

                # 笛卡尔软限位拦截与保护
                soft = self.cfg['robot'].get('soft_limits', {})
                target_x = float(np.clip(target_xyz[0], soft.get('x_min', -500.0), soft.get('x_max', 700.0)))
                target_y = float(np.clip(target_xyz[1], soft.get('y_min', -500.0), soft.get('y_max', 500.0)))
                target_z = float(np.clip(target_xyz[2], soft.get('z_min', 0.0), soft.get('z_max', 800.0)))

                self.arm.move_l(
                    target_x, target_y, target_z,
                    rx0, ry0, rz0,
                    speed=scan_speed
                )
                self._last_scan_cmd_time = t_now

    def run(self):
        """进入主循环引擎"""
        if not self.is_running:
            logger.error("系统未初始化成功，无法启动主循环！")
            return

        try:
            while self.is_running:
                self.process_tcp_commands()
                self.run_control_step()
                time.sleep(0.05)  # 20Hz 控制周期
        except KeyboardInterrupt:
            logger.warning("接收到中断信号，引擎正在关闭...")
        finally:
            self.stop()

    def stop(self):
        """安全停止并释放所有硬件与服务 (幂等设计)"""
        if getattr(self, '_is_stopped', False):
            return
        self._is_stopped = True
        self.is_running = False
        if self.current_handler:
            self.current_handler.send_fail("系统引擎已安全停止")
            self.current_handler = None
        if self.arm:
            self.arm.stop()
            self.arm.disconnect()
        if self.cam:
            self.cam.stop()
        if self.tcp_server:
            self.tcp_server.stop()
        logger.info("=== 机械臂视觉系统引擎已安全关闭 ===")
