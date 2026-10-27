import time
from typing import Dict, Any, Optional, List
from plugins.base import BasePlugin
from core.logger_manager import get_logger
from core.context_manager import ContextManager
from plugins.record.video_recorder import MultiChannelRecorder
from plugins.record.seaweed_sync_worker import SeaweedSyncWorker
from utils import generate_msg_id

logger = get_logger("RecordPlugin")

class RecordPlugin(BasePlugin):
    """
    独立录像与云端视频归档插件 (RecordPlugin)
    1. 动态别名流管理：支持 vis, thm, arm, rear 等任意 N 路 RTSP 流切片录制；
    2. 动态能力上报：start_record 的 channel 选项自动读取配置文件的别名列表；
    3. 断电与断网高可用：fMP4 本地切片优先，SQLite WAL 事务保证掉电不坏盘；
    4. 状态门控与即传即删：无任务 (IDLE/FINISHED) 跑满上传 SeaweedFS，全量同步后自动销毁本地视频、日志与 task_id 目录。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.plugin_name = "RecordPlugin"

        self.recording_cfg = self.config.get("recording", {})
        self.sync_cfg = self.config.get("server_sync", {})

        # 实例化后台同步工作器与通用多通道录像调度引擎
        self.sync_worker = SeaweedSyncWorker(
            config=self.sync_cfg,
            check_idle_fn=self._is_robot_idle
        )
        self.recorder = MultiChannelRecorder(
            config=self.recording_cfg,
            on_segment_ready=self.sync_worker.register_new_segment
        )
        self.sync_worker.start()

        # 订阅全局状态机变更事件
        try:
            from core.event_manager import EventManager
            EventManager().subscribe("global_state_changed", self._on_state_changed)
        except Exception as e:
            logger.error(f"[{self.plugin_name}] 订阅全局事件异常: {e}")

        configured_aliases = self.recorder.get_configured_aliases()
        logger.info(f"✨ [{self.plugin_name}] 录像与归档插件初始化完毕 -> 已加载 {len(configured_aliases)} 路流通道: {configured_aliases}")

    def _is_robot_idle(self) -> bool:
        """检查机器人当前是否处于无任务空闲状态 (状态为 idle/finished/aborted/none)"""
        task_info = ContextManager.get_robot_task()
        state = str(task_info.get("state", "")).upper()
        return state in ["IDLE", "FINISHED", "ABORTED", "NONE", ""]

    def _on_state_changed(self, event_data: Any) -> None:
        """根据机器人巡检状态动态门控视频同步带宽，并在任务终态（取消/失败/完成）时自动安全停止录像"""
        if isinstance(event_data, dict):
            new_state = str(event_data.get("state", "")).upper()
        elif hasattr(event_data, "extra_data") and isinstance(event_data.extra_data, dict):
            new_state = str(event_data.extra_data.get("state", "")).upper()
        elif hasattr(event_data, "get"):
            new_state = str(event_data.get("state", "")).upper()
        else:
            new_state = ""
        if new_state == "RUNNING":
            logger.info(f"[{self.plugin_name}] 状态机变更为 RUNNING，挂起视频同步上传以独占 MQTT/控制带宽")
            self.sync_worker.pause_sync()
        elif new_state in ["FINISHED", "FINISH", "ABORTED", "FAILED", "IDLE", "NONE"]:
            # 1. 若当前录像正在运行，且进入了任务终态 (取消/失败/完成)，自动停止录像并封包归档
            if new_state in ["FINISHED", "FINISH", "ABORTED", "FAILED"]:
                if self.recorder.get_status().get("is_recording"):
                    logger.info(f"🛑 [{self.plugin_name}] 检测到任务状态变更为 [{new_state}]，自动停止全部录像管线并封包尾部分片")
                    try:
                        self.recorder.stop_recording()
                    except Exception as e:
                        logger.error(f"[{self.plugin_name}] 任务终态自动停止录像异常: {e}")

            # 2. 状态机处于无任务或终态，唤醒 SeaweedFS 视频回传
            logger.info(f"[{self.plugin_name}] 状态机变更为 {new_state}，恢复 SeaweedFS 视频回传")
            self.sync_worker.resume_sync()

    def abort(self) -> None:
        """响应系统紧急打断信号，迅速退出所有录像管线并安全封包"""
        logger.warning(f"🚨 [{self.plugin_name}] 收到 abort 紧急打断信号，正在强制停止所有录像管线...")
        try:
            self.recorder.stop_recording()
        except Exception as e:
            logger.error(f"[{self.plugin_name}] abort 停止录像异常: {e}")

    def execute(self, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """统一控制动作分发入口"""
        params = params or {}
        action_lower = (action or "").lower()

        if action == "status" or action_lower == "status":
            return {
                "status": "success",
                "message": "录像插件在线",
                "data": {"online": True}
            }

        elif action == "start_record":
            task_info = ContextManager.get_robot_task()
            raw_task_id = (
                params.get("msg_id")                           # 1. 显式指定或单能力即时下发透传的 msg_id
                or params.get("task_id")                       # 2. 调试时手动显式指定的 task_id (如 test_01)
                or task_info.get("msg_id")                     # 3. 核心：平台下发执行离线任务的流水号 msg_id
                or task_info.get("task_id")                    # 4. 任务模板名称 (如 TASK_OFFLINE_F3_01) 兜底
                or f"debug_{generate_msg_id()}"  # 5. 无任何上下文时的单能力本地调试时间戳
            )
            safe_task_id = (
                str(raw_task_id)
                .replace("/", "_")
                .replace("\\", "_")
                .replace(":", "_")
                .replace(" ", "_")
            )

            channel = params.get("channel", "all")
            dur = params.get("segment_duration")

            logger.info(f"🎬 [{self.plugin_name}] 收到开启录像请求 -> 通道: {channel}, 分片时长: {dur}s, task_id: {safe_task_id}")
            return self.recorder.start_recording(
                channels=channel,
                segment_duration=dur,
                task_id=safe_task_id
            )

        elif action == "stop_record":
            logger.info(f"🛑 [{self.plugin_name}] 收到停止录像请求 -> 停止全部通道录像")
            return self.recorder.stop_recording()

        elif action == "record_status":
            rec_status = self.recorder.get_status()
            sync_status = self.sync_worker.get_status()
            return {
                "status": "success",
                "message": "获取录像与同步综合状态成功",
                "data": {
                    "recording": rec_status,
                    "sync": sync_status
                }
            }

        elif action == "sync_control":
            control_type = str(params.get("control", "pause")).lower()
            if control_type == "pause":
                self.sync_worker.pause_sync()
                return {"status": "success", "message": "已手动挂起后台视频同步"}
            elif control_type == "resume":
                self.sync_worker.resume_sync()
                return {"status": "success", "message": "已手动恢复后台视频同步"}
            else:
                return {"status": "error", "message": f"不支持的同步控制命令: {control_type}，仅支持 pause 或 resume"}

        else:
            return {"status": "error", "message": f"[{self.plugin_name}] 不支持的动作指令: {action}"}

    def get_status(self) -> bool:
        """录像插件状态（规范定义直接返回 True）"""
        return True

    def get_capabilities(self) -> Dict[str, Any]:
        """动态上报能力定义，自动读取 config.yaml 中的别名并渲染为 channel 参数选项"""
        aliases = self.recorder.get_configured_aliases()

        # 动态构建 channel 选项
        channel_options = [{"name": "全部通道", "value": "all"}]
        for alias in aliases:
            label = self.recorder.get_channel_label(alias)
            channel_options.append({"name": label, "value": alias})

        return {
            "plugin_type": self.plugin_name,
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
                            "required": False,
                            "ui_component": "select",
                            "options": channel_options
                        },
                        {
                            "name": "segment_duration",
                            "label": "分片时长(秒)",
                            "type": "int",
                            "default": 60,
                            "required": False,
                            "ui_component": "input_number"
                        }
                    ],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "message", "label": "执行描述", "type": "string"},
                            {"name": "data", "label": "录像元数据", "type": "object"}
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
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "message", "label": "执行描述", "type": "string"},
                            {"name": "data", "label": "停止结果", "type": "object"}
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
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "message", "label": "执行描述", "type": "string"},
                            {"name": "data", "label": "状态数据", "type": "object"}
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
                            "required": True,
                            "ui_component": "select",
                            "options": [
                                {"name": "挂起同步(pause)", "value": "pause"},
                                {"name": "恢复同步(resume)", "value": "resume"}
                            ]
                        }
                    ],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "status", "label": "执行状态", "type": "string"},
                            {"name": "message", "label": "执行描述", "type": "string"}
                        ]
                    }
                },
                {
                    "action": "status",
                    "action_name": "状态查询",
                    "description": "查询录像插件通信在线与运行状态",
                    "scopes": ["config"],
                    "params": [],
                    "returns": {
                        "type": "object",
                        "fields": [
                            {"name": "online", "label": "在线状态", "type": "bool"}
                        ]
                    }
                }
            ]
        }
