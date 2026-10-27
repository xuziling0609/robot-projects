"""
MQTTManager - 边缘网关 MQTT 通信与离线持久化中枢
=================================================

设计背景与架构意图:
-----------------
在机器人边缘计算网关中，与上层云端/物联网平台 (IoT Platform) 的通信高度依赖 MQTT 长连接。
考虑到工业现场（变电站、隧道、管廊、化工厂区）存在复杂的无线多径反射与网络盲区，
机器人巡检过程中网络偶发性闪断、弱网或长时间掉线属于常态工况。

为保障控制流与数据流的高可靠交互，MQTTManager 确立了以下核心架构体系：
1. 【精简 Topic 命名空间规范 (1 下行 + 4 上行)】:
   - 唯一下行命令通道: `/edge/gateway/{robot_id}/cmd/down` (接收平台调度动作与任务)
   - 响应与反馈上行通道: `/edge/gateway/{robot_id}/response/up` (ACK 握手确认)
   - 状态心跳上行通道: `/edge/gateway/{robot_id}/status/up` (整机与全量插件实时遥测合流)
   - 能力物模型上行通道: `/edge/gateway/{robot_id}/capability/up` (插件与组件物模型注册)
   - 事件与告警上行通道: `/edge/gateway/{robot_id}/alarm/up` (设备异常与四级告警分级上报)

2. 【双层分级离线补偿机制 (Two-Tier Offline Compensation)】:
   - 高频丢弃策略 (Status 心跳): 采用内存固定容量环形队列 (`deque(maxlen=1)`)，
     弱网时仅保留最新一帧整机状态，旧状态丢弃，防止网络恢复后旧心跳引发平台状态倒退。
   - 强一致性持久化策略 (ACK 确认与告警 Alarm): 写入嵌入式本地 SQLite 磁盘队列 (`DiskQueue`)，
     即使网关断电重启也不会丢失。网络恢复后，后台守护线程以 0.5s 恒定速率顺序重传补偿。

3. 【生产级 SQLite WAL 模式加固 (Write-Ahead Logging)】:
   开启 WAL 模式与同步优化，高频写入与读重传并发互不阻塞，杜绝 `database is locked` 异常。

4. 【响应式生命周期与平滑停机】:
   采用 `threading.Event()` 实现毫秒级响应停机与资源回收，彻底消灭孤儿线程与连接泄漏。
"""

import os
import time
import json
import sqlite3
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any, Optional, Dict, List, Tuple
import paho.mqtt.client as mqtt

from core.logger_manager import get_logger
from utils import get_timestamp_ms, generate_msg_id
from utils.constants import PROJECT_ROOT

logger = get_logger("MQTTManager")


class DiskQueue:
    """
    轻量级工业嵌入式 SQLite 磁盘持久化队列
    专职用于弱网/断网环境下关键消息 (ACK、Alarm) 的原子落盘与可靠回放。
    """

    def __init__(self, db_path: Optional[str] = None, max_size: int = 10000):
        """
        初始化磁盘持久化队列。

        :param db_path: SQLite 数据库物理存储路径。若未指定，默认保存在 data/mqtt_offline.db
        :param max_size: 队列最大允许保留的离线消息条数，超过上限时自动淘汰最旧消息防磁盘暴涨
        """
        if db_path is None:
            db_path = os.path.join(PROJECT_ROOT, "data", "mqtt_offline.db")

        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.max_size = int(max_size)
        self.lock = threading.Lock()

        # 初始化数据库连接与性能优化配置 (WAL 模式)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        with self.lock:
            # 开启 WAL 预写日志与 5 秒繁忙超时，极大提高读写并发防锁库能力
            self.conn.execute("PRAGMA journal_mode = WAL;")
            self.conn.execute("PRAGMA synchronous = NORMAL;")
            self.conn.execute("PRAGMA busy_timeout = 5000;")
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS offline_msg (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    qos INTEGER NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            self.conn.commit()

    def put(self, topic: str, payload: dict, qos: int = 1) -> None:
        """
        将关键报文序列化并原子写入磁盘队列。

        :param topic: 目标 MQTT 发布主题
        :param payload: 字典格式的报文负载
        :param qos: MQTT QoS 服务质量等级 (0, 1, 2)
        """
        with self.lock:
            try:
                # 检查队列容量上限，超过上限时自动清理最旧的数据防爆盘
                cursor = self.conn.execute("SELECT COUNT(*) FROM offline_msg")
                current_count = cursor.fetchone()[0]
                if current_count >= self.max_size:
                    excess = current_count - self.max_size + 1
                    self.conn.execute(
                        "DELETE FROM offline_msg WHERE id IN (SELECT id FROM offline_msg ORDER BY id ASC LIMIT ?)",
                        (excess,)
                    )
                    logger.warning("离线磁盘队列达到容量上限 (%d条)，已自动淘汰最旧的 %d 条消息", self.max_size, excess)

                now = time.time()
                payload_str = json.dumps(payload, ensure_ascii=False)
                self.conn.execute(
                    "INSERT INTO offline_msg (topic, payload, qos, created_at) VALUES (?, ?, ?, ?)",
                    (topic, payload_str, int(qos), now)
                )
                self.conn.commit()
            except Exception as e:
                logger.error("写入离线磁盘队列发生异常: %s", e, exc_info=True)

    def get(self) -> Optional[Dict[str, Any]]:
        """
        以先进先出 (FIFO) 顺序读取队列头部的第一条离线消息（不删除）。

        :return: 包含 id, topic, payload(dict), qos 的字典；若队列为空返回 None
        """
        with self.lock:
            try:
                cursor = self.conn.execute(
                    "SELECT id, topic, payload, qos FROM offline_msg ORDER BY id ASC LIMIT 1"
                )
                row = cursor.fetchone()
                if row:
                    return {
                        "id": row[0],
                        "topic": row[1],
                        "payload": json.loads(row[2]),
                        "qos": row[3]
                    }
                return None
            except Exception as e:
                logger.error("读取离线磁盘队列发生异常: %s", e, exc_info=True)
                return None

    def delete(self, msg_id: int) -> bool:
        """
        确认成功补发后，根据主键 id 从磁盘队列中物理删除指定消息。

        :param msg_id: 离线消息主键自增 ID
        :return: 成功删除返回 True
        """
        with self.lock:
            try:
                self.conn.execute("DELETE FROM offline_msg WHERE id = ?", (msg_id,))
                self.conn.commit()
                return True
            except Exception as e:
                logger.error("从离线磁盘队列删除消息 [%s] 失败: %s", msg_id, e)
                return False

    def qsize(self) -> int:
        """
        查询当前离线磁盘队列中积压的消息总数。

        :return: 积压消息条数
        """
        with self.lock:
            try:
                cursor = self.conn.execute("SELECT COUNT(*) FROM offline_msg")
                return cursor.fetchone()[0]
            except Exception as e:
                logger.error("查询离线队列长度失败: %s", e)
                return 0

    def clear(self) -> None:
        """清空离线队列所有数据 (供测试与环境重置调用)"""
        with self.lock:
            try:
                self.conn.execute("DELETE FROM offline_msg")
                self.conn.commit()
            except Exception as e:
                logger.error("清空离线队列异常: %s", e)

    def close(self) -> None:
        """显式关闭 SQLite 数据库连接资源"""
        with self.lock:
            try:
                self.conn.close()
            except Exception:
                pass


class MQTTManager:
    """
    边缘网关 MQTT 通信中枢 (并发安全单例模式)
    负责维持与云端 Broker 的长连接通信，统一管理 1 下行 + 4 上行 Topic 交互与离线两级补发。
    """
    _instance: Optional["MQTTManager"] = None
    _instance_lock = threading.Lock()

    # 4 级标准化告警级别契约映射表
    ALARM_LEVEL_MAP: Dict[str, str] = {
        "info": "info",          # 提示级
        "notice": "info",
        "warning": "warning",    # 警告级
        "warn": "warning",
        "error": "error",        # 严重级
        "severe": "error",
        "major": "error",
        "fatal": "fatal",        # 致命级
        "critical": "fatal"
    }

    def __new__(cls, *args, **kwargs) -> "MQTTManager":
        """
        线程安全双重检测锁单例实现。
        """
        if not cls._instance:
            with cls._instance_lock:
                if not cls._instance:
                    instance = super(MQTTManager, cls).__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    @classmethod
    def send_alarm(
        cls,
        level: str = "error",
        code: int = 5000,
        message: str = "",
        data: Optional[dict] = None,
        source_plugin: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        全局快捷告警透传接口，供各插件或业务组件无须显式注入 MQTTManager 即可直达上报。
        """
        if cls._instance and hasattr(cls._instance, "publish_alarm"):
            try:
                cls._instance.publish_alarm(
                    level=level,
                    code=code,
                    message=message,
                    data=data,
                    source_plugin=source_plugin,
                    **kwargs
                )
            except Exception as e:
                logger.error("通过全局单例上报告警发生异常: %s", e, exc_info=True)

    def __init__(
        self,
        robot_id: Optional[str] = None,
        client_id: Optional[str] = None,
        broker_ip: str = "127.0.0.1",
        port: int = 1883,
        username: Optional[str] = None,
        password: Optional[str] = None,
        db_path: Optional[str] = None
    ):
        """
        初始化 MQTT 通信管理器。

        :param robot_id: 机器人唯一物理标识编码 (如 "robot_001")
        :param client_id: 可选的 MQTT Client ID (默认同 robot_id)
        :param broker_ip: MQTT 代理服务器 IP 地址
        :param port: MQTT 代理服务器连接端口 (默认 1883)
        :param username: 可选的 MQTT 鉴权用户名
        :param password: 可选的 MQTT 鉴权密码
        :param db_path: 可选的离线持久化数据库路径 (便于单元测试环境沙箱隔离)
        """
        if getattr(self, "_initialized", False):
            return

        with self._instance_lock:
            if getattr(self, "_initialized", False):
                return

            self.robot_id = robot_id or client_id or "robot888"
            self.client_id = self.robot_id
            self.broker_ip = broker_ip
            self.port = int(port)

            # 1. 规范 5 大核心 Topic 命名空间 (1下行 + 4上行)
            self.topic_cmd_down = f"/edge/gateway/{self.robot_id}/cmd/down"
            self.topic_response_up = f"/edge/gateway/{self.robot_id}/response/up"
            self.topic_status_up = f"/edge/gateway/{self.robot_id}/status/up"
            self.topic_caps_up = f"/edge/gateway/{self.robot_id}/capability/up"
            self.topic_alarm_up = f"/edge/gateway/{self.robot_id}/alarm/up"

            # 历史命名兼容别名
            self.topic_task_down = self.topic_cmd_down

            # 2. 外部回调与能力提供者
            self._on_task_received_callback: Optional[Callable[[dict], Any]] = None
            self._capability_provider: Optional[Callable[[], Any]] = None

            # 3. 异步任务派发线程池 (释放 MQTT 网络消息主线程)
            self._executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="MQTTTaskExec")

            # 4. 双层离线补偿结构
            self._offline_disk_queue = DiskQueue(db_path=db_path)
            self._offline_status_queue: deque = deque(maxlen=1)

            # 5. 线程生命周期控制与响应式补发线程
            self._stop_event = threading.Event()
            self._is_running = True
            self._last_status_pub_time: float = 0.0

            # 内部性能统计计数器
            self._stats = {
                "messages_received": 0,
                "responses_sent": 0,
                "alarms_sent": 0,
                "status_sent": 0,
                "retransmitted_success": 0
            }
            self._stats_lock = threading.Lock()

            self._retransmit_thread = threading.Thread(
                target=self._retransmit_loop,
                daemon=True,
                name="MQTTResponseRetransmit"
            )
            self._retransmit_thread.start()

            # 6. 初始化底层 Paho MQTT Client
            self.client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id=self.robot_id,
                clean_session=True
            )

            if username and password:
                self.client.username_pw_set(username, password)

            self.client.reconnect_delay_set(min_delay=1, max_delay=10)
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message

            self._initialized = True
            logger.info("MQTTManager 通信中枢初始化完成 (连接目标: %s:%d, 机器人ID: %s)", self.broker_ip, self.port, self.robot_id)

    def is_connected(self) -> bool:
        """
        自省接口：查询 MQTT 客户端当前是否与 Broker 处于连通状态。

        :return: 处于连接状态返回 True，否则返回 False
        """
        return bool(self.client and self.client.is_connected())

    def get_offline_queue_size(self) -> int:
        """
        自省接口：查询当前离线磁盘队列积压的消息总数。

        :return: 积压消息条数
        """
        return self._offline_disk_queue.qsize()

    def get_stats(self) -> Dict[str, Any]:
        """
        自省接口：获取 MQTT 通信链路统计指标。

        :return: 指标字典 (包含接收、发送、补发计数及当前离线积压量)
        """
        with self._stats_lock:
            stats_copy = dict(self._stats)
        stats_copy["offline_disk_queue_size"] = self.get_offline_queue_size()
        stats_copy["offline_status_queue_size"] = len(self._offline_status_queue)
        stats_copy["is_connected"] = self.is_connected()
        return stats_copy

    def register_task_callback(self, callback: Callable[[dict], Any]) -> None:
        """
        注册下行命令/任务接收分发回调函数。
        由上层 TaskManager 在启动时注入，解耦网络接收与业务调度。

        :param callback: 接收反序列化任务字典的回调函数
        """
        self._on_task_received_callback = callback

    def register_capability_provider(self, provider_func: Callable[[], Any]) -> None:
        """
        注入物模型能力提供者 (通常指向 PluginManager.get_all_capabilities)。
        当 MQTT 成功建连时，自动调用该方法向平台发布能力清单。

        :param provider_func: 无参返回物模型字典/列表的函数
        """
        self._capability_provider = provider_func

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        """MQTT 成功连接回调"""
        if reason_code == 0:
            logger.info("成功连接到 MQTT Broker: %s:%d", self.broker_ip, self.port)
            # 订阅统一命令下行通道
            client.subscribe(self.topic_cmd_down, qos=1)
            logger.info("已订阅云端唯一下行命令通道: %s", self.topic_cmd_down)

            # 首次建连或重连成功后，主动向平台推送全量能力物模型
            if self._capability_provider:
                try:
                    caps_data = self._capability_provider()
                    self.publish_capabilities({
                        "msg_id": generate_msg_id(),
                        "timestamp": get_timestamp_ms(),
                        "robot_id": self.robot_id,
                        "capabilities": caps_data
                    })
                except Exception as cap_err:
                    logger.error("建连后自动上报能力拓扑失败: %s", cap_err, exc_info=True)
        else:
            logger.error("连接 MQTT Broker 失败，原因码: %s", reason_code)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties) -> None:
        """MQTT 断开连接回调"""
        logger.warning("已断开与 MQTT Broker 的连接 (原因码: %s)。后台将自动尝试重连...", reason_code)

    def _safe_execute_callback(self, task_json: dict) -> None:
        """线程池安全包裹函数，捕获并记录任务派发执行时的未捕获异常"""
        try:
            if self._on_task_received_callback:
                self._on_task_received_callback(task_json)
        except Exception as e:
            logger.error("异步派发任务执行时发生未捕获异常: %s", e, exc_info=True)

    def _on_message(self, client, userdata, msg) -> None:
        """
        处理接收到的 MQTT 下行报文。
        仅在匹配唯一下行主题 /cmd/down 时响应，并自动触发接单 ACK (ACK_RECEIVE)。
        """
        logger.info("收到云端下行报文 [主题: %s, 字节数: %d]", msg.topic, len(msg.payload))

        with self._stats_lock:
            self._stats["messages_received"] += 1

        if msg.topic == self.topic_cmd_down:
            try:
                payload_str = msg.payload.decode("utf-8")
                task_json = json.loads(payload_str)

                msg_id = task_json.get("msg_id", task_json.get("task_id", "UNKNOWN"))

                # 1. 自动推送平台接单确认 ACK (ACK_RECEIVE)
                self.publish_response(
                    msg_id=msg_id,
                    reply_type="ACK_RECEIVE",
                    code=0,
                    message="网关已接收指令，正在调度执行"
                )

                # 2. 线程池异步派发任务，即刻释放 MQTT 网络事件循环线程
                if self._on_task_received_callback:
                    self._executor.submit(self._safe_execute_callback, task_json)
                else:
                    logger.warning("收到下行命令，但尚未注册回调处理函数，报文已丢弃")

            except json.JSONDecodeError as json_err:
                logger.error("云端下发了无效的 JSON 格式报文: %s", json_err)
            except Exception as e:
                logger.error("处理云端下行指令时发生异常: %s", e, exc_info=True)

    def start(self) -> None:
        """
        启动 MQTT 客户端后台网络循环守护线程 (异步非阻塞连接 + 自动断线重连)。
        """
        logger.info("正在启动 MQTT 网络循环并异步连接 %s:%d ...", self.broker_ip, self.port)
        try:
            self.client.connect_async(self.broker_ip, self.port, keepalive=60)
        except Exception as e:
            logger.warning("初始异步连接 Broker 失败: %s，后台网络循环将自动重试...", e)
        self.client.loop_start()

    def stop(self, timeout: float = 2.0) -> None:
        """
        平滑停止客户端通信、终止重传守护线程与线程池。

        :param timeout: 等待后台线程回收的最长超时时间 (秒)
        """
        logger.info("正在平滑停止 MQTTManager 通信中枢...")
        self._is_running = False
        self._stop_event.set()

        # 关闭任务执行线程池
        try:
            self._executor.shutdown(wait=False)
        except Exception:
            pass

        # 停止 MQTT 网络循环并断开连接
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass

        # 等待后台补发守护线程退出
        if self._retransmit_thread and self._retransmit_thread.is_alive():
            self._retransmit_thread.join(timeout=timeout)

        # 释放磁盘队列数据库句柄
        self._offline_disk_queue.close()
        logger.info("MQTTManager 通信中枢已完全安全退出。")

    def publish_response(
        self,
        msg_id: str,
        reply_type: str,
        code: int = 0,
        message: str = "",
        data: Optional[dict] = None,
        qos: int = 1
    ) -> None:
        """
        推送平台指令执行 ACK 回复 (带连接状态探测与断网离线缓存补发保障)。

        :param msg_id: 关联的原下行命令消息 ID
        :param reply_type: 确认类型 (ACK_RECEIVE, ACK_PROGRESS, ACK_EXECUTE)
        :param code: 响应错误码 (0 表示成功)
        :param message: 响应描述文本
        :param data: 可选的扩展数据字典
        :param qos: 发布服务质量等级 (默认 1)
        """
        payload = {
            "msg_id": msg_id,
            "timestamp": get_timestamp_ms(),
            "robot_id": self.robot_id,
            "reply_type": reply_type,
            "code": code,
            "message": message
        }
        if data is not None:
            payload["data"] = data

        self._send_or_cache_response(payload, qos)

    def _send_or_cache_response(self, payload: dict, qos: int = 1) -> None:
        """
        网络校验：连接畅通直接发布；断连或发送异常时转入 SQLite 离线磁盘队列。
        """
        try:
            if self.is_connected():
                payload_str = json.dumps(payload, ensure_ascii=False)
                res = self.client.publish(self.topic_response_up, payload_str, qos=qos)
                if res.rc == mqtt.MQTT_ERR_SUCCESS:
                    logger.info(
                        "已向云端发布 ACK [%s] msg_id=[%s], code=%s",
                        payload.get("reply_type"), payload.get("msg_id"), payload.get("code")
                    )
                    with self._stats_lock:
                        self._stats["responses_sent"] += 1
                    return
                else:
                    logger.warning("MQTT 发布 ACK 返回非零码 (rc=%d)，转入离线持久化队列", res.rc)
            else:
                logger.warning("MQTT 当前处于断连状态，ACK [%s] 已转入离线持久化队列", payload.get("reply_type"))
        except Exception as e:
            logger.error("发布回复报文出现异常: %s，转入离线持久化队列", e)

        # 写入持久化磁盘队列
        self._offline_disk_queue.put(self.topic_response_up, payload, qos)

    def _retransmit_once(self) -> None:
        """
        单次补发核心调度：
        1. 优先补发最新一帧 Status 心跳 (仅保留最新，淘汰旧心跳)；
        2. 顺序从 SQLite 磁盘队列读取一条关键消息 (ACK/Alarm) 尝试补发，成功则物理删除。
        """
        # 1. 补发最新一帧的 Status 心跳
        if len(self._offline_status_queue) > 0 and self.is_connected():
            payload, qos = self._offline_status_queue.popleft()
            payload_str = json.dumps(payload, ensure_ascii=False)
            try:
                self.client.publish(self.topic_status_up, payload_str, qos=qos)
                logger.info("离线最新 Status 心跳已成功补发")
            except Exception as e:
                logger.warning("补发离线 Status 异常: %s", e)

        # 2. 补发关键持久化消息 (Alarm, ACK 等)
        if self._offline_disk_queue.qsize() > 0 and self.is_connected():
            item = self._offline_disk_queue.get()
            if item:
                payload_str = json.dumps(item["payload"], ensure_ascii=False)
                try:
                    res = self.client.publish(item["topic"], payload_str, qos=item["qos"])
                    if res.rc == mqtt.MQTT_ERR_SUCCESS:
                        logger.info("离线关键报文补发成功: 主题=[%s], 剩余积压: %d", item["topic"], self._offline_disk_queue.qsize() - 1)
                        self._offline_disk_queue.delete(item["id"])
                        with self._stats_lock:
                            self._stats["retransmitted_success"] += 1
                    else:
                        logger.warning("补发关键报文返回非零状态 (rc=%d)，保留在队列等待下次尝试", res.rc)
                except Exception as e:
                    logger.error("补发关键报文发生异常: %s，保留在队列等待重试", e)

    def _retransmit_loop(self) -> None:
        """
        后台守护补发线程：以 0.5s 周期匀速触发离线报文重传。
        使用 _stop_event.wait 替代硬 sleep，实现毫秒级响应平滑退出。
        """
        while not self._stop_event.wait(timeout=0.5):
            if not self._is_running:
                break
            try:
                self._retransmit_once()
            except Exception as e:
                logger.error("离线补发守护线程发生未捕获异常: %s", e, exc_info=True)

    def publish_alarm(
        self,
        level: str = "error",
        code: int = 5000,
        message: str = "",
        data: Optional[dict] = None,
        alarm_id: Optional[str] = None,
        source_plugin: Optional[str] = None,
        error_code: Optional[int] = None,
        description: Optional[str] = None,
        params: Optional[dict] = None,
        msg_id: Optional[str] = None,
        qos: int = 1
    ) -> None:
        """
        上报设备/硬件告警 (遵循 4 级规范: info 提示 | warning 警告 | error 严重 | fatal 致命)。
        自动收敛清洗多态历史参数，确保 100% 向后兼容。
        """
        try:
            level_clean = str(level).strip().lower()
            norm_level = self.ALARM_LEVEL_MAP.get(level_clean, "error")

            # 多态参数统一归一化清洗
            eff_code = int(error_code if error_code is not None else code)
            eff_msg = str(description if description else message)
            eff_data = dict(data if data is not None else (params or {}))
            if source_plugin and "plugin_type" not in eff_data:
                eff_data["plugin_type"] = source_plugin

            payload = {
                "msg_id": msg_id or alarm_id or generate_msg_id(),
                "timestamp": get_timestamp_ms(),
                "robot_id": self.robot_id,
                "level": norm_level,
                "code": eff_code,
                "message": eff_msg,
                "data": eff_data
            }
            if alarm_id:
                payload["alarm_id"] = alarm_id

            payload_str = json.dumps(payload, ensure_ascii=False)

            if self.is_connected():
                res = self.client.publish(self.topic_alarm_up, payload_str, qos=qos)
                if res.rc != mqtt.MQTT_ERR_SUCCESS:
                    self._offline_disk_queue.put(self.topic_alarm_up, payload, qos)
                    logger.warning("MQTT 上报告警返回非零码 (rc=%d)，转入持久化队列", res.rc)
                else:
                    logger.info("已上报 [%s] 级告警 code=%d, msg=%s", norm_level.upper(), eff_code, eff_msg)
                    with self._stats_lock:
                        self._stats["alarms_sent"] += 1
            else:
                self._offline_disk_queue.put(self.topic_alarm_up, payload, qos)
                logger.warning("当前断网，告警已存入离线持久化队列: code=%d", eff_code)

        except Exception as e:
            logger.error("上报告警发生异常: %s", e, exc_info=True)

    def publish_status(
        self,
        task_state: str = "IDLE",
        robot_status: Optional[dict] = None,
        system_status: Optional[dict] = None,
        plugin_states: Optional[dict] = None,
        msg_id: Optional[str] = None,
        qos: int = 0,
        force: bool = False
    ) -> None:
        """
        向平台发送机器人与网关实时运行状态 (/status/up) (带 0.5s 防重抖动过滤)。

        :param task_state: 整机任务状态 (IDLE, RUNNING, PAUSED 等)
        :param robot_status: 包含 plugins 状态的字典
        :param system_status: 系统状态字典
        :param plugin_states: 兼容参数：插件状态字典
        :param msg_id: 消息 ID
        :param qos: QoS 等级 (默认 0 高频吞吐)
        :param force: 是否强制发送跳过防重限频
        """
        now = time.time()
        if not force and (now - self._last_status_pub_time < 0.5):
            return
        self._last_status_pub_time = now

        try:
            if robot_status is None:
                plugins = plugin_states or {}
                robot_status = {"plugins": plugins}
            elif "plugins" not in robot_status:
                robot_status = {"plugins": robot_status}

            payload = {
                "msg_id": msg_id or generate_msg_id(),
                "timestamp": get_timestamp_ms(),
                "robot_id": self.robot_id,
                "task_state": task_state,
                "robot_status": robot_status
            }

            payload_str = json.dumps(payload, ensure_ascii=False)
            if self.is_connected():
                res = self.client.publish(self.topic_status_up, payload_str, qos=qos)
                if res.rc != mqtt.MQTT_ERR_SUCCESS:
                    self._offline_status_queue.append((payload, qos))
                else:
                    logger.debug("已向云端上报实时状态 [%s]", self.topic_status_up)
                    with self._stats_lock:
                        self._stats["status_sent"] += 1
            else:
                self._offline_status_queue.append((payload, qos))
        except Exception as e:
            logger.error("发布状态报文发生异常: %s", e, exc_info=True)

    def publish_capabilities(
        self,
        payload: Optional[dict] = None,
        capabilities: Optional[list] = None,
        qos: int = 1
    ) -> None:
        """
        上报网关最新能力物模型拓扑至云端 (/capability/up)。
        """
        try:
            if payload is None:
                payload = {
                    "msg_id": generate_msg_id(),
                    "timestamp": get_timestamp_ms(),
                    "robot_id": self.robot_id,
                    "capabilities": capabilities or []
                }
            else:
                if "msg_id" not in payload:
                    payload["msg_id"] = generate_msg_id()
                if "robot_id" not in payload and "client_id" in payload:
                    payload["robot_id"] = payload.pop("client_id")
                elif "robot_id" not in payload:
                    payload["robot_id"] = self.robot_id

            payload_str = json.dumps(payload, ensure_ascii=False)
            if self.client:
                self.client.publish(self.topic_caps_up, payload_str, qos=qos)
            caps = payload.get("capabilities", [])
            if isinstance(caps, dict):
                plugins_count = len(caps.get("plugins", []))
                components_count = len(caps.get("components", []))
                logger.info("成功上报最新能力拓扑 (包含 %d 个插件, %d 个组件)", plugins_count, components_count)
            else:
                logger.info("成功上报最新能力拓扑 (包含 %d 个能力)", len(caps))
        except Exception as e:
            logger.error("上报能力拓扑发生异常: %s", e, exc_info=True)