#!/usr/bin/env python3
"""以 Web 模式运行 Flet 应用（用于浏览器访问）

浏览器无法读取服务器本地磁盘文件，因此将音乐目录以静态文件方式
挂载到 /local-music/，Web 会话播放时使用该 URL 而非本地路径。

用法:
    .venv/bin/python run_web.py          # 默认绑定 127.0.0.1，自动打开浏览器
    .venv/bin/python run_web.py --lan    # 绑定 0.0.0.0，局域网设备（如手机）可访问
"""

import os
import socket
import sys
import threading
import webbrowser

import flet as ft
import uvicorn
from starlette.staticfiles import StaticFiles

from nextcloud_music_player.app import main

# 本地音乐静态挂载路径（与 platform_audio.py 中 WEB_MUSIC_PREFIX 保持一致）
LOCAL_MUSIC_PREFIX = "/local-music"


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
    if "--lan" in sys.argv:
        host = "0.0.0.0"
        open_url = f"http://{get_lan_ip()}:{port}"
        print(f"\n局域网访问地址: {open_url}\n")
    else:
        host = "127.0.0.1"
        open_url = f"http://127.0.0.1:{port}"

    # 导出 ASGI 应用；Flet 自带根级 catch-all 路由，必须用外层应用包一层，
    # 让 /local-music 静态挂载先于 Flet 路由匹配（浏览器播放用）
    from fastapi import FastAPI
    flet_app = ft.run(main, port=port, host=host, export_asgi_app=True)
    app = FastAPI()
    app.mount(
        LOCAL_MUSIC_PREFIX,
        StaticFiles(directory=get_music_dir()),
        name="local-music",
    )
    app.mount("/", flet_app)

    # 延迟打开浏览器，等服务器就绪
    threading.Timer(1.5, lambda: webbrowser.open(open_url)).start()

    uvicorn.run(app, host=host, port=port, log_level="warning")
