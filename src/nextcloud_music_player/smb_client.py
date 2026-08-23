"""
SMB 音乐来源客户端 - 通过 pysmb 访问 SMB 共享中的音乐文件。

接口与 NextCloudClient 保持鸭子类型兼容（MusicService/FolderSelector/LyricsService
均按此事实接口调用，无需改动）：
- test_connection() -> bool
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
from typing import Callable, List, Dict, Optional

logger = logging.getLogger(__name__)

# 与 NextCloudClient.list_music_files 支持的音乐格式保持一致
MUSIC_EXTENSIONS = {'.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac', '.wma'}


def is_music_file(file_name: str) -> bool:
    """判断文件名是否为支持的音乐格式"""
    return Path(file_name).suffix.lower() in MUSIC_EXTENSIONS


def to_smb_path(folder_path: str) -> str:
    """把用户输入的共享内路径规范为 pysmb 使用的路径（以 / 开头，无尾斜杠）"""
    cleaned = (folder_path or '').strip().strip('/')
    return f"/{cleaned}" if cleaned else "/"


def format_smb_time(value) -> str:
    """pysmb 的时间字段转 ISO 字符串；不同版本可能是 datetime 或 epoch 秒"""
    if isinstance(value, datetime):
        try:
            return value.isoformat()
        except Exception:
            return ''
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value).isoformat()
        except Exception:
            return ''
    return ''


# pysmb 对不存在路径抛出的 SMBError status 片段（业务错误，不应触发重连）
_NOT_FOUND_STATUS = ('STATUS_NO_SUCH_FILE', 'STATUS_OBJECT_NAME_NOT_FOUND',
                     'STATUS_OBJECT_PATH_NOT_FOUND', 'PATH_NOT_FOUND', 'NO_SUCH_FILE')


def _is_not_found_error(exc: Exception) -> bool:
    """判断异常是否为'路径/文件不存在'（pysmb 1.x 的 SMBError.status 为字符串）"""
    status = str(getattr(exc, 'status', '') or '')
    return any(fragment in status for fragment in _NOT_FOUND_STATUS)


class SMBClient:
    """Client for accessing music files over SMB."""

    def __init__(self, host: str, username: str, password: str,
                 port: int = 445, domain: str = 'WORKGROUP', share: str = ''):
        self.host = (host or '').strip()
        self.username = username or ''
        self.password = password or ''
        try:
            self.port = int(port or 445)
        except (TypeError, ValueError):
            self.port = 445
        self.domain = (domain or '').strip() or 'WORKGROUP'
        self.share = (share or '').strip().strip('/').strip('\\')

        from .config_manager import ConfigManager
        config_manager = ConfigManager()

        # 缓存目录用于已下载的音乐文件（与 NextCloudClient 一致）
        self.cache_dir = config_manager.get_cache_directory()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._conn = None
        self._smb_lock = threading.Lock()

    # === 连接管理 ===

    def _get_conn(self):
        """获取或建立 SMB 连接（必须在持有 _smb_lock 时调用）"""
        if self._conn is not None:
            return self._conn

        if not self.host:
            raise ConnectionError("未配置 SMB 主机地址")
        if not self.share:
            raise ConnectionError("未配置 SMB 共享名称")

        from smb.SMBConnection import SMBConnection

        try:
            my_name = (socket.gethostname() or 'music-player').split('.')[0][:15]
        except Exception:
            my_name = 'music-player'

        # 445 端口为 SMB 直连 TCP；139 为传统 NetBIOS
        conn = SMBConnection(
            self.username,
            self.password,
            my_name=my_name,
            remote_name=self.host.upper(),
            domain=self.domain,
            use_ntlm_v2=True,
            is_direct_tcp=(self.port == 445),
        )
        if not conn.connect(self.host, self.port, timeout=10):
            conn.close()
            raise ConnectionError(
                f"无法连接到 SMB 服务器 {self.host}:{self.port}"
                f"（认证失败或服务器强制 SMB3 加密协议，当前实现支持 SMB1/SMB2）"
            )
        self._conn = conn
        logger.info(f"✅ SMB 连接已建立: {self.host}:{self.port} 共享 '{self.share}'")
        return self._conn

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

        if 'NtlmError' in name or 'LOGON' in msg.upper() or 'ACCESS_DENIED' in msg.upper():
            return f"SMB 认证失败，请检查用户名/密码/域（{text}）"
        if 'Timeout' in name or 'timed out' in msg.lower():
            return f"连接 SMB 服务器超时: {self.host}:{self.port}"
        if 'ConnectionRefused' in name or 'refused' in msg.lower():
            return f"SMB 服务器拒绝连接: {self.host}:{self.port}（检查端口 445/139 是否开放）"
        if 'ConnectionReset' in name or 'reset' in msg.lower():
            return (f"连接被服务器 {self.host} 重置；若服务器强制 SMB3 加密，"
                    f"当前 SMB1/SMB2 实现暂不支持，请在服务器端允许 SMB2")
        if 'NoRoute' in name or 'unreachable' in msg.lower():
            return f"网络不可达: {self.host}（检查主机地址或 VPN/局域网连接）"
        return f"SMB 操作失败: {text}"

    async def _run_in_executor(self, sync_fn: Callable):
        """与 NextCloudClient 相同模式：同步 SMB 调用放入线程池执行"""
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(executor, sync_fn)

    # === 事实接口实现 ===

    async def test_connection(self) -> bool:
        """测试连接：建立 SMB 连接并列出共享根目录验证凭据与共享可访问性"""
        def _sync():
            with self._smb_lock:
                try:
                    conn = self._get_conn()
                    conn.listPath(self.share, '/')
                    logger.info(f"✅ SMB 连接测试成功: {self.host} 共享 '{self.share}'")
                    return True
                except Exception as e:
                    self._reset_conn()
                    logger.error(f"❌ SMB 连接测试失败: {self._friendly_error(e)}")
                    return False

        return await self._run_in_executor(_sync)

    async def list_music_files(self, folder_path: str = "") -> List[Dict]:
        """列出共享内指定文件夹（单层）中的音乐文件"""
        smb_path = to_smb_path(folder_path)
        logger.info(f"🔍 [SMB_LIST] 列出音乐文件: 共享 '{self.share}' 路径 '{smb_path}'")

        def _sync():
            with self._smb_lock:
                entries = self._call(lambda conn: conn.listPath(self.share, smb_path))

            music_files = []
            for entry in entries:
                if entry.filename in ('.', '..') or entry.isDirectory:
                    continue
                if not is_music_file(entry.filename):
                    continue
                entry_path = f"{smb_path.rstrip('/')}/{entry.filename}"
                music_files.append({
                    'name': entry.filename,
                    'path': entry_path,
                    'size': entry.file_size or 0,
                    'modified': format_smb_time(entry.last_write_time),
                    'type': 'file',
                })

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
                if entry.filename in ('.', '..') or not entry.isDirectory:
                    continue
                entry_path = f"{smb_path.rstrip('/')}/{entry.filename}"
                directories.append({
                    'name': entry.filename,
                    'path': entry_path,
                    'modified': format_smb_time(entry.last_write_time),
                    'type': 'directory',
                })
            return directories

        try:
            return await self._run_in_executor(_sync)
        except Exception as e:
            error = self._friendly_error(e)
            logger.error(f"❌ [SMB_DIRS] {error}")
            raise Exception(error)

    async def download_file(self, file_path: str, file_name: str,
                            local_path: str = None) -> str:
        """从 SMB 共享下载文件到本地，返回本地路径；失败抛异常"""
        smb_path = to_smb_path(file_path)
        cached_path = Path(local_path) if local_path else self.cache_dir / file_name

        if cached_path.exists():
            logger.info(f"✅ [SMB_DOWNLOAD] 使用缓存文件: {cached_path}")
            return str(cached_path)

        logger.info(f"📥 [SMB_DOWNLOAD] 下载: '{self.share}{smb_path}' -> {cached_path}")

        def _sync():
            cached_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = cached_path.parent / (cached_path.name + '.part')
            try:
                with self._smb_lock:
                    def _do(conn):
                        with open(tmp_path, 'wb') as f:
                            conn.retrieveFile(self.share, smb_path, f)
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
                    attr = self._call(lambda conn: conn.getAttributes(self.share, smb_path))
                except Exception as e:
                    logger.debug(f"[SMB_INFO] 文件不存在或不可访问 {smb_path}: {e}")
                    return None
            return {
                'name': Path(smb_path).name,
                'size': attr.file_size or 0,
                'modified': format_smb_time(attr.last_write_time),
                'content_type': '',
            }

        return await self._run_in_executor(_sync)
