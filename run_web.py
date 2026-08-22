"""临时脚本：以 web 模式运行 Flet 应用用于截图"""
import flet as ft
from nextcloud_music_player.app import main

ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=8765, host="0.0.0.0")
