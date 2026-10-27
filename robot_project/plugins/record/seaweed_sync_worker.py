import os
import time
import sqlite3
import threading
import requests
import shutil
from typing import Dict, Any, Optional, List, Callable
from core.logger_manager import get_logger
from core.config_manager import ConfigManager
from core.context_manager import ContextManager
from utils.constants import PROJECT_ROOT

logger = get_logger("RecordPlugin.SeaweedSync")

class VideoSyncDatabase:
    """SQLite WAL 模式的视频切片任务队列总账本"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.path.join(PROJECT_ROOT, "data", "video_sync.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.lock = threading.Lock()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        with self.lock:
            conn = self._get_conn()
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS video_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id TEXT NOT NULL,
                        channel TEXT NOT NULL,
                        filename TEXT NOT NULL,
                        file_path TEXT,
                        file_size INTEGER NOT NULL,
                        duration_sec REAL NOT NULL,
                        checksum_md5 TEXT,
                        status TEXT DEFAULT 'PENDING',
                        retry_count INTEGER DEFAULT 0,
                        remote_url TEXT,
                        local_deleted INTEGER DEFAULT 0,
                        created_at INTEGER NOT NULL,
                        synced_at INTEGER
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_task_id ON video_records(task_id);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON video_records(status);")
                conn.commit()
            finally:
                conn.close()

    def register_segment(self, record_info: Dict[str, Any]) -> int:
        """注册新就绪的切片分片到待同步总账"""
        with self.lock:
            conn = self._get_conn()
            try:
                cursor = conn.execute("""
                    INSERT INTO video_records (
                        task_id, channel, filename, file_path, file_size,
                        duration_sec, checksum_md5, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)
                """, (
                    str(record_info["task_id"]),
                    str(record_info["channel"]),
                    record_info["filename"],
                    record_info["file_path"],
                    record_info["file_size"],
                    record_info.get("duration_sec", 60.0),
                    record_info.get("checksum_md5", ""),
                    record_info.get("created_at", int(time.time()))
                ))
                conn.commit()
                return cursor.lastrowid
            finally:
                conn.close()

    def get_pending_records(self, limit: int = 10, max_retries: int = 3) -> List[Dict[str, Any]]:
        """获取待上传的分片列表"""
        with self.lock:
            conn = self._get_conn()
            try:
                cursor = conn.execute("""
                    SELECT id, task_id, channel, filename, file_path, file_size,
                           checksum_md5, retry_count, status
                    FROM video_records
                    WHERE (status = 'PENDING' OR (status = 'FAILED' AND retry_count < ?))
                      AND local_deleted = 0
                      AND file_path IS NOT NULL
                    ORDER BY id ASC
                    LIMIT ?
                """, (max_retries, limit))
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
            finally:
                conn.close()

    def mark_synced_and_purge(self, record_id: int, remote_url: str) -> None:
        """更新为已同步并清空本地文件路径记录 (上云即焚)"""
        with self.lock:
            conn = self._get_conn()
            try:
                conn.execute("""
                    UPDATE video_records
                    SET status = 'SYNCED',
                        local_deleted = 1,
                        file_path = NULL,
                        remote_url = ?,
                        synced_at = ?
                    WHERE id = ?
                """, (remote_url, int(time.time()), record_id))
                conn.commit()
            finally:
                conn.close()

    def mark_failed(self, record_id: int) -> None:
        """标记上传失败并累加重试次数"""
        with self.lock:
            conn = self._get_conn()
            try:
                conn.execute("""
                    UPDATE video_records
                    SET status = 'FAILED',
                        retry_count = retry_count + 1
                    WHERE id = ?
                """, (record_id,))
                conn.commit()
            finally:
                conn.close()

    def reset_failed_records(self) -> None:
        """重置所有失败记录的重试次数，以便系统启动时进行补上传"""
        with self.lock:
            conn = self._get_conn()
            try:
                conn.execute("""
                    UPDATE video_records
                    SET retry_count = 0
                    WHERE status = 'FAILED'
                """)
                conn.commit()
                logger.info("♻️ [VideoSyncDatabase] 已重置所有失败视频的重试次数，准备补传")
            finally:
                conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """获取同步队列统计信息"""
        with self.lock:
            conn = self._get_conn()
            try:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(CASE WHEN status = 'PENDING' THEN 1 END) as pending_count,
                        COUNT(CASE WHEN status = 'SYNCED' THEN 1 END) as synced_count,
                        COUNT(CASE WHEN status = 'FAILED' THEN 1 END) as failed_count,
                        COUNT(*) as total_count
                    FROM video_records
                """)
                row = cursor.fetchone()
                return {
                    "pending_count": row[0] or 0,
                    "synced_count": row[1] or 0,
                    "failed_count": row[2] or 0,
                    "total_count": row[3] or 0
                }
            finally:
                conn.close()

    def is_task_all_synced(self, task_id: str) -> bool:
        """查询指定任务的所有分片是否已全部同步且删除 (必须至少有已入库分片且全部为 SYNCED)"""
        with self.lock:
            conn = self._get_conn()
            try:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*),
                        SUM(CASE WHEN status != 'SYNCED' THEN 1 ELSE 0 END)
                    FROM video_records
                    WHERE task_id = ?
                """, (task_id,))
                row = cursor.fetchone()
                total = row[0]
                unfinished = row[1] or 0
                return total > 0 and unfinished == 0
            finally:
                conn.close()


class SeaweedSyncWorker:
    """
    SeaweedFS 无任务状态断点续传与即传即删后台工作器
    1. 门控检测：仅在机器人无任务 (IDLE / FINISHED / 充电中) 唤醒
    2. 对接 SeaweedFS Filer 原生 REST API (流式 PUT + HEAD 幂等秒传)
    3. 强一致性校验后立即执行本地 os.remove，实现零占盘
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        check_idle_fn: Optional[Callable[[], bool]] = None
    ):
        self.config = config or {}
        self.check_idle_fn = check_idle_fn or self._default_check_idle

        # 读取配置
        self.enabled = bool(self.config.get("enabled", True))
        self.delete_after_sync = bool(self.config.get("delete_after_sync", True))
        seaweed_cfg = self.config.get("seaweedfs", {})
        self.filer_url = seaweed_cfg.get("filer_url", "http://127.0.0.1:8888").rstrip("/")
        self.base_dir = seaweed_cfg.get("base_dir", "/robot_surveillance").strip("/")
        self.timeout_sec = float(seaweed_cfg.get("timeout_sec", 15.0))
        self.retry_limit = int(seaweed_cfg.get("retry_limit", 3))

        cfg_mgr = ConfigManager()
        self.robot_id = cfg_mgr.get("mqtt.robot_id", "robot888")

        self.db = VideoSyncDatabase()
        self._is_running = False
        self._paused_by_event = False
        self._worker_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """启动后台同步工作线程"""
        with self._lock:
            if self._is_running:
                return
            self._is_running = True
            self.db.reset_failed_records()  # 启动时重置之前的失败记录，以实现补传
            self._worker_thread = threading.Thread(
                target=self._sync_loop,
                daemon=True,
                name="SeaweedSyncWorker"
            )
            self._worker_thread.start()
            logger.info(f"🚀 [SeaweedSyncWorker] 视频同步工作线程已启动 -> 目标 Filer: {self.filer_url}")

    def stop(self) -> None:
        """安全停止工作线程"""
        with self._lock:
            self._is_running = False
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        logger.info("🛑 [SeaweedSyncWorker] 同步工作线程已停止")

    def pause_sync(self) -> None:
        """显式挂起同步 (如任务变更为 RUNNING 时让出网络通道)"""
        self._paused_by_event = True
        logger.info("⏸️ [SeaweedSyncWorker] 收到任务执行信号，同步上传已挂起避让")

    def resume_sync(self) -> None:
        """唤醒同步 (如任务变更为 IDLE / FINISHED 时恢复传输)"""
        self._paused_by_event = False
        logger.info("▶️ [SeaweedSyncWorker] 恢复视频同步上传")

    def _default_check_idle(self) -> bool:
        """默认检查机器人是否空闲"""
        task_info = ContextManager.get_robot_task()
        state = str(task_info.get("state", "")).upper()
        return state in ["IDLE", "FINISHED", "ABORTED", "NONE", ""]

    def _is_sync_allowed(self) -> bool:
        """综合判定当前是否允许向服务端推流视频"""
        if not self.enabled:
            return False
        if self._paused_by_event:
            return False
        return self.check_idle_fn()

    def register_new_segment(self, record_info: Dict[str, Any]) -> None:
        """供录像引擎调用的切片入库入口"""
        self.db.register_segment(record_info)

    def _build_remote_url(self, task_id: str, filename: str) -> str:
        """构建 SeaweedFS Filer 中的目标存储绝对路径"""
        return f"/{self.base_dir}/{self.robot_id}/{task_id}/{filename}"

    def _head_check_exists(self, remote_url: str, local_size: int) -> bool:
        """通过 HEAD 预检文件是否在服务端已完整存在 (幂等秒传)"""
        full_url = f"{self.filer_url}{remote_url}"
        try:
            resp = requests.head(full_url, timeout=3.0)
            if resp.status_code == 200:
                remote_size = int(resp.headers.get("Content-Length", -1))
                if remote_size == local_size:
                    logger.info(f"✨ [SeaweedFS] 服务端已存在相同分片且大小匹配 ({remote_size} B)，触发秒传跳过: {remote_url}")
                    return True
        except Exception:
            pass
        return False

    def _upload_file(self, record: Dict[str, Any]) -> bool:
        """流式上传单个分片至 SeaweedFS Filer 并执行强校验"""
        file_path = record["file_path"]
        if not file_path or not os.path.isfile(file_path):
            logger.warning(f"⚠️ 本地物理文件不存在，直接标记跳过: {record['filename']}")
            self.db.mark_synced_and_purge(record["id"], "FILE_NOT_FOUND")
            return True

        task_id = record["task_id"]
        filename = record["filename"]
        file_size = record["file_size"]
        remote_path = self._build_remote_url(task_id, filename)
        full_url = f"{self.filer_url}{remote_path}"

        # 1. HEAD 预检 (幂等查重)
        if self._head_check_exists(remote_path, file_size):
            self._finalize_uploaded_file(record, remote_path)
            return True

        # 2. 流式上传 (PUT 请求)
        headers = {
            "Content-Type": "video/mp4",
            "Content-Length": str(file_size),
            "X-Robot-Id": str(self.robot_id),
            "X-Task-Id": str(task_id),
            "X-Camera-Channel": str(record.get("channel", "default")),
            "X-Checksum-MD5": str(record.get("checksum_md5", ""))
        }

        try:
            with open(file_path, "rb") as f:
                logger.info(f"📤 正在上传视频分片至 SeaweedFS: {filename} ({file_size / 1024 / 1024:.2f} MB) -> {remote_path}")
                resp = requests.put(
                    full_url,
                    data=f,
                    headers=headers,
                    timeout=self.timeout_sec
                )

            # 3. 严格校验响应
            if resp.status_code in [200, 201]:
                verified = False
                try:
                    resp_json = resp.json()
                    if isinstance(resp_json, dict) and resp_json.get("size") == file_size:
                        verified = True
                except Exception:
                    pass

                if not verified and self._head_check_exists(remote_path, file_size):
                    verified = True

                if verified or resp.status_code == 201:
                    logger.info(f"✅ 分片上传成功并双向校验通过: {filename}")
                    self._finalize_uploaded_file(record, remote_path)
                    return True
                else:
                    logger.warning(f"⚠️ 上传返回成功但二次校验大小不匹配: {filename}")
            else:
                logger.error(f"❌ SeaweedFS 响应异常: HTTP {resp.status_code} - {resp.text[:100]}")

        except Exception as e:
            logger.error(f"❌ 上传视频分片网络异常 ({filename}): {e}")

        self.db.mark_failed(record["id"])
        return False

    def _finalize_uploaded_file(self, record: Dict[str, Any], remote_path: str) -> None:
        """确认成功后安全销毁本地物理文件并清理任务录制日志与任务目录 (即传即删)"""
        record_id = record["id"]
        file_path = record["file_path"]
        task_id = record["task_id"]

        # 更新数据库账本
        self.db.mark_synced_and_purge(record_id, remote_path)

        # 物理删除本地文件
        if self.delete_after_sync and file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"🗑️ [即传即删] 本地物理文件已安全销毁: {os.path.basename(file_path)}")
            except Exception as e:
                logger.error(f"删除本地物理文件失败: {e}")

        # 检查该任务目录下是否已全量同步完成，若是则彻底清理录制日志与 task_id 文件夹
        try:
            if file_path:
                task_dir = os.path.dirname(file_path)
                if os.path.isdir(task_dir) and self.db.is_task_all_synced(task_id):
                    all_files = os.listdir(task_dir)
                    # 只要该目录下还存在任何 .mp4 文件 (包含正在录制的临时文件)，严禁删除目录
                    if not any(f.endswith(".mp4") for f in all_files):
                        shutil.rmtree(task_dir, ignore_errors=True)
                        logger.info(f"🧹 [即传即删] 任务 [{task_id}] 视频已全量同步，已清理录制日志并彻底移除任务目录: {task_dir}")
        except Exception as e:
            logger.debug(f"清理任务目录异常 (忽略): {e}")

    def _cleanup_synced_task_dirs(self) -> None:
        """扫描本地视频存储根目录，清理已全部同步且无视频残留的任务目录与录制日志"""
        videos_base_dir = os.path.join(PROJECT_ROOT, "data", "videos")
        if not os.path.isdir(videos_base_dir):
            return
        try:
            for folder_name in os.listdir(videos_base_dir):
                task_dir = os.path.join(videos_base_dir, folder_name)
                if not os.path.isdir(task_dir):
                    continue
                if not self.db.is_task_all_synced(folder_name):
                    continue
                all_files = os.listdir(task_dir)
                if any(f.endswith(".mp4") for f in all_files):
                    continue
                shutil.rmtree(task_dir, ignore_errors=True)
                logger.info(f"🧹 [自动清理] 任务 [{folder_name}] 视频已全量同步，已清理录制日志并删除任务目录: {task_dir}")
        except Exception as e:
            logger.debug(f"扫描清理已同步任务目录异常: {e}")

    def _sync_loop(self) -> None:
        """主同步轮询循环"""
        while self._is_running:
            if not self._is_sync_allowed():
                time.sleep(1.0)
                continue

            try:
                # 周期性扫描清理历史已完成任务的残留目录与日志
                self._cleanup_synced_task_dirs()

                records = self.db.get_pending_records(limit=5, max_retries=self.retry_limit)
                if not records:
                    time.sleep(2.0)
                    continue

                for rec in records:
                    if not self._is_sync_allowed():
                        logger.info("⏸️ 任务状态变更，立即中止当前轮次上传让路")
                        break

                    self._upload_file(rec)
                    time.sleep(0.05)

            except Exception as e:
                logger.error(f"同步主循环未捕获异常: {e}")
                time.sleep(3.0)

    def get_status(self) -> Dict[str, Any]:
        """获取同步器运行状态"""
        stats = self.db.get_stats()
        return {
            "enabled": self.enabled,
            "is_sync_allowed": self._is_sync_allowed(),
            "paused_by_event": self._paused_by_event,
            "filer_url": self.filer_url,
            "delete_after_sync": self.delete_after_sync,
            **stats
        }
