import pytest
from plugins.gas.gas_plugin import GasPlugin
from core.event_manager import TaskEvent

@pytest.fixture
def mock_gas_driver(mocker):
    """Mock 底层硬件驱动，隔离串口通信"""
    mock_driver_class = mocker.patch("plugins.gas.gas_plugin.GasDriver")
    return mock_driver_class

@pytest.fixture
def gas_plugin(mock_gas_driver):
    """初始化气体插件"""
    config = {
        "sensors": [
            {
                "sensor_id": 1,
                "name": "6合一气体检测模组",
                "port": "/dev/ttyUSB0",
                "baudrate": 9600
            }
        ]
    }
    return GasPlugin(config)


class TestGasPlugin:
    """测试气体传感器核心插件业务与状态机"""

    def test_get_capabilities(self, gas_plugin):
        """正常流程：验证物模型元数据声明结构"""
        caps = gas_plugin.get_capabilities()
        assert caps["plugin_type"] == "GasPlugin"
        assert "supported_actions" in caps

    def test_start_stop_pump_actions(self, gas_plugin, mock_gas_driver):
        """正常流程：测试单个气泵开关的动作下发"""
        driver_instance = gas_plugin.drivers[1]
        driver_instance.control_pump.return_value = True
        
        res_start = gas_plugin.execute("start", {"sensor_id": 1})
        assert res_start["status"] == "success"
        
        res_stop = gas_plugin.execute("stop", {"sensor_id": 1})
        assert res_stop["status"] == "success"

    def test_cycle_start_stop_action(self, gas_plugin, mock_gas_driver):
        """正常流程：测试 cycle 命令对循环线程的开启和关闭"""
        driver_instance = gas_plugin.drivers[1]
        driver_instance.control_pump.return_value = True
        driver_instance.read_concentration.return_value = {
            "status": "success",
            "channels": [
                {"channel_code": 1, "name": "CO", "value": 10.0, "unit": "PPM", "status": "NORMAL"}
            ]
        }
        
        res_start = gas_plugin.execute("cycle", {"action": "start", "interval": 1})
        assert res_start["status"] == "success"
        assert "已开启气泵并启动气体循环采集" in res_start["message"]
        assert gas_plugin._cycle_thread is not None

        res_stop = gas_plugin.execute("cycle", {"action": "stop"})
        assert res_stop["status"] == "success"
        assert "已停止气体循环采集并关停采样气泵" in res_stop["message"]

    def test_init_shutdown_pumps(self, gas_plugin, mock_gas_driver):
        """边界约束：插件初始化时必须主动下发一次复位关泵指令"""
        driver_instance = gas_plugin.drivers[1]
        # 第一次是被 _init_shutdown_pumps 调用的
        driver_instance.control_pump.assert_called_with(on_off=0x00, flow_level=0)

    @pytest.mark.parametrize("state_str, expected_polling", [
        ("RUNNING", True),
        ("ABORTED", False),
        ("FAILED", False),
        ("PAUSED", False),
        ("FINISHED", False)
    ])
    def test_global_state_changed_event(self, gas_plugin, state_str, expected_polling):
        """事件隔离验证：当任务大盘状态变迁时，事件总线回调能否正确修改拉取软锁"""
        event = TaskEvent(
            event_type="global_state_changed",
            task_id="system",
            extra_data={"state": state_str}
        )
        
        # 模拟事件总线广播到达
        gas_plugin._on_state_changed(event)
        
        assert gas_plugin._is_polling_allowed is expected_polling

    def test_cycle_loop_yields_when_locked(self, gas_plugin, mocker):
        """异常/边界防呆：验证当大盘停机(软锁闭合)时，循环线程必须休眠让出CPU且绝不调用驱动层"""
        gas_plugin._is_polling_allowed = False
        gas_plugin._cycle_stop_event.clear()
        
        # Patch sleep 防止进入真实无限死循环，并让它抛出异常主动退出 while
        mocker.patch("plugins.gas.gas_plugin.time.sleep", side_effect=InterruptedError("Break Loop"))
        
        try:
            gas_plugin._cycle_loop(interval=1.0)
        except InterruptedError:
            pass
            
        driver_instance = gas_plugin.drivers[1]
        # read_concentration 绝对不能被调用
        driver_instance.read_concentration.assert_not_called()

    def test_execute_invalid_action(self, gas_plugin):
        """异常抛出：执行非法的物模型动作应被拦截"""
        res = gas_plugin.execute("unknown_action", {})
        assert res["status"] == "error"
        assert "不支持" in res["message"]
