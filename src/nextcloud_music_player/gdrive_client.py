"""
Google Drive 音乐来源客户端 - 基于纯 requests 实现 Drive REST API v3。

不引入 google-api-python-client（依赖链过重，且 iOS serious-python 打包要求
来源库纯 Python），仅用 requests 覆盖列出/下载所需的三个端点。

接口与 NextCloudClient/SMBClient 保持鸭子类型兼容（MusicService/FolderSelector/
LyricsService 均按此事实接口调用，无需改动）：
- test_connection() -> bool
- list_music_files(folder_path) -> [{'name','path','size','modified','type'}]
- list_directories(folder_path) -> [{'name','path','modified','type'}]
- download_file(file_path, file_name, local_path) -> str（本地路径，失败抛异常）
- get_file_info(file_path) -> Optional[Dict]

路径约定：Google Drive 按 ID 而非路径组织文件，因此 folder_path/file_path
均为 Drive 的文件/文件夹 ID；''、'/'、'root' 归一化为根目录别名 'root'。

授权：OAuth 2.0 桌面应用流程（用户在 Google Cloud Console 创建 OAuth 客户端，
填入 Client ID/Secret 后经系统浏览器授权，loopback 回调回收授权码），
权限范围 drive.readonly。access_token 过期前自动用 refresh_token 刷新，
刷新结果经 on_tokens_updated 回调交由调用方持久化。
"""

import asyncio
import concurrent.futures
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlencode, urlparse

import requests

logger = logging.getLogger(__name__)

# 与 NextCloudClient/SMBClient 支持的音乐格式保持一致
MUSIC_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma"}

FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
OAUTH_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"

# 只读访问全部 Drive 文件（用户可在其中任选音乐文件夹）
OAUTH_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# access_token 有效期约 1 小时，提前刷新避免边界失败
_TOKEN_EXPIRY_SKEW = 60.0

# 桌面 loopback 重定向的候选端口（RFC 8252 允许 127.0.0.1 任意端口）。
# 优先固定端口：端到端测试可以直达回调地址，防火墙也只需放行一次；
# 被占用时按序回退，全部不可用退回系统随机端口。
PREFERRED_LOOPBACK_PORTS = (53691, 53692, 53693)

_LIST_PAGE_SIZE = 200
_DOWNLOAD_CHUNK_SIZE = 128 * 1024


def is_music_file(file_name: str) -> bool:
    """判断文件名是否为支持的音乐格式"""
    return Path(file_name).suffix.lower() in MUSIC_EXTENSIONS


def normalize_folder_path(folder_path: str) -> str:
    """把 folder_path 归一化为 Drive 文件夹 ID；''、'/'、'root' 均视为根目录"""
    cleaned = (folder_path or "").strip().strip("/")
    if not cleaned or cleaned == "root":
        return "root"
    return cleaned


def resolve_endpoints(api_base_url: str = "") -> Dict[str, str]:
    """把自定义 API 基础地址解析为三个端点；留空时返回 Google 官方端点。

    自定义地址形如 ``http://127.0.0.1:8931``（设置页「谷歌云盘」可配置），
    派生规则：Drive API = {base}/drive/v3，OAuth 授权页 = {base}/auth，
    OAuth 令牌 = {base}/token。官方端点域名各不相同，无法从一个地址派生，
    因此仅在自定义地址生效时统一派生。
    """
    base = (api_base_url or "").strip().rstrip("/")
    if not base:
        return {
            "drive_api": DRIVE_API_BASE,
            "oauth_auth": OAUTH_AUTH_URL,
            "oauth_token": OAUTH_TOKEN_URL,
        }
    return {
        "drive_api": f"{base}/drive/v3",
        "oauth_auth": f"{base}/auth",
        "oauth_token": f"{base}/token",
    }


# === OAuth 辅助（模块级纯函数，便于连接页与测试复用） ===


def build_authorization_url(
    client_id: str, redirect_uri: str, auth_url: str = None
) -> str:
    """构建 Google 授权页 URL；prompt=consent 确保每次都签发 refresh_token"""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(OAUTH_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{auth_url or OAUTH_AUTH_URL}?{urlencode(params)}"


def _request_tokens(data: Dict, session=None, token_url: str = None) -> Dict:
    """POST 令牌端点的公共实现，失败时抛出带原因的 RuntimeError"""
    poster = session if session is not None else requests
    resp = poster.post(token_url or OAUTH_TOKEN_URL, data=data, timeout=(10, 30))
    payload = {}
    try:
        payload = resp.json()
    except Exception:
        pass
    if resp.status_code != 200 or "access_token" not in payload:
        reason = payload.get("error", f"HTTP {resp.status_code}")
        raise RuntimeError(f"Google OAuth 令牌获取失败: {reason}")
    return payload


def exchange_authorization_code(
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    session=None,
    token_url: str = None,
) -> Dict:
    """用授权码换取令牌，返回 {access_token, refresh_token, expires_in, ...}"""
    return _request_tokens(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        session=session,
        token_url=token_url,
    )


def refresh_access_token(
    client_id: str, client_secret: str, refresh_token: str, session=None,
    token_url: str = None,
) -> Dict:
    """用 refresh_token 换取新的 access_token"""
    return _request_tokens(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        session=session,
        token_url=token_url,
    )


class LoopbackOAuthReceiver:
    """在本机随机端口监听 OAuth 重定向，捕获浏览器回传的授权码。

    Google 对"桌面应用"类型客户端允许 http://127.0.0.1:任意端口 的
    loopback 重定向（RFC 8252），无需在控制台逐一登记端口。
    """

    def __init__(self):
        self._server: Optional[ThreadingHTTPServer] = None
        self._redirect_uri: str = ""
        self._code: Optional[str] = None
        self._error: Optional[str] = None
        self._done = threading.Event()

    @property
    def redirect_uri(self) -> str:
        # start() 时记录 URI，close() 后仍可读取：OAuth 换取令牌必须传
        # 与授权请求完全相同的 redirect_uri，即使监听器已关闭；
        # 未曾启动时才视为错误
        if not self._redirect_uri:
            raise RuntimeError("接收器尚未启动")
        return self._redirect_uri

    def start(self):
        receiver = self

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse(self.path)
                if parsed.path not in ("", "/"):
                    self.send_error(404)
                    return
                query = parse_qs(parsed.query)
                receiver._code = (query.get("code") or [None])[0]
                receiver._error = (query.get("error") or [None])[0]
                receiver._done.set()
                body = (
                    "<h2>✅ 授权成功，请返回音乐播放器应用</h2>"
                    if receiver._code
                    else "<h2>❌ 授权失败，请返回应用重试</h2>"
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                # 静默默认的请求日志，避免刷屏
                pass

        self._server = None
        for port in (*PREFERRED_LOOPBACK_PORTS, 0):
            try:
                self._server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
                break
            except OSError:
                continue
        if self._server is None:
            raise OSError("无法绑定 loopback 回调端口")
        self._redirect_uri = f"http://127.0.0.1:{self._server.server_address[1]}"
        threading.Thread(
            target=self._server.serve_forever, daemon=True, name="gdrive-oauth"
        ).start()
        logger.info(f"📡 [GDRIVE_OAUTH] loopback 接收器已启动: {self.redirect_uri}")

    def wait_for_code(self, timeout: float = 300.0) -> str:
        """阻塞等待授权码；超时或 Google 返回错误时抛异常"""
        try:
            if not self._done.wait(timeout):
                raise TimeoutError("等待浏览器完成授权超时")
            if self._error:
                raise RuntimeError(f"Google 返回授权错误: {self._error}")
            if not self._code:
                raise RuntimeError("重定向中缺少授权码")
            return self._code
        finally:
            self.close()

    def close(self):
        if self._server is not None:
            server, self._server = self._server, None
            # shutdown 等待 serve_forever 退出（至多一个 poll 周期），
            # server_close 释放监听端口；只 shutdown 不 close 会泄漏 socket，
            # 固定优先端口被泄漏端口占满后就只能回退随机端口
            server.shutdown()
            server.server_close()


class GoogleDriveClient:
    """Client for accessing music files on Google Drive."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str = "",
        access_token: str = "",
        token_expiry: float = 0.0,
        session=None,
        on_tokens_updated: Optional[Callable[[Dict], None]] = None,
        api_base_url: str = "",
    ):
        self.client_id = (client_id or "").strip()
        self.client_secret = client_secret or ""
        self.refresh_token = (refresh_token or "").strip()
        self.access_token = access_token or ""
        try:
            self.token_expiry = float(token_expiry or 0)
        except (TypeError, ValueError):
            self.token_expiry = 0.0
        self._session = session if session is not None else requests.Session()
        self._on_tokens_updated = on_tokens_updated
        self._token_lock = threading.Lock()
        # 自定义 API 地址（设置页「谷歌云盘」配置，测试/自建网关用），留空走官方
        endpoints = resolve_endpoints(api_base_url)
        self._drive_api_base = endpoints["drive_api"]
        self._oauth_token_url = endpoints["oauth_token"]
        self._oauth_auth_url = endpoints["oauth_auth"]

        from .config_manager import ConfigManager

        config_manager = ConfigManager()

        # 缓存目录用于已下载的音乐文件（与 NextCloudClient/SMBClient 一致）
        self.cache_dir = config_manager.get_cache_directory()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # === 令牌管理 ===

    def _token_is_valid(self) -> bool:
        return bool(self.access_token) and (
            time.time() < self.token_expiry - _TOKEN_EXPIRY_SKEW
        )

    def _refresh_tokens_locked(self):
        """刷新 access_token（必须在持有 _token_lock 时调用）"""
        if not self.refresh_token:
            raise ConnectionError(
                "缺少 Refresh Token，请先在连接页完成 Google 账号授权"
            )
        try:
            payload = refresh_access_token(
                self.client_id,
                self.client_secret,
                self.refresh_token,
                session=self._session,
                token_url=self._oauth_token_url,
            )
        except RuntimeError as e:
            if "invalid_grant" in str(e) or "invalid_client" in str(e):
                raise ConnectionError(f"Google 授权已失效，请重新授权（{e}）")
            raise
        self.access_token = payload.get("access_token", "")
        try:
            self.token_expiry = time.time() + int(payload.get("expires_in", 3600))
        except (TypeError, ValueError):
            self.token_expiry = time.time() + 3600
        # Google 通常不轮换 refresh_token，但响应携带时以新值为准
        new_refresh_token = payload.get("refresh_token")
        if new_refresh_token:
            self.refresh_token = new_refresh_token
        self._notify_tokens_updated()
        logger.info("✅ [GDRIVE_TOKEN] access_token 已刷新")

    def _notify_tokens_updated(self):
        if self._on_tokens_updated is None:
            return
        try:
            self._on_tokens_updated(
                {
                    "access_token": self.access_token,
                    "refresh_token": self.refresh_token,
                    "token_expiry": self.token_expiry,
                }
            )
        except Exception as e:
            logger.warning(f"持久化 Google Drive 令牌失败: {e}")

    def _get_access_token(self) -> str:
        with self._token_lock:
            if not self._token_is_valid():
                self._refresh_tokens_locked()
            return self.access_token

    def _force_refresh(self):
        with self._token_lock:
            self._refresh_tokens_locked()

    # === 请求封装 ===

    def _api_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        stream: bool = False,
        timeout=(15, 60),
    ):
        """携带 Bearer 令牌发起请求；401 时强制刷新令牌重试一次"""
        headers = {"Authorization": f"Bearer {self._get_access_token()}"}
        resp = self._session.request(
            method, url, headers=headers, params=params, stream=stream, timeout=timeout
        )
        if resp.status_code == 401:
            resp.close()
            logger.warning("⚠️ [GDRIVE_API] 收到 401，刷新令牌后重试")
            self._force_refresh()
            headers = {"Authorization": f"Bearer {self.access_token}"}
            resp = self._session.request(
                method,
                url,
                headers=headers,
                params=params,
                stream=stream,
                timeout=timeout,
            )
        return resp

    def _friendly_error(self, exc: Exception) -> str:
        """把底层异常翻译为可读的中文提示"""
        if isinstance(exc, ConnectionError):
            return str(exc)
        if isinstance(exc, requests.HTTPError):
            status = exc.response.status_code if exc.response is not None else 0
            if status in (401, 403):
                return (
                    f"Google Drive 拒绝访问 (HTTP {status})，"
                    f"授权可能已失效或超出配额，请在连接页重新授权"
                )
            if status == 404:
                return "Google Drive 文件不存在 (HTTP 404)"
            if status == 429:
                return "Google Drive API 配额不足 (HTTP 429)，请稍后重试"
            return f"Google Drive API 错误: HTTP {status}"
        if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
            return f"无法连接 Google 服务（检查网络或代理）: {exc}"
        return f"Google Drive 操作失败: {exc}"

    async def _run_in_executor(self, sync_fn: Callable):
        """与 NextCloudClient/SMBClient 相同模式：同步调用放入线程池执行"""
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(executor, sync_fn)

    # === 事实接口实现 ===

    async def test_connection(self) -> bool:
        """测试连接：验证 OAuth 令牌可访问当前 Google 账号"""

        def _sync():
            try:
                resp = self._api_request(
                    "GET",
                    f"{self._drive_api_base}/about",
                    params={"fields": "user(displayName)"},
                )
                resp.raise_for_status()
                display_name = resp.json().get("user", {}).get("displayName", "")
                logger.info(
                    f"✅ Google Drive 连接测试成功{f'（{display_name}）' if display_name else ''}"
                )
                return True
            except Exception as e:
                logger.error(f"❌ Google Drive 连接测试失败: {self._friendly_error(e)}")
                return False

        return await self._run_in_executor(_sync)

    def _list_children_sync(self, folder_id: str, folders_only: bool) -> List[Dict]:
        """列出文件夹（单层）内容并分页聚合，按 music/目录 过滤映射为事实接口结构"""
        query = f"'{folder_id}' in parents and trashed = false"
        if folders_only:
            query += f" and mimeType = '{FOLDER_MIME_TYPE}'"

        items: List[Dict] = []
        page_token = None
        while True:
            params = {
                "q": query,
                "pageSize": _LIST_PAGE_SIZE,
                "fields": "nextPageToken, files(id, name, size, modifiedTime, mimeType)",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            }
            if page_token:
                params["pageToken"] = page_token
            resp = self._api_request(
                "GET", f"{self._drive_api_base}/files", params=params
            )
            resp.raise_for_status()
            payload = resp.json()

            for item in payload.get("files", []):
                name = item.get("name", "")
                item_id = item.get("id", "")
                modified = item.get("modifiedTime", "")
                if item.get("mimeType") == FOLDER_MIME_TYPE:
                    if not folders_only:
                        continue
                    items.append(
                        {
                            "name": name,
                            "path": item_id,
                            "modified": modified,
                            "type": "directory",
                        }
                    )
                else:
                    if folders_only or not is_music_file(name):
                        continue
                    items.append(
                        {
                            "name": name,
                            "path": item_id,
                            # Drive 的 size 是字符串
                            "size": int(item.get("size") or 0),
                            "modified": modified,
                            "type": "file",
                        }
                    )

            page_token = payload.get("nextPageToken")
            if not page_token:
                break
        return items

    async def list_music_files(self, folder_path: str = "") -> List[Dict]:
        """列出指定文件夹（单层）中的音乐文件，path 为 Drive 文件 ID"""
        folder_id = normalize_folder_path(folder_path)
        logger.info(f"🔍 [GDRIVE_LIST] 列出音乐文件: 文件夹 '{folder_id}'")

        try:
            files = await self._run_in_executor(
                lambda: self._list_children_sync(folder_id, folders_only=False)
            )
            logger.info(f"✅ [GDRIVE_LIST] 找到 {len(files)} 个音乐文件")
            return files
        except Exception as e:
            error = self._friendly_error(e)
            logger.error(f"❌ [GDRIVE_LIST] {error}")
            raise Exception(error)

    async def list_directories(self, folder_path: str = "") -> List[Dict]:
        """列出指定文件夹（单层）中的子目录，path 为 Drive 文件夹 ID"""
        folder_id = normalize_folder_path(folder_path)

        try:
            return await self._run_in_executor(
                lambda: self._list_children_sync(folder_id, folders_only=True)
            )
        except Exception as e:
            error = self._friendly_error(e)
            logger.error(f"❌ [GDRIVE_DIRS] {error}")
            raise Exception(error)

    async def download_file(
        self,
        file_path: str,
        file_name: str,
        local_path: str = None,
        progress_callback=None,
    ) -> str:
        """从 Google Drive 下载文件到本地，返回本地路径；失败抛异常"""
        file_id = (file_path or "").strip().strip("/")
        cached_path = Path(local_path) if local_path else self.cache_dir / file_name

        if cached_path.exists():
            logger.info(f"✅ [GDRIVE_DOWNLOAD] 使用缓存文件: {cached_path}")
            return str(cached_path)

        logger.info(f"📥 [GDRIVE_DOWNLOAD] 下载: '{file_id}' -> {cached_path}")

        def _sync():
            cached_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = cached_path.parent / (cached_path.name + ".part")
            resp = None
            try:
                resp = self._api_request(
                    "GET",
                    f"{self._drive_api_base}/files/{file_id}",
                    params={"alt": "media"},
                    stream=True,
                    timeout=(15, None),
                )
                resp.raise_for_status()
                total = int(resp.headers.get("Content-Length") or 0)
                downloaded = 0
                with open(tmp_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=_DOWNLOAD_CHUNK_SIZE):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total)
                tmp_path.replace(cached_path)
                logger.info(f"✅ [GDRIVE_DOWNLOAD] 下载完成: {cached_path}")
                return str(cached_path)
            except Exception:
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass
                raise
            finally:
                if resp is not None:
                    resp.close()

        try:
            return await self._run_in_executor(_sync)
        except Exception as e:
            error = self._friendly_error(e)
            logger.error(f"❌ [GDRIVE_DOWNLOAD] 下载 {file_name} 失败: {error}")
            raise Exception(error)

    async def get_file_info(self, file_path: str) -> Optional[Dict]:
        """获取文件属性（歌词服务用于探测 .lrc 是否存在），不存在返回 None"""
        file_id = (file_path or "").strip().strip("/")

        def _sync():
            try:
                resp = self._api_request(
                    "GET",
                    f"{self._drive_api_base}/files/{file_id}",
                    params={
                        "fields": "id,name,size,modifiedTime,mimeType",
                        "supportsAllDrives": "true",
                    },
                )
                if resp.status_code == 404:
                    logger.debug(f"[GDRIVE_INFO] 文件不存在或不可访问 {file_id}")
                    return None
                resp.raise_for_status()
                item = resp.json()
                return {
                    "name": item.get("name", ""),
                    "size": int(item.get("size") or 0),
                    "modified": item.get("modifiedTime", ""),
                    "content_type": item.get("mimeType", ""),
                }
            except requests.HTTPError:
                logger.debug(f"[GDRIVE_INFO] 文件不可访问 {file_id}")
                return None

        return await self._run_in_executor(_sync)
