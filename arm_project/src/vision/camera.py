import time
import numpy as np
try:
    import pyrealsense2 as rs
except ImportError:
    rs = None  # 在没有相机的环境下允许被导入，防止崩溃

from src.core.logger import logger
from src.core.config_loader import get_config

class RealSenseCamera:
    """
    D435i 相机驱动模块。
    负责初始化数据流、执行广角对齐(Color to Depth)以及获取内参。
    """
    def __init__(self):
        if rs is None:
            logger.error("pyrealsense2 库未安装，相机驱动将无法启动！")
            
        self.cfg = get_config()['vision']['camera']
        self.pipeline = None
        self.align = None
        self.intrinsics = None
        self.depth_scale = None
        self.is_running = False

    @staticmethod
    def reset_usb_device() -> bool:
        """调用系统级 usbreset 工具重置 D435i USB 端口 (VID 8086, PID 0b3a)"""
        try:
            import subprocess
            res = subprocess.run(['usbreset', '8086:0b3a'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
            if res.returncode == 0:
                logger.info("已通过 usbreset 成功重置 RealSense USB 端口")
                return True
        except Exception as e:
            logger.debug(f"usbreset 执行跳过或失败: {e}")
        return False

    def reset_realsense_hardware(self) -> bool:
        """
        执行硬件/USB总线级复位与链路重建：
        优先使用 librealsense 原生 hardware_reset()，若无设备枚举则尝试系统级 usbreset。
        """
        logger.warning("正在对 D435i 相机执行硬件/USB总线级复位与链路重建...")
        reset_done = False
        
        # 1. 尝试 librealsense 原生 hardware_reset
        if rs is not None:
            try:
                ctx = rs.context()
                devices = list(ctx.query_devices())
                for dev in devices:
                    dev_name = dev.get_info(rs.camera_info.name) if dev.supports(rs.camera_info.name) else "RealSense"
                    logger.info(f"发送 hardware_reset 指令至相机固件: {dev_name}")
                    dev.hardware_reset()
                    reset_done = True
            except Exception as e:
                logger.warning(f"librealsense hardware_reset 异常: {e}")

        # 2. 若原生方式未枚举到设备，调用底层 usbreset
        if not reset_done:
            reset_done = self.reset_usb_device()

        if reset_done:
            # 给予 Linux 内核与 RealSense 固件 2 秒重新枚举时间
            time.sleep(2.0)
            return True
        return False

    def start(self, retry_on_failure: bool = True) -> bool:
        """启动相机管线并配置对齐，支持启动失败自动硬件级复位重试"""
        if self.is_running:
            return True

        # 若此前管线异常，先清理残留句柄
        if self.pipeline:
            try:
                self.pipeline.stop()
            except Exception:
                pass
            self.pipeline = None

        if rs is None:
            logger.error("pyrealsense2 库未安装，相机驱动无法启动！")
            return False

        max_attempts = 2 if retry_on_failure else 1
        for attempt in range(max_attempts):
            try:
                self.pipeline = rs.pipeline()
                config = rs.config()

                # 从全局配置中读取分辨率和帧率
                config.enable_stream(rs.stream.depth, 
                                     self.cfg['depth_width'], 
                                     self.cfg['depth_height'], 
                                     rs.format.z16, 
                                     self.cfg['fps'])
                                     
                config.enable_stream(rs.stream.color, 
                                     self.cfg['color_width'], 
                                     self.cfg['color_height'], 
                                     rs.format.bgr8, 
                                     self.cfg['fps'])

                # 启动数据流
                profile = self.pipeline.start(config)
                
                # 获取深度传感器的缩放比例 (真实世界距离 = 像素值 * depth_scale)
                depth_sensor = profile.get_device().first_depth_sensor()
                self.depth_scale = depth_sensor.get_depth_scale()
                logger.info(f"D435i 深度比例尺 (Depth Scale): {self.depth_scale}")

                # 获取彩色相机的内参 (因深度图强制对齐到彩色图，像素坐标系属于 1280x720 彩色相机)
                color_stream = profile.get_stream(rs.stream.color)
                self.intrinsics = color_stream.as_video_stream_profile().get_intrinsics()
                try:
                    logger.info(f"D435i 彩色内参已加载 (用于 2D->3D 重投影): {self.intrinsics.width}x{self.intrinsics.height}, fx={float(self.intrinsics.fx):.2f}, fy={float(self.intrinsics.fy):.2f}, ppx={float(self.intrinsics.ppx):.2f}, ppy={float(self.intrinsics.ppy):.2f}")
                except Exception:
                    logger.info(f"D435i 彩色内参已加载: {self.intrinsics}")

                # 【核心架构对齐】：深度图强制对齐到彩色图 (Depth to Color Alignment)
                align_to = rs.stream.color
                self.align = rs.align(align_to)
                
                # 丢弃前几帧以允许自动曝光(AE)稳定
                for _ in range(10):
                    self.pipeline.wait_for_frames(timeout_ms=3000)
                    
                self.is_running = True
                logger.info("D435i 相机启动成功，广角对齐(Color-to-Depth)就绪。")
                return True

            except Exception as e:
                logger.error(f"D435i 相机启动尝试 [{attempt+1}/{max_attempts}] 失败: {e}")
                self.mark_disconnected()
                
                # 如果首次失败且允许重试，触发硬件级复位后重试
                if attempt == 0 and retry_on_failure:
                    logger.info("正在执行相机硬件/USB链路自愈复位，稍候将重试连接...")
                    self.reset_realsense_hardware()
                else:
                    return False
        return False

    def mark_disconnected(self):
        """标记相机掉线并释放失效管线"""
        self.is_running = False
        if self.pipeline:
            try:
                self.pipeline.stop()
            except Exception:
                pass
            self.pipeline = None

    def reconnect(self) -> bool:
        """尝试重新连接并恢复相机管线 (内嵌硬件复位自愈)"""
        if self.is_running:
            return True
        logger.info("正在尝试重新建立 D435i 相机管线连接...")
        self.mark_disconnected()
        return self.start(retry_on_failure=True)

    def get_frames(self, timeout_ms: int = 1000):
        """
        获取对齐后的深度图和彩色图
        :param timeout_ms: 帧获取超时毫秒数，默认 1000ms 防止阻塞 20Hz 主循环
        :return: (depth_image_np, color_image_np, depth_frame_raw)
                 如果失败返回 (None, None, None)
        """
        if not self.is_running or self.pipeline is None:
            return None, None, None

        try:
            frames = self.pipeline.wait_for_frames(timeout_ms=timeout_ms)
            
            # 执行对齐操作 (将 RGB 像素拉伸/映射到广角的 Depth 坐标系下)
            aligned_frames = self.align.process(frames)
            
            aligned_depth_frame = aligned_frames.get_depth_frame()
            aligned_color_frame = aligned_frames.get_color_frame()

            if not aligned_depth_frame or not aligned_color_frame:
                logger.warning("获取对齐帧失败，丢弃当前帧")
                return None, None, None

            # 转换为 numpy 数组以便进行 OpenCV / YOLO 处理
            depth_image = np.asanyarray(aligned_depth_frame.get_data())
            color_image = np.asanyarray(aligned_color_frame.get_data())

            return depth_image, color_image, aligned_depth_frame

        except Exception as e:
            err_msg = str(e)
            logger.error(f"获取相机帧异常: {err_msg}")
            # 检测设备物理掉线、管线损坏或超时失效，及时重置状态避免刷屏
            if any(k in err_msg for k in ["before start", "disconnected", "No device connected", "Frame didn't arrive"]):
                logger.warning("D435i 相机数据流异常中断，已自动标记离线并重置管线。")
                self.mark_disconnected()
            return None, None, None

    def stop(self):
        """安全关闭相机管线"""
        was_running = self.is_running or (self.pipeline is not None)
        self.is_running = False
        if self.pipeline:
            try:
                self.pipeline.stop()
            except Exception:
                pass
            self.pipeline = None
        if was_running:
            try:
                logger.info("D435i 相机已安全关闭。")
            except Exception:
                pass

# 测试模块
if __name__ == "__main__":
    cam = RealSenseCamera()
    cam.start()
    depth, color, _ = cam.get_frames()
    if depth is not None:
        logger.info(f"成功抓取深度图，分辨率: {depth.shape}")
        logger.info(f"成功抓取彩色图，分辨率: {color.shape} (已对齐至深度图视野)")
    cam.stop()
