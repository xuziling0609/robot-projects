import time
import sys
import signal
from core import ConfigManager, PluginManager, MQTTManager, TaskManager, TelemetryManager, AlarmManager, EventManager, get_logger

logger = get_logger("MainEntry")

def main():
    logger.info("=" * 60)
    logger.info("🚀 工业边缘智能网关启动中...")
    logger.info("=" * 60)

    # 0. 启动解耦事件管理器与告警管理器
    event_manager = EventManager()
    event_manager.start()
    alarm_manager = AlarmManager()

    # 1. 载入全局配置
    config = ConfigManager()
    config.load_main("configs/config.yaml")

    # 2. 插件管理器与任务引擎初始化
    pm = PluginManager()
    task_engine = TaskManager(plugin_manager=pm, config_loader=config)
    
    pm.discover_plugins("plugins")

    # 3. 启动 MQTT 客户端，接管云端通信
    mqtt_robot_id = config.get("mqtt.robot_id", config.get("mqtt.client_id", "DEFAULT_EDGE_GW"))
    mqtt_broker = config.get("mqtt.broker_ip", "127.0.0.1")
    mqtt_port = config.get("mqtt.port", 1883)

    mqtt_cli = MQTTManager(
        robot_id=mqtt_robot_id, 
        broker_ip=mqtt_broker, 
        port=mqtt_port,
        username=config.get("mqtt.username"),
        password=config.get("mqtt.password")
    )

    # 绑定统一 ACK 回复回调与任务接收回调
    task_engine.response_callback = mqtt_cli.publish_response
    mqtt_cli.register_task_callback(task_engine.handle_task)
    def get_unified_capabilities():
        return {
            "plugins": pm.get_all_capabilities(),
            "components": task_engine.component_manager.get_all_capabilities()
        }
    mqtt_cli.register_capability_provider(get_unified_capabilities)    
    # 4. 初始化状态与遥测管理器 (TelemetryManager)
    heartbeat_interval = float(config.get("mqtt.heartbeat_interval", 5.0))
    telemetry_manager = TelemetryManager(
        plugin_manager=pm,
        mqtt_manager=mqtt_cli,
        task_manager=task_engine,
        interval=heartbeat_interval
    )

    # 启动后台守护线程，连接 Broker 与开启 TelemetryManager 心跳管理
    mqtt_cli.start()
    telemetry_manager.start()
    
    logger.info("✅ 边缘网关初始化完毕，主程序进入守护状态。")
    logger.info("=" * 60)

    # 4. 主线程守护与优雅退出机制 (Graceful Shutdown)
    def sigterm_handler(signum, frame):
        logger.warning("⚡ 接收到系统终止信号 (SIGTERM)！正在执行平滑关机...")
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, sigterm_handler)

    try:
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.warning("⚡ 接收到强行终止信号 (KeyboardInterrupt)！")
    except Exception as e:
        logger.critical(f"⚡ 发生不可恢复的致命异常: {e}")
    finally:
        logger.info("=" * 60)
        logger.info("🛑 边缘网关程序开始安全退出...")
        if hasattr(pm, "trigger_global_abort"):
            pm.trigger_global_abort()
            
        task_engine.stop()
        telemetry_manager.stop()
        event_manager.stop()
        mqtt_cli.stop()
        
        logger.info("=" * 60)
        logger.info("✅ 边缘网关程序已安全退出。")
        logger.info("=" * 60)
        sys.exit(0)

if __name__ == "__main__":
    main()