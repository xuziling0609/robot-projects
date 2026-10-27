import sys
from pathlib import Path
from loguru import logger

def setup_logger():
    """
    配置全局日志系统，支持控制台输出与本地文件留存。
    """
    # 移除默认的 handler
    logger.remove()

    # 1. 控制台输出 (颜色高亮，方便调试)
    logger.add(
        sys.stdout, 
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )

    # 2. 文件输出 (按天轮转，保留 7 天，适合工业现场排查问题)
    # 获取根目录
    base_dir = Path(__file__).resolve().parent.parent.parent
    log_dir = base_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    
    logger.add(
        log_dir / "arm_sys_{time:YYYY-MM-DD}.log",
        rotation="00:00",      # 每天午夜轮转
        retention="7 days",    # 保留 7 天历史
        compression="zip",     # 压缩旧日志
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",         # 文件中记录更详尽的信息
        encoding="utf-8"
    )

# 初始化时即配置好
setup_logger()

# 导出 logger 供其他模块使用: from core.logger import logger
