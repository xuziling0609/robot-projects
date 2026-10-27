import numpy as np
from src.core.logger import logger
from src.core.config_loader import get_config

try:
    import pyrealsense2 as rs
    from ultralytics import YOLO
except ImportError:
    rs = None
    YOLO = None

class CableDetector:
    """
    电缆视觉检测器 (基于 YOLOv8 彩色图语义识别与深度测距)。
    采用 RGB-D 标准融合架构，集成假阳性防呆 (Spatial Validation) 与 深度黑洞滤除 (ROI Median)。
    """
    def __init__(self, exclude_spare_cable: bool = None):
        self.full_cfg = get_config()
        self.cfg = self.full_cfg.get('vision', {})
        self.model_path = self.cfg.get('model_path', 'models/demo.pt')
        self.model = None
        self.depth_top_ratio = float(
            self.full_cfg.get('robot', {}).get('target_approach', {}).get('depth_top_ratio', 0.20)
        )
        if exclude_spare_cable is not None:
            self.exclude_spare_cable = exclude_spare_cable
        else:
            self.exclude_spare_cable = bool(self.cfg.get('exclude_spare_cable', False))

    def load_model(self):
        if YOLO is None:
            logger.error("ultralytics 库未安装，无法加载 YOLO 模型！")
            return
            
        try:
            logger.info(f"正在加载 YOLO 模型: {self.model_path}")
            self.model = YOLO(self.model_path)
            logger.info(f"YOLO 模型 [{self.model_path}] 加载成功！")
        except Exception as e:
            logger.warning(f"加载模型 {self.model_path} 失败 ({e})，尝试自动降级加载 models/cable.pt...")
            try:
                self.model = YOLO("models/cable.pt")
                logger.info("降级加载 models/cable.pt 成功！")
            except Exception as ex:
                logger.error(f"降级加载通用模型同样失败: {ex}")

    def group_bboxes_into_rows(self, bboxes: list, y_threshold: int = 40) -> list:
        """
        Step 1: 按 Y 轴中心高度对 Bounding Box 进行动态聚类。
        应对不同视角下线缆被垂直金属支架/夹具切分为多段（如2段或3段）的情况。
        将同一高度水平线上的碎片归为同一层线缆。
        """
        if not bboxes:
            return []

        # 按照 y_center 升序排序
        sorted_boxes = sorted(bboxes, key=lambda b: (b[1] + b[3]) / 2.0)

        rows = []
        current_row = [sorted_boxes[0]]

        for box in sorted_boxes[1:]:
            prev_y = (current_row[-1][1] + current_row[-1][3]) / 2.0
            curr_y = (box[1] + box[3]) / 2.0

            # Y 轴中心在阈值范围内，归为同一层线缆
            if abs(curr_y - prev_y) < y_threshold:
                current_row.append(box)
            else:
                rows.append(current_row)
                current_row = [box]
        rows.append(current_row)

        return rows

    def select_main_segment(self, row_boxes: list) -> list:
        """
        Step 2: 在同层线缆的多段 Bounding Box 中，挑选包围盒面积 (Width x Height) 最大的主体段。
        有效规避边缘残缺小片段的噪点干扰。
        """
        best_box = max(row_boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
        return best_box

    def validate_spatial_geometry(self, rows: list, expected_rows: int = 4) -> bool:
        """
        假阳性防呆校验：
        判断聚类出的线缆层数是否符合预期的 4 层。
        """
        if len(rows) != expected_rows:
            logger.warning(f"空间校验失败：当前场景聚类出 {len(rows)} 层线缆，期望为 {expected_rows} 层。可能是扫描视角偏离。")
            return False
        return True

    def get_robust_depth(self, depth_frame_np: np.ndarray, bbox: list, roi_size: int = 10, top_k_ratio: float = 0.20) -> float:
        """
        Step 3: 抗黑洞与背景滤除鲁棒深度提取 (参考 RealMan verticalGrab 规范)
        在主体 bbox 中心区域采样，过滤 0 值黑洞后进行排序，
        取最近的前 20% 有效深度计算平均值，精准获取物体最外层真实物理表面，
        杜绝背景板穿透与边缘飞点。
        """
        x1, y1, x2, y2 = map(int, bbox)
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        
        half = roi_size // 2
        h, w = depth_frame_np.shape
        r_y1 = max(0, cy - half)
        r_y2 = min(h, cy + half)
        r_x1 = max(0, cx - half)
        r_x2 = min(w, cx + half)
        
        roi = depth_frame_np[r_y1:r_y2, r_x1:r_x2]
        valid_depths = roi[roi > 0]
        
        if len(valid_depths) == 0:
            logger.error(f"坐标 ({cx}, {cy}) 处 ROI 深度全部失效 (遇到黑洞)！")
            return 0.0
            
        if len(valid_depths) >= 5:
            # 采用 RealMan verticalGrab 规范: 取前 20% 最近深度平均值
            sorted_values = np.sort(valid_depths)
            top_k = max(1, int(top_k_ratio * len(sorted_values)))
            return float(np.mean(sorted_values[:top_k]))
        return float(np.median(valid_depths))

    def pixel_to_3d(self, pixel_point: list, depth: float, intrinsics) -> np.ndarray:
        """
        Step 4: 利用相机内参将 2D 像素坐标重投影为 3D 相机坐标系下的物理坐标。
        """
        if intrinsics is None or rs is None:
            return np.array([0.0, 0.0, 0.0])
        point_3d = rs.rs2_deproject_pixel_to_point(intrinsics, pixel_point, depth)
        return np.array(point_3d)

    def process_detections(self, detected_bboxes: list, depth_img: np.ndarray = None, intrinsics = None, allow_partial: bool = False) -> dict:
        """
        核心后处理流水线：
        1. Y 轴动态聚类合并同层碎片
        2. 判断视野完整性 (是否完整捕获 4 层，或在逼近特写阶段允许局部提取)
        3. 选出每层面积最大的主体段进行 ROI 抗黑洞采样与 3D 重投影
        4. 完整视野下排除最高一层（备用电缆），输出上/中/下 3 根工作电缆 3D 向量；
           局部逼近模式下输出当前检测到的各层候选电缆 3D 向量。

        返回字典结构：
        {
            "status": "COMPLETE" | "PARTIAL" | "INCOMPLETE" | "EMPTY",
            "detected_rows": int,
            "cables": list
        }
        """
        if not detected_bboxes:
            return {"status": "EMPTY", "detected_rows": 0, "cables": []}

        # 1. 动态按行聚类
        rows = self.group_bboxes_into_rows(detected_bboxes)

        # 2. 视野完整性校验：若不足 4 层且未开启局部特写逼近模式，判定为 INCOMPLETE (触发 Active Scanning)
        if len(rows) < 4 and not allow_partial:
            logger.debug(f"当前视野检测到 {len(rows)} 层线缆，未达 4 层完整标准 (触发 Active Scanning)。")
            return {
                "status": "INCOMPLETE",
                "detected_rows": len(rows),
                "cables": []
            }

        cables = []
        for row in rows:
            # 选出该层面积最大的主体段
            main_box = self.select_main_segment(row)
            
            cx = (main_box[0] + main_box[2]) / 2.0
            cy = (main_box[1] + main_box[3]) / 2.0
            
            depth = 0.0
            pos_3d = np.array([0.0, 0.0, 0.0])
            
            if depth_img is not None:
                depth = self.get_robust_depth(depth_img, main_box, top_k_ratio=self.depth_top_ratio)
                pos_3d = self.pixel_to_3d([cx, cy], depth, intrinsics)
                
            cables.append({
                "bbox": main_box,
                "segments_count": len(row),
                "depth": depth,
                "pos_camera": pos_3d
            })

        # 按 Y 轴升序排列 (图像坐标系下最上面的在 index 0)
        cables.sort(key=lambda x: (x["bbox"][1] + x["bbox"][3]) / 2.0)

        # 3. 完整视野与局部追踪处理
        if not allow_partial and len(rows) >= 4:
            if self.exclude_spare_cable:
                # 仅在明确开启 exclude_spare_cable 时，剔除最上方备用电缆
                spare_cable = cables.pop(0)
                spare_cy = (spare_cable['bbox'][1] + spare_cable['bbox'][3]) / 2.0
                logger.info(f"已按配置剔除最上方备用电缆 (Bbox Y1: {spare_cable['bbox'][1]:.1f}, 中心 Cy: {spare_cy:.1f})")
            else:
                logger.info(f"全局初始扫描完成，保留全部 {len(cables)} 根电缆 (从上至下点位: 1~{len(cables)})")

            return {
                "status": "COMPLETE",
                "detected_rows": len(rows),
                "cables": cables
            }
        else:
            # 逼近过程中（allow_partial=True）为局部追踪模式：严禁剔除顶层线缆，提供当前视野所有候选线缆供基坐标系空间最近邻匹配
            logger.debug(f"当前视野检测到 {len(rows)} 层线缆 (局部追踪模式，保留全部候选供空间匹配)。")
            return {
                "status": "PARTIAL",
                "detected_rows": len(rows),
                "cables": cables
            }

    def process_frame(self, color_img: np.ndarray, depth_img: np.ndarray, intrinsics, allow_partial: bool = False):
        """
        主入口：输入对齐后的彩色图、深度图和内参，输出工作电缆的三维信息。
        :param allow_partial: 是否允许近景局部模式 (如目标锁定后靠近时视野不足 4 层仍提取线缆)
        """
        if self.model is not None and color_img is not None:
            results = self.model(color_img, verbose=False)
            bboxes = []
            for result in results:
                if hasattr(result, 'boxes') and result.boxes is not None:
                    for box in result.boxes:
                        bboxes.append(box.xyxy[0].cpu().numpy().tolist())
            return self.process_detections(bboxes, depth_img, intrinsics, allow_partial=allow_partial)

        # 降级/Mock 模拟数据 (用于硬件未连接时的单元测试与语法验证)
        mock_bboxes = [
            [100, 100, 400, 150], [600, 105, 900, 155], # 第1层 (备用电缆，左右两段)
            [105, 200, 410, 250], [605, 202, 905, 252], # 第2层 (上工作电缆)
            [95,  300, 395, 350], [595, 305, 895, 355], # 第3层 (中工作电缆)
            [110, 400, 410, 450], [610, 405, 910, 455]  # 第4层 (下工作电缆)
        ]
        return self.process_detections(mock_bboxes, depth_img, intrinsics, allow_partial=allow_partial)
