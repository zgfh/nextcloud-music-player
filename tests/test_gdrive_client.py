"""
GoogleDriveClient 单元测试 - 不发起真实网络请求

OAuth 辅助函数用注入的假 session 验证；客户端方法通过 session 注入点
（GoogleDriveClient(session=...)）覆盖令牌刷新、列表映射/过滤、
下载进度、错误翻译等路径；LoopbackOAuthReceiver 用真实本机 HTTP 请求
端到端验证（与 mock_nextcloud 的自环思路一致）。
"""

import asyncio
import socket
import time
from pathlib import Path

import pytest
import requests

from nextcloud_music_player import gdrive_client as gdrive
from nextcloud_music_player.gdrive_client import GoogleDriveClient


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """把 ConfigManager 的目录指到临时目录，避免测试触碰真实用户配置"""
    from nextcloud_music_player.config_manager import ConfigManager

    monkeypatch.setattr(ConfigManager, "_get_config_directory", lambda self: tmp_path)
    return tmp_path


class FakeResponse:
    """requests.Response 替身"""

    def __init__(self, status_code=200, json_data=None, headers=None, chunks=None):
        self.status_code = status_code
        self._json = json_data
        self.headers = headers or {}
        self._chunks = chunks if chunks is not None else []
        self.closed = False

    def json(self):
        if self._json is None:
            raise ValueError("该响应没有 JSON 体")
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def iter_content(self, chunk_size=None):
        yield from self._chunks

    def close(self):
        self.closed = True


class FakeSession:
    """requests.Session 替身：按谓词路由预设响应，记录全部出站请求"""

    def __init__(self):
        self.requests = []  # [{"method", "url", "kwargs"}]
        self._routes = []  # [(predicate, FakeResponse | 零参可调用)]

    def route(self, predicate, provider):
        self._routes.append((predicate, provider))

    def _match(self, method, url, kwargs):
        self.requests.append({"method": method, "url": url, "kwargs": kwargs})
        for predicate, provider in self._routes:
            try:
                matched = predicate(method, url, kwargs)
            except Exception:
                matched = False
            if matched:
                return provider() if callable(provider) else provider
        raise AssertionError(f"FakeSession 收到未预期的请求: {method} {url} {kwargs}")

    def request(self, method, url, **kwargs):
        return self._match(method, url, kwargs)

    def post(self, url, data=None, timeout=None, **kwargs):
        return self._match("POST", url, {"data": data, "timeout": timeout, **kwargs})

    def calls(self, method=None):
        return [r for r in self.requests if method is None or r["method"] == method]


def valid_token_client(session, **kwargs) -> GoogleDriveClient:
    """构造带有效令牌的客户端（跳过首次刷新）"""
    return GoogleDriveClient(
        client_id="cid",
        client_secret="csecret",
        refresh_token="rt",
        access_token="tok",
        token_expiry=time.time() + 3600,
        session=session,
        **kwargs,
    )


def route_token_refresh(session, access_token="newtok", status=200, error=None):
    payload = {"access_token": access_token, "expires_in": 3600}
    if error:
        payload = {"error": error}
    session.route(
        lambda m, u, kw: u == gdrive.OAUTH_TOKEN_URL
        and (kw.get("data") or {}).get("grant_type") == "refresh_token",
        FakeResponse(status_code=status, json_data=payload),
    )


# === 路径与 OAuth 辅助 ===


def test_normalize_folder_path():
    assert gdrive.normalize_folder_path("") == "root"
    assert gdrive.normalize_folder_path("/") == "root"
    assert gdrive.normalize_folder_path("root") == "root"
    assert gdrive.normalize_folder_path("/1AbC/") == "1AbC"
    assert gdrive.normalize_folder_path("  folderId  ") == "folderId"


def test_build_authorization_url_contains_required_params():
    url = gdrive.build_authorization_url("cid", "http://127.0.0.1:8080")
    assert url.startswith(gdrive.OAUTH_AUTH_URL)
    assert "client_id=cid" in url
    assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A8080" in url
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "drive.readonly" in url


def test_exchange_authorization_code_parses_payload():
    session = FakeSession()
    session.route(
        lambda m, u, kw: u == gdrive.OAUTH_TOKEN_URL,
        FakeResponse(
            json_data={
                "access_token": "at",
                "refresh_token": "rt",
                "expires_in": 3600,
            }
        ),
    )

    payload = gdrive.exchange_authorization_code(
        "cid", "csecret", "code123", "http://127.0.0.1:8080", session=session
    )

    assert payload["access_token"] == "at"
    assert payload["refresh_token"] == "rt"
    sent = session.calls("POST")[0]["kwargs"]["data"]
    assert sent["grant_type"] == "authorization_code"
    assert sent["code"] == "code123"


def test_token_helpers_raise_with_reason_on_error():
    session = FakeSession()
    session.route(
        lambda m, u, kw: u == gdrive.OAUTH_TOKEN_URL,
        FakeResponse(status_code=400, json_data={"error": "invalid_grant"}),
    )

    with pytest.raises(RuntimeError, match="invalid_grant"):
        gdrive.refresh_access_token("cid", "csecret", "rt", session=session)


def test_loopback_receiver_captures_code_end_to_end():
    receiver = gdrive.LoopbackOAuthReceiver()
    receiver.start()
    try:
        resp = requests.get(receiver.redirect_uri, params={"code": "abc123"}, timeout=5)
        assert resp.status_code == 200
        assert "授权成功" in resp.text
        assert receiver.wait_for_code(timeout=5) == "abc123"
    finally:
        receiver.close()


def test_loopback_receiver_surfaces_error_param():
    receiver = gdrive.LoopbackOAuthReceiver()
    receiver.start()
    try:
        requests.get(
            receiver.redirect_uri, params={"error": "access_denied"}, timeout=5
        )
        with pytest.raises(RuntimeError, match="access_denied"):
            receiver.wait_for_code(timeout=5)
    finally:
        receiver.close()


def test_loopback_receiver_times_out():
    receiver = gdrive.LoopbackOAuthReceiver()
    receiver.start()
    try:
        with pytest.raises(TimeoutError):
            receiver.wait_for_code(timeout=0.05)
    finally:
        receiver.close()


def test_loopback_receiver_uri_survives_close():
    """回归：wait_for_code 返回时接收器已关闭，但换取令牌必须携带与
    授权请求完全相同的 redirect_uri（OAuth 规范），close 后仍需可读"""
    receiver = gdrive.LoopbackOAuthReceiver()
    receiver.start()
    uri = receiver.redirect_uri
    try:
        requests.get(uri, params={"code": "abc"}, timeout=5)
        assert receiver.wait_for_code(timeout=5) == "abc"
    finally:
        receiver.close()

    assert receiver._server is None  # 监听器确已关闭
    assert receiver.redirect_uri == uri  # URI 仍可读

    # 未曾启动过的接收器才报"尚未启动"
    assert pytest.raises(RuntimeError, lambda: gdrive.LoopbackOAuthReceiver().redirect_uri)


# === 列表与映射 ===


def test_list_music_files_maps_and_filters(config_dir):
    session = FakeSession()
    session.route(
        lambda m, u, kw: u == f"{gdrive.DRIVE_API_BASE}/files",
        FakeResponse(
            json_data={
                "files": [
                    {
                        "id": "f1",
                        "name": "song.mp3",
                        "size": "12345",
                        "modifiedTime": "2026-08-01T00:00:00Z",
                        "mimeType": "audio/mpeg",
                    },
                    {
                        "id": "d1",
                        "name": "专辑",
                        "mimeType": gdrive.FOLDER_MIME_TYPE,
                    },
                    {
                        "id": "f2",
                        "name": "cover.jpg",
                        "size": "99",
                        "mimeType": "image/jpeg",
                    },
                    {
                        "id": "f3",
                        "name": "track.flac",
                        "size": "7",
                        "modifiedTime": "2026-08-02T00:00:00Z",
                        "mimeType": "audio/flac",
                    },
                ]
            }
        ),
    )
    client = valid_token_client(session)

    files = asyncio.run(client.list_music_files("/"))

    assert [f["name"] for f in files] == ["song.mp3", "track.flac"]
    assert files[0]["path"] == "f1"
    assert files[0]["size"] == 12345  # Drive 的 size 字符串转 int
    assert files[0]["type"] == "file"
    assert files[0]["modified"] == "2026-08-01T00:00:00Z"
    q = session.calls("GET")[0]["kwargs"]["params"]["q"]
    assert "'root' in parents" in q and "trashed = false" in q


def test_list_music_files_paginates(config_dir):
    session = FakeSession()
    pages = [
        FakeResponse(
            json_data={
                "files": [
                    {"id": "a", "name": "1.mp3", "size": "1", "mimeType": "audio/mpeg"}
                ],
                "nextPageToken": "PAGE2",
            }
        ),
        FakeResponse(
            json_data={
                "files": [
                    {"id": "b", "name": "2.mp3", "size": "2", "mimeType": "audio/mpeg"}
                ]
            }
        ),
    ]
    session.route(
        lambda m, u, kw: u == f"{gdrive.DRIVE_API_BASE}/files",
        lambda: pages.pop(0),
    )
    client = valid_token_client(session)

    files = asyncio.run(client.list_music_files("folderX"))

    assert [f["name"] for f in files] == ["1.mp3", "2.mp3"]
    gets = session.calls("GET")
    assert gets[0]["kwargs"]["params"].get("pageToken") is None
    assert gets[1]["kwargs"]["params"]["pageToken"] == "PAGE2"
    assert "'folderX' in parents" in gets[0]["kwargs"]["params"]["q"]


def test_list_directories_returns_only_folders(config_dir):
    session = FakeSession()
    session.route(
        lambda m, u, kw: u == f"{gdrive.DRIVE_API_BASE}/files",
        FakeResponse(
            json_data={
                "files": [
                    {"id": "d1", "name": "音乐", "mimeType": gdrive.FOLDER_MIME_TYPE},
                    {
                        "id": "f1",
                        "name": "a.mp3",
                        "size": "1",
                        "mimeType": "audio/mpeg",
                    },
                    {"id": "d2", "name": "备份", "mimeType": gdrive.FOLDER_MIME_TYPE},
                ]
            }
        ),
    )
    client = valid_token_client(session)

    dirs = asyncio.run(client.list_directories(""))

    assert [d["path"] for d in dirs] == ["d1", "d2"]
    assert all(d["type"] == "directory" for d in dirs)
    q = session.calls("GET")[0]["kwargs"]["params"]["q"]
    assert gdrive.FOLDER_MIME_TYPE in q


# === 下载 ===


def test_download_file_streams_and_reports_progress(config_dir):
    session = FakeSession()
    session.route(
        lambda m, u, kw: u == f"{gdrive.DRIVE_API_BASE}/files/fid",
        FakeResponse(headers={"Content-Length": "6"}, chunks=[b"ID3", b"ab"]),
    )
    client = valid_token_client(session)
    local_path = Path(config_dir) / "song.mp3"
    progress = []

    result = asyncio.run(
        client.download_file(
            "fid", "song.mp3", str(local_path), lambda d, t: progress.append((d, t))
        )
    )

    assert result == str(local_path)
    assert local_path.read_bytes() == b"ID3ab"
    assert progress == [(3, 6), (5, 6)]
    params = session.calls("GET")[0]["kwargs"]["params"]
    assert params == {"alt": "media"}


def test_download_file_uses_cache_without_network(config_dir):
    session = FakeSession()
    client = valid_token_client(session)
    local_path = Path(config_dir) / "cached.mp3"
    local_path.write_bytes(b"existing")

    result = asyncio.run(client.download_file("fid", "cached.mp3", str(local_path)))

    assert result == str(local_path)
    assert session.requests == []  # 缓存命中，无网络请求


def test_download_file_failure_cleans_part_file(config_dir):
    session = FakeSession()
    session.route(
        lambda m, u, kw: u == f"{gdrive.DRIVE_API_BASE}/files/gone",
        FakeResponse(status_code=404),
    )
    client = valid_token_client(session)

    with pytest.raises(Exception, match="404"):
        asyncio.run(client.download_file("gone", "song.mp3"))

    leftovers = list((Path(config_dir)).glob("*.part"))
    assert leftovers == []
    assert not (Path(config_dir) / "song.mp3").exists()


# === 令牌管理与错误翻译 ===


def test_expired_token_refreshes_before_request(config_dir):
    session = FakeSession()
    route_token_refresh(session)
    session.route(
        lambda m, u, kw: u == f"{gdrive.DRIVE_API_BASE}/about",
        FakeResponse(json_data={"user": {"displayName": "测试用户"}}),
    )
    client = GoogleDriveClient(
        client_id="cid",
        client_secret="csecret",
        refresh_token="rt",
        access_token="stale",
        token_expiry=time.time() - 10,  # 已过期
        session=session,
    )

    ok = asyncio.run(client.test_connection())

    assert ok is True
    assert len(session.calls("POST")) == 1  # 触发过一次刷新
    auth_header = session.calls("GET")[0]["kwargs"]["headers"]["Authorization"]
    assert auth_header == "Bearer newtok"


def test_401_triggers_refresh_and_single_retry(config_dir):
    responses = [
        FakeResponse(status_code=401),
        FakeResponse(json_data={"files": []}),
    ]
    session = FakeSession()
    route_token_refresh(session)
    session.route(
        lambda m, u, kw: u == f"{gdrive.DRIVE_API_BASE}/files",
        lambda: responses.pop(0),
    )
    client = valid_token_client(session)

    asyncio.run(client.list_music_files())

    gets = session.calls("GET")
    assert len(gets) == 2  # 原请求 + 刷新后重试一次
    assert gets[0]["kwargs"]["headers"]["Authorization"] == "Bearer tok"
    assert gets[1]["kwargs"]["headers"]["Authorization"] == "Bearer newtok"


def test_missing_refresh_token_gives_friendly_error(config_dir):
    session = FakeSession()
    client = GoogleDriveClient(
        client_id="cid", client_secret="csecret", session=session
    )

    with pytest.raises(Exception, match="授权"):
        asyncio.run(client.list_music_files())


def test_invalid_grant_reports_reauthorization(config_dir):
    session = FakeSession()
    route_token_refresh(session, status=400, error="invalid_grant")
    session.route(
        lambda m, u, kw: u == f"{gdrive.DRIVE_API_BASE}/files",
        FakeResponse(json_data={"files": []}),
    )
    client = GoogleDriveClient(
        client_id="cid",
        client_secret="csecret",
        refresh_token="revoked",
        session=session,
    )

    with pytest.raises(Exception, match="重新授权"):
        asyncio.run(client.list_music_files())


def test_tokens_updated_callback_receives_new_tokens(config_dir):
    received = []
    session = FakeSession()
    route_token_refresh(session)
    session.route(
        lambda m, u, kw: u == f"{gdrive.DRIVE_API_BASE}/about",
        FakeResponse(json_data={"user": {}}),
    )
    client = GoogleDriveClient(
        client_id="cid",
        client_secret="csecret",
        refresh_token="rt",
        session=session,
        on_tokens_updated=received.append,
    )

    asyncio.run(client.test_connection())

    assert received and received[0]["access_token"] == "newtok"
    assert received[0]["refresh_token"] == "rt"


# === 文件信息与连接测试 ===


def test_get_file_info_maps_fields(config_dir):
    session = FakeSession()
    session.route(
        lambda m, u, kw: u == f"{gdrive.DRIVE_API_BASE}/files/fid",
        FakeResponse(
            json_data={
                "id": "fid",
                "name": "song.mp3",
                "size": "42",
                "modifiedTime": "2026-08-01T00:00:00Z",
                "mimeType": "audio/mpeg",
            }
        ),
    )
    client = valid_token_client(session)

    info = asyncio.run(client.get_file_info("fid"))

    assert info == {
        "name": "song.mp3",
        "size": 42,
        "modified": "2026-08-01T00:00:00Z",
        "content_type": "audio/mpeg",
    }


def test_get_file_info_404_returns_none(config_dir):
    session = FakeSession()
    session.route(
        lambda m, u, kw: u == f"{gdrive.DRIVE_API_BASE}/files/gone",
        FakeResponse(status_code=404),
    )
    client = valid_token_client(session)

    assert asyncio.run(client.get_file_info("gone")) is None


def test_test_connection_false_on_http_error(config_dir):
    session = FakeSession()
    route_token_refresh(session)
    session.route(
        lambda m, u, kw: u == f"{gdrive.DRIVE_API_BASE}/about",
        FakeResponse(status_code=403),
    )
    client = GoogleDriveClient(
        client_id="cid", client_secret="csecret", refresh_token="rt", session=session
    )

    assert asyncio.run(client.test_connection()) is False


# === 自定义 API 端点 ===


def test_resolve_endpoints_default_and_custom():
    defaults = gdrive.resolve_endpoints("")
    assert defaults == {
        "drive_api": gdrive.DRIVE_API_BASE,
        "oauth_auth": gdrive.OAUTH_AUTH_URL,
        "oauth_token": gdrive.OAUTH_TOKEN_URL,
    }
    # 尾部斜杠与空白应被归一化
    custom = gdrive.resolve_endpoints("  http://127.0.0.1:8931/ ")
    assert custom == {
        "drive_api": "http://127.0.0.1:8931/drive/v3",
        "oauth_auth": "http://127.0.0.1:8931/auth",
        "oauth_token": "http://127.0.0.1:8931/token",
    }


def test_custom_api_base_routes_all_traffic(config_dir):
    """自定义地址时令牌刷新/连接测试/列表全部改走派生端点；
    FakeSession 对未路由的请求直接抛错，官方 URL 一次都不应命中。"""
    base = "http://127.0.0.1:8931"
    session = FakeSession()
    session.route(
        lambda m, u, kw: u == f"{base}/token"
        and (kw.get("data") or {}).get("grant_type") == "refresh_token",
        FakeResponse(json_data={"access_token": "newtok", "expires_in": 3600}),
    )
    session.route(
        lambda m, u, kw: u == f"{base}/drive/v3/about",
        FakeResponse(json_data={"user": {"displayName": "测试用户"}}),
    )
    session.route(
        lambda m, u, kw: u == f"{base}/drive/v3/files",
        FakeResponse(
            json_data={
                "files": [
                    {
                        "id": "f1",
                        "name": "song.mp3",
                        "size": "10",
                        "mimeType": "audio/mpeg",
                    }
                ]
            }
        ),
    )
    client = GoogleDriveClient(
        client_id="cid",
        client_secret="csecret",
        refresh_token="rt",
        session=session,
        api_base_url=f"{base}/",
    )

    assert asyncio.run(client.test_connection()) is True
    files = asyncio.run(client.list_music_files())
    assert [f["name"] for f in files] == ["song.mp3"]

    urls = [r["url"] for r in session.requests]
    assert urls and all(u.startswith(base) for u in urls)


def test_loopback_receiver_prefers_fixed_port():
    receiver = gdrive.LoopbackOAuthReceiver()
    receiver.start()
    try:
        port = receiver._server.server_address[1]
        assert port in gdrive.PREFERRED_LOOPBACK_PORTS
    finally:
        receiver.close()


def test_loopback_receiver_falls_back_when_fixed_ports_busy():
    squatters = []
    try:
        for port in gdrive.PREFERRED_LOOPBACK_PORTS:
            sock = socket.socket()
            # 与 HTTPServer 的 allow_reuse_address 一致，避免被先前测试连接的
            # TIME_WAIT 残留挡住绑定
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", port))
            sock.listen(1)
            squatters.append(sock)

        receiver = gdrive.LoopbackOAuthReceiver()
        receiver.start()
        try:
            port = receiver._server.server_address[1]
            assert port not in gdrive.PREFERRED_LOOPBACK_PORTS
            assert port > 0
        finally:
            receiver.close()
    finally:
        for sock in squatters:
            sock.close()
