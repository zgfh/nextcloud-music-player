"""In-process mock of the Google Drive / OAuth endpoints for Flet E2E tests.

模拟 ``resolve_endpoints()`` 从自定义 API 地址派生出的端点组：
- POST /token          OAuth 令牌（authorization_code / refresh_token 两种 grant）
- GET  /auth           授权页：302 回 loopback 并携带授权码，
                       等价于用户在浏览器完成同意后的重定向
- GET  /drive/v3/about 连接测试（test_connection）
- GET  /drive/v3/files 文件列表（从 q 解析文件夹 ID 与仅目录标记）
- GET  /drive/v3/files/{id}?alt=media  音频下载（复用 mock_nextcloud 的 WAV）

故障注入：
- set_token_error("invalid_grant") 令牌端点统一返回 400，模拟授权被撤销
- set_expires_in(seconds)          控制签发令牌有效期（1 秒 = 客户端
                                   60 秒提前刷新偏移下一次请求必然触发刷新）
- set_fault(status=N / drop=True)  Drive API 故障，对齐 mock_nextcloud 的 FaultPlan
"""

from __future__ import annotations

import json
import sys
import threading
import time
from dataclasses import dataclass, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from mock_nextcloud import NO_FAULTS, WAV_BYTES, FaultPlan

FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

AUTH_CODE = "e2e-auth-code"
REFRESH_TOKEN = "e2e-refresh-token"
SONG_NAME = "drive-tone.wav"
SONG_ID = "file-song-1"
FOLDER_NAME = "音乐"
FOLDER_ID = "folder-music"
USER_NAME = "E2E 用户"


def _song_metadata() -> dict:
    return {
        "id": SONG_ID,
        "name": SONG_NAME,
        "size": str(len(WAV_BYTES)),
        "modifiedTime": "2026-08-30T00:00:00Z",
        "mimeType": "audio/wav",
    }


def _folder_metadata() -> dict:
    return {
        "id": FOLDER_ID,
        "name": FOLDER_NAME,
        "modifiedTime": "2026-08-30T00:00:00Z",
        "mimeType": FOLDER_MIME_TYPE,
    }


# 根目录内容：一首可播放的歌 + 一个空的音乐文件夹
_ROOT_ENTRIES = {"file": [_song_metadata()], "folder": [_folder_metadata()]}


class _State:
    """Handler 与测试共享的可变状态（挂在 server 实例上）"""

    def __init__(self):
        self.faults: FaultPlan = NO_FAULTS
        # 非空时 /token 统一返回 400 {"error": <token_error>}
        self.token_error = ""
        self.expires_in = 3600
        self.issued_tokens: set[str] = set()
        # [(grant_type, ok)]，供断言授权码换令牌/刷新是否发生、是否被拒
        self.token_requests: list[tuple[str, bool]] = []
        # /auth 最近一次收到的 redirect_uri（应用构建的 loopback 回调地址）
        self.oauth_redirect_uri = ""

    def issue_access_token(self) -> str:
        token = f"mock-at-{len(self.issued_tokens) + 1}"
        self.issued_tokens.add(token)
        return token


class _Handler(BaseHTTPRequestHandler):
    server_version = "MockGdrive/1.0"

    def log_message(self, _format, *_args):
        return

    @property
    def state(self) -> _State:
        return self.server.state

    # --- 响应辅助 ---

    def _send_json(self, payload: dict, status: int = 200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, content: bytes, content_type: str):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _consume_fault(self) -> bool:
        """对 Drive API 应用故障计划；返回 True 表示请求已被消费"""
        faults = self.state.faults
        if faults.delay_seconds > 0:
            time.sleep(faults.delay_seconds)
        if faults.drop:
            self.close_connection = True
            return True
        if faults.status is not None:
            self.send_response(faults.status)
            self.end_headers()
            return True
        return False

    def _bearer_ok(self) -> bool:
        header = self.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else ""
        if token and token in self.state.issued_tokens:
            return True
        self._send_json(
            {"error": {"code": 401, "message": "Invalid Credentials"}}, status=401
        )
        return False

    # --- 端点 ---

    def do_POST(self):  # noqa: N802 - HTTP method name
        if urlsplit(self.path).path != "/token":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = parse_qs(self.rfile.read(length).decode("utf-8")) if length else {}
        grant = (body.get("grant_type") or [""])[0]
        state = self.state

        if state.token_error:
            state.token_requests.append((grant, False))
            self._send_json({"error": state.token_error}, status=400)
            return
        if grant == "authorization_code":
            if (body.get("code") or [""])[0] != AUTH_CODE:
                state.token_requests.append((grant, False))
                self._send_json({"error": "invalid_grant"}, status=400)
                return
            payload = {
                "access_token": state.issue_access_token(),
                "refresh_token": REFRESH_TOKEN,
                "expires_in": state.expires_in,
                "token_type": "Bearer",
            }
        elif grant == "refresh_token":
            payload = {
                "access_token": state.issue_access_token(),
                "expires_in": state.expires_in,
                "token_type": "Bearer",
            }
        else:
            state.token_requests.append((grant, False))
            self._send_json({"error": "unsupported_grant_type"}, status=400)
            return
        state.token_requests.append((grant, True))
        self._send_json(payload)

    def do_GET(self):  # noqa: N802 - HTTP method name
        path = urlsplit(self.path).path
        query = parse_qs(urlsplit(self.path).query)

        if path == "/auth":
            self._handle_authorize_page(query)
            return

        if not path.startswith("/drive/v3/"):
            self.send_response(404)
            self.end_headers()
            return
        if self._consume_fault():
            return
        if not self._bearer_ok():
            return

        if path == "/drive/v3/about":
            self._send_json({"user": {"displayName": USER_NAME}})
        elif path == "/drive/v3/files":
            self._send_file_list(query)
        else:
            file_id = path.rsplit("/", 1)[-1]
            if file_id != SONG_ID:
                self._send_json(
                    {"error": {"code": 404, "message": "File not found"}},
                    status=404,
                )
            elif query.get("alt") == ["media"]:
                self._send_bytes(WAV_BYTES, "audio/wav")
            else:
                self._send_json(_song_metadata())

    def _handle_authorize_page(self, query):
        """记录应用的 loopback 回调地址，并 302 回去携带授权码。

        若系统浏览器真的打开了授权页，重定向会像真实 Google 一样完成授权；
        测试也可以拿 oauth_redirect_uri 手动投递授权码，两条路径等价。
        """
        redirect_uri = (query.get("redirect_uri") or [""])[0]
        if not redirect_uri:
            self.send_response(400)
            self.end_headers()
            return
        self.state.oauth_redirect_uri = redirect_uri
        separator = "&" if "?" in redirect_uri else "?"
        self.send_response(302)
        self.send_header(
            "Location", f"{redirect_uri}{separator}code={AUTH_CODE}"
        )
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_file_list(self, query):
        q = (query.get("q") or [""])[0]
        # q 形如 'root' in parents and trashed = false [and mimeType = '...folder']
        folder_id = q.split("'")[1] if "'" in q else "root"
        folders_only = FOLDER_MIME_TYPE in q
        entries = _ROOT_ENTRIES if folder_id in ("root", "") else {"file": [], "folder": []}
        kind = "folder" if folders_only else "file"
        self._send_json({"files": entries[kind]})


class _StatefulHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, handler):
        super().__init__(address, handler)
        self.state = _State()

    def handle_error(self, request, client_address):
        # 注入断线时客户端可能中途放弃，socket 关闭属预期，避免淹没输出
        if isinstance(sys.exc_info()[1], ConnectionError):
            return
        super().handle_error(request, client_address)


@dataclass
class MockGdriveServer:
    httpd: ThreadingHTTPServer
    thread: threading.Thread

    @classmethod
    def start(cls) -> "MockGdriveServer":
        httpd = _StatefulHTTPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        return cls(httpd=httpd, thread=thread)

    @property
    def url(self) -> str:
        host, port = self.httpd.server_address
        return f"http://{host}:{port}"

    # --- 测试侧控制与观测 ---

    def set_fault(self, **kwargs) -> None:
        """Drive API 故障，如 ``set_fault(status=403)`` / ``set_fault(drop=True)``"""
        self.httpd.state.faults = replace(NO_FAULTS, **kwargs)

    def clear_fault(self) -> None:
        self.httpd.state.faults = NO_FAULTS

    def set_token_error(self, error: str = "") -> None:
        self.httpd.state.token_error = error

    def set_expires_in(self, seconds: int) -> None:
        self.httpd.state.expires_in = seconds

    def token_requests(self) -> list[tuple[str, bool]]:
        return list(self.httpd.state.token_requests)

    @property
    def oauth_redirect_uri(self) -> str:
        return self.httpd.state.oauth_redirect_uri

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)
