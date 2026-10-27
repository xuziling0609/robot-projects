# -*- coding: utf-8 -*-
"""
================================================================================
机器人边缘网关 - 工业级 TCP 连接池与链路管理器 (TCPManager / TCPPoolManager)
================================================================================
核心职责：
1. 【硬件长连接池化复用 (Connection Pooling)】：
   集中维护与下位机硬件控制器（开门机控制器、升降电梯通信板、充电站 PLC、
   机械臂上位机、LoRa 网关等）的 Socket 长连接，杜绝高频短连接三次握手对硬件造成的网络风暴。
2. 【高并发细粒度加锁解耦 (Fine-grained Lock Decoupling)】：
   将阻塞的物理握手过程 (`sock.connect`) 彻底移出全局互斥锁，仅在查池与登记连接时短时持锁；
   彻底解决“单一硬件离线超时阻塞 3 秒导致全机所有其他硬件交互死锁”的严重架构缺陷。
3. 【无侵入 Socket 存活探测 (Non-invasive Liveness Probing)】：
   结合 `SO_ERROR` 检查与零延迟 `MSG_PEEK` 探测对端断开事件 (FIN/RST)；
   采用严格的上下文保存与恢复（old_timeout -> try-finally）机制，
   彻底修复存活探测将 Socket 超时参数篡改为 0.001s 导致后续业务高频超时报错的历史隐患。
4. 【工业自愈与重试能力 (Auto-healing & Retry)】：
   自动检测并剔除僵死断开的链路，支持可选的轻量建连重试机制，增强对现场工业总线抖动的抵抗力。
5. 【自省可观测性 (Observability)】：
   提供连接池大小查询、活动连接列表展示、指定硬件在线存活判定等健康检查接口。
================================================================================
"""

import socket
import threading
import time
from typing import Dict, List, Optional, Tuple
from core.logger_manager import get_logger

logger = get_logger("TCPManager")


class TCPManager:
    """
    工业级 TCP 连接池与链路管理器 (线程安全单例)。
    
    单例设计与长连接维护机制：
    1. 【双重检测锁 (Double-Checked Locking)】：
       确保在多硬件插件并发初始化启动时，全局仅存在唯一的连接池实例；
    2. 【细粒度读写互斥锁 (_lock)】：
       只对内部 `_pool` 字典的读写操作加锁，阻塞耗时的网络 I/O 握手在锁外并发执行；
    3. 【无污染存活校验 (_is_socket_alive)】：
       采用非破坏性探测，探测完毕严格复原原始调用方配置的超时属性。
    """
    _instance: Optional["TCPManager"] = None
    _instance_lock: threading.Lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> "TCPManager":
        """双重检测锁保障多线程并发初始化时单例唯一性"""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    instance = super(TCPManager, cls).__new__(cls)
                    # 连接池缓存字典：{ "ip:port": socket.socket }
                    instance._pool: Dict[str, socket.socket] = {}
                    # 细粒度池化管理互斥锁
                    instance._lock: threading.RLock = threading.RLock()
                    # 单设备建连互斥锁字典，实现相同设备防风暴与不同设备无锁并发
                    instance._connecting_locks: Dict[str, threading.Lock] = {}
                    cls._instance = instance
        return cls._instance

    # --------------------------------------------------------------------------
    # 核心连接获取与复用接口 (Connection Acquisition APIs)
    # --------------------------------------------------------------------------

    def get_connection(self, ip: str, port: int, timeout: float = 3.0, retries: int = 0) -> socket.socket:
        """
        获取或复用与目标硬件的 TCP Socket 连接。
        
        执行时序与并发安全保障：
        1. 【快速查池】：在互斥锁保护下快速检索连接池。若已有连接且经存活探测正常，直接复用返回 (<0.1ms)；
        2. 【失效清理】：若池中连接已失效（对端已断开或错误），将其安全关闭并从池中剔除；
        3. 【分段键级锁 (Key-level Lock)】：
           - 针对相同设备 (ip:port) 的并发请求，仅由排在首位的线程发起单次建连，其余线程等待后双重检查直接复用，
             杜绝同一硬件并发产生多次握手风暴与连接覆盖；
           - 针对不同设备 (不同 ip:port)，各自持有独立的设备锁并发建连，互不干扰，
             彻底消除“某一台硬件掉电超时导致整机所有硬件交互死锁”的架构隐患！
           
        Args:
            ip: 目标设备 IP 地址。
            port: 目标设备端口号。
            timeout: 连接建立与后续默认操作的超时时间 (秒，默认 3.0s)。
            retries: 遇网络抖动建连失败时的可选重试次数 (默认 0 即不重试)。
            
        Returns:
            socket.socket: 有效的 TCP Socket 客户端对象。
            
        Raises:
            socket.timeout: 建立连接超时。
            ConnectionRefusedError: 目标硬件拒绝连接。
            Exception: 其他网络不可达或系统级 Socket 异常。
        """
        key = f"{ip}:{port}"

        # 阶段一：快速加锁检查存量连接池
        with self._lock:
            if key in self._pool:
                sock = self._pool[key]
                if self._is_socket_alive(sock):
                    return sock
                else:
                    logger.warning(f"⚠️ [TCPManager] 缓存的硬件链路 [{key}] 已失效，正在销毁准备重建...")
                    self._close_socket(sock)
                    self._pool.pop(key, None)

            # 获取针对该设备的建连专用锁
            if key not in self._connecting_locks:
                self._connecting_locks[key] = threading.Lock()
            key_lock = self._connecting_locks[key]

        # 阶段二：仅在设备级锁内建连（不同设备完全并发）
        with key_lock:
            # 双重检测：前序排队线程可能已将该设备的连接建好并入池
            with self._lock:
                if key in self._pool:
                    sock = self._pool[key]
                    if self._is_socket_alive(sock):
                        return sock
                    else:
                        self._close_socket(sock)
                        self._pool.pop(key, None)

            # 真正执行底层 Socket 物理握手
            sock = self._create_socket_with_retry(ip, port, timeout, retries)

            # 登记入池
            with self._lock:
                self._pool[key] = sock
                return sock

    def _create_socket_with_retry(self, ip: str, port: int, timeout: float, retries: int) -> socket.socket:
        """在锁外创建并连接 Socket，支持工业网络轻量重试"""
        key = f"{ip}:{port}"
        attempts = 0
        max_attempts = max(1, retries + 1)

        while attempts < max_attempts:
            attempts += 1
            logger.info(f"🔌 [TCPManager] 正在建立与硬件的 TCP 连接: [{key}] (第 {attempts}/{max_attempts} 次尝试)...")
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                # 开启 TCP_NODELAY 降低工业控制延迟
                try:
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                except (OSError, AttributeError):
                    pass

                sock.connect((ip, port))
                logger.info(f"✅ [TCPManager] 成功建立硬件 TCP 链路: [{key}]")
                return sock
            except socket.timeout:
                logger.error(f"❌ [TCPManager] 建立 TCP 连接超时 [{key}] (超时设定: {timeout}s)")
                self._close_socket(sock)
                if attempts >= max_attempts:
                    raise
            except ConnectionRefusedError:
                logger.error(f"❌ [TCPManager] 硬件设备拒绝连接 [{key}]，请检查目标设备服务状态与网线")
                self._close_socket(sock)
                if attempts >= max_attempts:
                    raise
            except Exception as e:
                logger.error(f"❌ [TCPManager] 建立 TCP 链路异常 [{key}]: {e}", exc_info=True)
                self._close_socket(sock)
                if attempts >= max_attempts:
                    raise

            # 重试前轻微休眠防抖
            time.sleep(0.2)

        raise socket.error(f"建立 TCP 连接失败 [{key}] (已重试 {retries} 次)")

    # --------------------------------------------------------------------------
    # 链路存活探测与健康检查 (Liveness Probing)
    # --------------------------------------------------------------------------

    def _is_socket_alive(self, sock: socket.socket) -> bool:
        """
        无污染、高可靠的 Socket 存活检测算法。
        
        检测机制：
        1. 【SO_ERROR 状态查询】：检查操作系统内核底层 Socket 是否存在未决错误；
        2. 【非侵入窥探 (MSG_PEEK)】：
           - 严格暂存当前连接的原始 `old_timeout = sock.gettimeout()`；
           - 临时将超时设为 0.001s 并执行 `recv(1, MSG_PEEK)` 窥探；
           - 若读到 `b''` 则说明对端已正常发送 FIN 关闭连接，判定为断开；
           - 若触发 `socket.timeout`，说明 Socket 处于正常空闲状态，未收到任何断开包，链路健康；
           - 【关键修复】：在 `finally` 块中**100% 恢复原始 `old_timeout`**，彻底消除 1ms 超时污染 Bug！
        """
        try:
            # 1. 检查底层内核 Socket 错误标志
            error = sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if error != 0:
                return False

            # 2. 窥探对端断开事件 (必须保护并恢复原始超时)
            old_timeout = sock.gettimeout()
            try:
                sock.settimeout(0.001)
                data = sock.recv(1, socket.MSG_PEEK)
                if data == b'':
                    return False  # 对端已正常断开 (FIN)
            except socket.timeout:
                pass  # 超时说明没有收到断开信号，链路正常
            finally:
                # 核心防线：必须恢复原始超时时间！
                sock.settimeout(old_timeout)

            return True
        except Exception as e:
            logger.debug(f"🔍 [TCPManager] Socket 存活探测判定为已失效: {e}")
            return False

    def _close_socket(self, sock: Optional[socket.socket]) -> None:
        """安全关闭 Socket 句柄并捕获所有异常"""
        if sock:
            try:
                sock.close()
            except Exception as e:
                logger.debug(f"⚠️ [TCPManager] 关闭 Socket 异常: {e}")

    # --------------------------------------------------------------------------
    # 连接释放与生命周期管理 (Release & Lifecycle APIs)
    # --------------------------------------------------------------------------

    def release_connection(self, ip: str, port: int) -> None:
        """
        主动释放并关闭指定的 TCP 连接（从连接池中注销并断开物理链接）。
        
        Args:
            ip: 设备 IP 地址。
            port: 设备端口号。
        """
        key = f"{ip}:{port}"
        with self._lock:
            if key in self._pool:
                logger.info(f"🔒 [TCPManager] 主动释放并关闭硬件 TCP 链路: [{key}]")
                sock = self._pool.pop(key, None)
                self._close_socket(sock)

    def close_all(self) -> None:
        """关闭连接池中的所有连接并清空缓存（常用于系统停机、插件重载或单测复位）"""
        with self._lock:
            logger.info(f"🛑 [TCPManager] 正在清空并关闭所有 TCP 链路缓存 (共 {len(self._pool)} 条)...")
            for key, sock in list(self._pool.items()):
                self._close_socket(sock)
            self._pool.clear()
            logger.info("✅ [TCPManager] 所有硬件 TCP 链路已安全释放完毕。")

    # --------------------------------------------------------------------------
    # 可观测性与自省接口 (Observability APIs)
    # --------------------------------------------------------------------------

    def get_pool_size(self) -> int:
        """获取当前连接池中已缓存的连接总数"""
        with self._lock:
            return len(self._pool)

    def list_connections(self) -> List[str]:
        """获取当前连接池中所有已建立链路的设备键清单 (形如 ['192.168.1.10:8000', ...])"""
        with self._lock:
            return list(self._pool.keys())

    def is_connected(self, ip: str, port: int) -> bool:
        """
        查询指定设备当前是否在池中且连接处于活跃健康状态。
        
        Args:
            ip: 设备 IP 地址。
            port: 设备端口号。
            
        Returns:
            bool: 链路是否处于健康存活连接状态。
        """
        key = f"{ip}:{port}"
        with self._lock:
            if key in self._pool:
                return self._is_socket_alive(self._pool[key])
            return False


# ==============================================================================
# 兼容别名导出
# ==============================================================================
TCPPoolManager = TCPManager