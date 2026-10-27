#!/usr/bin/env python3
"""
TensorRT 引擎导出与修复工具 (Jetson Orin 专用)

本工具解决以下核心痛点：
1. 直接使用 /usr/src/tensorrt/bin/trtexec 编译生成的 .engine 属于裸引擎 (Raw Engine)，
   缺乏 Ultralytics 专用元数据头部 (前 4 字节小端长度 + JSON 元数据)，导致 YOLO() 加载时丢失 task('segment')、names 等属性。
2. 传统 Ultralytics Python API (onnx2engine) 在 Jetson 上容易阻塞、显存占用高，且 PyTorch 1.12 GPU JIT 导出 ONNX 存在设备不匹配 Bug。

功能特性：
- 支持命令行原生参数：兼容 trtexec 参数风格 (--onnx, --saveEngine, --fp16)；
- 裸引擎即时修复 (--fix-only / 自动检测)：无需重新耗时编译，毫秒级注入元数据头；
- 原生 trtexec 极速编译：自动调用底层硬件优化编译器，编译完成后自动注入元数据封装；
- 支持 .pt 与 .onnx 输入：若输入为 .pt，自动在 CPU 安全导出 ONNX；若输入为 .onnx，自动提取原模型元数据；
- 导出后自动使用 YOLO 进行前向推理闭环验证与延迟评测。
"""

import os
import sys
import argparse
import ast
import json
import shutil
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("export_engine")

DEFAULT_TRTEXEC_PATHS = [
    "/usr/src/tensorrt/bin/trtexec",
    "/usr/local/bin/trtexec",
]


def find_trtexec(custom_path: Optional[str] = None) -> Path:
    """查找系统中可用的 trtexec 二进制程序"""
    if custom_path:
        p = Path(custom_path)
        if p.exists() and os.access(p, os.X_OK):
            return p
        raise FileNotFoundError(f"未找到指定的 trtexec 程序: {custom_path}")

    which_path = shutil.which("trtexec")
    if which_path:
        return Path(which_path)

    for p_str in DEFAULT_TRTEXEC_PATHS:
        p = Path(p_str)
        if p.exists() and os.access(p, os.X_OK):
            return p

    raise FileNotFoundError(
        "未在系统标准路径中找到 trtexec (/usr/src/tensorrt/bin/trtexec)！请确认 TensorRT 已正确安装或通过 --trtexec 指定路径。"
    )


def inspect_engine(engine_path: Path) -> Tuple[bool, int, Dict[str, Any]]:
    """
    检查 .engine 文件是否包含 Ultralytics 元数据头。
    返回: (has_header, offset, metadata)
    """
    if not engine_path.exists():
        return False, 0, {}

    total_size = engine_path.stat().st_size
    if total_size < 4:
        return False, 0, {}

    with open(engine_path, "rb") as f:
        data = f.read(4)
        if len(data) < 4:
            return False, 0, {}
        n = int.from_bytes(data, byteorder="little")
        if 0 < n <= total_size - 4:
            f.seek(4)
            try:
                meta = json.loads(f.read(n).decode("utf-8"))
                return True, 4 + n, meta
            except Exception:
                pass
    return False, 0, {}


def extract_metadata_from_onnx(onnx_path: Path) -> Dict[str, Any]:
    """从 ONNX 模型的 metadata_props 中提取模型元数据"""
    try:
        import onnx
        model = onnx.load(str(onnx_path))
        meta = {}
        for p in model.metadata_props:
            try:
                val = ast.literal_eval(p.value)
            except Exception:
                val = p.value
            meta[p.key] = val
        if meta:
            logger.info(f"成功从 ONNX 文件 [{onnx_path.name}] 提取元数据 (task={meta.get('task')}, names={meta.get('names')})")
            return meta
    except Exception as e:
        logger.warning(f"无法直接从 ONNX 文件提取元数据: {e}")
    return {}


def extract_metadata_from_pt(pt_path: Path, imgsz: int = 640, half: bool = True, workspace: int = 4) -> Dict[str, Any]:
    """从 PyTorch .pt 权重文件中提取模型元数据"""
    try:
        from ultralytics import YOLO, __version__
        model = YOLO(str(pt_path))
        stride = int(max(model.model.stride)) if hasattr(model.model, "stride") else 32
        head = type(model.model.model[-1]).__name__ if hasattr(model.model, "model") else "Segment"
        return {
            "description": "Ultralytics YOLO model exported for Jetson TensorRT",
            "author": "Ultralytics",
            "date": datetime.now().astimezone().isoformat(),
            "version": __version__,
            "license": "AGPL-3.0 License (https://ultralytics.com/license)",
            "docs": "https://docs.ultralytics.com",
            "stride": stride,
            "task": model.task or "segment",
            "head": head,
            "batch": 1,
            "imgsz": [imgsz, imgsz],
            "names": model.names,
            "args": {"batch": 1, "half": half, "workspace": workspace, "format": "engine"},
            "channels": 3,
            "end2end": False,
        }
    except Exception as e:
        logger.warning(f"从 .pt 提取元数据失败: {e}")
    return {}


def build_default_metadata(
    task: str = "segment",
    names: Optional[Dict[int, str]] = None,
    imgsz: int = 640,
    half: bool = True,
    workspace: int = 4,
) -> Dict[str, Any]:
    """构造默认的 Ultralytics 元数据字典 (适配 cable 导线检测)"""
    names = names or {0: "cable"}
    return {
        "description": "Ultralytics YOLO model exported for Jetson TensorRT",
        "author": "Ultralytics",
        "date": datetime.now().astimezone().isoformat(),
        "version": "8.4.174",
        "stride": 32,
        "task": task,
        "head": "Segment" if task == "segment" else "Detect",
        "batch": 1,
        "imgsz": [imgsz, imgsz],
        "names": names,
        "args": {"batch": 1, "half": half, "workspace": workspace, "format": "engine"},
        "channels": 3,
        "end2end": False,
    }


def attach_metadata_header(raw_engine_bytes: bytes, metadata: Dict[str, Any]) -> bytes:
    """为裸引擎数据添加 Ultralytics 专用元数据头部 (4字节长度 + JSON)"""
    meta_json = json.dumps(metadata).encode("utf-8")
    meta_len = len(meta_json)
    return meta_len.to_bytes(4, byteorder="little") + meta_json + raw_engine_bytes


def fix_raw_engine(
    engine_path: Path,
    metadata: Dict[str, Any],
    output_path: Optional[Path] = None,
) -> bool:
    """
    检查并修复未封装元数据的裸 .engine 文件 (如 trtexec 直接保存的文件)
    """
    has_header, offset, existing_meta = inspect_engine(engine_path)
    if has_header and existing_meta.get("task") and existing_meta.get("names"):
        logger.info(
            f"✓ 引擎文件 [{engine_path}] 已包含完整的 Ultralytics 元数据: "
            f"task='{existing_meta.get('task')}', names={existing_meta.get('names')}"
        )
        return True

    with open(engine_path, "rb") as f:
        raw_bytes = f.read()

    # 如果有旧的不完整头，跳过旧头
    if has_header and offset > 0:
        raw_bytes = raw_bytes[offset:]

    if not raw_bytes.startswith(b"ptrt"):
        logger.warning(f"⚠️ 文件 [{engine_path}] 不以 'ptrt' 开头，请确认是否为有效的 TensorRT 序列化引擎！")

    wrapped_bytes = attach_metadata_header(raw_bytes, metadata)
    target_path = output_path or engine_path
    with open(target_path, "wb") as f:
        f.write(wrapped_bytes)

    logger.info(
        f"✓ 成功将元数据头 (长度: {len(json.dumps(metadata))} 字节, task='{metadata.get('task')}') "
        f"写入 [{target_path}]！"
    )
    return True


def verify_engine(engine_path: Path, imgsz: int = 640) -> bool:
    """使用 Ultralytics YOLO 载入引擎并执行推理验证"""
    try:
        from ultralytics import YOLO
        import numpy as np

        logger.info(f"正在通过 Ultralytics YOLO 验证导出的引擎 [{engine_path}]...")
        model = YOLO(str(engine_path))
        dummy = np.zeros((imgsz, imgsz, 3), dtype=np.uint8)
        results = model(dummy, verbose=False)
        speed = results[0].speed
        logger.info(
            f"✓ 引擎验证成功！Task: {model.task}, Classes: {model.names}, "
            f"推理延迟: {speed.get('inference', 0):.2f} ms (~{1000.0 / max(speed.get('inference', 1e-3), 1e-3):.1f} FPS)"
        )
        return True
    except Exception as e:
        logger.error(f"❌ 引擎验证失败: {e}", exc_info=True)
        return False


def export_or_fix_engine(
    onnx_path: Optional[str] = None,
    model_path: Optional[str] = None,
    output_engine_path: Optional[str] = None,
    half: bool = True,
    workspace_mb: int = 4096,
    imgsz: int = 640,
    trtexec_bin: Optional[str] = None,
    fix_only: bool = False,
    force: bool = False,
) -> str:
    """
    核心导出与修复流程：
    1. 确定输入模型与目标引擎路径；
    2. 获取或提取 Ultralytics 元数据；
    3. 若输出引擎已存在且为裸引擎 (或处于 fix_only 模式)，直接修复；
    4. 否则调用 trtexec 编译生成裸引擎，随后追加元数据头完成封装；
    5. 验证推理可用性。
    """
    # 路径解析与自动推断
    input_onnx = Path(onnx_path) if onnx_path else None
    input_model = Path(model_path) if model_path else None

    # 如果只传了 model_path，根据后缀分类
    if input_model and not input_onnx:
        if input_model.suffix.lower() == ".onnx":
            input_onnx = input_model
            input_model = None

    # 确定默认 ONNX 路径
    if not input_onnx:
        if input_model and input_model.exists():
            input_onnx = input_model.with_suffix(".onnx")
        else:
            default_candidate = PROJECT_ROOT / "models" / "cable.onnx"
            if default_candidate.exists():
                input_onnx = default_candidate
            else:
                input_onnx = PROJECT_ROOT / "models" / "cable.onnx"

    # 确定目标 engine 路径
    if output_engine_path:
        target_engine = Path(output_engine_path)
    elif input_onnx:
        target_engine = input_onnx.with_suffix(".engine")
    elif input_model:
        target_engine = input_model.with_suffix(".engine")
    else:
        target_engine = PROJECT_ROOT / "models" / "cable.engine"

    # 准备元数据
    metadata: Dict[str, Any] = {}
    if input_onnx and input_onnx.exists():
        metadata = extract_metadata_from_onnx(input_onnx)

    if not metadata and input_model and input_model.exists() and input_model.suffix == ".pt":
        metadata = extract_metadata_from_pt(input_model, imgsz=imgsz, half=half, workspace=int(workspace_mb / 1024))

    if not metadata:
        # 尝试查找同名 .pt 文件
        candidate_pt = (input_onnx.with_suffix(".pt") if input_onnx else None) or (PROJECT_ROOT / "models" / "cable.pt")
        if candidate_pt.exists():
            metadata = extract_metadata_from_pt(candidate_pt, imgsz=imgsz, half=half, workspace=int(workspace_mb / 1024))

    if not metadata:
        logger.info("未从文件中解析到元数据，使用默认电缆检测元数据 (task='segment', names={0: 'cable'})")
        metadata = build_default_metadata(task="segment", imgsz=imgsz, half=half, workspace=int(workspace_mb / 1024))

    # 更新元数据运行参数
    if "args" in metadata and isinstance(metadata["args"], dict):
        metadata["args"]["half"] = half
        metadata["args"]["workspace"] = int(workspace_mb / 1024)

    # 场景 A: 目标 engine 文件已存在
    if target_engine.exists():
        has_header, offset, existing_meta = inspect_engine(target_engine)
        if fix_only or (not force):
            if has_header and existing_meta.get("task"):
                logger.info(
                    f"目标引擎 [{target_engine}] 已经拥有完整元数据 (task='{existing_meta.get('task')}')."
                )
                verify_engine(target_engine, imgsz=imgsz)
                return str(target_engine)
            else:
                logger.info(f"检测到 [{target_engine}] 为裸 TensorRT 引擎，开始执行快速元数据封装注入...")
                fix_raw_engine(target_engine, metadata)
                verify_engine(target_engine, imgsz=imgsz)
                return str(target_engine)

    if fix_only:
        raise FileNotFoundError(f"指定的待修复引擎文件不存在: {target_engine}")

    # 场景 B: 需要通过 trtexec 编译生成
    trtexec = find_trtexec(trtexec_bin)
    logger.info(f"使用 TensorRT 编译工具链: {trtexec}")

    # 检查并确保 ONNX 文件存在
    if not input_onnx or not input_onnx.exists():
        if input_model and input_model.exists() and input_model.suffix == ".pt":
            logger.info(f"未找到 ONNX 文件，正在使用 CPU 安全导出 PyTorch 模型为 ONNX...")
            from ultralytics import YOLO
            pt_model = YOLO(str(input_model))
            # 避免 Jetson PyTorch 1.12 GPU JIT bug，强制在 CPU 导出
            pt_model.model.to("cpu")
            exported_onnx = pt_model.export(format="onnx", device="cpu", batch=1, imgsz=imgsz, simplify=False)
            input_onnx = Path(exported_onnx)
            logger.info(f"ONNX 文件已生成: {input_onnx}")
        else:
            raise FileNotFoundError(f"未找到用于编译的 ONNX 文件: {input_onnx}")

    temp_raw_engine = target_engine.with_name(f"{target_engine.stem}_temp_raw.engine")

    cmd = [
        str(trtexec),
        f"--onnx={input_onnx}",
        f"--saveEngine={temp_raw_engine}",
        f"--workspace={workspace_mb}",
    ]
    if half:
        cmd.append("--fp16")

    cmd_str = " \\\n  ".join(cmd)
    logger.info(f"开始执行 TensorRT 算子编译优化:\n{cmd_str}")

    try:
        proc = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        logger.info("✓ trtexec 硬件算子编译完成！")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ trtexec 编译失败 (exit {e.returncode}):\n{e.output}")
        if temp_raw_engine.exists():
            temp_raw_engine.unlink()
        raise RuntimeError(f"trtexec 执行失败: {e}")

    # 注入元数据封装
    try:
        with open(temp_raw_engine, "rb") as f:
            raw_bytes = f.read()

        wrapped_bytes = attach_metadata_header(raw_bytes, metadata)
        with open(target_engine, "wb") as f:
            f.write(wrapped_bytes)

        logger.info(f"✓ 成功注入 Ultralytics 元数据头并生成最终引擎: {target_engine}")
    finally:
        if temp_raw_engine.exists():
            temp_raw_engine.unlink()

    # 校验引擎推理能力
    verify_engine(target_engine, imgsz=imgsz)
    return str(target_engine)


def main():
    parser = argparse.ArgumentParser(
        description="TensorRT 引擎编译与元数据修复工具 (Jetson Orin 专用)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例用法:
  1. 直接修复 trtexec 生成的裸引擎 (毫秒级):
     python tools/export_engine.py --onnx=models/cable.onnx --saveEngine=models/cable.engine --fix-only

  2. 从 ONNX 重新编译并自动注入元数据:
     python tools/export_engine.py --onnx=models/cable.onnx --saveEngine=models/cable.engine --fp16

  3. 从 PyTorch 权重一键端到端导出:
     python tools/export_engine.py --model=models/cable.pt --output=models/cable.engine --fp16
""",
    )
    # trtexec 风格参数
    parser.add_argument("--onnx", type=str, default=None, help="输入 ONNX 模型路径 (例如 models/cable.onnx)")
    parser.add_argument(
        "--saveEngine",
        "--save-engine",
        "--output",
        "-o",
        dest="saveEngine",
        type=str,
        default=None,
        help="目标 .engine 输出路径 (例如 models/cable.engine)",
    )
    parser.add_argument(
        "--fp16",
        dest="fp16",
        action="store_true",
        default=True,
        help="启用 FP16 半精度加速 (默认启用)",
    )
    parser.add_argument(
        "--no-fp16",
        dest="fp16",
        action="store_false",
        help="关闭 FP16 半精度加速",
    )
    parser.add_argument(
        "--workspace",
        type=int,
        default=4096,
        help="TensorRT 工作空间内存限制 (单位 MB，若数值<=32 则自动按 GB 解析，默认: 4096)",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="输入图像分辨率尺寸 (默认: 640)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="输入模型权重路径 (支持 .pt 或 .onnx，兼容历史传参)",
    )
    parser.add_argument(
        "--trtexec",
        type=str,
        default=None,
        help="自定义 trtexec 可执行文件路径 (默认优先搜索 /usr/src/tensorrt/bin/trtexec)",
    )
    parser.add_argument(
        "--fix-only",
        action="store_true",
        help="仅执行元数据头快速修复/注入，不重新调用 trtexec 耗时编译",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新调用 trtexec 编译 (即使目标 engine 已存在)",
    )

    args = parser.parse_args()

    # 处理 workspace 单位转换 (用户若输入 4 则代表 4GB = 4096MB)
    workspace_mb = args.workspace
    if workspace_mb <= 32:
        workspace_mb = workspace_mb * 1024

    export_or_fix_engine(
        onnx_path=args.onnx,
        model_path=args.model,
        output_engine_path=args.saveEngine,
        half=args.fp16,
        workspace_mb=workspace_mb,
        imgsz=args.imgsz,
        trtexec_bin=args.trtexec,
        fix_only=args.fix_only,
        force=args.force,
    )


if __name__ == "__main__":
    main()
