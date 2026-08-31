#!/usr/bin/env python3
"""以 Web 模式运行 Flet 应用（用于浏览器访问）

浏览器无法读取服务器本地磁盘文件，因此将音乐目录以静态文件方式
挂载到 /local-music/，Web 会话播放时使用该 URL 而非本地路径。

公网/局域网暴露时的防扫描措施：所有请求（含 WebSocket 升级）必须携带
访问令牌，否则一律返回 404（与"服务不存在"表现一致，扫描工具无差别拒绝）。
首次以 ?k=<令牌> 访问后浏览器获得 HttpOnly cookie，后续请求自动携带。

用法:
    .venv/bin/python run_web.py                    # 127.0.0.1，自动打开浏览器
    .venv/bin/python run_web.py --lan              # 0.0.0.0，局域网设备可访问
    .venv/bin/python run_web.py --no-browser       # 不自动打开浏览器（隧道场景）
    WEB_ACCESS_TOKEN=xxx .venv/bin/python run_web.py   # 固定令牌（默认每次随机）
"""

import os
import secrets
import socket
import sys
import threading
import uuid
import webbrowser
from urllib.parse import parse_qsl

import flet as ft
import uvicorn
from starlette.staticfiles import StaticFiles

from nextcloud_music_player.app import main

# 本地音乐静态挂载路径（与 platform_audio.py 中 WEB_MUSIC_PREFIX 保持一致）
LOCAL_MUSIC_PREFIX = "/local-music"

# 访问令牌：URL 用 ?k=<token> 携带，命中后种入该 cookie
TOKEN_QUERY_PARAM = "k"
TOKEN_COOKIE = "ncmp_token"


class TokenGateMiddleware:
    """ASGI 门卫：http 与 websocket 请求统一校验访问令牌，未通过返回 404。

    纯 ASGI 实现（Starlette 的 BaseHTTPMiddleware 不覆盖 websocket 连接）。
    """

    def __init__(self, app, token: str):
        self.app = app
        self.token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        query_token = self._query_token(scope)
        cookie_token = self._cookie_token(scope)
        valid = secrets.compare_digest(query_token or "", self.token) or (
            secrets.compare_digest(cookie_token or "", self.token)
        )

        if not valid:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            await send(
                {
                    "type": "http.response.start",
                    "status": 404,
                    "headers": [(b"content-type", b"text/plain; charset=utf-8")],
                }
            )
            await send({"type": "http.response.body", "body": b"Not Found"})
            return

        if scope["type"] == "http" and secrets.compare_digest(
            query_token or "", self.token
        ):
            # 首次带令牌访问：种 cookie，此后（含 WS 升级）凭 cookie 放行
            async def send_with_cookie(message):
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    cookie = (
                        f"{TOKEN_COOKIE}={self.token}; Path=/; "
                        f"HttpOnly; SameSite=Lax; Max-Age=86400"
                    )
                    headers.append((b"set-cookie", cookie.encode()))
                    message = {**message, "headers": headers}
                await send(message)

            await self.app(scope, receive, send_with_cookie)
            return

        await self.app(scope, receive, send)

    @staticmethod
    def _query_token(scope) -> str | None:
        for key, value in parse_qsl(scope.get("query_string", b"").decode()):
            if key == TOKEN_QUERY_PARAM:
                return value
        return None

    @classmethod
    def _cookie_token(cls, scope) -> str | None:
        for name, value in scope.get("headers", []):
            if name == b"cookie":
                for part in value.decode().split(";"):
                    cookie_name, _, cookie_value = part.strip().partition("=")
                    if cookie_name == TOKEN_COOKIE:
                        return cookie_value
        return None


def get_music_dir() -> str:
    """获取已下载音乐的本地目录"""
    from nextcloud_music_player.config_manager import ConfigManager
    cm = ConfigManager()
    music_dir = os.path.join(str(cm.get_config_directory()), 'music')
    os.makedirs(music_dir, exist_ok=True)
    return music_dir


def get_lan_ip() -> str:
    """获取本机局域网 IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == '__main__':
    port = 8765
    for arg in sys.argv[1:]:
        if arg.startswith("--port="):
            port = int(arg.split("=", 1)[1])

    token_gate_enabled = os.environ.get("WEB_DISABLE_TOKEN_GATE") != "1"
    token = (os.environ.get("WEB_ACCESS_TOKEN") or uuid.uuid4().hex) if token_gate_enabled else ""
    open_browser = "--no-browser" not in sys.argv

    if "--lan" in sys.argv:
        host = "0.0.0.0"
        open_url = f"http://{get_lan_ip()}:{port}"
    else:
        host = "127.0.0.1"
        open_url = f"http://127.0.0.1:{port}"

    # 导出 ASGI 应用；Flet 自带根级 catch-all 路由，必须用外层应用包一层，
    # 让 /local-music 静态挂载先于 Flet 路由匹配（浏览器播放用）
    from fastapi import FastAPI
    # 调试链路通常位于无法稳定访问 Google CDN 的内网/VPN 环境；
    # CanvasKit、Pyodide 和字体均使用 flet_web 随包资源，避免页面卡在加载动画。
    flet_app = ft.run(
        main,
        port=port,
        host=host,
        export_asgi_app=True,
        no_cdn=True,
    )
    app = FastAPI()
    if token_gate_enabled:
        app.add_middleware(TokenGateMiddleware, token=token)
    app.mount(
        LOCAL_MUSIC_PREFIX,
        StaticFiles(directory=get_music_dir()),
        name="local-music",
    )
    app.mount("/", flet_app)

    if token_gate_enabled:
        print(f"\n访问令牌: {token}")
        print(f"带令牌访问: {open_url}/?{TOKEN_QUERY_PARAM}={token}")
        print(f"无令牌访问: {open_url}  (返回 404)\n")
    else:
        print(f"\n访问令牌已禁用: {open_url}/\n")

    # 延迟打开浏览器，等服务器就绪
    if open_browser:
        browser_url = (
            f"{open_url}/?{TOKEN_QUERY_PARAM}={token}"
            if token_gate_enabled
            else f"{open_url}/"
        )
        threading.Timer(
            1.5, lambda: webbrowser.open(browser_url)
        ).start()

    uvicorn.run(app, host=host, port=port, log_level="warning")
