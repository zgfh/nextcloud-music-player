"""Small in-process Nextcloud/WebDAV server for integration and Flet E2E tests.

支持两类用法：
- 正常路径：Basic Auth 登录、PROPFIND 列目录、GET 歌词/音频文件；
- 故障注入：通过 ``server.set_fault(...)`` 在任意时刻切换慢响应、
  强制状态码（401/404/500…）或直接断线，用于覆盖客户端与 UI 的异常分支。
"""

from __future__ import annotations

import base64
import io
import math
import struct
import sys
import threading
import time
import wave
from dataclasses import dataclass, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit


USERNAME = "e2e"
PASSWORD = "e2e-password"
SONG_NAME = "test-tone.wav"
LYRICS_NAME = "test-tone.lrc"
MUSIC_PATH = f"/remote.php/dav/files/{USERNAME}/music"
SONG_PATH = f"{MUSIC_PATH}/{SONG_NAME}"
LYRICS_PATH = f"{MUSIC_PATH}/{LYRICS_NAME}"


def _test_wav() -> bytes:
    """Return a short, valid PCM tone that AVFoundation can load in CI."""
    sample_rate = 8_000
    duration = 0.5
    frames = bytearray()
    for index in range(int(sample_rate * duration)):
        sample = int(8_000 * math.sin(2 * math.pi * 440 * index / sample_rate))
        frames.extend(struct.pack("<h", sample))
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(frames)
    return output.getvalue()


WAV_BYTES = _test_wav()
LRC_BYTES = b"[ar:E2E]\n[ti:Test Tone]\n[00:00.00]Mock Nextcloud playback\n"


@dataclass
class FaultPlan:
    """单个故障场景；测试在请求之间切换，模拟真实服务端异常。

    - delay_seconds: 处理任何请求前先 sleep，模拟慢响应/慢网络；
    - status: 非 None 时无视认证与路径，统一返回该状态码（401/404/500…）；
    - drop: 直接关闭 TCP 连接不回响应，客户端会收到 ConnectionError。
    """

    delay_seconds: float = 0.0
    status: int | None = None
    drop: bool = False


NO_FAULTS = FaultPlan()



def _propfind_xml() -> bytes:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<d:multistatus xmlns:d="DAV:">
  <d:response>
    <d:href>{MUSIC_PATH}/</d:href>
    <d:propstat><d:prop>
      <d:displayname>music</d:displayname>
      <d:resourcetype><d:collection/></d:resourcetype>
    </d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat>
  </d:response>
  <d:response>
    <d:href>{SONG_PATH}</d:href>
    <d:propstat><d:prop>
      <d:displayname>{SONG_NAME}</d:displayname>
      <d:getcontentlength>{len(WAV_BYTES)}</d:getcontentlength>
      <d:getcontenttype>audio/wav</d:getcontenttype>
      <d:getlastmodified>Sun, 30 Aug 2026 00:00:00 GMT</d:getlastmodified>
      <d:getetag>&quot;e2e-tone&quot;</d:getetag>
      <d:resourcetype/>
    </d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat>
  </d:response>
</d:multistatus>""".encode()


class _Handler(BaseHTTPRequestHandler):
    server_version = "MockNextcloud/1.0"

    def log_message(self, _format, *_args):
        return

    @property
    def _faults(self) -> FaultPlan:
        return getattr(self.server, "faults", NO_FAULTS)

    def _consume_fault(self) -> bool:
        """Apply the active fault plan; returns True when the request is consumed."""
        faults = self._faults
        if faults.delay_seconds > 0:
            time.sleep(faults.delay_seconds)
        if faults.drop:
            # 不写任何响应直接关闭连接，requests 侧表现为
            # "Remote end closed connection without response" 的 ConnectionError。
            self.close_connection = True
            return True
        if faults.status is not None:
            self.send_response(faults.status)
            if faults.status == 401:
                self.send_header("WWW-Authenticate", 'Basic realm="Mock Nextcloud"')
            self.end_headers()
            return True
        return False

    def _authorized(self) -> bool:
        expected = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
        return self.headers.get("Authorization") == f"Basic {expected}"

    def _require_auth(self) -> bool:
        if self._authorized():
            return True
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Mock Nextcloud"')
        self.end_headers()
        return False

    def _send_bytes(self, content: bytes, content_type: str):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_HEAD(self):
        if self._consume_fault():
            return
        self.send_response(200)
        self.end_headers()

    def do_PROPFIND(self):  # noqa: N802 - HTTP method name
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length:
            self.rfile.read(content_length)
        if self._consume_fault():
            return
        if not self._require_auth():
            return
        path = unquote(urlsplit(self.path).path).rstrip("/")
        while "//" in path:
            path = path.replace("//", "/")
        user_root = f"/remote.php/dav/files/{USERNAME}"
        if path not in (user_root, MUSIC_PATH):
            self.send_response(404)
            self.end_headers()
            return
        content = _propfind_xml()
        self.send_response(207)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        if self._consume_fault():
            return
        if not self._require_auth():
            return
        path = unquote(urlsplit(self.path).path)
        if path == SONG_PATH:
            self._send_bytes(WAV_BYTES, "audio/wav")
        elif path == LYRICS_PATH:
            self._send_bytes(LRC_BYTES, "text/plain; charset=utf-8")
        else:
            self.send_response(404)
            self.end_headers()


class _FaultableHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, handler):
        super().__init__(address, handler)
        self.faults = NO_FAULTS

    def handle_error(self, request, client_address):
        # 注入断线/慢响应时客户端可能中途放弃，socket 关闭属预期；
        # 其余异常仍走默认处理，避免吞掉 mock 自身的 bug。
        if isinstance(sys.exc_info()[1], ConnectionError):
            return
        super().handle_error(request, client_address)


@dataclass
class MockNextcloudServer:
    httpd: ThreadingHTTPServer
    thread: threading.Thread

    @classmethod
    def start(cls) -> "MockNextcloudServer":
        httpd = _FaultableHTTPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        return cls(httpd=httpd, thread=thread)

    @property
    def url(self) -> str:
        host, port = self.httpd.server_address
        return f"http://{host}:{port}"

    def set_fault(self, **kwargs) -> None:
        """切换故障场景，如 ``set_fault(status=401)`` / ``set_fault(drop=True)``。"""
        self.httpd.faults = replace(NO_FAULTS, **kwargs)

    def clear_fault(self) -> None:
        self.httpd.faults = NO_FAULTS

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)
