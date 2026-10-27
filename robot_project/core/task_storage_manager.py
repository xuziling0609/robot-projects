# -*- coding: utf-8 -*-
"""
================================================================================
机器人边缘网关 - 离线任务存储管理器 (TaskStorageManager)
================================================================================
核心职责：
1. 【两阶段原子落盘 (Atomic Commit)】：
   采用“临时文件写入 -> os.fsync 物理扇区刷盘 -> os.replace POSIX 原子替换”两阶段提交机制，
   杜绝系统断电或进程强退导致的 JSON 损坏（半写入数据）风险。
2. 【高内聚高速两级缓存 (Thread-Safe Two-Level Cache)】：
   内部维护专用的高速内存缓存字典 (_cache)，配备细粒度可重入锁 (RLock)；
   高频任务查询零磁盘 I/O 开销，多线程并发 CRUD 读写互斥，安全无竞态。
3. 【临时文件零泄漏防护 (Zero Orphan Leaks)】：
   写入过程使用 try-finally 保证异常发生时即刻清理临时文件；
   启动初始化时自动扫盘清除因历史异常掉电滞留的 `.tmp_` 孤儿文件。
4. 【解耦同步与向后兼容 (Decoupled Sync)】：
   将任务业务持久化与 ConfigManager 全局基础配置严格隔离，
   同时提供只写镜像同步适配，100% 保持存量模块与单测的无缝兼容。
================================================================================
"""

import os
import json
import time
import threading
from typing import Optional, Dict, Any, List
from core.logger_manager import get_logger
from core.config_manager import ConfigManager
from utils.constants import PROJECT_ROOT

logger = get_logger("TaskStorageManager")


class TaskStorageManager:
    """
    离线任务持久化与存储管理中枢 (TaskStorageManager)。
    
    用于管理边缘网关本地持久化的离线预设巡检任务。
    存储路径默认为 `data/tasks/{task_id}.json`。
    """

    def __init__(self, config_loader: Optional[ConfigManager] = None, storage_dir: Optional[str] = None):
        """
        初始化任务存储管理器。
        
        Args:
            config_loader: 可选的系统配置管理器。若不提供则默认使用 ConfigManager() 单例。
            storage_dir: 可选的任务持久化存储目录。若不提供则默认使用 `PROJECT_ROOT/data/tasks`。
        """
        self.config_loader = config_loader or ConfigManager()
        self.storage_dir = storage_dir or os.path.join(PROJECT_ROOT, "data", "tasks")
        os.makedirs(self.storage_dir, exist_ok=True)

        # 内部专属可重入互斥锁，保障多线程并发 I/O 与缓存一致性
        self._lock = threading.RLock()

        # 内部专属内存缓存：{ task_id: task_data_dict }
        self._cache: Dict[str, Dict[str, Any]] = {}

        # 启动时自动清理历史异常掉电滞留的孤儿临时文件
        self._cleanup_orphan_tmp_files()

    # --------------------------------------------------------------------------
    # 辅助与兼容同步方法 (Internal Helpers)
    # --------------------------------------------------------------------------

    def _cleanup_orphan_tmp_files(self) -> None:
        """扫描任务存储目录，自动清理遗留的 .tmp_ 临时文件，避免磁盘垃圾累积"""
        with self._lock:
            if not os.path.exists(self.storage_dir):
                return
            cleaned_count = 0
            try:
                for fname in os.listdir(self.storage_dir):
                    if fname.startswith(".tmp_"):
                        fpath = os.path.join(self.storage_dir, fname)
                        try:
                            os.remove(fpath)
                            cleaned_count += 1
                        except OSError as e:
                            logger.warning(f"⚠️ 清理孤儿临时文件失败 [{fname}]: {e}")
                if cleaned_count > 0:
                    logger.info(f"🧹 [TaskStorageManager] 启动自动清理完成，已清除 {cleaned_count} 个历史孤儿临时文件")
            except Exception as e:
                logger.warning(f"⚠️ [TaskStorageManager] 扫描孤儿临时文件异常: {e}")

    def _sync_to_external_config(self, task_id: Optional[str] = None, task_data: Optional[Dict[str, Any]] = None,
                                 remove: bool = False, clear: bool = False) -> None:
        """
        向后兼容同步适配器：
        若外部传入的 config_loader 具有 `_config` 字典，则将变更镜像同步给它，
        以确保依赖 `config_loader._config["tasks"]` 的旧逻辑与测试用例平稳运行。
        """
        if not hasattr(self.config_loader, "_config") or not isinstance(self.config_loader._config, dict):
            return

        tasks_dict = self.config_loader._config.setdefault("tasks", {})
        if not isinstance(tasks_dict, dict):
            self.config_loader._config["tasks"] = {}
            tasks_dict = self.config_loader._config["tasks"]

        if clear:
            tasks_dict.clear()
        elif remove and task_id:
            tasks_dict.pop(task_id, None)
        elif task_id and task_data:
            tasks_dict[task_id] = task_data

    # --------------------------------------------------------------------------
    # 核心 CRUD 接口 (CRUD APIs)
    # --------------------------------------------------------------------------

    def save_task_to_disk(self, task_id: str, steps: list, name: Optional[str] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        两阶段工业级原子落盘持久化至 `data/tasks/{task_id}.json`。
        
        执行时序与可靠性保障：
        1. 严格参数校验（拒绝空 task_id 或非列表 steps）；
        2. 写入带进程 PID 和时间戳的临时文件 (`.tmp_{task_id}_*.json`)；
        3. 强制 `flush()` 并调用 `os.fsync(fileno)` 确保数据穿透 OS 页面缓存强刷至物理存储介质；
        4. 使用 `os.replace` POSIX 原子替换目标文件，杜绝文件半写入损坏；
        5. 写入内部内存缓存并镜像同步外部兼容配置；
        6. 使用 `finally` 块确保发生任何意外异常时临时文件绝不残留。
        
        Args:
            task_id: 任务唯一标识符 (非空字符串)。
            steps: 任务步骤数组 (必须为包含操作字典的非空列表)。
            name: 任务可读名称 (可选，若未指定则默认等于 task_id)。
            metadata: 任务业务元数据字典 (可选，如 {"rth_point": 100, "task_type": "patrol"})。
            
        Returns:
            bool: 是否落盘并更新缓存成功。
        """
        if not task_id or not isinstance(task_id, str):
            logger.warning(f"⚠️ [TaskStorageManager] 落盘被拒：无效的 task_id: {task_id}")
            return False
        if not steps or not isinstance(steps, list):
            logger.warning(f"⚠️ [TaskStorageManager] 落盘被拒：任务 [{task_id}] steps 必须为非空列表")
            return False

        with self._lock:
            os.makedirs(self.storage_dir, exist_ok=True)
            target_file = os.path.join(self.storage_dir, f"{task_id}.json")
            tmp_file = os.path.join(self.storage_dir, f".tmp_{task_id}_{os.getpid()}_{time.time()}.json")

            task_data: Dict[str, Any] = {
                "task_id": task_id,
                "task_name": name or task_id,
                "steps": steps,
                "total_steps": len(steps),
                "updated_at": int(time.time() * 1000)
            }
            if metadata and isinstance(metadata, dict):
                for k, v in metadata.items():
                    if k not in task_data:
                        task_data[k] = v

            try:
                # 阶段一：写入临时文件并强行物理落盘
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(task_data, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())

                # 阶段二：POSIX 原语原子重命名替换
                os.replace(tmp_file, target_file)

                # 更新内部缓存与外部兼容配置
                self._cache[task_id] = task_data
                self._sync_to_external_config(task_id=task_id, task_data=task_data)

                logger.info(f"💾 [TaskStorageManager] 离线任务 [{task_id}] 原子落盘成功: {target_file}")
                return True
            except Exception as e:
                logger.error(f"❌ [TaskStorageManager] 任务 [{task_id}] 原子落盘异常: {e}", exc_info=True)
                return False
            finally:
                # 确保临时文件在任何异常路径下均被完全清除
                if os.path.exists(tmp_file):
                    try:
                        os.remove(tmp_file)
                    except OSError:
                        pass

    def get_task_data(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        检索离线任务的完整元数据字典。
        
        查询策略（分级穿透）：
        1. 一级缓存：优先读取内存高速缓存 `self._cache`；
        2. 外部配置回退：若未命中，检索 `config_loader`；
        3. 磁盘回源：从 `data/tasks/{task_id}.json` 载入，解析成功后自动回填至内存缓存，加速后续查询。
        
        Args:
            task_id: 目标任务 ID。
            
        Returns:
            Optional[Dict[str, Any]]: 任务完整字典；若任务不存在或读取失败则返回 None。
        """
        if not task_id:
            return None

        with self._lock:
            # 1. 优先命中内部高速缓存
            if task_id in self._cache:
                cached = self._cache[task_id]
                return dict(cached) if isinstance(cached, dict) else cached

            # 2. 检索 external config (兼容旧版本将 task_id 直接映射为 steps list 的配置模式)
            local_tasks = self.config_loader.get("tasks", {}) if hasattr(self.config_loader, "get") else {}
            if isinstance(local_tasks, dict) and task_id in local_tasks:
                raw_val = local_tasks[task_id]
                if isinstance(raw_val, dict):
                    self._cache[task_id] = raw_val
                    return dict(raw_val)
                elif isinstance(raw_val, list):
                    normalized = {
                        "task_id": task_id,
                        "task_name": task_id,
                        "steps": raw_val,
                        "total_steps": len(raw_val),
                        "updated_at": int(time.time() * 1000)
                    }
                    self._cache[task_id] = normalized
                    return dict(normalized)
                return raw_val

            # 3. 磁盘回源读取
            target_file = os.path.join(self.storage_dir, f"{task_id}.json")
            if os.path.exists(target_file):
                try:
                    with open(target_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            self._cache[task_id] = data
                            self._sync_to_external_config(task_id=task_id, task_data=data)
                            logger.info(f"📂 [TaskStorageManager] 从磁盘回源载入离线任务: [{task_id}] ({target_file})")
                            return dict(data)
                        elif isinstance(data, list):
                            normalized = {
                                "task_id": task_id,
                                "task_name": task_id,
                                "steps": data,
                                "total_steps": len(data),
                                "updated_at": int(os.path.getmtime(target_file) * 1000)
                            }
                            self._cache[task_id] = normalized
                            return dict(normalized)
                except Exception as e:
                    logger.error(f"❌ [TaskStorageManager] 读取磁盘任务文件 [{target_file}] 失败: {e}", exc_info=True)

            return None

    def get_task_steps(self, task_id: str) -> Optional[list]:
        """
        向后兼容查询接口：获取指定离线任务的执行步骤数组 (steps)。
        
        Args:
            task_id: 目标任务 ID。
            
        Returns:
            Optional[list]: 步骤数组；若任务不存在则返回 None。
        """
        data = self.get_task_data(task_id)
        if isinstance(data, list):
            return data
        return data.get("steps") if isinstance(data, dict) else None

    def has_task(self, task_id: str) -> bool:
        """
        快速判定指定任务是否存在（检查内存缓存或磁盘文件）。
        
        Args:
            task_id: 目标任务 ID。
            
        Returns:
            bool: 是否存在。
        """
        if not task_id:
            return False
        with self._lock:
            if task_id in self._cache:
                return True
            target_file = os.path.join(self.storage_dir, f"{task_id}.json")
            return os.path.exists(target_file)

    def delete_task(self, task_id: str) -> Dict[str, Any]:
        """
        删除指定的离线任务（淘汰内存缓存并物理删除磁盘 JSON 文件）。
        
        Args:
            task_id: 要删除的任务 ID。
            
        Returns:
            Dict[str, Any]: 包含执行状态和结果消息的字典。
        """
        if not task_id:
            return {"status": "error", "message": "缺少 task_id 参数"}

        with self._lock:
            # 1. 淘汰内存缓存与外部兼容镜像
            self._cache.pop(task_id, None)
            self._sync_to_external_config(task_id=task_id, remove=True)

            # 2. 物理删除磁盘文件
            target_file = os.path.join(self.storage_dir, f"{task_id}.json")
            deleted_file = False
            if os.path.exists(target_file):
                try:
                    os.remove(target_file)
                    deleted_file = True
                    logger.info(f"🗑️ [TaskStorageManager] 离线任务磁盘文件已物理删除: {target_file}")
                except Exception as e:
                    logger.error(f"❌ [TaskStorageManager] 删除磁盘任务文件 [{target_file}] 失败: {e}", exc_info=True)

            if deleted_file:
                return {"status": "success", "message": f"离线任务 [{task_id}] 已成功删除"}
            return {"status": "success", "message": f"离线任务 [{task_id}] 已清理"}

    def list_tasks(self) -> Dict[str, Any]:
        """
        盘点并汇总网关本地已存储的所有离线任务摘要清单。
        
        返回摘要数据结构：
            {
                "status": "success",
                "total_count": int,
                "tasks": [
                    {
                        "task_id": str,
                        "task_name": str,
                        "total_steps": int,
                        "updated_at": int
                    }, ...
                ]
            }
        """
        with self._lock:
            tasks_list: List[Dict[str, Any]] = []
            scanned_ids = set()

            if os.path.exists(self.storage_dir):
                for fname in os.listdir(self.storage_dir):
                    # 过滤临时文件与隐藏文件
                    if fname.endswith(".json") and not fname.startswith("."):
                        fpath = os.path.join(self.storage_dir, fname)
                        try:
                            with open(fpath, "r", encoding="utf-8") as f:
                                data = json.load(f)
                                tid = data.get("task_id") or fname.replace(".json", "")
                                if tid in scanned_ids:
                                    continue
                                scanned_ids.add(tid)

                                tname = data.get("task_name") or data.get("name") or tid
                                total_steps = data.get("total_steps") or len(data.get("steps", []))
                                updated_at = data.get("updated_at") or int(os.path.getmtime(fpath) * 1000)

                                tasks_list.append({
                                    "task_id": tid,
                                    "task_name": tname,
                                    "total_steps": total_steps,
                                    "updated_at": updated_at
                                })
                        except Exception as e:
                            logger.error(f"❌ [TaskStorageManager] 盘点任务文件异常 [{fname}]: {e}", exc_info=True)

            # 按更新时间倒序排列
            tasks_list.sort(key=lambda x: x.get("updated_at", 0), reverse=True)

            return {
                "status": "success",
                "total_count": len(tasks_list),
                "tasks": tasks_list
            }

    def clear_tasks(self) -> Dict[str, Any]:
        """
        一键清空网关本地所有离线任务（清空内存缓存并批量删除所有任务文件）。
        
        Returns:
            Dict[str, Any]: 包含清空统计的响应字典。
        """
        with self._lock:
            # 清空内存缓存与外部兼容配置
            self._cache.clear()
            self._sync_to_external_config(clear=True)

            cleared_files = set()
            if os.path.exists(self.storage_dir):
                for fname in os.listdir(self.storage_dir):
                    if fname.endswith(".json"):
                        fpath = os.path.join(self.storage_dir, fname)
                        try:
                            os.remove(fpath)
                            cleared_files.add(fname)
                        except Exception as e:
                            logger.error(f"❌ [TaskStorageManager] 清理任务文件失败 [{fname}]: {e}", exc_info=True)

            cleared_count = len(cleared_files)
            logger.info(f"🧹 [TaskStorageManager] 已成功清空本地所有离线任务 (共清理 {cleared_count} 个文件)")
            return {
                "status": "success",
                "message": f"成功清空本地所有离线任务 (共 {cleared_count} 个)",
                "cleared_count": cleared_count
            }
