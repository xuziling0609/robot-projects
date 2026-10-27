# 📡 边缘网关 MQTT 通信协议与 Topic 设计规范 (全实例数据包与 Code 码表)

本规范基于机器人边缘网关 (`robot_project`) 的实际生产代码落地，详细记录 MQTT Topic 命名规则、报文方向、触发时机、**Code 应答状态码全量字典**、**所有平台下发指令及回复**、以及**全量插件能力动作 (Action) 的指令与完整回复实例**。

---

## 1. Topic 命名架构与总览

以网关唯一设备 ID `robot_id` (配置参见 `configs/config.yaml`，示例: `robot888`) 为命名空间，分为 1 个下行控制通道与 4 个上行汇报通道：

```text
/edge/gateway/{robot_id}/
├── cmd/down          [下行] 云端 -> 网关 唯一下行指令通道 (QoS=1)
├── response/up       [上行] 网关 -> 云端 控制指令 ACK 回复通道 (ACK_RECEIVE / ACK_STEP / ACK_EXECUTE) (QoS=1)
├── status/up         [上行] 网关 -> 云端 机器人与插件实时状态上报通道 (去重防抖) (QoS=0)
├── alarm/up          [上行] 网关 -> 云端 硬件故障与紧急告警通道 (QoS=1)
└── capability/up     [上行] 网关 -> 云端 物模型与能力插件定义上报通道 (QoS=1)
```

---

## 2. Response / Status Code 应答状态码全量字典

网关通过 `/edge/gateway/{robot_id}/response/up` 通道上报 `ACK_RECEIVE` 或 `ACK_EXECUTE` 时，响应报文中的 `code` 状态码定义如下：

| Code 状态码 | 名称标识 | 含义说明 | 典型场景及处理建议 |
| :--- | :--- | :--- | :--- |
| **`0`** | `SUCCESS` | **操作成功 / 接收确认** | 1. 网关成功解析命令并进入队列 (`ACK_RECEIVE`)<br>2. 动作或任务链圆满执行完成 (`ACK_EXECUTE`) |
| **`4000`** | `BAD_REQUEST` | **报文格式或参数非法** | 下发了非合法 JSON 格式，或缺少必要字段 (如缺少 `cmd_type`/`action`，或 `task` 的 `steps` 数组为空) |
| **`4004`** | `PLUGIN_NOT_FOUND` | **找不到指定能力插件** | 下发的 `plugin_type` 在网关插件管理器中未注册 (如 `UnknownPlugin`) |
| **`4005`** | `TASK_NOT_FOUND` | **本地任务/剧本不存在** | 尝试执行的 `task_id` 在网关内存及 `data/tasks/` 磁盘中均找不到对应 JSON |
| **`4008`** | `EXECUTION_TIMEOUT` | **硬件动作执行超时** | 机器人导航到点超时、开门机轮询到位超时或硬件无回应 |
| **`4009`** | `TASK_ABORTED` | **任务提前取消/打断** | 任务在步骤开始前被取消，或在暂停轮询等待期间收到了平台下发的 `abort` 指令 |
| **`5000`** | `INTERNAL_ERROR` | **网关内部或硬件执行错误** | 底层串口/Socket 断开、任务步骤执行逻辑失败 (自动挂起 PAUSED 等待重试) |
| **`5001`** | `ACTION_FAILED` | **即时动作执行失败** | 驱动层或底层硬件返回 status != "success" (如机械臂不可达、导航点校验失败) |
| **`5005`** | `UNHANDLED_EXCEPTION` | **未捕获严重异常** | 执行动作时发生未捕获的 Python 内部抛错与崩溃 |

---

## 3. 平台下发指令 (Downstream Command) 与完整回复 (Upstream ACK) 规范

* **下行 Topic**: `/edge/gateway/{robot_id}/cmd/down`
* **上行 ACK Topic**: `/edge/gateway/{robot_id}/response/up`

所有接收到的命令，网关都会在收到时**立刻回复**一条 `ACK_RECEIVE` 报文，并在执行完毕后**回复**一条 `ACK_EXECUTE` 报文。

---

### 3.1 单能力即时指令 (`cmd_type: "action"`)

#### 📥 下发控制报文 (`cmd/down`)
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800000000,
  "cmd_type": "action",
  "plugin_type": "DoorPlugin",
  "action": "open",
  "params": {
    "ips": ["127.0.0.1", "127.0.0.2"]
  }
}
```

#### 📤 阶段 1: 接单确认回复 (`ACK_RECEIVE`)
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800000050,
  "robot_id": "robot888",
  "reply_type": "ACK_RECEIVE",
  "code": 0,
  "message": "网关已接收指令，正在调度执行"
}
```

#### 📤 阶段 2: 执行结果回复 (`ACK_EXECUTE` - 成功示例)
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800002150,
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "动作执行成功",
  "data": {
    "result": {
      "status": "success",
      "message": "开门机 open 完成"
    },
    "duration_ms": 2100
  }
}
```

#### 📤 阶段 2: 执行结果回复 (`ACK_EXECUTE` - 失败示例)
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800003000,
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "动作执行失败: 未提取到门控 IPs",
  "data": {
    "result": {
      "status": "failed",
      "message": "未提取到门控 IPs"
    },
    "duration_ms": 10
  }
}
```

> [!IMPORTANT]
> **可靠性保证（离线缓存与 0.5s 补发机制）**：
> 当机器人位于弱网/死角导致 MQTT 未连接或 `publish` 异常时，发往 `/response/up` 的所有 ACK 报文（`ACK_RECEIVE` / `ACK_PROGRESS` / `ACK_EXECUTE`）将被自动转入网关本地 FIFO 离线队列缓存。当检测到 MQTT 网络连通恢复后，后台守护线程将自动以 **`0.5s` 的固定时间间隔** 匀速弹出并重发积压的 ACK 报文。

---

### 3.2 离线任务生命周期管理 (`cmd_type: "task"`)

> 💡 **工业级设计规范说明**：
> 系统采用工业强一致性与断电/断网可靠性设计，**禁止直接透传 steps 动态任务链就地执行**。所有多步骤任务必须先通过写盘保存 (`save` / `sync`) 存入本地离线任务库 (`data/tasks/{task_id}.json`)，再通过触发指令 (`run`) 载入执行。同时完整支持离线任务运行时暂停 (`pause`)、恢复 (`resume`)、打断 (`abort`)、逆向返航 (`rth`)、删除 (`delete`)、清单查询 (`list`) 及一键清空 (`clear`)。

#### 3.2.1 任务暂停/恢复/取消/返航控制指令 (`action: "pause"` / `"resume"` / `"abort"` / `"rth"`)

当任务处于执行中时，可直接下发对应的 `action` 控制正在运行的任务：

> 💡 **关键机制 - 参数降级与缓存补齐**：下发全局控制指令时，建议携带目标 `task_id` 和 `task_name` 以供校验。若平台下发时未携带（为空），网关会自动从本地上下文（`ContextManager`）中寻找当前正在运行的任务。如果本地也没有正在运行的任务，回复的 `ACK_EXECUTE` 报文中 `task_id` 和 `task_name` 将直接为空字符串 `""`，**不再向下降级使用 `msg_id`**。

* **下发暂停 (`cmd/down`)**:
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800008000,
  "cmd_type": "task",
  "task_id": "TASK_20260728_001",
  "task_name": "配电房综合巡检任务",
  "action": "pause"
}
```
* **回复暂停成功 (`ACK_EXECUTE`)**:
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800008050,
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务 [配电房综合巡检任务] 暂停成功",
  "data": {
    "task_id": "TASK_20260728_001",
    "task_name": "配电房综合巡检任务",
    "task_action": "pause",
    "task_status": "PAUSED",
    "duration_ms": 50
  }
}
```

* **下发恢复 (`cmd/down`)**:
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800009000,
  "cmd_type": "task",
  "task_id": "TASK_20260728_001",
  "task_name": "配电房综合巡检任务",
  "action": "resume"
}
```
* **回复恢复成功 (`ACK_EXECUTE`)**:
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800009050,
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务 [配电房综合巡检任务] 恢复执行成功",
  "data": {
    "task_id": "TASK_20260728_001",
    "task_name": "配电房综合巡检任务",
    "task_action": "resume",
    "task_status": "RUNNING",
    "duration_ms": 50
  }
}
```

* **下发取消/打断 (`cmd/down`)**:
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800010000,
  "cmd_type": "task",
  "task_id": "TASK_20260728_001",
  "task_name": "配电房综合巡检任务",
  "action": "abort"
}
```
* **回复取消成功 (`ACK_EXECUTE`)**:
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800010050,
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务 [配电房综合巡检任务] 已成功终止/打断",
  "data": {
    "task_id": "TASK_20260728_001",
    "task_name": "配电房综合巡检任务",
    "task_action": "abort",
    "task_status": "ABORTED",
    "duration_ms": 50
  }
}
```

* **下发一键安全返航/逆向回退 (`cmd/down`)**:
> 💡 **机制说明**：网关在 `RUNNING`, `PAUSED` 或 `FAILED` 状态收到 `rth` 指令时，将立即打断当前任务，并基于当前已执行的任务步骤记录生成安全的“原路逆向返回”步骤链进行执行。若当前为 `IDLE` 或无历史任务记录，则会直接拒绝执行。
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800011000,
  "cmd_type": "task",
  "task_id": "TASK_20260728_001",
  "task_name": "配电房综合巡检任务",
  "action": "rth"
}
```
* **拒接返航 (如当前为 IDLE 无历史步骤) (`ACK_EXECUTE`)**:
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800011050,
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 4000,
  "message": "当前状态不可返航",
  "data": {
    "task_id": "",
    "task_name": "",
    "task_action": "rth",
    "duration_ms": 10,
    "status": "idle"
  }
}
```
* **接受并开始返航执行 (视作一个新生成任务处理，执行完发送最终 `ACK_EXECUTE`)**:
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800025000,
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "task_id": "TASK_20260728_001_RTH",
    "task_name": "配电房综合巡检任务_返航",
    "total_steps": 2,
    "executed_steps": 2,
    "duration_ms": 13950
  }
}
```

#### 3.2.2 离线任务写盘保存 (`action: "save"` / `"sync"`)

* **下发 (`cmd/down`)**:
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800002000,
  "cmd_type": "task",
  "action": "save",
  "task_id": "TASK_OFFLINE_F3_01",
  "task_name": "3楼配电房巡检预设任务",
  "rth": {
    "localization": [1, 2],
    "point_id": 1
  },
  "steps": [
    {
      "step": 1,
      "plugin_type": "NavPlugin",
      "action": "start_nav",
      "params": { "goal_point": 10 }
    },
    {
      "step": 2,
      "plugin_type": "DoorPlugin",
      "action": "open",
      "params": { "ips": ["127.0.0.1"] }
    }
  ]
}
```
* **回复 (`ACK_EXECUTE`)**:
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800002080,
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务 [TASK_OFFLINE_F3_01] 保存/修改完成",
  "data": {
    "task_id": "TASK_OFFLINE_F3_01",
    "task_name": "3楼配电房巡检预设任务",
    "steps_count": 2,
    "task_action": "save",
    "duration_ms": 80
  }
}
```

#### 3.2.3 离线任务触发执行 (`action: "run"`)

* **下发 (`cmd/down`)**:
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800003000,
  "cmd_type": "task",
  "action": "run",
  "task_id": "TASK_OFFLINE_F3_01"
}
```
* **回复接收 (`ACK_RECEIVE`)**:
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800003050,
  "robot_id": "robot888",
  "reply_type": "ACK_RECEIVE",
  "code": 0,
  "message": "网关已接收指令，正在调度执行"
}
```

* **回复阶段性子任务完成 (`ACK_PROGRESS`)**:
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800008000,
  "robot_id": "robot888",
  "reply_type": "ACK_PROGRESS",
  "code": 0,
  "message": "步骤 1/2 [NavPlugin.start_nav] 执行完成",
  "data": {
    "task_id": "TASK_OFFLINE_F3_01",
    "task_name": "3楼配电房巡检预设任务",
    "step": 1,
    "total_steps": 2,
    "plugin_type": "NavPlugin",
    "plugin_action": "start_nav",
    "task_status": "RUNNING",
    "step_status": "success",
    "duration_ms": 4950,
    "result": {
      "status": "success",
      "message": "已成功到达导航目标点 [10]"
    }
  }
}
```

* **回复总体完成 (`ACK_EXECUTE`)**:
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800015000,
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "task_id": "TASK_OFFLINE_F3_01",
    "task_name": "3楼配电房巡检预设任务",
    "task_status": "FINISH",
    "total_steps": 2,
    "executed_steps": 2,
    "duration_ms": 12000,
    "result": {
      "status": "success",
      "message": "开门机 open 完成"
    }
  }
}
```

#### 3.2.4 本地离线任务删除 (`action: "delete"`)

* **下发 (`cmd/down`)**:
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800004000,
  "cmd_type": "task",
  "action": "delete",
  "task_id": "TASK_OFFLINE_F3_01"
}
```
* **回复 (`ACK_EXECUTE`)**:
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800004020,
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "离线任务 [TASK_OFFLINE_F3_01] 已成功删除",
  "data": {
    "task_id": "TASK_OFFLINE_F3_01",
    "duration_ms": 20
  }
}
```

#### 3.2.5 本地任务清单盘点 (`action: "list"`)

* **下发 (`cmd/down`)**:
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800005000,
  "cmd_type": "task",
  "action": "list"
}
```
* **回复 (`ACK_EXECUTE`)**:
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800005010,
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "获取本地离线任务清单成功",
  "data": {
    "status": "success",
    "total_count": 1,
    "tasks": [
      {
        "task_id": "TASK_OFFLINE_F3_01",
        "task_name": "3楼配电房巡检预设任务",
        "total_steps": 2,
        "updated_at": 1721800002000
      }
    ],
    "duration_ms": 10
  }
}
```

#### 3.2.6 本地任务一键清空 (`action: "clear"`)

* **下发 (`cmd/down`)**:
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800006000,
  "cmd_type": "task",
  "action": "clear"
}
```
* **回复 (`ACK_EXECUTE`)**:
```json
{
  "msg_id": "20260728-092443-471-250",
  "timestamp": 1721800006015,
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "成功清空本地所有离线任务 (共 1 个)",
  "data": {
    "status": "success",
    "message": "成功清空本地所有离线任务 (共 1 个)",
    "cleared_count": 1,
    "duration_ms": 15
  }
}
```

---

## 4. 全量插件能力动作 (Plugin Actions) 指令与完整回复实例

> 💡 **统一通信规范说明**：
> - **命令下发 Topic**: `/edge/gateway/{robot_id}/command/down` (QoS=1, `cmd_type: "action"`)
> - **响应上报 Topic**: `/edge/gateway/{robot_id}/command/ack` (QoS=1, `reply_type: "ACK_EXECUTE"`)
> - **成功响应结构**: `code: 0`, `message: "任务完成"`, `data.result.status: "success"`
> - **失败响应结构**: `code: 500` (或 400), `message: "任务处理失败"`, `data.result.status: "error"`, `data.result.message: "异常说明信息"`

---

### 4.1 导航插件 (`NavPlugin`)

#### 1) 开始导航 (`action: "start_nav"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-250",
  "cmd_type": "action",
  "plugin_type": "NavPlugin",
  "action": "start_nav",
  "params": { "goal_point": 15, "type": 0 }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-250",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 8500,
    "result": {
      "status": "success",
      "message": "成功到达导航目标点 [15]"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-250",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "导航路径被阻挡或目标点不可达",
  "data": {
    "duration_ms": 4200,
    "result": {
      "status": "error",
      "message": "导航控制器返回导航异常: OBSTACLE_BLOCKED (目标点: 15)"
    }
  }
}
```

#### 2) 暂停导航 (`action: "pause_nav"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-251",
  "cmd_type": "action",
  "plugin_type": "NavPlugin",
  "action": "pause_nav",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-251",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 120,
    "result": {
      "status": "success",
      "message": "暂停导航 成功"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-251",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "暂停导航失败",
  "data": {
    "duration_ms": 100,
    "result": {
      "status": "error",
      "message": "当前处于 IDLE 空闲状态，无需暂停导航"
    }
  }
}
```

#### 3) 恢复导航 (`action: "resume_nav"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-252",
  "cmd_type": "action",
  "plugin_type": "NavPlugin",
  "action": "resume_nav",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-252",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 150,
    "result": {
      "status": "success",
      "message": "恢复导航 成功"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-252",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "恢复导航失败",
  "data": {
    "duration_ms": 110,
    "result": {
      "status": "error",
      "message": "当前导航未在 PAUSED 暂停状态，无法恢复"
    }
  }
}
```

#### 4) 取消导航 (`action: "abort_nav"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-253",
  "cmd_type": "action",
  "plugin_type": "NavPlugin",
  "action": "abort_nav",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-253",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 95,
    "result": {
      "status": "success",
      "message": "取消导航 成功"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-253",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "取消导航失败",
  "data": {
    "duration_ms": 80,
    "result": {
      "status": "error",
      "message": "导航 WebAPI 接口通信断开，取消指令下发超时"
    }
  }
}
```

#### 5) 模式切换 (`action: "set_mode"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-254",
  "cmd_type": "action",
  "plugin_type": "NavPlugin",
  "action": "set_mode",
  "params": { "mode": "AUTO" }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-254",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 210,
    "result": {
      "status": "success",
      "message": "切换模式为 [AUTO] 成功"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-254",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 400,
  "message": "无效的运行模式",
  "data": {
    "duration_ms": 50,
    "result": {
      "status": "error",
      "message": "不支持的模式参数: UNKNOWN_MODE，可选: AUTO / MANUAL"
    }
  }
}
```

#### 6) 步态切换 (`action: "set_gait"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-255",
  "cmd_type": "action",
  "plugin_type": "NavPlugin",
  "action": "set_gait",
  "params": { "gait_index": 1, "robot_type": 513 }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-255",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 310,
    "result": {
      "status": "success",
      "message": "切换步态为 [1] 成功"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-255",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "步态切换失败",
  "data": {
    "duration_ms": 280,
    "result": {
      "status": "error",
      "message": "底层驱动拒绝步态切换: 底盘正在急速奔跑中"
    }
  }
}
```

#### 7) 动作执行 (`action: "execute_motion"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-256",
  "cmd_type": "action",
  "plugin_type": "NavPlugin",
  "action": "execute_motion",
  "params": { "motion_cmd": 1 }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-256",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 1200,
    "result": {
      "status": "success",
      "message": "执行机器人动作 (cmd=1) 成功"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-256",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "特技动作执行失败",
  "data": {
    "duration_ms": 500,
    "result": {
      "status": "error",
      "message": "电量不足(12%)，保护机制拒绝执行跳跃打滚特技动作"
    }
  }
}
```

#### 8) 摇杆遥控 (`action: "manual_control"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-257",
  "cmd_type": "action",
  "plugin_type": "NavPlugin",
  "action": "manual_control",
  "params": { "speed_x": 0.5, "speed_y": 0.0, "speed_theta": 0.1 }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-257",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 45,
    "result": {
      "status": "success",
      "message": "下发遥控速度 (x=0.5, y=0.0, theta=0.1) 成功"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-257",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 400,
  "message": "遥控参数超限",
  "data": {
    "duration_ms": 30,
    "result": {
      "status": "error",
      "message": "速度限制保护: speed_x=3.5 超过最大允许安全限制 1.5m/s"
    }
  }
}
```

#### 9) 急停阻尼 (`action: "jerk_stop"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-258",
  "cmd_type": "action",
  "plugin_type": "NavPlugin",
  "action": "jerk_stop",
  "params": { "jerk": true }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-258",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 80,
    "result": {
      "status": "success",
      "message": "阻尼急停请求 (jerk=True) 成功"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-258",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "阻尼急停响应失败",
  "data": {
    "duration_ms": 60,
    "result": {
      "status": "error",
      "message": "底盘控制器无响应，无法建立急停阻尼姿态"
    }
  }
}
```

#### 10) 状态查询 (`action: "status"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-259",
  "cmd_type": "action",
  "plugin_type": "NavPlugin",
  "action": "status",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-259",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 50,
    "result": {
      "status": "success",
      "message": "获取导航状态成功",
      "data": {
        "online": true
      }
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-259",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "导航状态查询失败",
  "data": {
    "duration_ms": 3000,
    "result": {
      "status": "error",
      "message": "连接导航 WebAPI 接收 HTTP 端口超时 (127.0.0.1:17899)"
    }
  }
}
```

#### 11) 设置告警配置 (`action: "set_config"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-260",
  "cmd_type": "action",
  "plugin_type": "NavPlugin",
  "action": "set_config",
  "params": {
    "config": [
      {
        "metric_name": "BATTERY",
        "unit": "%",
        "thresholds": {
          "warning": { "operator": "lt", "value": 30.0, "message": "底盘电量低于30%，建议及时充电" },
          "fatal": { "operator": "lt", "value": 15.0, "message": "底盘电量严重不足，立即强制中断返航！", "auto_action": "rth" }
        }
      }
    ]
  }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-260",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "动作执行成功",
  "data": {
    "duration_ms": 25,
    "result": {
      "status": "success",
      "message": "成功保存导航电量告警配置至 /home/zonwey/robot_project/data/plugins/NavPlugin_alarm.json",
      "data": [
        {
          "metric_name": "BATTERY",
          "unit": "%",
          "thresholds": {
            "warning": { "operator": "lt", "value": 30.0, "message": "底盘电量低于30%，建议及时充电" },
            "fatal": { "operator": "lt", "value": 15.0, "message": "底盘电量严重不足，立即强制中断返航！", "auto_action": "rth" }
          }
        }
      ]
    }
  }
}
```

#### 12) 查询告警配置 (`action: "get_config"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-261",
  "cmd_type": "action",
  "plugin_type": "NavPlugin",
  "action": "get_config",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-261",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "动作执行成功",
  "data": {
    "duration_ms": 15,
    "result": {
      "status": "success",
      "message": "成功获取导航电量告警配置",
      "data": [
        {
          "metric_name": "BATTERY",
          "unit": "%",
          "thresholds": {
            "warning": { "operator": "lt", "value": 30.0, "message": "底盘电量低于30%，建议及时充电" },
            "fatal": { "operator": "lt", "value": 15.0, "message": "底盘电量严重不足，立即强制中断返航！", "auto_action": "rth" }
          }
        }
      ]
    }
  }
}
```

---

### 4.2 开门机插件 (`DoorPlugin`)

#### 1) 自动开门 (`action: "open"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-260",
  "cmd_type": "action",
  "plugin_type": "DoorPlugin",
  "action": "open",
  "params": { "ips": ["127.0.0.1"] }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-260",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 3200,
    "result": {
      "status": "success",
      "message": "开门机 open 完成"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-260",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "门控机通信失败",
  "data": {
    "duration_ms": 5000,
    "result": {
      "status": "error",
      "message": "门控机 [127.0.0.1] 网络连接超时无响应"
    }
  }
}
```

#### 2) 自动关门 (`action: "close"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-261",
  "cmd_type": "action",
  "plugin_type": "DoorPlugin",
  "action": "close",
  "params": { "ips": ["127.0.0.1"] }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-261",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 3100,
    "result": {
      "status": "success",
      "message": "开门机 close 完成"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-261",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "关门失败",
  "data": {
    "duration_ms": 3000,
    "result": {
      "status": "error",
      "message": "门控机 [127.0.0.1] 防夹传感器触发，关门阻挡中断"
    }
  }
}
```

#### 3) 停止动作 (`action: "pause"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-262",
  "cmd_type": "action",
  "plugin_type": "DoorPlugin",
  "action": "pause",
  "params": { "ips": ["127.0.0.1"] }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-262",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 250,
    "result": {
      "status": "success",
      "message": "开门机 pause 完成"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-262",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "停止指令下发失败",
  "data": {
    "duration_ms": 1500,
    "result": {
      "status": "error",
      "message": "门控机 [127.0.0.1] 网络中断，无法发送停止指令"
    }
  }
}
```

#### 4) 状态查询 (`action: "status"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-263",
  "cmd_type": "action",
  "plugin_type": "DoorPlugin",
  "action": "status",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-263",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 120,
    "result": {
      "status": "success",
      "message": "查询门控机状态成功",
      "data": {
        "online": true,
        "door_state": "CLOSED"
      }
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-263",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "门控机状态查询异常",
  "data": {
    "duration_ms": 5000,
    "result": {
      "status": "error",
      "message": "门控机设备离线，未配置默认 IP 列表"
    }
  }
}
```

---

### 4.3 智能电梯插件 (`ElevatorPlugin`)

#### 1) 乘梯前往 (`action: "goToFloor"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-264",
  "cmd_type": "action",
  "plugin_type": "ElevatorPlugin",
  "action": "goToFloor",
  "params": { "addr": 18191, "floor": 3 }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-264",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 15400,
    "result": {
      "status": "success",
      "message": "电梯已成功到达 3 层"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-264",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "电梯联动失败",
  "data": {
    "duration_ms": 30000,
    "result": {
      "status": "error",
      "message": "电梯梯控服务器超时无响应或目标楼层 [3] 被禁用"
    }
  }
}
```

#### 2) 电梯开门 (`action: "openDoor"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-265",
  "cmd_type": "action",
  "plugin_type": "ElevatorPlugin",
  "action": "openDoor",
  "params": { "addr": 18191 }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-265",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 450,
    "result": {
      "status": "success",
      "message": "已开启电梯循环保持开门模式"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-265",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "电梯开门失败",
  "data": {
    "duration_ms": 300,
    "result": {
      "status": "error",
      "message": "梯控系统响应错误: ELEVATOR_BUSY_OR_OFFLINE"
    }
  }
}
```

#### 3) 电梯关门 (`action: "closeDoor"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-266",
  "cmd_type": "action",
  "plugin_type": "ElevatorPlugin",
  "action": "closeDoor",
  "params": { "addr": 18191 }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-266",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 380,
    "result": {
      "status": "success",
      "message": "已关闭电梯门"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-266",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "电梯关门失败",
  "data": {
    "duration_ms": 250,
    "result": {
      "status": "error",
      "message": "无法关闭电梯门: 关门光幕检测到人员进出"
    }
  }
}
```

#### 4) 状态查询 (`action: "status"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-267",
  "cmd_type": "action",
  "plugin_type": "ElevatorPlugin",
  "action": "status",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-267",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 100,
    "result": {
      "status": "success",
      "message": "查询电梯连接状态成功",
      "data": {
        "online": true,
        "current_floor": 1
      }
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-267",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "电梯状态查询异常",
  "data": {
    "duration_ms": 2000,
    "result": {
      "status": "error",
      "message": "电梯云服务 TCP 链路超时断开"
    }
  }
}
```

---

### 4.4 充电站插件 (`StationPlugin`)

#### 1) 基站开门 (`action: "open"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-268",
  "cmd_type": "action",
  "plugin_type": "StationPlugin",
  "action": "open",
  "params": { "ips": ["127.0.0.1"] }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-268",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 1500,
    "result": {
      "status": "success",
      "message": "开门成功"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-268",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "基站开门失败",
  "data": {
    "duration_ms": 2000,
    "result": {
      "status": "error",
      "message": "Tasio211 继电器控制器 [127.0.0.1] 连接超时"
    }
  }
}
```

#### 2) 基站关门 (`action: "close"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-269",
  "cmd_type": "action",
  "plugin_type": "StationPlugin",
  "action": "close",
  "params": { "ips": ["127.0.0.1"] }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-269",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 1400,
    "result": {
      "status": "success",
      "message": "关门成功"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-269",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "基站关门失败",
  "data": {
    "duration_ms": 1800,
    "result": {
      "status": "error",
      "message": "继电器通道 1 写入硬件平移门驱动时产生通信 Error"
    }
  }
}
```

#### 3) 状态查询 (`action: "status"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-270",
  "cmd_type": "action",
  "plugin_type": "StationPlugin",
  "action": "status",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-270",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 90,
    "result": {
      "status": "success",
      "message": "基站继电器状态查询成功",
      "data": {
        "online": true
      }
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-270",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "充电基站状态查询异常",
  "data": {
    "duration_ms": 3000,
    "result": {
      "status": "error",
      "message": "Tasio211 继电器设备未在本地网段建立连接"
    }
  }
}
```

---

### 4.5 基础系统插件 (`SystemPlugin`)

#### 1) 延时等待 (`action: "delay"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-271",
  "cmd_type": "action",
  "plugin_type": "SystemPlugin",
  "action": "delay",
  "params": { "seconds": 5.0 }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-271",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 5005,
    "result": {
      "status": "success",
      "message": "延时 5.0 秒完成"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-271",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "延时中断",
  "data": {
    "duration_ms": 1200,
    "result": {
      "status": "error",
      "message": "延时过程中收到外部 pause 暂停/abort 打断信号，任务链强制退出"
    }
  }
}
```

#### 2) 状态查询 (`action: "status"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-272",
  "cmd_type": "action",
  "plugin_type": "SystemPlugin",
  "action": "status",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-272",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 10,
    "result": {
      "status": "success",
      "message": "基础系统运行正常",
      "data": {
        "online": true
      }
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-272",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "系统状态查询异常",
  "data": {
    "duration_ms": 15,
    "result": {
      "status": "error",
      "message": "系统高负载告警(CPU 100%)"
    }
  }
}
```

#### 3) 重启网关服务 (`action: "restart_service"`)
* **说明**：触发边缘网关中间件服务平滑重启。内置“先回 ACK 后重启”机制与安全互锁判定。默认若检测到当前有正在执行或挂起的任务，将拦截并返回失败提示；如需紧急重启，可在参数中指定 `"force": true`。
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-273",
  "cmd_type": "action",
  "plugin_type": "SystemPlugin",
  "action": "restart_service",
  "params": {
    "delay_s": 1.0,
    "force": false
  }
}
```
* **成功回复 (ACK_EXECUTE)**:
```json
{
  "msg_id": "20260728-092443-471-273",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "动作执行成功",
  "data": {
    "duration_ms": 12,
    "result": {
      "status": "success",
      "message": "网关服务正在重启中，将在 1.0 秒后触发优雅退出并重新拉起",
      "data": {
        "target": "service",
        "delay_s": 1.0
      }
    }
  }
}
```
* **安全互锁拦截回复 (ACK_EXECUTE)**:
```json
{
  "msg_id": "20260728-092443-471-273",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5001,
  "message": "动作执行失败: 当前机器人正在执行或挂起任务[TASK_20260728_001]，已拒绝执行重启。如需紧急强制执行请指定 force=True",
  "data": {
    "duration_ms": 8,
    "result": {
      "status": "error",
      "message": "当前机器人正在执行或挂起任务[TASK_20260728_001]，已拒绝执行重启。如需紧急强制执行请指定 force=True"
    }
  }
}
```

#### 4) 重启操作系统 (`action: "reboot_system"`)
* **说明**：触发工控机操作系统整机重启。同样具备“先回 ACK 后重启”与动态任务安全互锁防护。
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-274",
  "cmd_type": "action",
  "plugin_type": "SystemPlugin",
  "action": "reboot_system",
  "params": {
    "delay_s": 2.0,
    "force": false
  }
}
```
* **成功回复 (ACK_EXECUTE)**:
```json
{
  "msg_id": "20260728-092443-471-274",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "动作执行成功",
  "data": {
    "duration_ms": 15,
    "result": {
      "status": "success",
      "message": "工控机操作系统正在重启中，将在 2.0 秒后切断物理系统并重新启动",
      "data": {
        "target": "system",
        "delay_s": 2.0
      }
    }
  }
}
```
* **安全互锁拦截回复 (ACK_EXECUTE)**:
```json
{
  "msg_id": "20260728-092443-471-274",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5001,
  "message": "动作执行失败: 当前机器人正在执行或挂起任务[TASK_20260728_001]，已拒绝执行重启。如需紧急强制执行请指定 force=True",
  "data": {
    "duration_ms": 8,
    "result": {
      "status": "error",
      "message": "当前机器人正在执行或挂起任务[TASK_20260728_001]，已拒绝执行重启。如需紧急强制执行请指定 force=True"
    }
  }
}
```

---

### 4.6 摄像头插件 (`CameraPlugin`)

#### 1) 图像抓拍 (`action: "capture"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-273",
  "cmd_type": "action",
  "plugin_type": "CameraPlugin",
  "action": "capture",
  "params": { "channel": 1 }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-273",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 450,
    "result": {
      "status": "success",
      "message": "双光热成像云台相机图像抓图指令执行完毕",
      "data": {
        "base64": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ...",
        "image_size_bytes": 104857,
        "channel": 1
      }
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-273",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "图像抓拍失败",
  "data": {
    "duration_ms": 3000,
    "result": {
      "status": "error",
      "message": "ISAPI HTTP 抓图请求返回 401 Unauthorized (Digest 认证失败)"
    }
  }
}
```

#### 2) 调预置位 (`action: "preset"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-274",
  "cmd_type": "action",
  "plugin_type": "CameraPlugin",
  "action": "set_preset",
  "params": { "preset_id": 2 }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-274",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 320,
    "result": {
      "status": "success",
      "message": "云台调度预置点 [ID=2] 请求下发完毕"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-274",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 400,
  "message": "无效预置位",
  "data": {
    "duration_ms": 150,
    "result": {
      "status": "error",
      "message": "相机未配置预置位 ID: 999"
    }
  }
}
```

#### 3) 云台控制 (`action: "ptz"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-275",
  "cmd_type": "action",
  "plugin_type": "CameraPlugin",
  "action": "ptz",
  "params": { "pan": 20.0, "tilt": 0.0, "zoom": 0.0 }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-275",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 180,
    "result": {
      "status": "success",
      "message": "云台运动指令下发完毕 (Pan:20.0, Tilt:0.0, Zoom:0.0)"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-275",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "云台控制失败",
  "data": {
    "duration_ms": 2500,
    "result": {
      "status": "error",
      "message": "相机 PTZ 接口拒绝请求: 硬件到达物理限位点"
    }
  }
}
```

#### 4) 工业测温 (`action: "thermometry"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-276",
  "cmd_type": "action",
  "plugin_type": "CameraPlugin",
  "action": "thermometry",
  "params": {}
}
```
> **说明**：工业测温固定采集热成像红外通道，无须下发 `channel` 参数，底层默认固定为热成像通道 2。
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-276",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 320,
    "result": {
      "status": "success",
      "message": "工业测温实时温度查询完毕",
      "data": {
        "1": {
          "status": "success",
          "max_temp": 45.8,
          "min_temp": 22.3,
          "avg_temp": 31.4,
          "alarm_status": "NORMAL"
        }
      }
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-276",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "测温数据读取失败",
  "data": {
    "duration_ms": 1500,
    "result": {
      "status": "error",
      "message": "热成像测温通道 2 未开启或 ISAPI 测温 XML 解析失败"
    }
  }
}
```

#### 5) 状态查询 (`action: "status"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-277",
  "cmd_type": "action",
  "plugin_type": "CameraPlugin",
  "action": "status",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-277",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 80,
    "result": {
      "status": "success",
      "message": "海康云台相机在线",
      "data": {
        "online": true
      }
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-277",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "相机在线状态异常",
  "data": {
    "duration_ms": 3000,
    "result": {
      "status": "error",
      "message": "相机 IP 地址 (127.0.0.1) Ping 不通或 HTTP 80 端口拒绝连接"
    }
  }
}
```

#### 6) 循环测温 (`action: "cycle"`)

* **开启循环测温下发**:
```json
{
  "msg_id": "20260728-092443-471-278",
  "cmd_type": "action",
  "plugin_type": "CameraPlugin",
  "action": "cycle",
  "params": {
    "action": "start",
    "interval": 5
  }
}
```
* **开启成功回复**:
```json
{
  "msg_id": "20260728-092443-471-278",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 50,
    "result": {
      "status": "success",
      "message": "已成功启动双光热成像相机循环测温 (采样间隔: 5s)"
    }
  }
}
```
* **停止循环测温下发**:
```json
{
  "msg_id": "20260728-092443-471-279",
  "cmd_type": "action",
  "plugin_type": "CameraPlugin",
  "action": "cycle",
  "params": {
    "action": "stop"
  }
}
```
* **停止成功回复**:
```json
{
  "msg_id": "20260728-092443-471-279",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 30,
    "result": {
      "status": "success",
      "message": "已停止双光热成像相机循环测温"
    }
  }
}
```

* **`/status/up` 主题中 `CameraPlugin` 循环测温实时数据载荷结构**:
当开启 `CameraPlugin` 循环测温且成功从传感器/热成像获取真实数据时，`TelemetryManager` 自动将其动态拼入 `/status/up` 状态数据流：
```json
{
  "robot_status": {
    "plugins": {
      "NavPlugin": { "mode": "AUTO" },
      "CameraPlugin": [
        {
          "metric_name": "THERMAL",
          "max_temp": 45.8,
          "min_temp": 22.3,
          "avg_temp": 31.4
        }
      ]
    }
  }
}
```

#### 7) 下发告警配置 (`action: "set_config"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-280",
  "cmd_type": "action",
  "plugin_type": "CameraPlugin",
  "action": "set_config",
  "params": {
    "config": [
      {
        "metric_name": "THERMAL",
        "unit": "℃",
        "thresholds": {
          "warning": { "operator": "between", "value": [70.0, 90.0], "message": "设备表面温度偏高预警" },
          "error": { "operator": "between", "value": [90.0, 110.0], "message": "设备表面高温严重告警！" },
          "fatal": { "operator": "gte", "value": 110.0, "message": "设备温度极度危险，存在起火隐患！", "auto_action": "abort" }
        }
      }
    ]
  }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-280",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "动作执行成功",
  "data": {
    "duration_ms": 20,
    "result": {
      "status": "success",
      "message": "成功保存告警配置至 /home/zonwey/robot_project/data/plugins/CameraPlugin_alarm.json",
      "data": [
        {
          "metric_name": "THERMAL",
          "unit": "℃",
          "thresholds": {
            "warning": { "operator": "between", "value": [70.0, 90.0], "message": "设备表面温度偏高预警" },
            "error": { "operator": "between", "value": [90.0, 110.0], "message": "设备表面高温严重告警！" },
            "fatal": { "operator": "gte", "value": 110.0, "message": "设备温度极度危险，存在起火隐患！", "auto_action": "abort" }
          }
        }
      ]
    }
  }
}
```

#### 8) 查询告警配置 (`action: "get_config"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-281",
  "cmd_type": "action",
  "plugin_type": "CameraPlugin",
  "action": "get_config",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-281",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "动作执行成功",
  "data": {
    "duration_ms": 15,
    "result": {
      "status": "success",
      "message": "成功获取本地告警配置",
      "data": [
        {
          "metric_name": "THERMAL",
          "unit": "℃",
          "thresholds": {
            "warning": { "operator": "between", "value": [70.0, 90.0], "message": "设备表面温度偏高预警" },
            "error": { "operator": "between", "value": [90.0, 110.0], "message": "设备表面高温严重告警！" },
            "fatal": { "operator": "gte", "value": 110.0, "message": "设备温度极度危险，存在起火隐患！", "auto_action": "abort" }
          }
        }
      ]
    }
  }
}
```

---

### 4.7 气体插件 (`GasPlugin`)

#### 1) 气体采集 (`action: "acquire"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-278",
  "cmd_type": "action",
  "plugin_type": "GasPlugin",
  "action": "acquire",
  "params": { "wait_time": 30.0, "flow_level": 10 }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-278",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 30800,
    "result": {
      "status": "success",
      "message": "气体采样采集完毕（已完成 30s 稳定等待与关泵动作）",
      "data": [
        { "sensor_id": 1, "channel_code": 1, "name": "CO", "value": 12.5, "unit": "PPM" },
        { "sensor_id": 1, "channel_code": 2, "name": "H2S", "value": 0.0, "unit": "PPM" },
        { "sensor_id": 1, "channel_code": 3, "name": "O2", "value": 20.9, "unit": "%VOL" },
        { "sensor_id": 1, "channel_code": 4, "name": "EX", "value": 0.0, "unit": "%LEL" },
        { "sensor_id": 1, "channel_code": 5, "name": "CO2", "value": 450.0, "unit": "PPM" },
        { "sensor_id": 1, "channel_code": 6, "name": "NOX", "value": 0.1, "unit": "PPM" },
        { "sensor_id": 2, "channel_code": 1, "name": "SF6", "value": 0.0, "unit": "PPM" }
      ]
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-278",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "气体采集失败",
  "data": {
    "duration_ms": 5200,
    "result": {
      "status": "error",
      "message": "气体传感器 RS485 串口 (/dev/ttyUSB0) 读写超时 CRC 校验错误"
    }
  }
}
```

#### 2) 即时读取 (`action: "query"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-279",
  "cmd_type": "action",
  "plugin_type": "GasPlugin",
  "action": "query",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-279",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 120,
    "result": {
      "status": "success",
      "message": "即时读取气体浓度成功",
      "data": [
        { "sensor_id": 1, "channel_code": 1, "name": "CO", "value": 12.5, "unit": "PPM" },
        { "sensor_id": 1, "channel_code": 2, "name": "H2S", "value": 0.0, "unit": "PPM" },
        { "sensor_id": 1, "channel_code": 3, "name": "O2", "value": 20.9, "unit": "%VOL" },
        { "sensor_id": 1, "channel_code": 4, "name": "EX", "value": 0.0, "unit": "%LEL" },
        { "sensor_id": 1, "channel_code": 5, "name": "CO2", "value": 450.0, "unit": "PPM" },
        { "sensor_id": 1, "channel_code": 6, "name": "NOX", "value": 0.1, "unit": "PPM" },
        { "sensor_id": 2, "channel_code": 1, "name": "SF6", "value": 0.0, "unit": "PPM" }
      ]
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-279",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "即时读取失败",
  "data": {
    "duration_ms": 500,
    "result": {
      "status": "error",
      "message": "传感器未初始化或 Modbus 响应丢失"
    }
  }
}
```

#### 3) 流量调节 (`action: "level"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-280",
  "cmd_type": "action",
  "plugin_type": "GasPlugin",
  "action": "level",
  "params": { "flow_level": 8 }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-280",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 150,
    "result": {
      "status": "success",
      "message": "设置气泵流量等级 [8] 成功"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-280",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 400,
  "message": "流量调节参数非法",
  "data": {
    "duration_ms": 20,
    "result": {
      "status": "error",
      "message": "flow_level 必须在 1~10 范围之内"
    }
  }
}
```

#### 4) 开启气泵 (`action: "start"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-281",
  "cmd_type": "action",
  "plugin_type": "GasPlugin",
  "action": "start_nav",
  "params": { "flow_level": 10 }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-281",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 180,
    "result": {
      "status": "success",
      "message": "开启气泵 (等级 10) 成功"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-281",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "开启气泵失败",
  "data": {
    "duration_ms": 500,
    "result": {
      "status": "error",
      "message": " Modbus 指令写入失败: 气泵硬件故障或过载保护"
    }
  }
}
```

#### 5) 关闭气泵 (`action: "stop"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-282",
  "cmd_type": "action",
  "plugin_type": "GasPlugin",
  "action": "stop",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-282",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 110,
    "result": {
      "status": "success",
      "message": "关闭气泵成功"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-282",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "关闭气泵失败",
  "data": {
    "duration_ms": 300,
    "result": {
      "status": "error",
      "message": "串口无响应，无法下发关泵控制指令"
    }
  }
}
```

#### 6) 通道查询 (`action: "channel"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-283",
  "cmd_type": "action",
  "plugin_type": "GasPlugin",
  "action": "channel",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-283",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 250,
    "result": {
      "status": "success",
      "message": "读取通道配置成功",
      "data": [
        {"sensor_id":1,"channel_code":1,"name":"CO","range":1000,"magnification":1,"unit":"PPM","concentration":0.5,"alarm_point_level1":50,"alarm_point_level2":100,"alarm_point_level3":200,"alarm_status":0,"raw_ad_value":12000},
        {"sensor_id":1,"channel_code":2,"name":"H2S","range":100,"magnification":1,"unit":"PPM","concentration":0.5,"alarm_point_level1":10,"alarm_point_level2":20,"alarm_point_level3":50,"alarm_status":0,"raw_ad_value":11000},
        {"sensor_id":1,"channel_code":3,"name":"O2","range":30,"magnification":2,"unit":"%VOL","concentration":20.9,"alarm_point_level1":19.5,"alarm_point_level2":23.5,"alarm_point_level3":25,"alarm_status":1,"raw_ad_value":20900},
        {"sensor_id":1,"channel_code":4,"name":"EX","range":100,"magnification":1,"unit":"%LEL","concentration":0,"alarm_point_level1":25,"alarm_point_level2":50,"alarm_point_level3":75,"alarm_status":0,"raw_ad_value":10000},
        {"sensor_id":1,"channel_code":5,"name":"CO2","range":5000,"magnification":1,"unit":"PPM","concentration":400,"alarm_point_level1":1000,"alarm_point_level2":2000,"alarm_point_level3":3000,"alarm_status":0,"raw_ad_value":14000},
        {"sensor_id":1,"channel_code":6,"name":"NOX","range":100,"magnification":1,"unit":"PPM","concentration":0,"alarm_point_level1":20,"alarm_point_level2":40,"alarm_point_level3":60,"alarm_status":0,"raw_ad_value":10500},
        {"sensor_id":2,"channel_code":1,"name":"SF6","range":1000,"magnification":1,"unit":"PPM","concentration":0,"alarm_point_level1":50,"alarm_point_level2":100,"alarm_point_level3":500,"alarm_status":0,"raw_ad_value":10000}
      ]
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-283",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "通道查询失败",
  "data": {
    "duration_ms": 800,
    "result": {
      "status": "error",
      "message": "读取 80-byte 寄存器出现帧头校验失败"
    }
  }
}
```

#### 7) 信息查询 (`action: "base"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-284",
  "cmd_type": "action",
  "plugin_type": "GasPlugin",
  "action": "base",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-284",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 101,
    "result": {
      "status": "success",
      "message": "获取基本信息完毕",
      "data": [
        {
          "channel_count": 6,
          "device_uid": "1234567890ABCDEF12345678",
          "manufacturer": "M-B6 Gas Sensor",
          "hardware_version": "HW_1.0",
          "software_version": "SW_1.0",
          "build_time": "1987-01-30 11:39:17",
          "sensor_id": 1
        },
        {
          "channel_count": 1,
          "device_uid": "1234567890ABCDEF12345678",
          "manufacturer": "M-B6 Gas Sensor",
          "hardware_version": "HW_1.0",
          "software_version": "SW_1.0",
          "build_time": "1987-01-30 11:39:17",
          "sensor_id": 2
        }
      ]
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-284",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "信息查询失败",
  "data": {
    "duration_ms": 600,
    "result": {
      "status": "error",
      "message": "模组响应超时，无法读取设备 UID"
    }
  }
}
```

#### 8) 通道校准 (`action: "calibrate"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-285",
  "cmd_type": "action",
  "plugin_type": "GasPlugin",
  "action": "calibrate",
  "params": { "sensor_id": 1, "channel_code": 1, "level": 1, "calibration_data": 100 }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-285",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 450,
    "result": {
      "status": "success",
      "message": "通道校准成功",
      "data": {
        "sensor_id": 1,
        "channel_code": 1,
        "success": true
      }
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-285",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "通道校准失败",
  "data": {
    "duration_ms": 500,
    "result": {
      "status": "error",
      "message": "标定数据写入 Flash 被硬件锁保护拒绝"
    }
  }
}
```

#### 9) 恢复出厂 (`action: "reset"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-286",
  "cmd_type": "action",
  "plugin_type": "GasPlugin",
  "action": "reset",
  "params": { "channel_code": 255 }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-286",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 680,
    "result": {
      "status": "success",
      "message": "恢复出厂校准成功"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-286",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "恢复出厂失败",
  "data": {
    "duration_ms": 700,
    "result": {
      "status": "error",
      "message": "复位出厂参数指令下发后模组未确认 ACK"
    }
  }
}
```

#### 10) 状态查询 (`action: "status"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-287",
  "cmd_type": "action",
  "plugin_type": "GasPlugin",
  "action": "status",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-287",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 60,
    "result": {
      "status": "success",
      "message": "气体插件运行正常",
      "data": {
        "online": true
      }
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-287",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "气体插件串口异常",
  "data": {
    "duration_ms": 2000,
    "result": {
      "status": "error",
      "message": "无法打开串口 /dev/ttyUSB0 (Permission denied 或 设备断开)"
    }
  }
}
#### 11) 循环采集 (`action: "cycle"`)
* **下发 (启动)**:
```json
{
  "msg_id": "20260728-092443-471-301",
  "cmd_type": "action",
  "plugin_type": "GasPlugin",
  "plugin_action": "cycle",
  "params": {
    "plugin_action": "start_nav",
    "interval": 5
  }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-301",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 15,
    "result": {
      "status": "success",
      "message": "已开启气泵并启动气体循环采集 (上报间隔: 5s)"
    }
  }
}
```
* **下发 (停止)**:
```json
{
  "msg_id": "20260728-092443-471-302",
  "cmd_type": "action",
  "plugin_type": "GasPlugin",
  "action": "cycle",
  "params": {
    "action": "stop"
  }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-302",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 10,
```

#### 12) 下发告警配置 (`action: "set_config"`)
* **下发**:
```json
{
  "msg_id": "20260731-155000-001-100",
  "cmd_type": "action",
  "plugin_type": "GasPlugin",
  "action": "set_config",
  "params": {
    "config": [
      {
        "gasType": "CO2",
        "unit": "PPM",
        "thresholds": {
          "info": { "operator": "between", "value": [400, 700], "message": "CO2浓度轻度偏高提示" },
          "warning": { "operator": "between", "value": [700, 1000], "message": "CO2浓度偏高预警" },
          "error": { "operator": "between", "value": [1000, 2000], "message": "CO2浓度超标" },
          "fatal": { "operator": "gte", "value": 2000, "message": "CO2严重超标，窒息危险！" }
        }
      }
    ]
  }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260731-155000-001-100",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 15,
    "result": {
      "status": "success",
      "message": "成功保存告警配置至 data/plugins/GasPlugin_alarm.json"
    }
  }
}
```

#### 13) 查询告警配置 (`action: "get_config"`)
* **下发**:
```json
{
  "msg_id": "20260731-155000-001-101",
  "cmd_type": "action",
  "plugin_type": "GasPlugin",
  "action": "get_config",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260731-155000-001-101",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 5,
    "result": {
      "status": "success",
      "message": "获取告警阈值配置成功",
      "data": ["json文件"]
    }
  }
}
```

---

### 4.8 局放插件 (`GdpdPlugin`)

#### 1) 局放检测 (`action: "monitor"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-288",
  "cmd_type": "action",
  "plugin_type": "GdpdPlugin",
  "action": "monitor",
  "params": { "sample_count": 10, "sample_interval": 1.0 }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-288",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 10200,
    "result": {
      "status": "success",
      "message": "局放全闭环采集与数据统计成功",
      "data": {
        "peak": 24.5,
        "mean": 18.2,
        "frequency": 142
      }
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-288",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "局放检测全闭环流程异常",
  "data": {
    "duration_ms": 3000,
    "result": {
      "status": "error",
      "message": "采样过程中 TEV 设备串口中断，有效采样次数不足"
    }
  }
}
```

#### 2) 启动采集 (`action: "start"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-289",
  "cmd_type": "action",
  "plugin_type": "GdpdPlugin",
  "action": "start",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-289",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 100,
    "result": {
      "status": "success",
      "message": "启动局放采集成功"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-289",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "启动局放采集失败",
  "data": {
    "duration_ms": 500,
    "result": {
      "status": "error",
      "message": "TEV 硬件指令响应错误: DEVICE_NOT_READY"
    }
  }
}
```

#### 3) 读取局放 (`action: "acquire"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-290",
  "cmd_type": "action",
  "plugin_type": "GdpdPlugin",
  "action": "acquire",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-290",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 150,
    "result": {
      "status": "success",
      "message": "读取局放数据成功",
      "data": {
        "peak": 23.1,
        "mean": 17.5,
        "frequency": 15
      }
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-290",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "读取局放数据失败",
  "data": {
    "duration_ms": 1000,
    "result": {
      "status": "error",
      "message": "地电波检测仪数据解析异常 (Packet CRC Fail)"
    }
  }
}
```

#### 4) 停止采集 (`action: "stop"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-291",
  "cmd_type": "action",
  "plugin_type": "GdpdPlugin",
  "action": "stop",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-291",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 90,
    "result": {
      "status": "success",
      "message": "停止局放采集成功"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-291",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "停止局放采集失败",
  "data": {
    "duration_ms": 300,
    "result": {
      "status": "error",
      "message": "停止采集指令下发超时"
    }
  }
}
```

#### 5) 数据清空 (`action: "clear"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-292",
  "cmd_type": "action",
  "plugin_type": "GdpdPlugin",
  "action": "clear",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-292",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 70,
    "result": {
      "status": "success",
      "message": "清空局放数据成功"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-292",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "数据清空失败",
  "data": {
    "duration_ms": 200,
    "result": {
      "status": "error",
      "message": "设备无响应，未能清空局放历史缓存"
    }
  }
}
```

#### 6) 状态查询 (`action: "status"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-293",
  "cmd_type": "action",
  "plugin_type": "GdpdPlugin",
  "action": "status",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-293",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 60,
    "result": {
      "status": "success",
      "message": "局放设备连接正常",
      "data": {
        "online": true
      }
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-293",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "局放设备通信失败",
  "data": {
    "duration_ms": 2000,
    "result": {
      "status": "error",
      "message": "串口/TCP 端口连接断开，未侦听到 TEV 响应"
    }
  }
}
```

#### 7) 下发告警配置 (`action: "set_config"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-294",
  "cmd_type": "action",
  "plugin_type": "GdpdPlugin",
  "action": "set_config",
  "params": {
    "config": [
      {
        "metric_name": "PEAK",
        "unit": "dBm",
        "thresholds": {
          "warning": { "operator": "gte", "value": 20.0, "message": "局放峰值异常偏高预警" },
          "error": { "operator": "gte", "value": 35.0, "message": "局放峰值严重超标，疑似存在严重局部放电隐患！" }
        }
      }
    ]
  }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-294",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "动作执行成功",
  "data": {
    "duration_ms": 20,
    "result": {
      "status": "success",
      "message": "成功保存局放告警配置至 /home/zonwey/robot_project/data/plugins/GdpdPlugin_alarm.json",
      "data": [
        {
          "metric_name": "PEAK",
          "unit": "dBm",
          "thresholds": {
            "warning": { "operator": "gte", "value": 20.0, "message": "局放峰值异常偏高预警" },
            "error": { "operator": "gte", "value": 35.0, "message": "局放峰值严重超标，疑似存在严重局部放电隐患！" }
          }
        }
      ]
    }
  }
}
```

#### 8) 查询告警配置 (`action: "get_config"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-295",
  "cmd_type": "action",
  "plugin_type": "GdpdPlugin",
  "action": "get_config",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-295",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "动作执行成功",
  "data": {
    "duration_ms": 15,
    "result": {
      "status": "success",
      "message": "成功获取局放告警配置",
      "data": [
        {
          "metric_name": "PEAK",
          "unit": "dBm",
          "thresholds": {
            "warning": { "operator": "gte", "value": 20.0, "message": "局放峰值异常偏高预警" },
            "error": { "operator": "gte", "value": 35.0, "message": "局放峰值严重超标，疑似存在严重局部放电隐患！" }
          }
        }
      ]
    }
  }
}
```

---

### 4.9 LoRa 插件 (`LoraPlugin`)

#### 1) 状态查询 (`action: "status"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-294",
  "cmd_type": "action",
  "plugin_type": "LoraPlugin",
  "action": "status",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-294",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 40,
    "result": {
      "status": "success",
      "message": "LoRa TCP 网关连接正常",
      "data": {
        "online": true
      }
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-294",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "LoRa 状态异常",
  "data": {
    "duration_ms": 1000,
    "result": {
      "status": "error",
      "message": "LoRa TCP 网关链路超时，无心跳包(0x50)捕获"
    }
  }
}
```

---

### 4.10 机械臂插件 (`ArmPlugin`)

#### 1) 姿态移动 (`action: "goto"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-295",
  "cmd_type": "action",
  "plugin_type": "ArmPlugin",
  "action": "goto",
  "params": { "point": 0 }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-295",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 3200,
    "result": {
      "status": "success",
      "message": "机械臂 goto 动作执行成功"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-295",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "机械臂移动失败",
  "data": {
    "duration_ms": 5000,
    "result": {
      "status": "error",
      "message": "机械臂 TCP 运动超时，目标点位超出关节角极值限位"
    }
  }
}
```

#### 2) 暂停动作 (`action: "pause"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-296",
  "cmd_type": "action",
  "plugin_type": "ArmPlugin",
  "action": "pause",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-296",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 180,
    "result": {
      "status": "success",
      "message": "机械臂 pause 动作执行成功"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-296",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "机械臂暂停失败",
  "data": {
    "duration_ms": 1500,
    "result": {
      "status": "error",
      "message": "TCP 连接异常断开，暂停命令无法透传至控制器"
    }
  }
}
```

#### 3) 复位归位 (`action: "goback"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-297",
  "cmd_type": "action",
  "plugin_type": "ArmPlugin",
  "action": "goback",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-297",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 4100,
    "result": {
      "status": "success",
      "message": "机械臂 goback 动作执行成功"
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-297",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "机械臂复位失败",
  "data": {
    "duration_ms": 6000,
    "result": {
      "status": "error",
      "message": "机械臂复位过程检测到碰撞干涉告警"
    }
  }
}
```

#### 4) 状态查询 (`action: "status"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-298",
  "cmd_type": "action",
  "plugin_type": "ArmPlugin",
  "action": "status",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-298",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 70,
    "result": {
      "status": "success",
      "message": "机械臂控制器在线",
      "data": {
        "online": true
      }
    }
  }
}
```
* **失败回复**:
```json
{
  "msg_id": "20260728-092443-471-298",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,
  "message": "机械臂状态查询失败",
  "data": {
    "duration_ms": 2500,
    "result": {
      "status": "error",
      "message": "机械臂服务器 (127.0.0.1:8080) TCP 连接拒绝"
    }
  }
}
```

### 4.11 声纹插件 (`AcousticPlugin`)

#### 1) 循环检测 (`action: "cycle"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-401",
  "cmd_type": "action",
  "plugin_type": "AcousticPlugin",
  "action": "cycle",
  "params": {
    "action": "start"
  }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-401",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 15,
    "result": {
      "status": "success",
      "message": "循环检测已开启"
    }
  }
}
```

#### 2) 查询声压 (`action: "query_spl"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-402",
  "cmd_type": "action",
  "plugin_type": "AcousticPlugin",
  "action": "query_spl",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-402",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 20,
    "result": {
      "status": "success",
      "data": { "spl": 55.4 }
    }
  }
}
```

#### 3) 查询设备状态 (`action: "get_status"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-403",
  "cmd_type": "action",
  "plugin_type": "AcousticPlugin",
  "action": "get_status",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-403",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 25,
    "result": {
      "status": "success",
      "data": {
        "app": "C168",
        "cam_height": 1080,
        "cam_width": 1920,
        "complie_time": "2024-11-25 11:18:01",
        "cpu_temp": 44.384,
        "device_no": "200001",
        "fs": 200000,
        "gpu_temp": 44.384,
        "httpflv_port": 5000,
        "npu_temp": 0,
        "rtmp_port": 1935,
        "rtsp_port": 554,
        "sn_fpga": "",
        "time": "2024-11-25 11:20:27.806",
        "version": "1.0.6",
        "version_fpga": "",
        "rms_enable": false
      }
    }
  }
}
```

#### 4) 使能通道 (`action: "enable_channel"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-404",
  "cmd_type": "action",
  "plugin_type": "AcousticPlugin",
  "action": "enable_channel",
  "params": {
    "enable": true
  }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-404",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 15,
    "result": {
      "status": "success",
      "data": {
        "ret": 0,
        "msg": "success"
      }
    }
  }
}
```

#### 5) 查询 PRPD 深度诊断 (`action: "query_fault"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-405",
  "cmd_type": "action",
  "plugin_type": "AcousticPlugin",
  "action": "query_fault",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-405",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 25,
    "result": {
      "status": "success",
      "data": {
        "discharge_acceptance": 0.85,
        "discharge_malfunction_grade": 2,
        "discharge_type": 1
      }
    }
  }
}
```

#### 6) 查询连通状态 (`action: "status"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-406",
  "cmd_type": "action",
  "plugin_type": "AcousticPlugin",
  "action": "status",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-406",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 10,
    "result": {
      "status": "success",
      "data": {
        "online": true
      }
    }
  }
}
```

#### 7) 重启设备 (`action: "reboot"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-407",
  "cmd_type": "action",
  "plugin_type": "AcousticPlugin",
  "action": "reboot",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-407",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 40,
    "result": {
      "status": "success",
      "message": "重启指令已发送"
    }
  }
}
```

#### 8) 设置告警配置 (`action: "set_config"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-408",
  "cmd_type": "action",
  "plugin_type": "AcousticPlugin",
  "action": "set_config",
  "params": {
    "config": [
      {
        "type": "SPL",
        "unit": "dB",
        "thresholds": {
          "info": {
            "operator": "between",
            "value": [60.0, 75.0],
            "message": "检测到周围环境出现轻微异常声响"
          },
          "warning": {
            "operator": "between",
            "value": [75.0, 85.0],
            "message": "环境声压偏大，请注意"
          },
          "error": {
            "operator": "between",
            "value": [85.0, 100.0],
            "message": "环境声压严重超标，可能存在设备异响或放电"
          },
          "fatal": {
            "operator": "gte",
            "value": 100.0,
            "message": "出现极高声压，疑似发生严重放电或机械断裂事故！"
          }
        }
      }
    ]
  }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-408",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 18,
    "result": {
      "status": "success",
      "message": "声纹告警规则更新成功"
    }
  }
}
```

#### 9) 查询告警配置 (`action: "get_config"`)
* **下发**:
```json
{
  "msg_id": "20260728-092443-471-409",
  "cmd_type": "action",
  "plugin_type": "AcousticPlugin",
  "action": "get_config",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260728-092443-471-409",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 12,
    "result": {
      "status": "success",
      "data": [
        {
          "type": "SPL",
          "unit": "dB",
          "thresholds": {
            "info": {
              "operator": "between",
              "value": [60.0, 75.0],
              "message": "检测到周围环境出现轻微异常声响"
            },
            "warning": {
              "operator": "between",
              "value": [75.0, 85.0],
              "message": "环境声压偏大，请注意"
            },
            "error": {
              "operator": "between",
              "value": [85.0, 100.0],
              "message": "环境声压严重超标，可能存在设备异响或放电"
            },
            "fatal": {
              "operator": "gte",
              "value": 100.0,
              "message": "出现极高声压，疑似发生严重放电或机械断裂事故！"
            }
          }
        }
      ]
    }
  }
}
```

---

### 4.12 录像插件 (`RecordPlugin`)

专职负责多路 RTSP 视频流（如可见光通道 `vis`、热成像通道 `thm`、机械臂相机 `arm` 等）的 fMP4 分片切片录像存储、无干扰网络门控自适应挂起、SeaweedFS Filer 原生分布式对象存储对接，以及文件校验秒传与本地“上云即焚”安全清理。

#### 1) 开启录像 (`action: "start_record"`)
启动多路视频流 fMP4 切片录制。支持指定录像通道（默认 `"all"` 录制所有已配置视频流，或传入通道别名如 `"vis"`、`"thm"`），支持按需自定义分片时长和关联任务 ID。
* **下发**:
```json
{
  "msg_id": "20260914-165000-471-501",
  "cmd_type": "action",
  "plugin_type": "RecordPlugin",
  "action": "start_record",
  "params": {
    "channel": "all",
    "segment_duration": 60,
    "task_id": "TASK_OFFLINE_F3_01"
  }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260914-165000-471-501",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 32,
    "result": {
      "status": "success",
      "message": "成功启动 2 路 fMP4 切片录像 (通道: ['vis', 'thm'])",
      "data": {
        "recording_id": "REC_TASK_OFFLINE_F3_01_1726131000",
        "task_id": "TASK_OFFLINE_F3_01",
        "channels": ["vis", "thm"],
        "segment_duration": 60,
        "save_dir": "/home/zonwey/robot_project/data/videos/TASK_OFFLINE_F3_01"
      }
    }
  }
}
```

#### 2) 停止录像 (`action: "stop_record"`)
安全停止当前正在运行的所有录像管线并完成尾部分片原子封包归档。无需传递任何参数，默认直接停止全部通道。
* **下发**:
```json
{
  "msg_id": "20260914-165000-471-502",
  "cmd_type": "action",
  "plugin_type": "RecordPlugin",
  "action": "stop_record",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260914-165000-471-502",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 45,
    "result": {
      "status": "success",
      "message": "已安全停止并归档 2 路录像",
      "data": {
        "stopped_channels": ["vis", "thm"],
        "remaining_active": []
      }
    }
  }
}
```

#### 3) 查询录像与同步综合状态 (`action: "record_status"`)
一站式查询录像管线当前运行状态与 SeaweedFS 视频同步队列积压情况。
* **下发**:
```json
{
  "msg_id": "20260914-165000-471-503",
  "cmd_type": "action",
  "plugin_type": "RecordPlugin",
  "action": "record_status",
  "params": {}
}
```
* **成功回复**:
```json
{
  "msg_id": "20260914-165000-471-503",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 10,
    "result": {
      "status": "success",
      "message": "获取录像与同步综合状态成功",
      "data": {
        "recording": {
          "is_recording": true,
          "active_channels": ["vis", "thm"],
          "current_task_id": "TASK_OFFLINE_F3_01",
          "elapsed_sec": 128.5
        },
        "sync": {
          "enabled": true,
          "is_sync_allowed": true,
          "paused_by_event": false,
          "filer_url": "http://192.168.3.100:8888",
          "delete_after_sync": true,
          "pending_count": 0,
          "synced_count": 4,
          "failed_count": 0,
          "total_count": 4
        }
      }
    }
  }
}
```

#### 4) 视频同步控制 (`action: "sync_control"`)
手动挂起或恢复 SeaweedFS 视频后台同步服务。适用于现场弱网、紧急远程遥控高清图传排障等需要独占无线网络带宽的运维场景。
* **下发 (挂起同步)**:
```json
{
  "msg_id": "20260914-165000-471-504",
  "cmd_type": "action",
  "plugin_type": "RecordPlugin",
  "action": "sync_control",
  "params": {
    "control": "pause"
  }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260914-165000-471-504",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 5,
    "result": {
      "status": "success",
      "message": "已手动挂起后台视频同步"
    }
  }
}
```
* **下发 (恢复同步)**:
```json
{
  "msg_id": "20260914-165000-471-505",
  "cmd_type": "action",
  "plugin_type": "RecordPlugin",
  "action": "sync_control",
  "params": {
    "control": "resume"
  }
}
```
* **成功回复**:
```json
{
  "msg_id": "20260914-165000-471-505",
  "robot_id": "robot888",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务完成",
  "data": {
    "duration_ms": 5,
    "result": {
      "status": "success",
      "message": "已手动恢复后台视频同步"
    }
  }
}
```

---

## 5. 业务宏组件 (Macro Components) 指令规范

与原子级能力插件 (Plugin) 不同，系统中的宏组件 (Component) 是**无状态、单任务全包揽**的跨插件业务流，例如：自动穿行门控系统、进出充电站系统等。

**重要说明**：调用 `component` 时，**无需指定 `action` 字段**，直接通过 `component_type` 和 `params` 即可触发其内部唯一的 `execute()` 执行流。

### 5.1 自动穿门组件 (`DoorComponent`)
组件执行逻辑：导航至门外 -> 开启并驻留门状态 -> 穿行至门内 -> 关门。内置防夹车打断(abort)与现场重置能力。

#### 📥 下发控制报文 (`cmd/down`)
```json
{
  "msg_id": "20260803-100001-000-001",
  "timestamp": 1722300000000,
  "cmd_type": "action",
  "component_type": "DoorComponent",
  "params": {
    "entry_point": 105,
    "exit_point": 106,
    "door_ips": ["192.168.1.100", "192.168.1.101"]
  }
}
```
*(注：这里没有任何 `"plugin_action": "pass"` 这种设定，因为组件本身就代表了一个特定的完整业务！)*

#### 📤 执行结果回复 (`ACK_EXECUTE` - 成功示例)
```json
{
  "msg_id": "20260803-100001-000-001",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "动作执行成功",
  "data": {
    "duration_ms": 15000,
    "result": {
      "status": "success"
    }
  }
}
```

### 5.2 充电站进出组件 (`StationComponent`)
封装了完整的充电站对接动作。正向任务仅需下发出站操作，返航进站逻辑会在系统倒推时由 `get_reverse_params` 自动生成。

#### 📥 下发控制报文 (`cmd/down`)
```json
{
  "msg_id": "20260803-100001-000-002",
  "timestamp": 1722300000000,
  "cmd_type": "action",
  "component_type": "StationComponent",
  "params": {
    "inner_point": 201,
    "outer_point": 200,
    "ips": ["192.168.2.100"]
  }
}
```

### 5.3 智能电梯组件 (`ElevatorComponent`)
封装了完整的乘梯上下楼业务流（含内外呼梯与进出轿厢导航）。返航时会由系统自动倒推反向乘坐。

#### 📥 下发控制报文 (`cmd/down`)
```json
{
  "msg_id": "20260803-100001-000-003",
  "timestamp": 1722300000000,
  "cmd_type": "action",
  "component_type": "ElevatorComponent",
  "params": {
    "addr": "18191",
    "start_floor": 1,
    "start_point": 10,
    "start_ele_point": 11,
    "target_floor": 3,
    "target_point": 12,
    "target_ele_point": 13
  }
}
```


---

## 附录：核心协议规范补充

### 4. 任务全生命周期完整交互报文案例 (Task Message Lifecycles)

为了彻底消除平台与网关在报文交互上的歧义，以下整理了最核心的四大生命周期（完整执行、完整暂停、完整恢复、完整取消）的“一问一答”时间轴报文规范：

#### 场景一：正常任务执行全生命周期 (Normal Execution)
1. **平台下发开始任务**
```json
{
  "msg_id": "RUN_001",
  "timestamp": 1790159900000,
  "cmd_type": "task",
  "action": "run",
  "task_id": "TASK_12345"
}
```
2. **网关瞬间回复已收到指令 (ACK_RECEIVE)**
（表示网关已成功解析指令并放入调度队列，平台前端可据此关闭 loading 弹窗，将状态切换为“正在启动”）
```json
{
  "msg_id": "RUN_001",
  "timestamp": 1790159900050,
  "robot_id": "P2026083101",
  "reply_type": "ACK_RECEIVE",
  "code": 0,
  "message": "任务指令已接收，准备进入队列执行"
}
```
3. **网关刚开始执行第一步时 (ACK_PROGRESS)**
```json
{
  "msg_id": "RUN_001",
  "timestamp": 1790159900100,
  "robot_id": "P2026083101",
  "reply_type": "ACK_PROGRESS",
  "code": 0,
  "message": "开始执行步骤 1/5 [NavPlugin.move_to]", 
  "data": {
    "task_id": "TASK_12345",
    "task_name": "日常巡检任务",
    "step": 1,
    "total_steps": 5,
    "plugin_type": "NavPlugin",
    "plugin_action": "move_to",          // 【解耦】专指子任务插件动作
    "task_status": "RUNNING",            // 大任务状态：全大写
    "step_status": "started",            // 步骤状态：转圈加载中 (由 running 修正为 started)
    "duration_ms": 0
  }
}
```
3. **第一步执行完毕时 (ACK_PROGRESS)**
```json
{
  "msg_id": "RUN_001",
  "timestamp": 1790159915500,
  "robot_id": "P2026083101",
  "reply_type": "ACK_PROGRESS",
  "code": 0,
  "message": "步骤 1/5 [NavPlugin.move_to] 执行完成", 
  "data": {
    "task_id": "TASK_12345",
    "task_name": "日常巡检任务",
    "step": 1,
    "total_steps": 5,
    "plugin_type": "NavPlugin",
    "plugin_action": "move_to",
    "task_status": "RUNNING",            
    "step_status": "success",            // 步骤状态：绿勾完成
    "duration_ms": 15400
  }
}
```
*(...中间步骤循环重复上述 running -> success 的进度推送...)*

4. **任务整体大满贯结束 (ACK_EXECUTE)**
```json
{
  "msg_id": "RUN_001",
  "timestamp": 1790160020500,
  "robot_id": "P2026083101",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "命令 [RUN_001] 处理圆满完成", 
  "data": {
    "task_id": "TASK_12345",
    "task_name": "日常巡检任务",
    "task_status": "FINISH",             // 大任务状态：整体圆满完成
    "total_steps": 5,
    "executed_steps": 5,
    "duration_ms": 120500
  }
}
```

#### 场景二 & 三：完整暂停与恢复闭环 (Pause & Resume Lifecycle)
在 `RUN_001` 任务还在 `task_status: RUNNING` 的时候，平台突然决定暂停它。
1. **平台下发暂停指令 (必须是新的 msg_id)**
```json
{
  "msg_id": "PAUSE_002",
  "timestamp": 1790159950000,
  "cmd_type": "task",
  "action": "pause"                 // 【解耦】专指顶层大任务控制指令
}
```
2. **网关瞬间回复已收到指令 (ACK_RECEIVE)**
```json
{
  "msg_id": "PAUSE_002",
  "timestamp": 1790159950050,
  "robot_id": "P2026083101",
  "reply_type": "ACK_RECEIVE",
  "code": 0,
  "message": "接收到暂停请求"
}
```
3. **网关成功挂起后回复指令完成 (ACK_EXECUTE)**
```json
{
  "msg_id": "PAUSE_002",
  "timestamp": 1790159950100,
  "robot_id": "P2026083101",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "data": {
    "task_id": "TASK_12345",
    "task_name": "日常巡检任务",
    "task_action": "pause",
    "task_status": "PAUSED",
    "duration_ms": 50
  } 
}
```
4. **网关主动向原任务发双闭环更新 (ACK_EXECUTE) - 非常关键！**
```json
{
  "msg_id": "RUN_001",                   // 注意！这里是原任务的 ID！
  "timestamp": 1790159950150,
  "robot_id": "P2026083101",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "message": "任务 [日常巡检任务] 已挂起暂停", 
  "data": {
    "task_id": "TASK_12345",
    "task_status": "PAUSED",             // 平台 UI 收到这个，瞬间把外层任务卡片置灰暂停
    "duration_ms": 1500
  }
}
```
5. **平台下发恢复指令** (平台下发 `{"msg_id": "RESUME_003", "task_action": "resume"}`)
6. **网关同样回复双闭环**：
   - 先用 `msg_id: "RESUME_003"` 回复 `ACK_RECEIVE`，表示收到恢复请求。
   - 恢复成功后，用 `msg_id: "RESUME_003"` 回复 `ACK_EXECUTE`，表示指令完成。
   - 最后用 `msg_id: "RUN_001"` 主动推送 `ACK_EXECUTE` + `task_status: "RUNNING"`，此时平台 UI 任务卡片重新亮起并继续推进度条。

#### 场景四：完整取消/终止闭环 (Abort Lifecycle)
在 `RUN_001` 任务跑的时候，平台点击“取消任务”。
1. **平台下发取消指令 (必须是新的 msg_id)**
```json
{
  "msg_id": "ABORT_004",
  "timestamp": 1790159980000,
  "cmd_type": "task",
  "action": "abort"
}
```
2. **网关瞬间回复已收到指令 (ACK_RECEIVE)**
```json
{
  "msg_id": "ABORT_004",
  "timestamp": 1790159980050,
  "robot_id": "P2026083101",
  "reply_type": "ACK_RECEIVE",
  "code": 0,
  "message": "接收到终止请求"
}
```
3. **网关回复取消指令完成 (ACK_EXECUTE)**
```json
{
  "msg_id": "ABORT_004",
  "timestamp": 1790159980100,
  "robot_id": "P2026083101",
  "reply_type": "ACK_EXECUTE",
  "code": 0,
  "data": {
    "task_id": "TASK_12345",
    "task_name": "日常巡检任务",
    "task_action": "abort",
    "task_status": "ABORTED",
    "duration_ms": 50
  }
}
```
4. **底层工作线程死前，发送最终遗言 (ACK_EXECUTE)**
```json
{
  "msg_id": "RUN_001",                   // 最终归宿：原任务的 msg_id 收到了终态
  "timestamp": 1790159980150,
  "robot_id": "P2026083101",
  "reply_type": "ACK_EXECUTE",
  "code": 4009,                          // 核心终态码：被强行终止
  "message": "任务 [日常巡检任务] 在步骤 2/5 因 [收到终止取消指令] 已终止取消",
  "data": {
    "task_id": "TASK_12345",
    "task_name": "日常巡检任务",
    "task_status": "ABORTED",            // UI 彻底把 RUN_001 置为灰色/死刑状态
    "aborted_at_step": 2,
    "total_steps": 5,
    "duration_ms": 15000
  }
}
```

#### 场景五：任务异常崩溃闭环 (Failed Lifecycle)
区别于被打断的 `ABORTED`，当机器人在执行第 3 步时，如果底层导航插件抛出了致命异常（如传感器离线）。
1. **网关捕获异常，发送当前子步骤失败 (ACK_PROGRESS)**
```json
{
  "msg_id": "RUN_001",
  "timestamp": 1790159990000,
  "robot_id": "P2026083101",
  "reply_type": "ACK_PROGRESS",
  "code": 5000,
  "message": "步骤 3/5 [NavPlugin.move_to] 执行失败: 导航底盘离线",
  "data": {
    "task_id": "TASK_12345",
    "task_name": "日常巡检任务",
    "step": 3,
    "total_steps": 5,
    "plugin_type": "NavPlugin",
    "plugin_action": "move_to",
    "task_status": "FAILED",             // 大任务状态直接转为失败
    "step_status": "failed",             // 步骤状态：红叉失败
    "duration_ms": 1200
  }
}
```
2. **底层工作线程死前，发送全局任务失败终态 (ACK_EXECUTE)**
```json
{
  "msg_id": "RUN_001",
  "timestamp": 1790159990050,
  "robot_id": "P2026083101",
  "reply_type": "ACK_EXECUTE",
  "code": 5000,                          // 核心异常终态码
  "message": "任务 [日常巡检任务] 因步骤 3 发生致命异常已彻底崩溃终止",
  "data": {
    "task_id": "TASK_12345",
    "task_name": "日常巡检任务",
    "task_status": "FAILED",             // UI 将任务置为飘红报错状态
    "aborted_at_step": 3,
    "total_steps": 5,
    "duration_ms": 90050
  }
}
```


### 6. 报文核心字段全量说明字典 (Payload Field Dictionary)

为方便联调，以下是报文及 `data` 载荷中可能出现的所有核心字段的详细定义：

| 字段名 | 类型 | 必选/可选 | 含义描述 |
| :--- | :--- | :--- | :--- |
| **`msg_id`** | String | 必选 | 消息唯一流水号。对于状态更新，这里必须是**触发该任务运行的那条原始指令的 ID**，供平台将状态精准匹配回那张任务卡片。 |
| **`timestamp`**| Integer| 必选 | 消息产生时的 Unix 毫秒时间戳（如 `1790159905692`），用于时序排列与延迟计算。 |
| **`robot_id`** | String | 必选 | 机器人的唯一标识符。 |
| **`reply_type`** | String | 必选 | 报文类型。**`ACK_RECEIVE`** 用于瞬间反馈网关已收到请求；**`ACK_EXECUTE`** 用于反馈控制指令执行结果或大任务的终态变更；**`ACK_PROGRESS`** 专用于反馈子任务的执行进度。 |
| **`code`** | Integer | 必选 | 系统级状态码。0 为成功/正常推进，非 0（如 4009, 5000）代表任务已不可逆终止或报错。 |
| **`message`** | String | 必选 | 供前端 UI 弹窗、日志记录或控制台输出的人类可读文本描述。 |
| **`data`** | Object | 必选 | 业务核心载荷包，包含以下属性： |
| **`action`** | String | 下发必选 | **【下行专属】**无论平台下发大任务控制指令还是原子插件指令，请求体统一使用 `action` 字段进行意图分流。 |
| `data.task_id` | String | 必选 | 机器人内部执行的原始任务唯一 ID。 |
| `data.task_name` | String | 可选 | 任务的可读名称，便于展示。 |
| `data.task_status`| String | 必选 | **大任务的宏观生命周期状态（全大写）**。枚举：`RUNNING`, `PAUSED`, `ABORTED`, `FAILED`, `FINISH`, `IDLE`。 |
| `data.step_status`| String | ACK_PROGRESS 必选 | **子步骤的微观执行状态（小写）**。枚举：`started`, `success`, `failed`。 |
| `data.step` | Integer| ACK_PROGRESS 必选 | 当前正在执行（或刚执行完）的子步骤序号（从 1 开始）。 |
| `data.total_steps`| Integer| ACK_PROGRESS 必选 | 当前任务拥有的总步骤数。 |
| `data.plugin_type`| String | ACK_PROGRESS 必选 | 当前步骤调用的底层能力层组件名（如 `NavPlugin`）。 |
| `data.plugin_action`| String | ACK_PROGRESS 必选 | **【上行解耦】** 专用于 `ACK_PROGRESS` 进度回执，指明当前正在执行的具体底层动作（如 `move_to`）。 |
| `data.task_action` | String | 控制类指令必选 | **【上行解耦】** 专用于全局控制指令完成后的 `ACK_EXECUTE` 回执，指明触发状态变更的源头动作（如 `pause`）。 |
| `data.duration_ms`| Integer| 必选 | 当前步骤或控制动作的执行耗时（毫秒）。任务或步骤刚开始时通常为 0。 |
| `data.aborted_at_step`| Integer | 仅 4009 必选 | 若任务被打断或取消，记录其“死”在了第几个步骤。 |
| `data.result` | Object | 可选 | 插件或动作执行完毕后，回传给平台的业务透传数据（例如坐标数组、图片路径、传感器数值等）。**注意：前端应忽略 `result` 内部的任何 `status` 字段，一切以顶层的 `task_status` 与 `step_status` 为准。** |

