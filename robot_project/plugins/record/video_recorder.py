import os
import sys
import time
import shutil
import platform
import subprocess
import threading
from typing import Dict, List, Any, Optional, Callable, Union
from core.logger_manager import get_logger
from utils.constants import PROJECT_ROOT
import hashlib

logger = get_logger("RecordPlugin.VideoRecorder")

class FFmpegResolver:
    """跨操作系统与硬件架构的 FFmpeg 二进制智能探测与权限解析器"""

    OS_MAP = {
        "linux": "linux",
        "windows": "windows",
        "darwin": "darwin",
    }

    ARCH_MAP = {
        # 64-bit ARM
        "aarch64": "aarch64",
        "arm64": "aarch64",
        # 64-bit x86
        "x86_64": "x86_64",
        "amd64": "x86_64",
    }

    @classmethod
    def get_binary_path(cls, custom_path: Optional[str] = None) -> Optional[str]:
        """按优先级解析可用的 FFmpeg 二进制路径并自动修复可执行权限"""
        # 1. 优先使用用户在配置中显式指定的路径
        if custom_path and os.path.isfile(custom_path):
            cls._ensure_executable(custom_path)
            return custom_path

        # 2. 检查插件内置的标准多平台目录: plugins/record/lib/{os}/{arch}/ffmpeg
        current_os_raw = platform.system().lower()
        current_arch_raw = platform.machine().lower()

        mapped_os = cls.OS_MAP.get(current_os_raw)
        mapped_arch = cls.ARCH_MAP.get(current_arch_raw)

        if mapped_os and mapped_arch:
            exe_name = "ffmpeg.exe" if mapped_os == "windows" else "ffmpeg"
            embedded_path = os.path.join(
                PROJECT_ROOT,
                "plugins", "record", "lib",
                mapped_os, mapped_arch,
                exe_name
            )
            if os.path.isfile(embedded_path):
                cls._ensure_executable(embedded_path)
                logger.info(f"🎯 [FFmpegResolver] 成功匹配专用版本: {embedded_path} (系统: {mapped_os}, 架构: {mapped_arch})")
                return embedded_path

        # 3. 回退尝试系统全局 PATH 中的 ffmpeg
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            logger.info(f"🌐 [FFmpegResolver] 回退采用系统全局环境变量中的 FFmpeg: {system_ffmpeg}")
            return system_ffmpeg

        logger.warning("⚠️ [FFmpegResolver] 未能检测到可用的 FFmpeg 二进制文件，录像功能将受限。")
        return None

    @classmethod
    def _ensure_executable(cls, path: str) -> None:
        """在 POSIX 环境下自动追加 chmod +x 权限"""
        if platform.system().lower() != "windows":
            try:
                current_mode = os.stat(path).st_mode
                if not (current_mode & 0o111):
                    os.chmod(path, current_mode | 0o755)
                    logger.info(f"🔧 [FFmpegResolver] 已自动修复二进制可执行权限 (chmod 755): {path}")
            except Exception as e:
                logger.warning(f"⚠️ 尝试修复执行权限失败: {path}, 错误: {e}")


def calculate_file_md5(file_path: str) -> str:
    """计算文件的 MD5 校验码"""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return ""


class ChannelPipeline:
    """单路音视频流 fMP4 分片录制管线"""

    def __init__(
        self,
        alias: str,
        rtsp_url: str,
        ffmpeg_bin: str,
        task_id: str,
        save_dir: str,
        segment_duration: int = 60,
        on_segment_ready: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.alias = alias
        self.rtsp_url = rtsp_url
        self.ffmpeg_bin = ffmpeg_bin
        self.task_id = task_id
        self.save_dir = save_dir
        self.segment_duration = segment_duration
        self.on_segment_ready = on_segment_ready

        self.process: Optional[subprocess.Popen] = None
        self.is_running = False
        self._stop_event = threading.Event()
        self._watcher_thread: Optional[threading.Thread] = None
        self.segment_list_file = os.path.join(self.save_dir, f".segments_{self.alias}.csv")
        self.processed_segments = set()
        self._ffmpeg_log_fp = None
        self.lock = threading.Lock()

    def start(self) -> bool:
        """启动 FFmpeg 录像子进程与切片归档监听线程"""
        with self.lock:
            if self.is_running:
                return True

            os.makedirs(self.save_dir, exist_ok=True)
            if os.path.exists(self.segment_list_file):
                try:
                    os.remove(self.segment_list_file)
                except Exception:
                    pass

            # 命名模板：.tmp_{alias}_%04d.mp4
            segment_pattern = os.path.join(self.save_dir, f".tmp_{self.alias}_%04d.mp4")

            # 核心参数：
            # -rtsp_transport tcp (防弱网丢包花屏)
            # -map 0:v:0 -c:v copy (视频零拷贝极低CPU占用)
            # -map 0:a? -c:a aac (若有音频如 pcm_alaw 则安全转码为 AAC，无音频则自动忽略，彻底避免 MP4 崩溃)
            # -f segment (分片切流)
            # -movflags empty_moov+default_base_moof+frag_keyframe (fMP4断电不坏盘)
            # -segment_list ... (输出已完成分片CSV)
            cmd = [
                self.ffmpeg_bin,
                "-nostats",
                "-loglevel", "warning",
                "-y",
                "-rtsp_transport", "tcp",
                "-i", self.rtsp_url,
                "-map", "0:v:0", "-c:v", "copy",
                "-map", "0:a?", "-c:a", "aac",
                "-f", "segment",
                "-segment_time", str(self.segment_duration),
                "-segment_format", "mp4",
                "-segment_format_options", "movflags=empty_moov+default_base_moof+frag_keyframe",
                "-reset_timestamps", "1",
                "-segment_list", self.segment_list_file,
                "-segment_list_type", "csv",
                "-segment_list_flags", "+live",
                segment_pattern
            ]

            logger.info(f"🎬 [{self.alias}] 启动 FFmpeg fMP4 分片录制 -> 时长: {self.segment_duration}s | RTSP: {self.rtsp_url}")
            try:
                log_file = os.path.join(self.save_dir, f".ffmpeg_{self.alias}.log")
                self._ffmpeg_log_fp = open(log_file, "a", encoding="utf-8")
                self.process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=self._ffmpeg_log_fp,
                    text=True
                )
                self.is_running = True
                self._stop_event.clear()

                self._watcher_thread = threading.Thread(
                    target=self._watch_segments_loop,
                    daemon=True,
                    name=f"SegmentWatcher_{self.alias}"
                )
                self._watcher_thread.start()
                return True
            except Exception as e:
                logger.error(f"❌ [{self.alias}] 启动 FFmpeg 失败: {e}")
                if self._ffmpeg_log_fp:
                    try:
                        self._ffmpeg_log_fp.close()
                    except Exception:
                        pass
                    self._ffmpeg_log_fp = None
                self.is_running = False
                return False

    def _watch_segments_loop(self) -> None:
        """周期性读取 CSV 列表并原子重命名就绪分片"""
        while not self._stop_event.is_set():
            self._scan_and_commit_segments()
            time.sleep(1.0)
        # 退出前最后扫描一次
        self._scan_and_commit_segments()

    def _scan_and_commit_segments(self) -> None:
        """解析 CSV 列表，对已封闭的分片执行原子重命名与入库"""
        if not os.path.exists(self.segment_list_file):
            return

        try:
            with open(self.segment_list_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for line in lines:
                parts = line.strip().split(",")
                if not parts:
                    continue
                tmp_filename = parts[0].strip()
                if not tmp_filename or tmp_filename in self.processed_segments:
                    continue

                tmp_filepath = os.path.join(self.save_dir, tmp_filename)
                if not os.path.exists(tmp_filepath):
                    continue

                # 提取分片序号并生成正式文件名: {alias}_{task_id}_{seq_str}_{now_ts}.mp4
                seq_str = "0000"
                base_name = os.path.basename(tmp_filename)
                name_no_ext = os.path.splitext(base_name)[0]
                tokens = name_no_ext.split("_")
                if len(tokens) >= 3:
                    seq_str = tokens[-1]

                now_ts = int(time.time())
                final_filename = f"{self.alias}_{self.task_id}_{seq_str}_{now_ts}.mp4"
                final_filepath = os.path.join(self.save_dir, final_filename)

                # 原子替换 (Atomic Rename)
                try:
                    os.replace(tmp_filepath, final_filepath)
                    self.processed_segments.add(tmp_filename)

                    file_size = os.path.getsize(final_filepath)
                    md5_val = calculate_file_md5(final_filepath)

                    duration = float(self.segment_duration)
                    if len(parts) >= 3:
                        try:
                            start_t = float(parts[1])
                            end_t = float(parts[2])
                            if end_t > start_t:
                                duration = round(end_t - start_t, 2)
                        except Exception:
                            pass

                    record_info = {
                        "task_id": self.task_id,
                        "channel": self.alias,
                        "filename": final_filename,
                        "file_path": final_filepath,
                        "file_size": file_size,
                        "duration_sec": duration,
                        "checksum_md5": md5_val,
                        "created_at": now_ts
                    }

                    logger.info(f"📦 [{self.alias}] 分片原子归档就绪: {final_filename} ({file_size / 1024 / 1024:.2f} MB, {duration}s)")

                    if self.on_segment_ready:
                        self.on_segment_ready(record_info)
                except Exception as e:
                    logger.error(f"原子归档分片失败 ({tmp_filepath} -> {final_filepath}): {e}")

        except Exception as e:
            logger.debug(f"读取分片 CSV 异常 (正常轮询中): {e}")

    def stop(self) -> None:
        """优雅关闭 FFmpeg 子进程，封包尾部分片"""
        with self.lock:
            if not self.is_running:
                return

            self.is_running = False
            self._stop_event.set()

            if self.process:
                try:
                    # 尝试向标准输入发送 'q' 触发优雅收口
                    if self.process.stdin:
                        try:
                            self.process.stdin.write("q\n")
                            self.process.stdin.flush()
                        except Exception:
                            pass
                    self.process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    # 超时后发送 terminate
                    try:
                        self.process.terminate()
                        self.process.wait(timeout=1.5)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait(timeout=1.0)
                except Exception as e:
                    logger.warning(f"终止 FFmpeg 异常: {e}")

                self.process = None

            if self._ffmpeg_log_fp:
                try:
                    self._ffmpeg_log_fp.close()
                except Exception:
                    pass
                self._ffmpeg_log_fp = None

            if self._watcher_thread and self._watcher_thread.is_alive():
                self._watcher_thread.join(timeout=2.0)

            # 1. 扫描并归档 CSV 中已轮转封包的分片
            self._scan_and_commit_segments()

            # 2. 扫尾归档尚未到达轮转周期提前停止的尾部分片
            self._commit_trailing_segment()

            # 3. 清理 CSV 索引
            if os.path.exists(self.segment_list_file):
                try:
                    os.remove(self.segment_list_file)
                except Exception:
                    pass

            logger.info(f"🛑 [{self.alias}] 录像管线已安全退出并封包归档")

    def _commit_trailing_segment(self) -> None:
        """
        扫尾处理：当录像停止时，最后一个正在写入的分片往往未到达 segment_duration，
        因此 FFmpeg 不会将其写入 segment_list CSV。
        此处主动扫描 save_dir 中的未完成 .tmp 分片，若文件大小 > 0 则原子收口并归档入库；
        若文件大小 == 0 (如未产生数据的坏流) 则清理删除。
        """
        if not os.path.exists(self.save_dir):
            return

        prefix = f".tmp_{self.alias}_"
        for fname in sorted(os.listdir(self.save_dir)):
            if fname.startswith(prefix) and fname.endswith(".mp4"):
                tmp_filepath = os.path.join(self.save_dir, fname)
                try:
                    size = os.path.getsize(tmp_filepath)
                    if size == 0:
                        logger.warning(f"🗑️ [{self.alias}] 清理 0 字节无效临时分片: {fname}")
                        os.remove(tmp_filepath)
                        continue

                    # 提取序号
                    tokens = os.path.splitext(fname)[0].split("_")
                    seq_str = tokens[-1] if len(tokens) >= 3 else "tail"

                    now_ts = int(time.time())
                    final_filename = f"{self.alias}_{self.task_id}_{seq_str}_{now_ts}.mp4"
                    final_filepath = os.path.join(self.save_dir, final_filename)

                    os.replace(tmp_filepath, final_filepath)
                    self.processed_segments.add(fname)

                    file_size = os.path.getsize(final_filepath)
                    md5_val = calculate_file_md5(final_filepath)

                    record_info = {
                        "task_id": self.task_id,
                        "channel": self.alias,
                        "filename": final_filename,
                        "file_path": final_filepath,
                        "file_size": file_size,
                        "duration_sec": 0.0,
                        "checksum_md5": md5_val,
                        "created_at": now_ts
                    }

                    logger.info(f"📦 [{self.alias}] 尾部分片原子归档就绪: {final_filename} ({file_size / 1024 / 1024:.2f} MB)")

                    if self.on_segment_ready:
                        self.on_segment_ready(record_info)
                except Exception as e:
                    logger.error(f"处理尾部分片异常 ({tmp_filepath}): {e}")


class MultiChannelRecorder:
    """
    多通道通用录像调度引擎 (MultiChannelRecorder)
    负责管理任意 N 路视频流 (以别名标识) 的并发分片录制
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        on_segment_ready: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.config = config or {}
        self.on_segment_ready = on_segment_ready

        self.segment_duration = int(self.config.get("segment_duration_sec", 60))
        self.base_save_dir = os.path.join(PROJECT_ROOT, self.config.get("save_dir", "data/videos"))

        # 解析通道配置: Dict[str, Dict[str, Any]] (alias -> {"url": ..., "label": ...})
        self.channels_cfg: Dict[str, Dict[str, Any]] = self._parse_channels(self.config.get("channels"))
        self.stream_map: Dict[str, str] = {
            alias: info["url"] for alias, info in self.channels_cfg.items() if info.get("url")
        }

        self.pipelines: Dict[str, ChannelPipeline] = {}
        self.active_task_id: Optional[str] = None
        self.start_time: float = 0.0
        self.lock = threading.Lock()

    def _parse_channels(self, raw_channels: Any) -> Dict[str, Dict[str, Any]]:
        """将配置的通道解析为标准的 alias -> {"url": ..., "label": ...} 字典映射"""
        channels_map: Dict[str, Dict[str, Any]] = {}
        if isinstance(raw_channels, dict):
            for k, v in raw_channels.items():
                alias = str(k).strip()
                if not alias:
                    continue
                if isinstance(v, dict):
                    url = str(v.get("url", "")).strip()
                    label = str(v.get("label", "")).strip() or f"{alias} 通道"
                    if url:
                        channels_map[alias] = {
                            "url": url,
                            "label": label
                        }
        return channels_map

    def get_configured_aliases(self) -> List[str]:
        """获取所有已配置的通道别名列表"""
        return list(self.stream_map.keys())

    def get_channel_label(self, alias: str) -> str:
        """获取指定通道别名的展示名称 (label)，若未找到则默认返回 '<alias> 通道'"""
        if alias in self.channels_cfg and self.channels_cfg[alias].get("label"):
            return self.channels_cfg[alias]["label"]
        return f"{alias} 通道"

    def _resolve_target_aliases(self, channels: Any) -> List[str]:
        """将用户传入的 channels (支持 0, 'all', 序号, 别名或列表) 解析为待操作的别名集合"""
        all_aliases = list(self.stream_map.keys())
        if not all_aliases:
            return []

        if channels is None or channels == 0 or channels == "0" or str(channels).lower() == "all":
            return all_aliases

        input_list = channels if isinstance(channels, list) else [channels]
        targets = []
        for item in input_list:
            item_str = str(item).strip()
            # 1. 直接匹配别名
            if item_str in self.stream_map:
                if item_str not in targets:
                    targets.append(item_str)
                continue

            # 2. 数字序号转换 (1 对应第1个别名, 2 对应第2个别名...)
            try:
                num = int(item_str)
                if 1 <= num <= len(all_aliases):
                    matched_alias = all_aliases[num - 1]
                    if matched_alias not in targets:
                        targets.append(matched_alias)
            except ValueError:
                pass

        return targets if targets else all_aliases

    def start_recording(
        self,
        channels: Optional[Union[int, str, List[Any]]] = None,
        segment_duration: Optional[int] = None,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """启动录像能力"""
        with self.lock:
            ffmpeg_bin = FFmpegResolver.get_binary_path()
            if not ffmpeg_bin:
                return {
                    "status": "error",
                    "message": "未找到可用的 FFmpeg 二进制文件，请确认 plugins/record/lib/ 下已放置对应架构的编译包。"
                }

            if not self.stream_map:
                return {
                    "status": "error",
                    "message": "未在配置文件中配置任何有效的视频通道 (channels 为空)"
                }

            target_aliases = self._resolve_target_aliases(channels)
            cur_task_id = task_id or f"task_{int(time.time())}"
            self.active_task_id = cur_task_id
            self.start_time = time.time()
            dur = segment_duration or self.segment_duration

            task_save_dir = os.path.join(self.base_save_dir, cur_task_id)
            os.makedirs(task_save_dir, exist_ok=True)

            started_channels = []
            for alias in target_aliases:
                if alias in self.pipelines and self.pipelines[alias].is_running:
                    started_channels.append(alias)
                    continue

                rtsp_url = self.stream_map.get(alias)
                if not rtsp_url:
                    continue

                pipeline = ChannelPipeline(
                    alias=alias,
                    rtsp_url=rtsp_url,
                    ffmpeg_bin=ffmpeg_bin,
                    task_id=cur_task_id,
                    save_dir=task_save_dir,
                    segment_duration=dur,
                    on_segment_ready=self.on_segment_ready
                )
                if pipeline.start():
                    self.pipelines[alias] = pipeline
                    started_channels.append(alias)

            if not started_channels:
                return {"status": "error", "message": "启动录像管线失败，请检查 RTSP 码流连接或网络配置"}

            rec_id = f"REC_{cur_task_id}_{int(self.start_time)}"
            return {
                "status": "success",
                "message": f"成功启动 {len(started_channels)} 路切片录像 (通道: {started_channels})",
                "data": {
                    "recording_id": rec_id,
                    "task_id": cur_task_id,
                    "channels": started_channels,
                    "segment_duration": dur,
                    "save_dir": task_save_dir
                }
            }

    def stop_recording(self, channels: Optional[Union[int, str, List[Any]]] = None) -> Dict[str, Any]:
        """停止录像能力"""
        with self.lock:
            if not self.pipelines:
                return {"status": "success", "message": "当前未在录像，无需停止", "data": {"stopped_channels": []}}

            if channels is not None:
                target_aliases = self._resolve_target_aliases(channels)
                aliases_to_stop = [a for a in target_aliases if a in self.pipelines]
            else:
                aliases_to_stop = list(self.pipelines.keys())

            stopped = []
            for alias in aliases_to_stop:
                pipeline = self.pipelines.pop(alias, None)
                if pipeline:
                    pipeline.stop()
                    stopped.append(alias)

            if not self.pipelines:
                cur_task_id = self.active_task_id
                self.active_task_id = None
                self.start_time = 0.0
                if cur_task_id:
                    self._cleanup_task_dir_if_empty(cur_task_id)

            return {
                "status": "success",
                "message": f"已安全停止并归档 {len(stopped)} 路录像",
                "data": {
                    "stopped_channels": stopped,
                    "remaining_active": list(self.pipelines.keys())
                }
            }

    def _cleanup_task_dir_if_empty(self, task_id: str) -> None:
        """若停止录像后该任务目录下已没有任何 .mp4 视频文件，清理残留日志并移除 task_id 目录"""
        task_dir = os.path.join(self.base_save_dir, task_id)
        if not os.path.isdir(task_dir):
            return
        mp4_files = [f for f in os.listdir(task_dir) if f.endswith(".mp4")]
        if not mp4_files:
            shutil.rmtree(task_dir, ignore_errors=True)
            logger.info(f"🧹 [录像引擎] 任务 [{task_id}] 无本地视频文件残留，已清理录制日志并移除目录: {task_dir}")

    def get_status(self) -> Dict[str, Any]:
        """获取录像状态"""
        with self.lock:
            active_channels = [alias for alias, p in self.pipelines.items() if p.is_running]
            is_recording = len(active_channels) > 0
            elapsed = round(time.time() - self.start_time, 1) if is_recording else 0.0

            return {
                "is_recording": is_recording,
                "active_channels": active_channels,
                "configured_channels": list(self.stream_map.keys()),
                "current_task_id": self.active_task_id,
                "elapsed_sec": elapsed
            }


# 保持向后兼容性别名
DualChannelRecorder = MultiChannelRecorder
