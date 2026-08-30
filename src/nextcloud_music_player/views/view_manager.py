"""
视图管理器 - 基于 Flet NavigationBar 管理四个主要界面的切换，
并统一处理应用前后台生命周期（后台冻结 UI 刷新、回前台续传下载）
"""

import logging

import flet as ft

from ..utils.theme import Color

logger = logging.getLogger(__name__)


class ViewManager:
    """管理应用的主要视图：连接、文件列表、播放、设置"""

    def __init__(self, page: ft.Page, app_context: dict):
        self.page = page
        self.app_context = app_context
        self.current_view = None

        config_manager = app_context["config_manager"]
        music_library = app_context["music_library"]
        nextcloud_client = app_context.get("nextcloud_client")

        # 创建服务（复用服务层）
        from ..services.lyrics_service import LyricsService
        from ..services.music_service import MusicService

        self.lyrics_service = LyricsService(
            config_manager=config_manager,
            nextcloud_client=nextcloud_client,
            music_library=music_library,
        )

        self.music_service = MusicService(
            music_library=music_library,
            nextcloud_client=nextcloud_client,
            config_manager=config_manager,
            lyrics_service=self.lyrics_service,
        )

        app_context["music_service"] = self.music_service
        app_context["lyrics_service"] = self.lyrics_service

        # 设置回调
        self.music_service.set_playlist_change_callback(self._handle_playlist_change)
        self.music_service.set_sync_folder_change_callback(
            self._handle_sync_folder_change
        )

        # 创建视图
        from .connection_view import ConnectionView
        from .file_list_view import FileListView
        from .playback_view import PlaybackView
        from .settings_view import SettingsView

        self.connection_view = ConnectionView(page, app_context, self)
        self.file_list_view = FileListView(page, app_context, self)
        self.playback_view = PlaybackView(page, app_context, self)
        self.settings_view = SettingsView(page, app_context, self)

        # 应用前后台状态：后台时暂停周期性 page.update（websocket 可能已冻结，
        # 调用会阻塞事件循环），回前台时续传下载队列
        self.app_backgrounded = False
        page.on_app_lifecycle_state_change = self._on_app_lifecycle_state_change

        # 内容区域
        self.content_area = ft.Container(
            expand=True,
            bgcolor=Color.BG_APP,
        )

        # 底部导航栏 - 深空霓虹风（悬浮胶囊 + 顶部霓虹分隔线）
        self.nav_bar = ft.NavigationBar(
            selected_index=0,
            on_change=self._on_nav_change,
            bgcolor=Color.BG_SURFACE,
            indicator_color="#0F2A3A",
            destinations=[
                ft.NavigationBarDestination(
                    key="nav_connection",
                    icon=ft.Icons.LINK_OUTLINED,
                    selected_icon=ft.Icons.LINK,
                    label="连接",
                ),
                ft.NavigationBarDestination(
                    key="nav_files",
                    icon=ft.Icons.LIST_OUTLINED,
                    selected_icon=ft.Icons.LIST,
                    label="文件",
                ),
                ft.NavigationBarDestination(
                    key="nav_playback",
                    icon=ft.Icons.MUSIC_NOTE_OUTLINED,
                    selected_icon=ft.Icons.MUSIC_NOTE,
                    label="播放",
                ),
                ft.NavigationBarDestination(
                    key="nav_settings",
                    icon=ft.Icons.SETTINGS_OUTLINED,
                    selected_icon=ft.Icons.SETTINGS,
                    label="设置",
                ),
            ],
        )

        # 组装页面 - SafeArea 处理 iOS 刘海/灵动岛（顶部）与 Home 指示条（底部）遮挡
        page.add(
            ft.SafeArea(
                content=ft.Column(
                    [
                        self.content_area,
                        ft.Container(
                            content=self.nav_bar,
                            border=ft.Border.only(top=ft.BorderSide(1, Color.BORDER)),
                        ),
                    ],
                    expand=True,
                    spacing=0,
                ),
                expand=True,
            )
        )

    def _on_nav_change(self, e):
        """导航栏切换事件"""
        index = e.control.selected_index
        view_map = {0: "connection", 1: "file_list", 2: "playback", 3: "settings"}
        self.switch_to_view(view_map.get(index, "playback"))

    def _on_app_lifecycle_state_change(self, e):
        """应用生命周期变化：后台时标记冻结，回前台时续传下载队列"""
        state = e.state
        logger.info(f"应用生命周期变化: {state}")
        if state in (
            ft.AppLifecycleState.PAUSE,
            ft.AppLifecycleState.HIDE,
            ft.AppLifecycleState.INACTIVE,
        ):
            self.app_backgrounded = True
        elif state in (ft.AppLifecycleState.RESUME, ft.AppLifecycleState.SHOW):
            was_backgrounded = self.app_backgrounded
            self.app_backgrounded = False
            if was_backgrounded and hasattr(self.file_list_view, "on_app_resumed"):
                try:
                    self.file_list_view.on_app_resumed()
                except Exception as ex:
                    logger.error(f"回前台恢复下载失败: {ex}")

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
            "settings": (self.settings_view, 3),
        }

        view, nav_index = view_map.get(view_name, (self.playback_view, 2))

        # 通知旧视图切出（停止定时刷新等）
        if self.current_view is not view and hasattr(
            self.current_view, "on_view_deactivated"
        ):
            try:
                self.current_view.on_view_deactivated()
            except Exception as e:
                logger.error(f"视图切出回调失败: {e}")

        # Flet 0.86：控件脱离页面后会被冻结且不可复用，切回时必须重建
        if hasattr(view, "rebuild"):
            self.content_area.content = view.rebuild()
        else:
            self.content_area.content = view.build()
        self.nav_bar.selected_index = nav_index
        self.current_view = view

        # 保存当前视图到配置
        self.app_context["config_manager"].set("app.last_view", view_name)
        self.app_context["config_manager"].save_config()

        # 通知视图激活
        if hasattr(view, "on_view_activated"):
            view.on_view_activated()

        self.page.update()

    def show_status_message(self, message: str, message_type: str = "info"):
        """在当前视图中显示状态消息"""
        if hasattr(self.current_view, "show_message"):
            self.current_view.show_message(message, message_type)

    def get_view(self, view_name: str):
        """获取指定的视图对象"""
        if view_name == "connection":
            return self.connection_view
        elif view_name == "file_list":
            return self.file_list_view
        elif view_name == "playback":
            return self.playback_view
        elif view_name == "settings":
            return self.settings_view
        return None
