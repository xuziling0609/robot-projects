#!/usr/bin/env python3
"""
🤖 工业机器人边缘网关 - 全量硬件模拟器一键启动入口 (All Simulators Manager)
一次性并行启动所有 10 大硬件模拟服务 (所有端口与串口路径统一由本脚本配置并下发):
1. 机械臂模拟器 (ArmSimulator): TCP 端口 10020
2. 开门机模拟器 (DoorSimulator): TCP 端口 10021
3. 气体检测模拟器 (GasSimulator): 双串口 /tmp/tty_gas_sim0 & /tmp/tty_gas_sim1
4. 充电站模拟器 (StationSimulator): TCP 端口 10022
5. 梯控模拟器 (ElevatorSimulator): TCP 端口 10023
6. LoRa 通讯模拟器 (LoraSimulator): TCP 端口 10024
7. 局放采集模拟器 (GdpdSimulator): 串口 /tmp/tty_gdpd_sim
8. 机器人激光导航模拟器 (NavSimulator): HTTP 端口 17808 (xRobotWebAPI)
9. 云台摄像头模拟器 (CameraSimulator): HTTP 端口 8080 (ISAPI Digest)
10. 声纹定位探头模拟器 (AcousticSimulator): HTTP 端口 8000, TCP 端口 13052
"""

import sys
import os
import time
import threading
import logging

# ==================== 日志配置 ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] [Sim-Manager] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("SimulatorsManager")

# 动态引入当前项目根目录
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from simulator.armSimulator import start_arm_simulator
from simulator.doorSimulator import start_door_simulator
from simulator.gasSimulator import start_gas_simulator
from simulator.stationSimulator import start_station_simulator
from simulator.elevatorSimulator import start_elevator_simulator
from simulator.loraSimulator import start_lora_simulator
from simulator.gdpdSimulator import start_gdpd_simulator
from simulator.navSimulator import start_nav_simulator
from simulator.cameraSimulator import start_camera_simulator
from simulator.acousticSimulator import start_acoustic_simulator

# 全局集中端口与路径定义
ARM_HOST, ARM_PORT = "0.0.0.0", 10020
DOOR_HOST, DOOR_PORT = "0.0.0.0", 10021
GAS_PORT0, GAS_PORT1 = "/tmp/tty_gas_sim0", "/tmp/tty_gas_sim1"
STATION_HOST, STATION_PORT = "0.0.0.0", 10022
ELEVATOR_HOST, ELEVATOR_PORT = "0.0.0.0", 10023
LORA_HOST, LORA_PORT = "0.0.0.0", 10024
GDPD_SERIAL_PATH = "/tmp/tty_gdpd_sim"
NAV_HOST, NAV_PORT = "0.0.0.0", 17808
CAMERA_HOST, CAMERA_PORT = "0.0.0.0", 8001
ACOUSTIC_HTTP_PORT, ACOUSTIC_TCP_PORT = 8000, 13052

def run_service(name, target_func, *args, **kwargs):
    try:
        target_func(*args, **kwargs)
    except Exception as e:
        logger.error(f"❌ [{name}] 模拟服务运行报错: {e}")

def main():
    logger.info("=" * 80)
    logger.info("🚀 工业边缘智能网关 - 全量硬件插件模拟器一键总控启动中...")
    logger.info("=" * 80)

    services = [
        ("🦾 机械臂模拟器 (ArmSimulator)", start_arm_simulator, (ARM_HOST, ARM_PORT)),
        ("🚪 开门机模拟器 (DoorSimulator)", start_door_simulator, (DOOR_HOST, DOOR_PORT)),
        ("🧪 气体检测模拟器 (GasSimulator)", start_gas_simulator, (GAS_PORT0, GAS_PORT1)),
        ("🔌 充电站继电器 (StationSimulator)", start_station_simulator, (STATION_HOST, STATION_PORT)),
        ("🛗 云迹梯控模拟器 (ElevatorSimulator)", start_elevator_simulator, (ELEVATOR_HOST, ELEVATOR_PORT)),
        ("📡 LoRa 通讯网关 (LoraSimulator)", start_lora_simulator, (LORA_HOST, LORA_PORT)),
        ("⚡ 局放采集模拟器 (GdpdSimulator)", start_gdpd_simulator, (GDPD_SERIAL_PATH,)),
        ("🤖 机器人激光导航模拟器 (NavSimulator)", start_nav_simulator, (NAV_HOST, NAV_PORT)),
        ("📷 云台摄像头模拟器 (CameraSimulator)", start_camera_simulator, (CAMERA_HOST, CAMERA_PORT)),
        ("🎤 声纹定位探头模拟器 (AcousticSimulator)", start_acoustic_simulator, ("0.0.0.0", ACOUSTIC_HTTP_PORT, ACOUSTIC_TCP_PORT))
    ]

    threads = []
    for name, func, args in services:
        t = threading.Thread(target=run_service, args=(name, func, *args), daemon=True, name=name)
        t.start()
        threads.append(t)
        time.sleep(0.1)

    logger.info("=" * 80)
    logger.info(f"✨ 所有 {len(services)} 个模拟服务已全量启动完成！监听端口/串口映射列表:")
    logger.info(f"  1. 🦾 机械臂:       TCP  {ARM_HOST}:{ARM_PORT}")
    logger.info(f"  2. 🚪 开门机:       TCP  {DOOR_HOST}:{DOOR_PORT}")
    logger.info(f"  3. 🧪 气体检测:     双串口 {GAS_PORT0} (6合一) & {GAS_PORT1} (1合一)")
    logger.info(f"  4. 🔌 充电站继电器: TCP  {STATION_HOST}:{STATION_PORT}")
    logger.info(f"  5. 🛗 梯控网关:     TCP  {ELEVATOR_HOST}:{ELEVATOR_PORT}")
    logger.info(f"  6. 📡 LoRa网关:     TCP  {LORA_HOST}:{LORA_PORT}")
    logger.info(f"  7. ⚡ 局放检测:     串口 {GDPD_SERIAL_PATH} (POSIX PTY)")
    logger.info(f"  8. 🤖 激光导航:     HTTP {NAV_HOST}:{NAV_PORT} (/kc/mrc/)")
    logger.info(f"  9. 📷 摄像头:       HTTP {CAMERA_HOST}:{CAMERA_PORT} (/ISAPI/)")
    logger.info(f" 10. 🎤 声纹定位:     HTTP 0.0.0.0:{ACOUSTIC_HTTP_PORT}, TCP 0.0.0.0:{ACOUSTIC_TCP_PORT}")
    logger.info("=" * 80)
    logger.info("按 Ctrl+C 可停止全量模拟服务。\n")

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        logger.info("🛑 接收到退出信号，正在关停所有模拟器线程...")
        sys.exit(0)

if __name__ == "__main__":
    main()
