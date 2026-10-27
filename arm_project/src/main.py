import sys
import signal
import atexit
from pathlib import Path

# 确保项目根目录加入 sys.path，支持在任意目录下直接执行 python src/main.py
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.core.system_engine import SystemEngine
from src.core.logger import logger

def main():
    """
    系统主入口：创建并运行业务引擎 SystemEngine
    包含完整信号捕获与 atexit 回调，确保无论通过 Ctrl+C 还是异常终止都能安全停止相机与机械臂
    """
    engine = SystemEngine()

    def handle_signal(signum, frame):
        logger.warning(f"接收到系统退出信号 ({signum})，正在安全停止系统...")
        engine.stop()
        sys.exit(0)

    # 捕获 Ctrl+C (SIGINT) 和 kill (SIGTERM)
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    atexit.register(engine.stop)

    try:
        if engine.start():
            engine.run()
    except KeyboardInterrupt:
        logger.warning("接收到中断信号，引擎退出中...")
    except Exception as e:
        logger.critical(f"主程序异常终止: {e}")
    finally:
        engine.stop()

if __name__ == "__main__":
    main()
