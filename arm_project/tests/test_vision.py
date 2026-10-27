import pytest
import numpy as np
from src.vision.detector import CableDetector

def test_cable_detector_grouping():
    detector = CableDetector()

    # 模拟图1/图2的碎片情况：4 层线缆，每层包含 2 个 Bbox (共 8 个框)
    mock_bboxes = [
        [100, 100, 400, 150], [600, 105, 900, 155],  # 第 1 层
        [105, 200, 410, 250], [605, 202, 905, 252],  # 第 2 层
        [95,  300, 395, 350], [595, 305, 895, 355],  # 第 3 层
        [110, 400, 410, 450], [610, 405, 910, 455]   # 第 4 层
    ]

    # 验证聚类
    rows = detector.group_bboxes_into_rows(mock_bboxes, y_threshold=40)
    assert len(rows) == 4, f"期望聚类出 4 层线缆，实际得到 {len(rows)} 层"

    # 验证完整视图后处理 (默认 exclude_spare_cable=False，保留全部 4 根电缆)
    res = detector.process_detections(mock_bboxes)
    assert res["status"] == "COMPLETE"
    assert res["detected_rows"] == 4
    cables = res["cables"]
    assert len(cables) == 4, f"期望返回全部 4 根电缆，实际返回 {len(cables)} 根"
    
    # 确认顺序从上到下：电缆 1, 2, 3, 4
    assert cables[0]['bbox'][1] < cables[1]['bbox'][1] < cables[2]['bbox'][1] < cables[3]['bbox'][1]


def test_cable_detector_exclude_spare_cable():
    """测试当明确开启 exclude_spare_cable=True 时，剔除最上方备用电缆返回 3 根工作电缆"""
    detector = CableDetector(exclude_spare_cable=True)
    mock_bboxes = [
        [100, 100, 400, 150], [600, 105, 900, 155],  # 第 1 层
        [105, 200, 410, 250], [605, 202, 905, 252],  # 第 2 层
        [95,  300, 395, 350], [595, 305, 895, 355],  # 第 3 层
        [110, 400, 410, 450], [610, 405, 910, 455]   # 第 4 层
    ]
    res = detector.process_detections(mock_bboxes)
    assert res["status"] == "COMPLETE"
    assert res["detected_rows"] == 4
    cables = res["cables"]
    assert len(cables) == 3, f"开启剔除备用电缆后应返回 3 根工作电缆，实际返回 {len(cables)} 根"
    assert cables[0]['bbox'][1] < cables[1]['bbox'][1] < cables[2]['bbox'][1]


def test_cable_detector_incomplete_view():
    detector = CableDetector()

    # 模拟图3近景局部情况：仅有 2 层线缆 (共 4 个碎片框)
    mock_bboxes_partial = [
        [100, 100, 400, 150], [600, 105, 900, 155],  # 第 1 层
        [105, 200, 410, 250], [605, 202, 905, 252]   # 第 2 层
    ]

    res = detector.process_detections(mock_bboxes_partial)
    assert res["status"] == "INCOMPLETE"
    assert res["detected_rows"] == 2
    assert len(res["cables"]) == 0


def test_cable_detector_allow_partial_preserves_all_cables():
    """测试逼近过程中开启 allow_partial=True 时，不剔除顶层线缆，完整保留所有候选供空间最近邻匹配"""
    detector = CableDetector()
    mock_bboxes = [
        [100, 100, 400, 150], [600, 105, 900, 155],  # 第 1 层
        [105, 200, 410, 250], [605, 202, 905, 252],  # 第 2 层
        [95,  300, 395, 350], [595, 305, 895, 355],  # 第 3 层
        [110, 400, 410, 450], [610, 405, 910, 455]   # 第 4 层
    ]
    res = detector.process_detections(mock_bboxes, allow_partial=True)
    assert res["status"] == "PARTIAL"
    assert res["detected_rows"] == 4
    # 局部追踪模式下绝不 pop(0)，保留所有 4 层
    assert len(res["cables"]) == 4


def test_get_robust_depth_top_20_percent():
    """测试 RealMan verticalGrab 规范: 取最近前 20% 有效深度平均值过滤背景穿透与飞点"""
    detector = CableDetector()

    # 构造深度图 (100x100)
    # ROI (bbox 中心) 包含:
    # 20 个目标电缆表面点 (395~405 mm)
    # 80 个背景板穿透点 (800~1000 mm)
    depth_map = np.zeros((100, 100), dtype=np.uint16)
    
    # 目标 bbox 区域在 [40, 40, 60, 60]，中心为 (50, 50)
    # roi_size=10, 对应 y: 45~55, x: 45~55 (共 10x10=100 个像素)
    for y in range(45, 55):
        for x in range(45, 55):
            depth_map[y, x] = 900  # 默认背景 900mm
    
    # 将其中 20 个像素设置为电缆真实表面 400mm
    cable_coords = [(45 + i, 45 + j) for i in range(4) for j in range(5)]
    for y, x in cable_coords:
        depth_map[y, x] = 400

    bbox = [40, 40, 60, 60]
    depth = detector.get_robust_depth(depth_map, bbox, roi_size=10, top_k_ratio=0.20)

    # 验证: 100 个点中最近的 20% 均为 400mm，均值应为 400.0，而非中位数或全局均值 800+mm
    assert abs(depth - 400.0) < 1.0


def test_get_robust_depth_handles_black_hole_zeros():
    """测试深度图中存在零值黑洞时，有效过滤 0 并计算真实有效深度"""
    detector = CableDetector()
    depth_map = np.zeros((100, 100), dtype=np.uint16)
    
    # 在 10x10 ROI 区域中，有 50 个 0 值黑洞，50 个 500mm 有效值
    for y in range(45, 55):
        for x in range(45, 50):
            depth_map[y, x] = 500

    bbox = [40, 40, 60, 60]
    depth = detector.get_robust_depth(depth_map, bbox, roi_size=10, top_k_ratio=0.20)
    assert abs(depth - 500.0) < 1.0

    # 全 0 黑洞情况下返回 0.0
    zero_map = np.zeros((100, 100), dtype=np.uint16)
    zero_depth = detector.get_robust_depth(zero_map, bbox, roi_size=10)
    assert zero_depth == 0.0

