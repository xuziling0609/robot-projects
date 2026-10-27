# 📡 插件物模型能力上报 (Capability Up) 协议规范

## 1. 协议元数据与概述

* **Topic Pattern**: `/edge/gateway/{robot_id}/capability/up`
* **方向**: 边缘网关 ➔ 云端平台 (QoS=1)
* **触发机制**: 网关启动连接 MQTT Broker 成功后自动上报全量已装载能力插件与宏组件拓扑。

```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800000000,
  "robot_id": "robot888",
  "capabilities": {
    "plugins": [
    {
      "plugin_type": "NavPlugin",
      "plugin_name": "导航插件",
      "description": "基于 xRobotWebAPI (HTTP 主动推送事件驱动) 提供点位导航、步态切换与动作控制能力",
      "version": "1.2.0",
      "supported_actions": [
        {
          "action": "start_nav",
          "action_name": "开始导航",
          "description": "控制机器人开启自主导航前往目标点位",
          "scopes": ["task"],
          "params": [
            { "name": "goal_point", "label": "目标点位ID", "type": "int", "required": true, "ui_component": "input_number" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "导航结果状态", "type": "string" },
              { "name": "message", "label": "状态说明描述", "type": "string" }
            ]
          }
        },
        {
          "action": "pause_nav",
          "action_name": "暂停导航",
          "description": "临时暂停当前进行中的点位导航流程",
          "scopes": ["task"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "resume_nav",
          "action_name": "恢复导航",
          "description": "恢复已暂停的导航任务继续前往目标点",
          "scopes": ["task"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "abort_nav",
          "action_name": "取消导航",
          "description": "强制中断并放弃当前导航任务",
          "scopes": ["task"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "set_mode",
          "action_name": "模式切换",
          "description": "切换机器人运行模式(如AUTO/MANU)",
          "scopes": ["task", "config"],
          "params": [
            { "name": "mode", "label": "模式", "type": "string", "default": "AUTO", "required": true, "ui_component": "select", "options": [{"name": "自动", "value": "AUTO"}, {"name": "手动", "value": "MANU"}] }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "set_gait",
          "action_name": "步态切换",
          "description": "配置足式机器人的行走步态",
          "scopes": ["task", "config"],
          "params": [
            { "name": "gait_index", "label": "步态索引", "type": "int", "required": true, "ui_component": "select", "options": [{"name": "灵动低速", "value": 1}, {"name": "灵动高速", "value": 2}, {"name": "经典低速", "value": 3}, {"name": "经典高速", "value": 4}, {"name": "视觉辅助", "value": 7}] }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "execute_motion",
          "action_name": "动作执行",
          "description": "触发机器人的特定组合动作（1:进入充电, 2:退出充电）",
          "scopes": ["task"],
          "params": [
            { "name": "motion_cmd", "label": "动作指令ID", "type": "int", "required": true, "ui_component": "select", "options": [{"name": "进入充电", "value": 1}, {"name": "退出充电", "value": 2}] }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "manual_control",
          "action_name": "摇杆遥控",
          "description": "下发三轴运动控制速度指令",
          "scopes": ["config"],
          "params": [
            { "name": "speed_x", "label": "X轴线速度(m/s)", "type": "float", "default": 0.0, "ui_component": "input_number" },
            { "name": "speed_y", "label": "Y轴线速度(m/s)", "type": "float", "default": 0.0, "ui_component": "input_number" },
            { "name": "speed_theta", "label": "角速度(rad/s)", "type": "float", "default": 0.0, "ui_component": "input_number" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "jerk_stop",
          "action_name": "急停阻尼",
          "description": "触发软急停并开启防倾倒阻尼防护",
          "scopes": ["config"],
          "params": [
            { "name": "jerk", "label": "开启阻尼标志", "type": "bool", "default": true, "required": true, "ui_component": "switch" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "status",
          "action_name": "状态查询",
          "description": "查询机器人导航及底盘状态",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "online", "label": "在线状态", "type": "bool" }
            ]
          }
        },
        {
          "action": "set_config",
          "action_name": "设置告警配置",
          "description": "配置底盘电池电量的告警阈值",
          "scopes": ["config"],
          "params": [
            { "name": "config", "label": "告警规则数组", "type": "array", "required": true, "ui_component": "json_editor" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "get_config",
          "action_name": "读取告警配置",
          "description": "读取当前底盘电池电量的告警规则",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "执行描述", "type": "string" },
              { "name": "data", "label": "配置数据", "type": "array" }
            ]
          }
        }
      ],
      "config_metrics": [
        { "metric_name": "BATTERY", "label": "底盘电量", "unit": "%", "type": "float", "alarm_type": ["info", "warning", "error", "fatal"], "operator": ["lt", "lte", "gt", "gte", "between", "eq"] },
        { "metric_name": "BLOCKED", "label": "底盘受阻", "unit": "bool", "type": "int", "alarm_type": ["warning", "error"], "operator": ["eq"] }
      ]
    },
    {
      "plugin_type": "DoorPlugin",
      "plugin_name": "开门机插件",
      "description": "提供电动推拉门控机的开门、关门与急停控制能力",
      "version": "1.2.0",
      "supported_actions": [
        {
          "action": "open",
          "action_name": "自动开门",
          "description": "控制开门机机构打开门体",
          "scopes": ["task"],
          "params": [
            { "name": "ips", "label": "门控机IP列表", "type": "array", "required": false, "ui_component": "input_text" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "close",
          "action_name": "自动关门",
          "description": "控制开门机机构关闭门体",
          "scopes": ["task"],
          "params": [
            { "name": "ips", "label": "门控机IP列表", "type": "array", "required": false, "ui_component": "input_text" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "pause",
          "action_name": "停止动作",
          "description": "控制门体运动立即停止",
          "scopes": ["task"],
          "params": [
            { "name": "ips", "label": "门控机IP列表", "type": "array", "required": false, "ui_component": "input_text" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "status",
          "action_name": "状态查询",
          "description": "查询开门机网络与联动状态",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "online", "label": "在线状态", "type": "bool" }
            ]
          }
        }
      ]
    },
    {
      "plugin_type": "ElevatorPlugin",
      "plugin_name": "电梯插件",
      "description": "基于云基双模电梯控制器的呼梯、乘梯及开关门联动控制能力",
      "version": "1.2.0",
      "supported_actions": [
        {
          "action": "goToFloor",
          "action_name": "电梯呼梯",
          "description": "呼叫电梯并乘梯前往指定目标楼层（同步阻塞至到位）",
          "scopes": ["task"],
          "params": [
            { "name": "addr", "label": "电梯编号", "type": "int", "default": 18191, "required": false, "ui_component": "input_number" },
            { "name": "floor", "label": "目标楼层", "type": "int", "required": true, "ui_component": "input_number" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "openDoor",
          "action_name": "电梯开门",
          "description": "开启电梯保持开门轮询模式（进出电梯保护）",
          "scopes": ["task"],
          "params": [
            { "name": "addr", "label": "电梯编号", "type": "int", "default": 18191, "required": false, "ui_component": "input_number" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "closeDoor",
          "action_name": "电梯关门",
          "description": "立即关闭电梯门并解除开门保持守护",
          "scopes": ["task"],
          "params": [
            { "name": "addr", "label": "电梯编号", "type": "int", "default": 18191, "required": false, "ui_component": "input_number" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "status",
          "action_name": "状态查询",
          "description": "查询电梯控制器网络连接状态",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "online", "label": "在线状态", "type": "bool" }
            ]
          }
        }
      ]
    },
    {
      "plugin_type": "StationPlugin",
      "plugin_name": "充电站插件",
      "description": "基于 Tasio211 多路继电器的狗窝充电基站舱门控制与状态管理",
      "version": "1.2.0",
      "supported_actions": [
        {
          "action": "open",
          "action_name": "基站开门",
          "description": "控制多路继电器开启充电站舱门",
          "scopes": ["task"],
          "params": [
            { "name": "ips", "label": "继电器控制器IP列表", "type": "array", "required": false, "ui_component": "input_text" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "close",
          "action_name": "基站关门",
          "description": "控制多路继电器关闭充电站舱门",
          "scopes": ["task"],
          "params": [
            { "name": "ips", "label": "继电器控制器IP列表", "type": "array", "required": false, "ui_component": "input_text" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "status",
          "action_name": "状态查询",
          "description": "查询充电基站继电器通讯与到位状态",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "online", "label": "在线状态", "type": "bool" }
            ]
          }
        }
      ]
    },
    {
      "plugin_type": "SystemPlugin",
      "plugin_name": "基础插件",
      "description": "提供网关本地系统级延时等待、服务重启与整机重启自愈控制能力",
      "version": "1.3.0",
      "supported_actions": [
        {
          "action": "delay",
          "action_name": "延时等待",
          "description": "阻塞式系统延时等待指定的秒数",
          "scopes": ["task"],
          "params": [
            { "name": "seconds", "label": "延时秒数(s)", "type": "float", "default": 1.0, "required": true, "ui_component": "input_number" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "status",
          "action_name": "状态查询",
          "description": "查询系统基本运行状态",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "online", "label": "在线状态", "type": "bool" }
            ]
          }
        },
        {
          "action": "restart_service",
          "action_name": "重启服务",
          "description": "安全重启边缘网关中间件服务进程 (带安全互锁与先ACK后重启保护)",
          "scopes": ["config"],
          "params": [
            { "name": "delay_s", "label": "延时触发秒数(s)", "type": "float", "default": 1.0, "required": false, "ui_component": "input_number" },
            { "name": "force", "label": "是否强制重启(忽略任务运行状态)", "type": "bool", "default": false, "required": false, "ui_component": "switch" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" },
              { "name": "data", "label": "数据", "type": "object" }
            ]
          }
        },
        {
          "action": "reboot_system",
          "action_name": "重启系统",
          "description": "安全重启边缘工控机操作系统 (带安全互锁与先ACK后重启保护)",
          "scopes": ["config"],
          "params": [
            { "name": "delay_s", "label": "延时触发秒数(s)", "type": "float", "default": 2.0, "required": false, "ui_component": "input_number" },
            { "name": "force", "label": "是否强制重启(忽略任务运行状态)", "type": "bool", "default": false, "required": false, "ui_component": "switch" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" },
              { "name": "data", "label": "数据", "type": "object" }
            ]
          }
        }
      ]
    },
    {
      "plugin_type": "CameraPlugin",
      "plugin_name": "摄像头插件",
      "description": "基于 ISAPI 规范的双光热成像云台相机图像抓拍、PTZ云台控制与工业测温能力",
      "version": "1.3.0",
      "supported_actions": [
        {
          "action": "cycle",
          "action_name": "循环测温",
          "description": "开启/停止双光热成像相机后台定时循环测温上报",
          "scopes": ["task"],
          "params": [
            { "name": "action", "label": "操作", "type": "string", "default": "start", "required": true, "ui_component": "select", "options": [{"name": "开启", "value": "start"}, {"name": "关闭", "value": "stop"}] },
            { "name": "interval", "label": "采样间隔(s)", "type": "float", "default": 5.0, "required": false, "ui_component": "input_number" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "capture",
          "action_name": "图像抓拍",
          "description": "抓取可见光或热成像高清画面图像",
          "scopes": ["task"],
          "params": [
            { "name": "channel", "label": "通道", "type": "int", "default": 1, "required": false, "ui_component": "select", "options": [{"name": "可见光", "value": 1}, {"name": "热成像", "value": 2}] }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "base64", "label": "图片Base64编码", "type": "string" },
              { "name": "channel", "label": "通道号", "type": "int" }
            ]
          }
        },
        {
          "action": "set_preset",
          "action_name": "云台旋转",
          "description": "调度云台精准转向指定预置位",
          "scopes": ["task"],
          "params": [
            { "name": "preset_id", "label": "预置位ID", "type": "int", "default": 1, "required": true, "ui_component": "input_number" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "ptz",
          "action_name": "云台控制",
          "description": "连续控制云台 Pan/Tilt/Zoom 旋转与缩放",
          "scopes": ["config"],
          "params": [
            { "name": "pan", "label": "水平速度", "type": "float", "default": 0.0, "ui_component": "input_number" },
            { "name": "tilt", "label": "垂直速度", "type": "float", "default": 0.0, "ui_component": "input_number" },
            { "name": "zoom", "label": "变焦速度", "type": "float", "default": 0.0, "ui_component": "input_number" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" }
            ]
          }
        },
        {
          "action": "thermometry",
          "action_name": "工业测温",
          "description": "实时读取热成像区域最高/最低/平均温度与告警状态",
          "scopes": ["task"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "max_temp", "label": "最高温度(℃)", "type": "float" },
              { "name": "min_temp", "label": "最低温度(℃)", "type": "float" },
              { "name": "avg_temp", "label": "平均温度(℃)", "type": "float" },
              { "name": "alarm_status", "label": "告警状态", "type": "string" }
            ]
          }
        },
        {
          "action": "status",
          "action_name": "状态查询",
          "description": "查询相机硬件与网络连接状态",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "online", "label": "在线状态", "type": "bool" }
            ]
          }
        },
        {
          "action": "set_config",
          "action_name": "下发配置",
          "description": "设置并持久化摄像头温度告警阈值与告警提示语",
          "scopes": ["config"],
          "params": [
            { "name": "config", "label": "告警配置规则列表", "type": "array", "required": true, "ui_component": "json_editor" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "get_config",
          "action_name": "查询配置",
          "description": "获取当前本地持久化保存的摄像头温度告警配置列表",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "执行描述", "type": "string" },
              { "name": "data", "label": "配置数据", "type": "array" }
            ]
          }
        }
      ],
      "config_metrics": [
        { "metric_name": "THERMAL", "label": "最高温度", "unit": "℃", "type": "float", "alarm_type": ["info", "warning", "error", "fatal"], "operator": ["lt", "lte", "gt", "gte", "between", "eq"] }
      ]
    },
    {
      "plugin_type": "GasPlugin",
      "plugin_name": "气体插件",
      "description": "基于 6合一(ID=1) 与 1合一(ID=2) 双模组的多通道气体浓度采集、气泵调速、传感器标定与诊断能力",
      "version": "1.2.0",
      "supported_actions": [
        {
          "action": "acquire",
          "action_name": "气体采集",
          "description": "标准巡检流程：开泵 -> 自动预热等待(默认30s) -> 读多通道浓度 -> 自动关泵",
          "scopes": ["task"],
          "params": [
            { "name": "wait_time", "label": "稳定等待时间(s)", "type": "float", "default": 30.0, "required": false, "ui_component": "input_number" },
            { "name": "flow_level", "label": "气泵流量等级(1-10级)", "type": "int", "default": 10, "min": 1, "max": 10, "step": 1, "required": false, "ui_component": "slider" }
          ],
          "returns": {
            "type": "array",
            "description": "拍平的气体通道实时浓度列表",
            "fields": [
              { "name": "sensor_id", "label": "传感器模组ID", "type": "int" },
              { "name": "channel_code", "label": "通道编号(1-6)", "type": "int" },
              { "name": "name", "label": "气体名称(CO/H2S/O2/EX/CO2/NOX/SF6)", "type": "string" },
              { "name": "value", "label": "气体浓度值", "type": "float" },
              { "name": "unit", "label": "浓度单位(PPM/%VOL/%LEL)", "type": "string" }
            ]
          }
        },
        {
          "action": "query",
          "action_name": "即时读取",
          "description": "不触发气泵预热与开关，直接即时读取当前气体传感器数据",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "array",
            "description": "拍平的气体通道实时浓度列表",
            "fields": [
              { "name": "sensor_id", "label": "传感器模组ID", "type": "int" },
              { "name": "channel_code", "label": "通道编号", "type": "int" },
              { "name": "name", "label": "气体名称", "type": "string" },
              { "name": "value", "label": "气体浓度值", "type": "float" },
              { "name": "unit", "label": "浓度单位", "type": "string" }
            ]
          }
        },
        {
          "action": "level",
          "action_name": "流量调节",
          "description": "动态调整气泵抽气流量档位",
          "scopes": ["config"],
          "params": [
            { "name": "flow_level", "label": "流量档位(1-10级)", "type": "int", "default": 10, "min": 1, "max": 10, "step": 1, "required": true, "ui_component": "slider" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态(success/error)", "type": "string" },
              { "name": "message", "label": "执行描述", "type": "string" }
            ]
          }
        },
        {
          "action": "start_nav",
          "action_name": "开启气泵",
          "description": "开启指定传感器的抽气气泵",
          "scopes": ["config"],
          "params": [
            { "name": "flow_level", "label": "启动流量档位(1-10级)", "type": "int", "default": 10, "min": 1, "max": 10, "ui_component": "slider" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" }
            ]
          }
        },
        {
          "action": "stop",
          "action_name": "关闭气泵",
          "description": "关闭指定传感器的抽气气泵",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" }
            ]
          }
        },
        {
          "action": "channel",
          "action_name": "通道查询",
          "description": "读取 80-byte 完整的通道配置参数（量程、放大倍数、报警点等）",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "array",
            "fields": [
              { "name": "sensor_id", "label": "模组ID", "type": "int" },
              { "name": "channel_code", "label": "通道编号", "type": "int" },
              { "name": "gas_name", "label": "气体名称", "type": "string" },
              { "name": "range_max", "label": "满量程上限", "type": "float" },
              { "name": "unit", "label": "单位", "type": "string" },
              { "name": "alarm_low", "label": "低报数值", "type": "float" },
              { "name": "alarm_high", "label": "高报数值", "type": "float" }
            ]
          }
        },
        {
          "action": "base",
          "action_name": "信息查询",
          "description": "读取设备的 UID 硬件唯一识别码、软硬件版本号与厂商信息",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "array",
            "fields": [
              { "name": "channel_count", "label": "通道数量", "type": "int" },
              { "name": "device_uid", "label": "设备UID", "type": "string" },
              { "name": "manufacturer", "label": "厂商名称", "type": "string" },
              { "name": "hardware_version", "label": "硬件版本", "type": "string" },
              { "name": "software_version", "label": "软件版本", "type": "string" },
              { "name": "build_time", "label": "出厂/构建时间", "type": "string" },
              { "name": "sensor_id", "label": "传感器ID", "type": "int" }
            ]
          }
        },
        {
          "action": "calibrate",
          "action_name": "通道校准",
          "description": "下发指定通道的零点/标气校准，保存校准数据至 Flash",
          "scopes": ["config"],
          "danger_level": "warning",
          "confirm_msg": "确定要对该气体通道下发校准命令吗？这会覆盖硬件 Flash 中的基准校准点！",
          "params": [
            { "name": "sensor_id", "label": "目标传感器模组", "type": "int", "required": true, "ui_component": "select", "options": [{"name": "模组1", "value": 1}, {"name": "模组2", "value": 2}] },
            { "name": "channel_code", "label": "通道编号", "type": "int", "required": true, "ui_component": "select", "options": [{"name": "通道1", "value": 1}, {"name": "通道2", "value": 2}, {"name": "通道3", "value": 3}, {"name": "通道4", "value": 4}, {"name": "通道5", "value": 5}, {"name": "通道6", "value": 6}] },
            { "name": "level", "label": "校准类型", "type": "int", "required": true, "ui_component": "select", "options": [{"name": "零点校准", "value": 0}, {"name": "标气校准", "value": 1}] },
            { "name": "calibration_data", "label": "标气标准值(PPM)", "type": "int", "default": 0, "ui_component": "input_number" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "sensor_id", "label": "目标模组ID", "type": "int" },
              { "name": "channel_code", "label": "通道编号", "type": "int" },
              { "name": "success", "label": "校准结果", "type": "bool" }
            ]
          }
        },
        {
          "action": "reset",
          "action_name": "恢复出厂",
          "description": "复位指定通道或全模组出厂校准参数",
          "scopes": ["config"],
          "danger_level": "warning",
          "confirm_msg": "高危操作警告：恢复出厂设置将清除硬件中的自定义校准点，无法撤销！",
          "params": [
            { "name": "channel_code", "label": "目标通道(255表示全部)", "type": "int", "default": 255, "ui_component": "input_number" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "cycle",
          "action_name": "循环采集",
          "description": "控制气泵开启/关闭，并进行周期的气体数据循环采集与 status/up 主题定时上报",
          "scopes": ["task"],
          "params": [
            { "name": "action", "label": "操作动作", "type": "string", "required": true, "ui_component": "select", "options": [{"name": "开启", "value": "start"}, {"name": "关闭", "value": "stop"}] },
            { "name": "interval", "label": "上报间隔(秒)", "type": "int", "default": 5, "required": false, "ui_component": "input_number" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态(success/error)", "type": "string" },
              { "name": "message", "label": "执行描述", "type": "string" }
            ]
          }
        },
        {
          "action": "status",
          "action_name": "状态查询",
          "description": "检查串口在线状态",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "online", "label": "串口在线状态", "type": "bool" }
            ]
          }
        },
        {
          "action": "set_config",
          "action_name": "下发配置",
          "description": "设置并持久化各气体通道浓度告警阈值与告警提示语",
          "scopes": ["config"],
          "params": [
            { "name": "config", "label": "告警配置规则列表", "type": "array", "required": true, "ui_component": "json_editor" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "get_config",
          "action_name": "查询配置",
          "description": "获取当前本地持久化保存的气体告警配置列表",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "执行描述", "type": "string" },
              { "name": "data", "label": "配置数据", "type": "array" }
            ]
          }
        }
      ],
      "config_metrics": [
        { "metric_name": "CO2", "label": "二氧化碳", "unit": "PPM", "type": "float", "alarm_type": ["info", "warning", "error", "fatal"], "operator": ["lt", "lte", "gt", "gte", "between", "eq"] },
        { "metric_name": "CO", "label": "一氧化碳", "unit": "PPM", "type": "float", "alarm_type": ["info", "warning", "error", "fatal"], "operator": ["lt", "lte", "gt", "gte", "between", "eq"] },
        { "metric_name": "H2S", "label": "硫化氢", "unit": "PPM", "type": "float", "alarm_type": ["info", "warning", "error", "fatal"], "operator": ["lt", "lte", "gt", "gte", "between", "eq"] },
        { "metric_name": "O2", "label": "氧气浓度", "unit": "%VOL", "type": "float", "alarm_type": ["info", "warning", "error", "fatal"], "operator": ["lt", "lte", "gt", "gte", "between", "eq"] },
        { "metric_name": "EX", "label": "可燃气体", "unit": "%LEL", "type": "float", "alarm_type": ["info", "warning", "error", "fatal"], "operator": ["lt", "lte", "gt", "gte", "between", "eq"] },
        { "metric_name": "SF6", "label": "六氟化硫", "unit": "PPM", "type": "float", "alarm_type": ["info", "warning", "error", "fatal"], "operator": ["lt", "lte", "gt", "gte", "between", "eq"] },
        { "metric_name": "NOX", "label": "氮氧化物", "unit": "PPM", "type": "float", "alarm_type": ["info", "warning", "error", "fatal"], "operator": ["lt", "lte", "gt", "gte", "between", "eq"] }
      ]
    },
    {
      "plugin_type": "GdpdPlugin",
      "plugin_name": "局放插件",
      "description": "基于 TEV 地电波局放检测仪的自动采样、峰值/均值/频次统计分析能力",
      "version": "1.2.0",
      "supported_actions": [
        {
          "action": "monitor",
          "action_name": "局放检测",
          "description": "闭环局放采样流程：启动检测 -> 连续多次采样 -> 自动统计峰值与频次 -> 发送停止",
          "scopes": ["task"],
          "params": [
            { "name": "sample_count", "label": "采样次数", "type": "int", "default": 10, "required": false, "ui_component": "input_number" },
            { "name": "sample_interval", "label": "采样间隔(s)", "type": "float", "default": 1.0, "required": false, "ui_component": "input_number" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "peak", "label": "局放峰值(dBm)", "type": "float" },
              { "name": "mean", "label": "局放均值(dBm)", "type": "float" },
              { "name": "frequency", "label": "局放放电总频次", "type": "int" }
            ]
          }
        },
        {
          "action": "start_nav",
          "action_name": "启动采集",
          "description": "单独向 TEV 硬件下发开始监测采样指令",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" }
            ]
          }
        },
        {
          "action": "acquire",
          "action_name": "读取局放",
          "description": "单次读取当前实时局放幅值与频次数据",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "peak", "label": "局放峰值(dBm)", "type": "float" },
              { "name": "mean", "label": "局放均值(dBm)", "type": "float" },
              { "name": "frequency", "label": "局放放电频次", "type": "int" }
            ]
          }
        },
        {
          "action": "stop",
          "action_name": "停止采集",
          "description": "向 TEV 硬件下发停止监测采样指令",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" }
            ]
          }
        },
        {
          "action": "clear",
          "action_name": "数据清空",
          "description": "清空局放检测仪内部缓存数据",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" }
            ]
          }
        },
        {
          "action": "set_config",
          "action_name": "设置局放告警配置",
          "description": "配置局放检测峰值阈值告警规则",
          "scopes": ["config"],
          "params": [
            { "name": "config", "label": "告警规则配置", "type": "array", "required": true, "ui_component": "json_editor" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "get_config",
          "action_name": "获取局放告警配置",
          "description": "获取当前本地持久化保存的局放峰值告警配置",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "执行描述", "type": "string" },
              { "name": "data", "label": "配置数据", "type": "array" }
            ]
          }
        }
      ],
      "config_metrics": [
        {
          "metric_name": "PEAK",
          "label": "局放峰值",
          "unit": "dBm",
          "type": "float",
          "alarm_type": ["info", "warning", "error", "fatal"],
          "operator": ["lt", "lte", "gt", "gte", "between", "eq"]
        }
      ]
    },
    {
      "plugin_type": "AcousticPlugin",
      "plugin_name": "声纹插件",
      "description": "声纹插件",
      "version": "1.0.0",
      "supported_actions": [
        {
          "action": "query_spl",
          "action_name": "查询声压",
          "description": "查询当前声压值",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态(success/error)", "type": "string" },
              { "name": "data", "label": "数据", "type": "object", "fields": [
                  { "name": "spl", "label": "声压级", "type": "float" }
                ]
              }
            ]
          }
        },
        {
          "action": "cycle",
          "action_name": "循环采集",
          "description": "开启或关闭自动截取报警合并上报功能",
          "scopes": ["task"],
          "params": [
            { "name": "action", "label": "操作动作", "type": "string", "required": true, "ui_component": "select", "options": [{"name": "开启", "value": "start"}, {"name": "关闭", "value": "stop"}] },
            { "name": "interval", "label": "上报间隔(秒)", "type": "int", "default": 5, "required": false, "ui_component": "input_number" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态(success/error)", "type": "string" },
              { "name": "message", "label": "执行描述", "type": "string" }
            ]
          }
        },
        {
          "action": "enable_channel",
          "action_name": "使能通道",
          "description": "启用或关闭声纹分析通道",
          "scopes": ["config"],
          "params": [
            { "name": "enable", "type": "bool", "label": "使能", "required": true }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "执行描述", "type": "string" }
            ]
          }
        },
        {
          "action": "get_config",
          "action_name": "获取告警配置",
          "description": "获取当前本地持久化保存的声纹告警配置列表",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "执行描述", "type": "string" },
              { "name": "data", "label": "配置数据", "type": "array" }
            ]
          }
        },
        {
          "action": "set_config",
          "action_name": "设置告警配置",
          "description": "动态设置分级告警规则",
          "scopes": ["config"],
          "params": [
            { "name": "config", "label": "告警配置规则列表", "type": "array", "required": true, "ui_component": "json_editor" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "query_fault",
          "action_name": "查询PRPD故障",
          "description": "拉取深度诊断分析PRPD结果",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "data", "label": "数据", "type": "object", "fields": [
                  { "name": "discharge_acceptance", "label": "故障置信度", "type": "float" },
                  { "name": "discharge_malfunction_grade", "label": "故障严重程度", "type": "int" },
                  { "name": "discharge_type", "label": "故障类型", "type": "int" }
                ]
              }
            ]
          }
        },
        {
          "action": "get_status",
          "action_name": "查询设备状态",
          "description": "调用/status获取硬件级健康状态",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "data", "label": "数据", "type": "object", "fields": [
                  { "name": "app", "label": "App", "type": "string" },
                  { "name": "cam_heihgt", "label": "摄像机高度", "type": "int" },
                  { "name": "cam_width", "label": "摄像机宽度", "type": "int" },
                  { "name": "complie_time", "label": "编译时间", "type": "string" },
                  { "name": "cpu_temp", "label": "CPU温度", "type": "float" },
                  { "name": "device_no", "label": "设备编号", "type": "string" },
                  { "name": "fs", "label": "采样率", "type": "int" },
                  { "name": "gpu_temp", "label": "GPU温度", "type": "float" },
                  { "name": "httpflv_port", "label": "HTTP FLV端口", "type": "int" },
                  { "name": "npu_temp", "label": "NPU温度", "type": "float" },
                  { "name": "rtmp_port", "label": "RTMP端口", "type": "int" },
                  { "name": "rtsp_port", "label": "RTSP端口", "type": "int" },
                  { "name": "sn_fpga", "label": "FPGA序列号", "type": "string" },
                  { "name": "time", "label": "时间", "type": "string" },
                  { "name": "version", "label": "版本号", "type": "string" },
                  { "name": "version_fpga", "label": "FPGA版本号", "type": "string" },
                  { "name": "rms_enable", "label": "RMS使能", "type": "bool" }
                ]
              }
            ]
          }
        },
        {
          "action": "status",
          "action_name": "状态查询",
          "description": "查询网络连通状态",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "data", "label": "数据", "type": "object", "fields": [
                  { "name": "online", "label": "在线状态", "type": "bool" }
                ]
              }
            ]
          }
        },
        {
          "action": "reboot",
          "action_name": "重启设备",
          "description": "设备热重启",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "set_config",
          "action_name": "设置告警配置",
          "description": "动态设置声纹分级告警规则",
          "scopes": ["config"],
          "params": [
            { "name": "config", "label": "告警配置规则列表", "type": "array", "required": true, "ui_component": "json_editor" }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "描述", "type": "string" }
            ]
          }
        },
        {
          "action": "get_config",
          "action_name": "获取告警配置",
          "description": "获取当前本地持久化保存的声纹告警配置列表",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "执行描述", "type": "string" },
              { "name": "data", "label": "配置数据", "type": "array" }
            ]
          }
        }
      ],
      "config_metrics": [
        { "metric_name": "SPL", "label": "声压", "unit": "dB", "type": "float", "alarm_type": ["info", "warning", "error", "fatal"], "operator": ["lt", "lte", "gt", "gte", "between", "eq"] }
      ]
    },
    {
      "plugin_type": "RecordPlugin",
      "plugin_name": "录像插件",
      "version": "1.0.0",
      "description": "多通道视频切片录像与 SeaweedFS 即传即删自动同步插件",
      "supported_actions": [
        {
          "action": "start_record",
          "action_name": "开启录像",
          "description": "启动多路视频流 fMP4 切片录像 (支持全部通道并发或指定可读别名通道)",
          "scopes": ["task", "config"],
          "params": [
            {
              "name": "channel",
              "label": "录像通道",
              "type": "string",
              "default": "all",
              "required": false,
              "ui_component": "select",
              "options": [
                { "name": "全部通道", "value": "all" },
                { "name": "可见光通道 (vis)", "value": "vis" },
                { "name": "热成像通道 (thm)", "value": "thm" }
              ]
            },
            {
              "name": "segment_duration",
              "label": "分片时长(秒)",
              "type": "int",
              "default": 60,
              "required": false,
              "ui_component": "input_number"
            },
            {
              "name": "task_id",
              "label": "关联任务ID",
              "type": "string",
              "required": false,
              "ui_component": "input_text"
            }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "执行描述", "type": "string" },
              { "name": "data", "label": "录像元数据", "type": "object" }
            ]
          }
        },
        {
          "action": "stop_record",
          "action_name": "停止录像",
          "description": "安全停止当前正在运行的所有录像管线并完成尾部分片原子封包归档 (无须传参，默认全部停止)",
          "scopes": ["task", "config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "执行描述", "type": "string" },
              { "name": "data", "label": "停止结果", "type": "object" }
            ]
          }
        },
        {
          "action": "record_status",
          "action_name": "录像状态查询",
          "description": "查询当前录像运行状态与 SeaweedFS 视频同步队列积压情况",
          "scopes": ["config"],
          "params": [],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "执行描述", "type": "string" },
              { "name": "data", "label": "状态数据", "type": "object" }
            ]
          }
        },
        {
          "action": "sync_control",
          "action_name": "视频同步控制",
          "description": "手动挂起或恢复 SeaweedFS 视频后台同步服务",
          "scopes": ["config"],
          "params": [
            {
              "name": "control",
              "label": "控制指令",
              "type": "string",
              "default": "pause",
              "required": true,
              "ui_component": "select",
              "options": [
                { "name": "挂起同步(pause)", "value": "pause" },
                { "name": "恢复同步(resume)", "value": "resume" }
              ]
            }
          ],
          "returns": {
            "type": "object",
            "fields": [
              { "name": "status", "label": "执行状态", "type": "string" },
              { "name": "message", "label": "执行描述", "type": "string" }
            ]
          }
        }
      ]
    }
  ],
  "components": [
    {
      "component_type": "DoorComponent",
      "component_name": "开门组件",
      "description": "高级业务组件：自动完成开门、穿行、关门，并包含防夹车紧急保护",
      "scopes": ["task"],
      "params": [
        { "name": "door_ips", "label": "IP列表", "type": "array", "required": true, "ui_component": "input_array" },
        { "name": "entry_point", "label": "门外点ID", "type": "int", "required": true, "ui_component": "input_number" },
        { "name": "exit_point", "label": "门内点ID", "type": "int", "required": true, "ui_component": "input_number" }
      ],
      "returns": {
        "type": "object",
        "fields": [
          { "name": "status", "label": "执行状态", "type": "string" },
          { "name": "message", "label": "描述", "type": "string" }
        ]
      }
    },
    {
      "component_type": "ElevatorComponent",
      "component_name": "呼梯组件",
      "description": "包含乘梯上下楼的完整业务流",
      "scopes": ["task"],
      "params": [
        { "name": "addr", "label": "电梯编号", "type": "int", "required": true, "ui_component": "input_number" },
        { "name": "start_floor", "label": "出发楼层", "type": "int", "required": true, "ui_component": "input_number" },
        { "name": "start_point", "label": "出发点", "type": "int", "required": true, "ui_component": "input_number" },
        { "name": "start_ele_point", "label": "出发地图连接点", "type": "int", "required": true, "ui_component": "input_number" },
        { "name": "target_floor", "label": "目标楼层", "type": "int", "required": true, "ui_component": "input_number" },
        { "name": "target_point", "label": "目标点", "type": "int", "required": true, "ui_component": "input_number" },
        { "name": "target_ele_point", "label": "目标地图连接点", "type": "int", "required": true, "ui_component": "input_number" }
      ],
      "returns": {
        "type": "object",
        "fields": [
          { "name": "status", "label": "执行状态", "type": "string" },
          { "name": "message", "label": "描述", "type": "string" }
        ]
      }
    },
    {
      "component_type": "StationComponent",
      "component_name": "充电站组件",
      "description": "包含进出充电站的完整业务流",
      "scopes": ["task"],
      "params": [
        { "name": "direction", "label": "动作方向", "type": "string", "default": "leave", "required": false, "ui_component": "select", "options": [{"name": "出站", "value": "leave"}, {"name": "进站", "value": "enter"}] },
        { "name": "inner_point", "label": "站内点位ID", "type": "int", "required": true, "ui_component": "input_number" },
        { "name": "outer_point", "label": "站外点位ID", "type": "int", "required": true, "ui_component": "input_number" },
        { "name": "ips", "label": "继电器控制器IP列表", "type": "array", "required": true, "ui_component": "input_array" }
      ],
      "returns": {
        "type": "object",
        "fields": [
          { "name": "status", "label": "执行状态", "type": "string" },
          { "name": "message", "label": "描述", "type": "string" }
        ]
      }
    }
  ]
}
```

---


