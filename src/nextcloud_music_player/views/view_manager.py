"""
视图管理器 - 基于 Flet NavigationBar 管理三个主要界面的切换
"""

import flet as ft
import logging

logger = logging.getLogger(__name__)


class ViewManager:
    """管理应用的三个主要视图：连接、文件列表、播放"""

    def __init__(self, page: ft.Page, app_context: dict):
        self.page = page
        self.app_context = app_context
        self.current_view = None

        config_manager = app_context['config_manager']
        music_library = app_context['music_library']
        nextcloud_client = app_context.get('nextcloud_client')

        # 创建服务（复用服务层）
        from ..services.lyrics_service import LyricsService
        from ..services.music_service import MusicService

        self.lyrics_service = LyricsService(
            config_manager=config_manager,
            nextcloud_client=nextcloud_client,
            music_library=music_library
        )

        self.music_service = MusicService(
            music_library=music_library,
            nextcloud_client=nextcloud_client,
            config_manager=config_manager,
            lyrics_service=self.lyrics_service
        )

        app_context['music_service'] = self.music_service
        app_context['lyrics_service'] = self.lyrics_service

        # 设置回调
        self.music_service.set_playlist_change_callback(self._handle_playlist_change)
        self.music_service.set_sync_folder_change_callback(self._handle_sync_folder_change)

        # 创建视图
        from .connection_view import ConnectionView
        from .file_list_view import FileListView
        from .playback_view import PlaybackView

        self.connection_view = ConnectionView(page, app_context, self)
        self.file_list_view = FileListView(page, app_context, self)
        self.playback_view = PlaybackView(page, app_context, self)

        # 内容区域
        self.content_area = ft.Container(expand=True)

        # 底部导航栏
        self.nav_bar = ft.NavigationBar(
            selected_index=0,
            on_change=self._on_nav_change,
            destinations=[
                ft.NavigationBarDestination(
                    icon=ft.Icons.LINK_OUTLINED,
                    selected_icon=ft.Icons.LINK,
                    label="连接",
                ),
                ft.NavigationBarDestination(
                    icon=ft.Icons.LIST_OUTLINED,
                    selected_icon=ft.Icons.LIST,
                    label="文件",
                ),
                ft.NavigationBarDestination(
                    icon=ft.Icons.MUSIC_NOTE_OUTLINED,
                    selected_icon=ft.Icons.MUSIC_NOTE,
                    label="播放",
                ),
            ],
        )

        # 组装页面
        page.add(
            ft.Column([
                self.content_area,
                self.nav_bar,
            ], expand=True, spacing=0)
        )

    def _on_nav_change(self, e):
        """导航栏切换事件"""
        index = e.control.selected_index
        view_map = {0: "connection", 1: "file_list", 2: "playback"}
        self.switch_to_view(view_map.get(index, "playback"))

    def _handle_playlist_change(self, playlist: list, start_index: int):
        """处理播放列表变化"""
        logger.info(f"播放列表已更新: {len(playlist)} 首歌曲，开始索引: {start_index}")

    def _handle_sync_folder_change(self, sync_folder: str):
        """处理同步文件夹变化"""
        logger.info(f"同步文件夹已更新: {sync_folder}")

    def switch_to_view(self, view_name: str):
        """切换到指定视图"""
        logger.info(f"切换到视图: {view_name}")

        view_map = {
            "connection": (self.connection_view, 0),
            "file_list": (self.file_list_view, 1),
            "playback": (self.playback_view, 2),
        }

        view, nav_index = view_map.get(view_name, (self.playback_view, 2))

        self.content_area.content = view.build()
        self.nav_bar.selected_index = nav_index
        self.current_view = view

        # 保存当前视图到配置
        self.app_context['config_manager'].set("app.last_view", view_name)
        self.app_context['config_manager'].save_config()

        # 通知视图激活
        if hasattr(view, 'on_view_activated'):
            view.on_view_activated()

        self.page.update()

    def show_status_message(self, message: str, message_type: str = "info"):
        """在当前视图中显示状态消息"""
        if hasattr(self.current_view, 'show_message'):
            self.current_view.show_message(message, message_type)

    def get_view(self, view_name: str):
        """获取指定的视图对象"""
        if view_name == "connection":
            return self.connection_view
        elif view_name == "file_list":
            return self.file_list_view
        elif view_name == "playback":
            return self.playback_view
        return None
