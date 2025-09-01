"""
视图管理器 - 管理三个主要界面的切换
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
import logging

logger = logging.getLogger(__name__)

class ViewManager:
    """管理应用的三个主要视图：连接、文件列表、播放"""
    
    def __init__(self, app):
        self.app = app
        self.current_view = None
        
        # 创建主容器
        self.main_container = toga.Box(style=Pack(direction=COLUMN))
        
        # 创建导航栏
        self.create_navigation()
        
        # 创建视图容器
        self.view_container = toga.Box(style=Pack(direction=COLUMN, flex=1))
        
        # 组装主界面
        self.main_container.add(self.navigation_box)
        self.main_container.add(self.view_container)
        
        # 创建各个视图
        from .connection_view import ConnectionView
        from .file_list_view import FileListView
        from .playback_view import PlaybackView
        from ..services.music_service import MusicService
        
        # 创建音乐服务
        self.music_service = MusicService(
            music_library=app.music_library,
            nextcloud_client=app.nextcloud_client,
            config_manager=app.config_manager
        )
        
        # 保存音乐服务引用到app中，以便其他地方可以更新NextCloud客户端
        app.music_service = self.music_service
        
        # 设置播放列表变化回调来更新app状态
        self.music_service.set_playlist_change_callback(self._handle_playlist_change)
        self.music_service.set_sync_folder_change_callback(self._handle_sync_folder_change)
        
        self.connection_view = ConnectionView(app, self)
        self.file_list_view = FileListView(self.music_service, self)
        self.playback_view = PlaybackView(app, self)
    
    def _handle_playlist_change(self, playlist: list, start_index: int):
        """处理播放列表变化"""
        try:
            # 更新app的播放列表
            self.app.set_playlist_from_music_list([{'name': name} for name in playlist])
            self.app.current_song_index = start_index
            logger.info(f"播放列表已更新: {len(playlist)} 首歌曲，开始索引: {start_index}")
        except Exception as e:
            logger.error(f"处理播放列表变化失败: {e}")
    
    def _handle_sync_folder_change(self, sync_folder: str):
        """处理同步文件夹变化"""
        try:
            # 更新app的同步文件夹
            self.app.current_sync_folder = sync_folder
            logger.info(f"同步文件夹已更新: {sync_folder}")
        except Exception as e:
            logger.error(f"处理同步文件夹变化失败: {e}")
        
        # 获取上次保存的视图，如果没有则默认显示播放界面
        last_view = self.app.config_manager.get("app.last_view", "playback")
        self.switch_to_view(last_view)
    
    def create_navigation(self):
        """创建导航栏"""
        self.navigation_box = toga.Box(style=Pack(
            direction=ROW, 
            padding=10,
            background_color="#f0f0f0"
        ))
        
        # 创建导航按钮
        self.connection_button = toga.Button(
            "🌐 连接配置",
            on_press=lambda widget: self.switch_to_view("connection"),
            style=Pack(flex=1, padding=5)
        )
        
        self.file_list_button = toga.Button(
            "📁 文件列表",
            on_press=lambda widget: self.switch_to_view("file_list"),
            style=Pack(flex=1, padding=5)
        )
        
        self.playback_button = toga.Button(
            "🎵 播放界面",
            on_press=lambda widget: self.switch_to_view("playback"),
            style=Pack(flex=1, padding=5)
        )
        
        self.navigation_box.add(self.connection_button)
        self.navigation_box.add(self.file_list_button)
        self.navigation_box.add(self.playback_button)
        
        # 初始化按钮状态
        self.update_navigation_buttons("connection")
    
    def switch_to_view(self, view_name: str):
        """切换到指定视图"""
        logger.info(f"切换到视图: {view_name}")
        
        # 清空当前视图容器
        self.view_container.clear()
        
        # 切换视图
        if view_name == "connection":
            self.view_container.add(self.connection_view.container)
            self.current_view = self.connection_view
        elif view_name == "file_list":
            self.view_container.add(self.file_list_view.container)
            self.current_view = self.file_list_view
        elif view_name == "playback":
            self.view_container.add(self.playback_view.container)
            self.current_view = self.playback_view
        
        # 更新导航按钮状态
        self.update_navigation_buttons(view_name)
        
        # 保存当前视图到配置
        self.app.config_manager.set("app.last_view", view_name)
        self.app.config_manager.save_config()
        
        # 通知视图激活
        if hasattr(self.current_view, 'on_view_activated'):
            self.current_view.on_view_activated()
    
    def update_navigation_buttons(self, active_view: str):
        """更新导航按钮的激活状态"""
        # 重置所有按钮样式
        buttons = {
            "connection": self.connection_button,
            "file_list": self.file_list_button,
            "playback": self.playback_button
        }
        
        for view_name, button in buttons.items():
            if view_name == active_view:
                button.style.background_color = "#007AFF"
                button.style.color = "white"
            else:
                button.style.background_color = "#f0f0f0"
                button.style.color = "black"
    
    def get_container(self):
        """获取主容器"""
        return self.main_container
    
    def enable_file_list_view(self, enabled: bool = True):
        """启用/禁用文件列表视图"""
        self.file_list_button.enabled = enabled
    
    def enable_playback_view(self, enabled: bool = True):
        """启用/禁用播放视图"""
        self.playback_button.enabled = enabled
    
    def show_status_message(self, message: str, message_type: str = "info"):
        """显示状态消息（在当前视图中）"""
        if hasattr(self.current_view, 'show_message'):
            self.current_view.show_message(message, message_type)
        else:
            logger.info(f"[{message_type.upper()}] {message}")
    
    def get_view(self, view_name: str):
        """获取指定的视图对象"""
        if view_name == "connection":
            return self.connection_view
        elif view_name == "file_list":
            return self.file_list_view
        elif view_name == "playback":
            return self.playback_view
        else:
            logger.warning(f"未知的视图名称: {view_name}")
            return None
    