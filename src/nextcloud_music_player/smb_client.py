"""
SMB 音乐来源客户端 - 通过 pysmb 访问 SMB 共享中的音乐文件。

协议支持：SMB1 / SMB 2.002 / SMB 2.1 / SMB 3.0（未加密）——
由 smb_dialects 扩展 pysmb 的协商方言实现，iOS 上同样可用；
SMB 3.1.1 与强制签名/加密的服务器暂不支持（见 smb_dialects.py）。

接口与 NextCloudClient 保持鸭子类型兼容（MusicService/FolderSelector/LyricsService
均按此事实接口调用，无需改动）：
- test_connection() -> bool
- list_shares() -> [{'name','comment','type'}]（连接向导列举服务器共享）
- list_music_files(folder_path) -> [{'name','path','size','modified','type'}]
- list_directories(folder_path) -> [{'name','path','modified','type'}]
- download_file(file_path, file_name, local_path) -> str（本地路径，失败抛异常）
- get_file_info(file_path) -> Optional[Dict]

路径约定：所有 folder_path/file_path 均为共享（share）内的相对路径，
'/' 表示共享根目录，如 '/music/流行/song.mp3'。

pysmb 的 SMBConnection 非线程安全，所有网络操作通过 _smb_lock 串行化，
并以懒初始化 + 失效重建一次的方式复用连接。
"""

import asyncio
import concurrent.futures
import logging
import socket
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# 与 NextCloudClient.list_music_files 支持的音乐格式保持一致
MUSIC_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma"}


def is_music_file(file_name: str) -> bool:
    """判断文件名是否为支持的音乐格式"""
    return Path(file_name).suffix.lower() in MUSIC_EXTENSIONS


def to_smb_path(folder_path: str) -> str:
    """把用户输入的共享内路径规范为 pysmb 使用的路径（以 / 开头，无尾斜杠）"""
    cleaned = (folder_path or "").strip().strip("/")
    return f"/{cleaned}" if cleaned else "/"


def format_smb_time(value) -> str:
    """pysmb 的时间字段转 ISO 字符串；不同版本可能是 datetime 或 epoch 秒"""
    if isinstance(value, datetime):
        try:
            return value.isoformat()
        except Exception:
            return ""
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value).isoformat()
        except Exception:
            return ""
    return ""


# pysmb 对不存在路径抛出的 SMBError status 片段（业务错误，不应触发重连）
_NOT_FOUND_STATUS = (
    "STATUS_NO_SUCH_FILE",
    "STATUS_OBJECT_NAME_NOT_FOUND",
    "STATUS_OBJECT_PATH_NOT_FOUND",
    "PATH_NOT_FOUND",
    "NO_SUCH_FILE",
)


def _is_not_found_error(exc: Exception) -> bool:
    """判断异常是否为'路径/文件不存在'（pysmb 1.x 的 SMBError.status 为字符串）"""
    status = str(getattr(exc, "status", "") or "")
    return any(fragment in status for fragment in _NOT_FOUND_STATUS)


class SMBClient:
    """Client for accessing music files over SMB."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 445,
        domain: str = "WORKGROUP",
        share: str = "",
    ):
        self.host = (host or "").strip()
        self.username = username or ""
        self.password = password or ""
        try:
            self.port = int(port or 445)
        except (TypeError, ValueError):
            self.port = 445
        self.domain = (domain or "").strip() or "WORKGROUP"
        self.share = (share or "").strip().strip("/").strip("\\")

        from .config_manager import ConfigManager

        config_manager = ConfigManager()

        # 缓存目录用于已下载的音乐文件（与 NextCloudClient 一致）
        self.cache_dir = config_manager.get_cache_directory()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._conn = None
        self._smb_lock = threading.Lock()

    # === 连接管理 ===

    def _get_conn(self):
        """获取或建立 SMB 连接（必须在持有 _smb_lock 时调用）

        share 可为空：空 share 表示"只连接服务器"（用于列举共享的向导阶段），
        具体共享在 listPath/retrieveFile 等调用时才需要。
        """
        if self._conn is not None:
            return self._conn

        if not self.host:
            raise ConnectionError("未配置 SMB 主机地址")

        from . import smb_dialects

        # 协商支持 SMB1 / SMB 2.002 / SMB 2.1 / SMB 3.0（见 smb_dialects.py）
        smb_dialects.enable_modern_negotiation()
        conn = self._connect_once()

        self._conn = conn
        logger.info(f"✅ SMB 连接已建立: {self.host}:{self.port} 共享 '{self.share}'")
        return self._conn

    def _connect_once(self):
        """以当前方言列表建立一条新的 SMB 连接"""
        from smb.SMBConnection import SMBConnection

        try:
            my_name = (socket.gethostname() or "music-player").split(".")[0][:15]
        except Exception:
            my_name = "music-player"

        # 直连 TCP 帧格式适用于除 139（传统 NetBIOS）外的所有端口，
        # 不能按"端口==445"判断：非 445 的直连端口同样不需要 NBT 会话头
        conn = SMBConnection(
            self.username,
            self.password,
            my_name=my_name,
            remote_name=self.host.upper(),
            domain=self.domain,
            use_ntlm_v2=True,
            is_direct_tcp=(self.port != 139),
        )
        if not conn.connect(self.host, self.port, timeout=10):
            conn.close()
            raise ConnectionError(
                f"无法连接到 SMB 服务器 {self.host}:{self.port}"
                f"（认证失败或服务器要求 SMB 3.1.1/强制加密协议，"
                f"当前实现支持 SMB1/SMB2/SMB3.0-未加密）"
            )
        return conn

    def _reset_conn(self):
        """丢弃当前连接（必须在持有 _smb_lock 时调用）"""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def _call(self, fn: Callable, retry: bool = True):
        """在持有 _smb_lock 的线程中执行 fn(conn)；连接失效时重建一次重试"""
        try:
            return fn(self._get_conn())
        except Exception as e:
            if _is_not_found_error(e):
                # 路径不存在属于业务错误（如探测歌词文件），连接本身有效
                raise
            self._reset_conn()
            if retry:
                logger.warning("SMB 操作失败，重建连接后重试一次")
                return self._call(fn, retry=False)
            raise

    def _friendly_error(self, exc: Exception) -> str:
        """把底层异常翻译为可读的中文提示"""
        name = type(exc).__name__
        msg = str(exc)
        text = f"{name}: {msg}" if msg else name

        # 服务器只接受 pysmb 无法协商的协议（SMB 3.1.1 / 强制签名或加密）
        if (
            "does not support any of the" in msg
            or ("ProtocolError" in name and "dialect" in msg.lower())
        ):
            return (
                f"服务器 {self.host} 要求 SMB 3.1.1 或强制签名/加密，"
                f"当前实现最高支持 SMB 3.0（未加密）。可在服务器端放宽协议要求"
                f"（Samba: server min protocol = SMB2，并关闭强制加密），"
                f"或改用支持 SMB 2/3 的共享主机"
            )
        if (
            "NtlmError" in name
            or "LOGON" in msg.upper()
            or "ACCESS_DENIED" in msg.upper()
        ):
            return f"SMB 认证失败，请检查用户名/密码/域（{text}）"
        if "Timeout" in name or "timed out" in msg.lower():
            return f"连接 SMB 服务器超时: {self.host}:{self.port}"
        if "ConnectionRefused" in name or "refused" in msg.lower():
            return f"SMB 服务器拒绝连接: {self.host}:{self.port}（检查端口 445/139 是否开放）"
        if "ConnectionReset" in name or "reset" in msg.lower():
            return (
                f"连接被服务器 {self.host} 重置；若服务器强制 SMB3 加密，"
                f"当前 SMB1/SMB2 实现暂不支持，请在服务器端允许 SMB2"
            )
        if "NoRoute" in name or "unreachable" in msg.lower():
            return f"网络不可达: {self.host}（检查主机地址或 VPN/局域网连接）"
        return f"SMB 操作失败: {text}"

    async def _run_in_executor(self, sync_fn: Callable):
        """与 NextCloudClient 相同模式：同步 SMB 调用放入线程池执行"""
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(executor, sync_fn)

    # === 事实接口实现 ===

    async def list_shares(self) -> List[Dict]:
        """列出服务器上可访问的共享（连接向导用），返回 [{'name','comment','type'}]"""
        logger.info(f"🔍 [SMB_SHARES] 列出服务器共享: {self.host}:{self.port}")

        def _sync():
            with self._smb_lock:
                shares = self._call(lambda conn: conn.listShares())

            result = []
            for share in shares:
                if share.isSpecial:
                    # IPC$ / ADMIN$ 等管理共享对音乐播放无意义
                    continue
                result.append(
                    {
                        "name": share.name,
                        "comment": getattr(share, "comments", "") or "",
                        "type": "share",
                    }
                )
            logger.info(f"✅ [SMB_SHARES] 找到 {len(result)} 个共享")
            return result

        try:
            return await self._run_in_executor(_sync)
        except Exception as e:
            error = self._friendly_error(e)
            logger.error(f"❌ [SMB_SHARES] {error}")
            raise Exception(error)

    async def test_connection(self) -> bool:
        """测试连接：验证认证可用的前提下，列出共享根目录（或共享列表）"""

        def _sync():
            with self._smb_lock:
                try:
                    conn = self._get_conn()
                    if self.share:
                        conn.listPath(self.share, "/")
                        logger.info(
                            f"✅ SMB 连接测试成功: {self.host} 共享 '{self.share}'"
                        )
                    else:
                        # 未指定共享（向导第一阶段）：能列出共享即认证通过
                        conn.listShares()
                        logger.info(f"✅ SMB 连接测试成功: {self.host}（未指定共享）")
                    return True
                except Exception as e:
                    self._reset_conn()
                    logger.error(f"❌ SMB 连接测试失败: {self._friendly_error(e)}")
                    return False

        return await self._run_in_executor(_sync)

    async def list_music_files(self, folder_path: str = "") -> List[Dict]:
        """列出共享内指定文件夹（单层）中的音乐文件"""
        smb_path = to_smb_path(folder_path)
        logger.info(
            f"🔍 [SMB_LIST] 列出音乐文件: 共享 '{self.share}' 路径 '{smb_path}'"
        )

        def _sync():
            with self._smb_lock:
                entries = self._call(lambda conn: conn.listPath(self.share, smb_path))

            music_files = []
            for entry in entries:
                if entry.filename in (".", "..") or entry.isDirectory:
                    continue
                if not is_music_file(entry.filename):
                    continue
                entry_path = f"{smb_path.rstrip('/')}/{entry.filename}"
                music_files.append(
                    {
                        "name": entry.filename,
                        "path": entry_path,
                        "size": entry.file_size or 0,
                        "modified": format_smb_time(entry.last_write_time),
                        "type": "file",
                    }
                )

            logger.info(f"✅ [SMB_LIST] 找到 {len(music_files)} 个音乐文件")
            return music_files

        try:
            return await self._run_in_executor(_sync)
        except Exception as e:
            error = self._friendly_error(e)
            logger.error(f"❌ [SMB_LIST] {error}")
            raise Exception(error)

    async def list_directories(self, folder_path: str = "") -> List[Dict]:
        """列出共享内指定文件夹（单层）中的子目录，供 FolderSelector 浏览"""
        smb_path = to_smb_path(folder_path)

        def _sync():
            with self._smb_lock:
                entries = self._call(lambda conn: conn.listPath(self.share, smb_path))

            directories = []
            for entry in entries:
                if entry.filename in (".", "..") or not entry.isDirectory:
                    continue
                entry_path = f"{smb_path.rstrip('/')}/{entry.filename}"
                directories.append(
                    {
                        "name": entry.filename,
                        "path": entry_path,
                        "modified": format_smb_time(entry.last_write_time),
                        "type": "directory",
                    }
                )
            return directories

        try:
            return await self._run_in_executor(_sync)
        except Exception as e:
            error = self._friendly_error(e)
            logger.error(f"❌ [SMB_DIRS] {error}")
            raise Exception(error)

    async def download_file(
        self,
        file_path: str,
        file_name: str,
        local_path: str = None,
        progress_callback=None,
    ) -> str:
        """从 SMB 共享下载文件到本地，返回本地路径；失败抛异常"""
        smb_path = to_smb_path(file_path)
        cached_path = Path(local_path) if local_path else self.cache_dir / file_name

        if cached_path.exists():
            logger.info(f"✅ [SMB_DOWNLOAD] 使用缓存文件: {cached_path}")
            return str(cached_path)

        logger.info(
            f"📥 [SMB_DOWNLOAD] 下载: '{self.share}{smb_path}' -> {cached_path}"
        )

        def _sync():
            cached_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = cached_path.parent / (cached_path.name + ".part")
            try:
                with self._smb_lock:

                    def _do(conn):
                        total = 0
                        try:
                            total = (
                                conn.getAttributes(self.share, smb_path).file_size or 0
                            )
                        except Exception:
                            pass
                        with open(tmp_path, "wb") as f:

                            class ProgressWriter:
                                def write(self, data):
                                    written = f.write(data)
                                    if progress_callback:
                                        progress_callback(f.tell(), total)
                                    return written

                                def __getattr__(self, name):
                                    return getattr(f, name)

                            conn.retrieveFile(self.share, smb_path, ProgressWriter())

                    self._call(_do)
                tmp_path.replace(cached_path)
                logger.info(f"✅ [SMB_DOWNLOAD] 下载完成: {cached_path}")
                return str(cached_path)
            except Exception:
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass
                raise

        try:
            return await self._run_in_executor(_sync)
        except Exception as e:
            error = self._friendly_error(e)
            logger.error(f"❌ [SMB_DOWNLOAD] 下载 {file_name} 失败: {error}")
            raise Exception(error)

    async def get_file_info(self, file_path: str) -> Optional[Dict]:
        """获取文件属性（歌词服务用于探测 .lrc 是否存在），不存在返回 None"""
        smb_path = to_smb_path(file_path)

        def _sync():
            with self._smb_lock:
                try:
                    attr = self._call(
                        lambda conn: conn.getAttributes(self.share, smb_path)
                    )
                except Exception as e:
                    logger.debug(f"[SMB_INFO] 文件不存在或不可访问 {smb_path}: {e}")
                    return None
            return {
                "name": Path(smb_path).name,
                "size": attr.file_size or 0,
                "modified": format_smb_time(attr.last_write_time),
                "content_type": "",
            }

        return await self._run_in_executor(_sync)
