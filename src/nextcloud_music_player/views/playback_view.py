"""
播放界面视图 - 音乐播放控制和显示
基于 playlists.json 的播放列表管理系统
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
import asyncio
import logging
from typing import Optional, Dict, List, Any
from enum import Enum
import os
import json
from datetime import datetime
from ..services.playback_service import PlaybackService
from ..services.playlist_manager import PlaylistManager
from ..services.playback_controller import PlaybackController, PlayMode
from .components.playlist_component import PlaylistViewComponent
from .components.playback_control_component import PlaybackControlComponent

logger = logging.getLogger(__name__)

class PlaybackView:
    """音乐播放界面视图 - 基于 playlists.json 的播放列表管理"""
    
    def __init__(self, app, view_manager):
        self.app = app  # 保留app引用以传递给service
        self.view_manager = view_manager
        self.play_mode = PlayMode.REPEAT_ONE

        # 初始化播放服务
        self.playback_service = PlaybackService(
            config_manager=app.config_manager,
            music_service=getattr(app, 'music_service', None),
            play_music_callback=None,  # 不使用app的回调，由服务自己处理
            add_background_task_callback=app.add_background_task
        )
        
        # 初始化播放列表管理器
        self.playlist_manager = PlaylistManager(
            config_manager=app.config_manager,
            music_service=getattr(app, 'music_service', None)
        )
        
        # 初始化播放控制器
        self.playback_controller = PlaybackController(
            playback_service=self.playback_service,
            playlist_manager=self.playlist_manager,
            play_song_callback=self.play_selected_song
        )
        
        # 初始化播放控制组件
        self.playback_control_component = PlaybackControlComponent(
            app=app,
            playback_controller=self.playback_controller,
            on_play_mode_change_callback=self.on_play_mode_changed
        )
        
        # 初始化播放列表视图组件
        self.playlist_component = PlaylistViewComponent(
            app=app,
            playlist_manager=self.playlist_manager,
            on_song_select_callback=self.on_playlist_song_selected,
            on_playlist_change_callback=self.on_playlist_changed
        )
        
        # 初始化歌词显示组件
        try:
            from .components.lyrics_component import LyricsDisplayComponent
            
            # 获取歌词服务（如果应用有的话）
            lyrics_service = getattr(app, 'lyrics_service', None)
            
            self.lyrics_component = LyricsDisplayComponent(
                app=app,
                config_manager=app.config_manager,
                lyrics_service=lyrics_service
            )
            logger.info("歌词组件初始化成功")
        except ImportError as e:
            logger.warning(f"歌词组件导入失败，将不显示歌词: {e}")
            self.lyrics_component = None
        
        # 设置播放控制回调
        self.playback_service.set_playback_callbacks(
            pause_callback=None,  # 由服务自己处理
            stop_callback=None,   # 由服务自己处理
            get_play_mode_callback=None,
            get_is_playing_callback=None,  # 由服务自己处理
            set_volume_callback=lambda volume: setattr(app, 'volume', volume),
            seek_to_position_callback=None,
            get_duration_callback=None,
            set_play_mode_callback=None
        )
        
        # 确保播放控制器、播放服务和视图的播放模式同步
        self.playback_controller.set_play_mode(PlayMode.REPEAT_ONE)
        self.playback_service.set_play_mode_by_string("repeat_one")
        logger.info("初始化播放模式为单曲循环")
        
        # 播放列表管理 - 由播放列表管理器和组件处理
        self.current_playlist_data = None  # 当前播放列表数据（保留以供兼容）
        self.current_song_info = None      # 当前歌曲信息（从 music_list.json 获取）
        self.current_song_state = {        # 当前歌曲播放状态
            'is_playing': False,
            'is_paused': False,
            'position': 0,
            'duration': 0,
            'play_count': 0,
            'last_played': None
        }
        # 播放完成标记
        self._song_completed = False
        self._last_position = 0
        # 切换歌曲状态标志（防止重复点击）
        self._switching_song = False
        
        # 构建界面
        self.build_interface()
        
        # 启动UI更新定时器
        self.start_ui_timer()
        
        # 更新播放模式按钮状态（初始化为单曲循环）
        # 更新播放控制组件的播放模式按钮
        if hasattr(self, 'playback_control_component') and self.playback_control_component:
            self.playback_control_component.update_mode_buttons()
        
        # 播放列表组件会自动处理初始化和加载
    
    
    def build_interface(self):
        """构建播放界面 - iOS优化版本"""
        # 创建可滚动视图容器，减少padding
        self.container = toga.ScrollContainer(
            content=toga.Box(style=Pack(direction=COLUMN, padding=8)),
            style=Pack(flex=1)
        )
        
        # 获取容器内容
        content_box = self.container.content
        
        # 消息显示区域 - 减少padding
        self.message_box = toga.Box(style=Pack(
            direction=ROW,
            padding=5,
            visibility="hidden"
        ))
        
        # 标题 - 减少字体大小和padding
        title = toga.Label(
            "🎵 音乐播放器",
            style=Pack(
                padding=(0, 0, 8, 0),
                font_size=16,
                font_weight="bold",
                text_align="center"
            )
        )
        
        # 添加消息框
        content_box.add(self.message_box)
        
        # 当前播放信息区域
        self.create_now_playing_section()
        
        # 播放控制区域 - 使用播放控制组件
        self.playback_controls_widget = self.playback_control_component.widget
        
        # 进度条区域
        self.create_progress_section()
        
        # 播放列表区域 - 使用播放列表组件
        self.playlist_box = self.playlist_component.get_widget()
        
        # 歌词显示区域
        if self.lyrics_component:
            self.lyrics_box = self.lyrics_component.get_widget()
        else:
            # 如果歌词组件不可用，创建占位符
            self.lyrics_box = toga.Box(style=Pack(
                direction=COLUMN,
                padding=8
            ))
            lyrics_placeholder = toga.Label(
                "歌词功能不可用",
                style=Pack(
                    text_align="center",
                    color="#999999",
                    font_size=11,
                    padding=20
                )
            )
            self.lyrics_box.add(lyrics_placeholder)
        
        # 组装界面
        content_box.add(title)
        content_box.add(self.now_playing_box)
        content_box.add(self.playback_controls_widget)  # 使用新的播放控制组件
        content_box.add(self.progress_box)
        
        # 创建视图切换按钮
        view_switch_box = toga.Box(style=Pack(
            direction=ROW,
            padding=5,
            alignment="center"
        ))
        
        self.playlist_tab_button = toga.Button(
            "播放列表",
            on_press=self.show_playlist_view,
            style=Pack(
                width=80,
                height=30,
                padding=(0, 2),
                font_size=11,
                background_color="#007bff",
                color="white"
            )
        )
        
        self.lyrics_tab_button = toga.Button(
            "歌词",
            on_press=self.show_lyrics_view,
            style=Pack(
                width=80,
                height=30,
                padding=(0, 2),
                font_size=11
            )
        )
        
        view_switch_box.add(self.playlist_tab_button)
        view_switch_box.add(self.lyrics_tab_button)
        
        # 内容区域容器
        self.content_container = toga.Box(style=Pack(
            direction=COLUMN,
            flex=1
        ))
        
        # 默认显示播放列表
        self.current_view = "playlist"
        self.content_container.add(self.playlist_box)
        
        content_box.add(view_switch_box)
        content_box.add(self.content_container)
        
    def show_playlist_view(self, widget):
        """显示播放列表视图"""
        try:
            if self.current_view != "playlist":
                self.content_container.clear()
                self.content_container.add(self.playlist_box)
                self.current_view = "playlist"
                
                # 更新按钮样式
                self.playlist_tab_button.style.background_color = "#007bff"
                self.playlist_tab_button.style.color = "white"
                self.lyrics_tab_button.style.background_color = "transparent"
                self.lyrics_tab_button.style.color = "#007bff"
                
                logger.debug("切换到播放列表视图")
        except Exception as e:
            logger.error(f"显示播放列表视图失败: {e}")
    
    def show_lyrics_view(self, widget):
        """显示歌词视图"""
        try:
            if self.current_view != "lyrics":
                self.content_container.clear()
                self.content_container.add(self.lyrics_box)
                self.current_view = "lyrics"
                
                # 更新按钮样式
                self.lyrics_tab_button.style.background_color = "#007bff"
                self.lyrics_tab_button.style.color = "white"
                self.playlist_tab_button.style.background_color = "transparent"
                self.playlist_tab_button.style.color = "#007bff"
                
                logger.debug("切换到歌词视图")
        except Exception as e:
            logger.error(f"显示歌词视图失败: {e}")
    
    def update_services(self):
        """更新服务依赖 - 当app的服务实例更新时调用"""
        if hasattr(self.app, 'music_service'):
            self.playback_service.music_service = self.app.music_service
            self.playlist_manager.music_service = self.app.music_service
    
    def on_playlist_song_selected(self, song_entry: Dict[str, Any], index: int):
        """播放列表歌曲选择回调"""
        try:
            song_info = song_entry.get('info', {})
            song_name = song_entry.get('name', '')
            logger.info(f"播放列表选择歌曲: {song_info.get('name', song_name)} (索引: {index})")
            
            # 更新当前歌曲信息
            self.current_song_info = song_info
            self.update_current_song_info()
            
            # 加载歌词
            if self.lyrics_component and song_name:
                self.lyrics_component.load_lyrics_for_song(song_name)
            
            # 如果设置了自动播放，则开始播放
            auto_play = self.app.config_manager.get("player.auto_play_on_select", True)
            if auto_play:
                self.app.add_background_task(self.play_selected_song(song_info))
                
        except Exception as e:
            logger.error(f"处理播放列表歌曲选择失败: {e}")
    
    def on_playlist_changed(self, change_type: str):
        """播放列表改变回调"""
        try:
            logger.info(f"播放列表发生改变: {change_type}")
            
            # 根据改变类型执行相应操作
            if change_type in ["song_added", "song_removed", "cleared", "playlist_created"]:
                # 更新当前播放列表数据缓存
                self.current_playlist_data = self.playlist_manager.get_current_playlist()
                
                # 如果播放列表被清空，停止播放
                if change_type == "cleared":
                    self.app.add_background_task(self.stop_music())
                    
        except Exception as e:
            logger.error(f"处理播放列表改变失败: {e}")
    
    def on_play_mode_changed(self, mode: str):
        """播放模式改变回调"""
        try:
            logger.info(f"播放模式已改变为: {mode}")
            # 同步更新视图的播放模式
            if mode == "normal":
                self.play_mode = PlayMode.NORMAL
            elif mode == "repeat_one":
                self.play_mode = PlayMode.REPEAT_ONE
            elif mode == "repeat_all":
                self.play_mode = PlayMode.REPEAT_ALL
            elif mode == "shuffle":
                self.play_mode = PlayMode.SHUFFLE
                
        except Exception as e:
            logger.error(f"处理播放模式改变失败: {e}")
    
    async def play_selected_song(self, song_info: Dict[str, Any]):
        """播放选中的歌曲"""
        try:
            # 如果歌曲已下载，直接播放本地文件
            if song_info.get('is_downloaded') and song_info.get('filepath'):
                local_path = song_info['filepath']
                if os.path.exists(local_path):
                    await self.play_music_file(local_path)
                    return
            
            # 否则需要先下载
            song_name = song_info.get('name', '')
            remote_path = song_info.get('remote_path', '')
            if self.app.music_service and remote_path:
                # 使用music_service下载文件，然后播放
                download_success = await self.app.music_service.download_file(remote_path, song_name)
                if download_success:
                    # 重新获取文件信息以获取本地路径
                    updated_song_info = self.app.music_library.get_song_info(song_name)
                    if updated_song_info and updated_song_info.get('filepath'):
                        await self.play_music_file(updated_song_info['filepath'])
                    else:
                        logger.error(f"下载成功但无法获取本地文件路径: {song_name}")
                else:
                    logger.error(f"下载歌曲失败: {song_name}")
            else:
                logger.error(f"无法下载歌曲，缺少必要信息: {song_name}")
            
        except Exception as e:
            logger.error(f"播放选中歌曲失败: {e}")
    
    async def play_music_file(self, file_path: str):
        """播放音乐文件"""
        try:
            logger.info(f"开始播放音乐文件: {file_path}")
            
            # 设置当前歌曲
            self.playback_service.set_current_song(file_path)
            
            # 开始播放 - 使用超时保护
            try:
                await asyncio.wait_for(self.playback_service.play_music(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.error("播放音乐超时，可能存在死锁")
                return
            
            # 更新播放状态
            self.current_song_state['is_playing'] = True
            self.current_song_state['is_paused'] = False
            
            # 自动加载歌词 - 从文件路径提取歌曲名（异步执行，不阻塞）
            if self.lyrics_component:
                try:
                    import os
                    song_name = os.path.basename(file_path)
                    logger.info(f"播放音乐时自动加载歌词: {song_name}")
                    # 使用后台任务加载歌词，避免阻塞播放
                    if hasattr(self.app, 'add_background_task'):
                        self.app.add_background_task(
                            self._load_lyrics_async(song_name)
                        )
                    else:
                        self.lyrics_component.load_lyrics_for_song(song_name, auto_download=True)
                except Exception as lyrics_error:
                    logger.warning(f"自动加载歌词失败: {lyrics_error}")
            
            # 更新UI
            self.update_ui()
            logger.info(f"音乐文件播放成功: {file_path}")
            
        except Exception as e:
            logger.error(f"播放音乐文件失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
    
    async def _load_lyrics_async(self, song_name: str):
        """异步加载歌词"""
        try:
            if self.lyrics_component:
                self.lyrics_component.load_lyrics_for_song(song_name, auto_download=True)
        except Exception as e:
            logger.warning(f"异步加载歌词失败: {e}")
            
    def show_message(self, message: str, message_type: str = "info"):
        """显示消息提示"""
        # 清除之前的消息
        self.message_box.clear()
        
        # 根据类型设置样式
        if message_type == "error":
            self.message_box.style.background_color = "#ffcccc"
            icon = "❌ "
        elif message_type == "success":
            self.message_box.style.background_color = "#ccffcc"
            icon = "✅ "
        elif message_type == "warning":
            self.message_box.style.background_color = "#ffffcc"
            icon = "⚠️ "
        else:  # info
            self.message_box.style.background_color = "#cce5ff"
            icon = "ℹ️ "
            
        # 创建消息标签
        message_label = toga.Label(
            f"{icon}{message}",
            style=Pack(
                padding=10,
                flex=1,
                color="#212529"
            )
        )
        
        self.message_box.add(message_label)
        self.message_box.style.visibility = "visible"
        
        # 设置定时器隐藏消息
        async def hide_message():
            await asyncio.sleep(5)
            self.message_box.style.visibility = "hidden"
        
        self.app.add_background_task(hide_message())
        logger.info(f"[{message_type.upper()}] {message}")

            
    def load_current_playlist(self):
        """加载当前播放列表"""
        
        try:
            playlists_data = self.playback_service.load_playlists()
            current_playlist_id = playlists_data.get("current_playlist_id")
            
            if current_playlist_id:
                self.current_playlist_data = self.playback_service.get_playlist_by_id(current_playlist_id)
                logger.info(f"加载当前播放列表: {self.current_playlist_data.get('name', '未知') if self.current_playlist_data else '无'}")
            else:
                # 创建临时播放列表
                self.current_playlist_data = {
                    "id": -1,
                    "name": "临时播放列表",
                    "songs": [],
                    "folder_path": "",
                    "created_at": datetime.now().isoformat(),
                    "last_played": None,
                    "play_count": 0,
                    "current_index": 0
                }
                logger.info("创建临时播放列表")
        except Exception as e:
            logger.error(f"加载播放列表失败: {e}")
            # 创建空的临时播放列表
            self.current_playlist_data = {
                "id": -1,
                "name": "临时播放列表",
                "songs": [],
                "folder_path": "",
                "created_at": datetime.now().isoformat(),
                "last_played": None,
                "play_count": 0,
                "current_index": 0
            }
    
    def get_song_info_from_music_list(self, song_name: str) -> Dict[str, Any]:
        """从 music_list.json 获取歌曲信息"""
        song_info = self.playback_service.get_song_info(song_name)
        return song_info
       
    
    def set_current_song_index(self, index: int):
        """设置当前播放歌曲索引"""
        try:
            if not self.current_playlist_data or not self.current_playlist_data["songs"]:
                return
            
            if 0 <= index < len(self.current_playlist_data["songs"]):
                self.current_playlist_data["current_index"] = index
                self.save_current_playlist()
                self.update_current_song_info()
                logger.info(f"设置当前播放索引: {index}")
        except Exception as e:
            logger.error(f"设置播放索引失败: {e}")
    
    def get_current_song_entry(self) -> Optional[Dict[str, Any]]:
        """获取当前播放歌曲条目"""
        try:
            if not self.current_playlist_data or not self.current_playlist_data["songs"]:
                return None
            
            current_index = self.current_playlist_data.get("current_index", 0)
            if 0 <= current_index < len(self.current_playlist_data["songs"]):
                return self.current_playlist_data["songs"][current_index]
            
            return None
        except Exception as e:
            logger.error(f"获取当前歌曲条目失败: {e}")
            return None
    
    def update_current_song_state(self, **state_updates):
        """更新当前歌曲播放状态"""
        try:
            current_song = self.get_current_song_entry()
            if current_song:
                current_song["state"].update(state_updates)
                if 'last_played' not in state_updates and any(k in state_updates for k in ['play_count']):
                    current_song["state"]["last_played"] = datetime.now().isoformat()
                self.save_current_playlist()
        except Exception as e:
            logger.error(f"更新歌曲状态失败: {e}")
    
    def update_current_song_info(self):
        """更新当前歌曲信息（从music_library获取详细信息）"""
        try:
            # 使用播放列表组件获取当前歌曲信息
            current_song = self.playlist_component.get_current_song_info()
            if not current_song:
                self.current_song_info = None
                return
            
            # 获取歌曲名称和信息
            song_info = current_song.get('info', {})
            song_name = current_song.get('name') or song_info.get('name')
            
            if not song_name:
                self.current_song_info = None
                return
            
            # 从music_library获取详细信息（如果可用）
            music_library = getattr(self.app, 'music_library', None)
            if music_library:
                detailed_info = music_library.get_song_info(song_name)
                if detailed_info:
                    # 合并播放列表中的信息和音乐库中的详细信息
                    self.current_song_info = {**song_info, **detailed_info}
                    logger.debug(f"更新歌曲信息: {song_name}")
                else:
                    # 使用播放列表中的信息
                    self.current_song_info = song_info
                    logger.warning(f"未在音乐库中找到歌曲详细信息: {song_name}")
            else:
                # 使用播放列表中的信息
                self.current_song_info = song_info
                logger.warning("music_library不可用")
                logger.warning("music_library不可用")
        
        except Exception as e:
            logger.error(f"更新当前歌曲信息失败: {e}")
            self.current_song_info = None
    
    def refresh_playlist_display(self):
        """刷新播放列表显示 - 使用播放列表组件"""
        try:
            if hasattr(self, 'playlist_component'):
                self.playlist_component.refresh_display()
        except Exception as e:
            logger.error(f"刷新播放列表显示失败: {e}")
    
    
    def create_now_playing_section(self):
        """创建当前播放信息区域 - iOS优化版本"""
        self.now_playing_box = toga.Box(style=Pack(
            direction=COLUMN,
            padding=8,
            background_color="#f8f9fa"
        ))
        
        # 当前歌曲信息 - 减小字体
        self.song_title_label = toga.Label(
            "未选择歌曲",
            style=Pack(
                font_size=14,
                font_weight="bold",
                text_align="center",
                padding=(0, 0, 3, 0),
                color="#212529"
            )
        )
        
        self.song_info_label = toga.Label(
            "选择一首歌曲开始播放",
            style=Pack(
                font_size=10,
                color="#666666",
                text_align="center",
                padding=(0, 0, 5, 0)
            )
        )
        
        # 播放状态 - 减小字体
        self.status_label = toga.Label(
            "⏹️ 停止",
            style=Pack(
                font_size=12,
                text_align="center",
                padding=(3, 0),
                color="#495057"
            )
        )
        
        self.now_playing_box.add(self.song_title_label)
        self.now_playing_box.add(self.song_info_label)
        self.now_playing_box.add(self.status_label)
    
    def create_playback_controls(self):
        """创建播放控制按钮 - iOS优化版本 - 已迁移到播放控制组件"""
        # 这个方法已经被 PlaybackControlComponent 取代
        pass
    
    def create_progress_section(self):
        """创建播放进度区域 - iOS优化版本"""
        self.progress_box = toga.Box(style=Pack(
            direction=COLUMN,
            padding=8
        ))
        
        # 时间显示 - 减小字体
        time_box = toga.Box(style=Pack(direction=ROW, padding=(0, 0, 3, 0)))
        
        self.current_time_label = toga.Label(
            "00:00",
            style=Pack(
                flex=0, 
                padding=(0, 5, 0, 0),
                color="#495057",
                font_size=10
            )
        )
        
        self.total_time_label = toga.Label(
            "00:00",
            style=Pack(
                flex=0, 
                text_align="right",
                color="#495057",
                font_size=10
            )
        )
        
        # 进度条（使用滑块模拟）- 减小padding
        self.progress_slider = toga.Slider(
            min=0,
            max=100,
            value=0,
            on_change=self.on_seek,
            style=Pack(flex=1, padding=(0, 5))
        )
        
        # 添加防抖控制变量
        self._updating_progress = False  # 标记是否正在程序更新进度条
        self._last_user_seek_time = 0  # 用户最后一次拖拽时间
        
        time_box.add(self.current_time_label)
        time_box.add(self.progress_slider)
        time_box.add(self.total_time_label)
        
        self.progress_box.add(time_box)
    
    def create_volume_and_mode_section(self):
        """创建音量和播放模式组合控制区域 - 已迁移到播放控制组件"""
        # 这个方法已经被 PlaybackControlComponent 取代
        pass
    
    def create_playlist_section(self):
        """创建播放列表区域 - iOS优化版本"""
        self.playlist_box = toga.Box(style=Pack(
            direction=COLUMN,
            padding=8,
            flex=1
        ))
        
        # 播放列表标题和管理按钮 - 减小按钮尺寸
        playlist_header = toga.Box(style=Pack(direction=ROW, padding=(0, 0, 5, 0)))
        
        playlist_label = toga.Label(
            "播放列表:",
            style=Pack(
                flex=1,
                font_weight="bold",
                color="#212529",
                font_size=12
            )
        )
        
        # 播放列表管理按钮 - 减小尺寸
        self.save_playlist_button = toga.Button(
            "💾",
            on_press=self.save_playlist_as_new,
            style=Pack(
                width=30,
                height=25,
                padding=(0, 2, 0, 0),
                font_size=10
            )
        )
        
        self.manage_playlists_button = toga.Button(
            "📋",
            on_press=self.show_playlist_manager,
            style=Pack(
                width=30,
                height=25,
                font_size=10
            )
        )
        
        playlist_header.add(playlist_label)
        playlist_header.add(self.save_playlist_button)
        playlist_header.add(self.manage_playlists_button)
        
        # 添加播放列表组件到布局
        self.playlist_box.add(playlist_header)
        self.playlist_box.add(self.playlist_component.view)
    
    def start_ui_timer(self):
        """启动UI更新定时器"""
        logger.info("启动UI更新定时器")
        self.update_ui()
        # 使用异步方式，在主线程中更新
        try:
            if hasattr(self.app, 'add_background_task'):
                logger.info("使用app.add_background_task启动UI更新")
                # 创建协程并包装为可调用的函数
                def start_task():
                    import asyncio
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(self.schedule_ui_update())
                        logger.info("成功创建UI更新协程任务")
                    except Exception as e:
                        logger.error(f"创建协程任务失败: {e}")
                
                self.app.add_background_task(start_task)
            else:
                logger.warning("没有找到add_background_task方法，UI更新定时器无法启动")
        except Exception as e:
            logger.error(f"启动UI更新定时器失败: {e}")
    
    async def schedule_ui_update(self):
        """定时更新UI - 在主线程异步执行"""
        logger.info("开始UI更新定时器")
        # iOS特殊处理：降低更新频率，避免卡顿
        from ..platform_audio import is_ios
        update_interval = 2.0 if is_ios() else 0.5  # iOS用2秒，其他平台0.5秒
        logger.info(f"设置UI更新间隔: {update_interval}秒")
        
        while True:
            await asyncio.sleep(update_interval)
            try:
                # 只更新播放进度，避免触发列表更新
                self.update_progress_only()
            except Exception as e:
                logger.error(f"UI更新失败: {e}")
    
    def update_progress_only(self):
        """只更新播放进度，不更新列表等复杂UI组件"""
        try:
            # iOS特殊处理：添加防抖机制
            from ..platform_audio import is_ios
            
            # 更新播放进度（从音频播放器获取实时状态）
            position = 0
            duration = 0
            
            # 从音频播放器获取实时播放位置和时长
            if self.playback_service.audio_player:
                try:
                    position = self.playback_service.audio_player.get_position()
                    duration = self.playback_service.audio_player.get_duration()
                    
                    # iOS特殊处理：增加额外的日志级别控制
                    if is_ios():
                        # 只在重要变化时记录日志
                        if not hasattr(self, '_last_logged_position') or abs(position - self._last_logged_position) > 5:
                            logger.info(f"iOS位置更新: {position:.2f}秒 / {duration:.2f}秒")
                            self._last_logged_position = position
                    else:
                        logger.debug(f"update_progress_only: position={position:.2f}, duration={duration:.2f}")
                    
                    # 确保值有效（iOS现在返回0而不是负数）
                    if position < 0:
                        position = 0
                    if duration <= 0:
                        # 如果无法从播放器获取时长，尝试从缓存获取
                        if hasattr(self, 'duration') and self.duration > 0:
                            duration = self.duration
                            logger.debug(f"使用缓存的时长: {duration}")
                        else:
                            # 尝试从歌曲信息获取时长
                            current_song = self.get_current_song_entry()
                            if current_song and current_song.get("info"):
                                song_info = current_song["info"]
                                if "duration" in song_info and song_info["duration"] > 0:
                                    duration = song_info["duration"]
                                    logger.debug(f"从歌曲信息获取时长: {duration}")
                        
                    # 更新本地状态（用于其他地方可能的引用）
                    if duration > 0:  # 只有在获取到有效时长时才更新
                        self.position = position
                        self.duration = duration
                        self.current_song_state['position'] = position
                        self.current_song_state['duration'] = duration
                    
                    # 检测播放完成并自动播放下一曲
                    if duration > 0 and position > 0:
                        progress_ratio = position / duration
                        # iOS特殊处理：提高完成阈值，避免频繁触发
                        completion_threshold = 0.98 if is_ios() else 0.99
                        
                        # 如果播放进度超过阈值，认为歌曲播放完成
                        if progress_ratio >= completion_threshold and not self._song_completed:
                            logger.info(f"歌曲播放完成，进度: {progress_ratio:.1%}")
                            self._song_completed = True  # 标记歌曲已完成
                            
                            # 立即停止UI更新避免后续的跳转警告
                            logger.info("歌曲完成，准备处理下一曲逻辑")
                            
                            # 使用异步方式处理下一曲播放，避免阻塞UI
                            try:
                                if hasattr(self.app, 'add_background_task'):
                                    self.app.add_background_task(self._auto_play_next_song)
                                    logger.info("已添加自动播放任务到后台")
                                else:
                                    # 备用方案：创建独立的异步任务
                                    import asyncio
                                    loop = asyncio.get_event_loop()
                                    loop.create_task(self._auto_play_next_song())
                                    logger.info("已创建独立的自动播放任务")
                            except Exception as task_error:
                                logger.error(f"创建自动播放任务失败: {task_error}")
                                # 最后的备用方案：直接调用同步版本
                                try:
                                    import threading
                                    def run_auto_play():
                                        import asyncio
                                        asyncio.run(self._auto_play_next_song())
                                    thread = threading.Thread(target=run_auto_play, daemon=True)
                                    thread.start()
                                    logger.info("已在独立线程中启动自动播放")
                                except Exception as thread_error:
                                    logger.error(f"线程启动自动播放也失败: {thread_error}")
                        # 重置播放完成标记（当位置明显减少时，比如重新开始播放或切换歌曲）
                        elif progress_ratio < 0.95 and self._song_completed:
                            logger.debug("歌曲位置重置，清除播放完成标记")
                            self._song_completed = False
                    
                except Exception as e:
                    logger.error(f"获取播放位置失败: {e}")
                    # 使用缓存值
                    position = getattr(self, 'position', 0)
                    duration = getattr(self, 'duration', 0)
            else:
                logger.debug("update_progress_only: 没有音频播放器")
                # 使用缓存值
                position = getattr(self, 'position', 0)
                duration = getattr(self, 'duration', 0)
            
            if duration > 0:
                progress_percent = (position / duration) * 100
                
                # 只有在进度变化较大时才更新进度条，减少触发on_change
                current_progress = getattr(self.progress_slider, 'value', 0)
                if abs(progress_percent - current_progress) > 0.1:  # 只有变化超过0.1%才更新
                    self._updating_progress = True
                    self.progress_slider.value = progress_percent
                    self._updating_progress = False
                
                # 更新时间显示
                current_min = int(position // 60)
                current_sec = int(position % 60)
                total_min = int(duration // 60)
                total_sec = int(duration % 60)
                
                self.current_time_label.text = f"{current_min:02d}:{current_sec:02d}"
                self.total_time_label.text = f"{total_min:02d}:{total_sec:02d}"
                
                # 更新歌词显示位置
                if self.lyrics_component:
                    self.lyrics_component.update_lyrics_position(position)
                
                logger.debug(f"进度更新: {current_min:02d}:{current_sec:02d} / {total_min:02d}:{total_sec:02d}")
            else:
                self._updating_progress = True
                self.progress_slider.value = 0
                self._updating_progress = False
                self.current_time_label.text = "00:00"
                self.total_time_label.text = "00:00"
                logger.debug("进度重置为00:00")
            
            # 更新播放状态（从应用获取实时状态）
            is_playing = getattr(self.app, 'is_playing', False)
            is_paused = getattr(self.app, 'is_paused', False)
            
            if is_playing:
                self.status_label.text = "▶️ 播放中"
                # 更新播放控制组件的播放/暂停按钮
                self.playback_control_component.update_play_pause_button(True)
            elif is_paused:
                self.status_label.text = "⏸️ 暂停"
                self.playback_control_component.update_play_pause_button(False)
            else:
                self.status_label.text = "⏹️ 停止"
                self.playback_control_component.update_play_pause_button(False)
                
        except Exception as e:
            logger.error(f"更新播放进度失败: {e}")
    
    async def _auto_play_next_song(self):
        """自动播放下一曲的内部方法 - 使用播放控制器"""
        try:
            logger.info("进入自动播放下一曲方法")
            
            # 检查是否已经在切换歌曲
            if hasattr(self, '_switching_song') and self._switching_song:
                logger.warning("正在手动切换歌曲，跳过自动播放")
                return
                
            await asyncio.sleep(0.2)  # 延迟稍长一点，确保播放状态稳定
            
            # 使用播放控制器的自动播放逻辑
            success = await self.playback_controller.auto_play_next_song()
            
            if success:
                # 更新播放列表显示
                if hasattr(self, 'playlist_component') and self.playlist_component:
                    self.playlist_component.refresh_display()
                # 更新UI显示
                self.update_ui()
                logger.info("自动播放下一曲成功")
            else:
                logger.info("自动播放下一曲结束或失败")
                
        except Exception as e:
            logger.error(f"自动播放下一曲失败: {e}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
    
    def update_ui(self):
        """更新UI显示"""
        try:
            # 更新当前歌曲信息显示
            self.update_current_song_info()
            
            current_song = self.get_current_song_entry()
            if current_song and self.current_song_info:
                song_info = self.current_song_info
                
                # 显示歌曲标题
                display_title = song_info.get('title', song_info.get('display_name', song_info.get('name', '未知歌曲')))
                if display_title.endswith('.mp3'):
                    display_title = display_title[:-4]
                
                self.song_title_label.text = display_title
                
                # 显示艺术家信息
                artist = song_info.get('artist', '未知艺术家')
                album = song_info.get('album', '')
                if album and album != '未知专辑':
                    self.song_info_label.text = f"艺术家: {artist} | 专辑: {album}"
                else:
                    self.song_info_label.text = f"艺术家: {artist}"
            else:
                self.song_title_label.text = "未选择歌曲"
                self.song_info_label.text = "选择一首歌曲开始播放"
            
            # 更新播放状态（从应用获取实时状态）
            is_playing = getattr(self.app, 'is_playing', False)
            is_paused = getattr(self.app, 'is_paused', False)
            
            if is_playing:
                self.status_label.text = "▶️ 播放中"
                # 更新播放控制组件的播放/暂停按钮
                self.playback_control_component.update_play_pause_button(True)
            elif is_paused:
                self.status_label.text = "⏸️ 暂停"
                self.playback_control_component.update_play_pause_button(False)
            else:
                self.status_label.text = "⏹️ 停止"
                self.playback_control_component.update_play_pause_button(False)
            
            # 更新播放进度（从音频播放器获取实时状态）
            position = 0
            duration = 0
            
            # 从音频播放器获取实时播放位置和时长
            if self.playback_service.audio_player:
                try:
                    position = self.playback_service.audio_player.get_position()
                    duration = self.playback_service.audio_player.get_duration()
                    
                    logger.debug(f"update_ui: position={position:.2f}, duration={duration:.2f}")
                    
                    # 如果返回的值为负数（表示不支持），使用默认值
                    if position < 0:
                        position = 0
                    if duration < 0:
                        duration = 0
                        
                    # 更新本地状态（用于其他地方可能的引用）
                    self.position = position
                    self.duration = duration
                    self.current_song_state['position'] = position
                    self.current_song_state['duration'] = duration
                    
                except Exception as e:
                    logger.error(f"获取播放位置失败: {e}")
                    position = 0
                    duration = 0
            else:
                logger.debug("update_ui: 没有音频播放器")
            
            if duration > 0:
                progress_percent = (position / duration) * 100
                
                # 只有在进度变化较大时才更新进度条，减少触发on_change
                current_progress = getattr(self.progress_slider, 'value', 0)
                if abs(progress_percent - current_progress) > 0.1:  # 只有变化超过0.1%才更新
                    self._updating_progress = True
                    self.progress_slider.value = progress_percent
                    self._updating_progress = False
                
                # 更新时间显示
                current_min = int(position // 60)
                current_sec = int(position % 60)
                total_min = int(duration // 60)
                total_sec = int(duration % 60)
                
                self.current_time_label.text = f"{current_min:02d}:{current_sec:02d}"
                self.total_time_label.text = f"{total_min:02d}:{total_sec:02d}"
                
                # 更新歌词显示位置  
                if self.lyrics_component:
                    self.lyrics_component.update_lyrics_position(position)
            else:
                self._updating_progress = True
                self.progress_slider.value = 0
                self._updating_progress = False
                self.current_time_label.text = "00:00"
                self.total_time_label.text = "00:00"
            
            # 更新音量显示（音量控制现在由播放控制组件处理）
            if hasattr(self, 'playback_control_component') and self.playback_control_component:
                # 播放控制组件会自己处理音量显示更新
                pass
            
            # 更新播放列表
            self.update_playlist_display()
            
            # 更新当前播放列表信息
            self.update_current_playlist_info()
            
            # 更新播放模式按钮状态
            # 更新播放控制组件的播放模式按钮
            if hasattr(self, 'playback_control_component') and self.playback_control_component:
                self.playback_control_component.update_mode_buttons()
            
        except Exception as e:
            logger.error(f"更新UI失败: {e}")
    
    def update_playlist_display(self):
        """更新播放列表显示 - 使用播放列表组件"""
        try:
            # 使用播放列表组件刷新显示
            if hasattr(self, 'playlist_component'):
                self.playlist_component.refresh_display()
        except Exception as e:
            logger.error(f"更新播放列表显示失败: {e}")
    
    def update_current_playlist_info(self):
        """更新当前播放列表信息显示 - 使用播放列表组件"""
        try:
            # 播放列表组件会自动处理信息显示更新
            if hasattr(self, 'playlist_component'):
                current_playlist = self.playlist_manager.get_current_playlist()
                if current_playlist:
                    self.current_playlist_data = current_playlist  # 保持兼容性
                    self.playlist_component.refresh_display()
        except Exception as e:
            logger.error(f"更新播放列表信息失败: {e}")
    
    def clear_current_playlist(self, widget):
        """清空当前播放列表"""
        try:
            if self.current_playlist_data:
                self.current_playlist_data["songs"] = []
                self.current_playlist_data["current_index"] = 0
                self.save_current_playlist()
                self.refresh_playlist_display()
                self.update_current_song_info()
                logger.info("已清空当前播放列表")
        except Exception as e:
            logger.error(f"清空播放列表失败: {e}")
    
    def remove_selected_song(self, widget):
        """移除选中的歌曲 - 使用播放列表组件"""
        try:
            # 通过播放列表组件获取选中的歌曲
            if hasattr(self, 'playlist_component'):
                selected_index = self.playlist_component.get_selected_index()
                if selected_index >= 0:
                    self.remove_song_from_playlist(selected_index)
                else:
                    logger.info("没有选中的歌曲")
            else:
                logger.info("播放列表组件不可用")
        except Exception as e:
            logger.error(f"移除选中歌曲失败: {e}")
    
    async def on_playlist_select(self, widget, selection):
        """播放列表项目选中事件 - 使用播放列表组件"""
        try:
            if selection and self.current_playlist_data and self.current_playlist_data.get("songs"):
                # 通过播放列表组件获取选中的索引
                if hasattr(self, 'playlist_component'):
                    selected_index = self.playlist_component.get_selected_index()
                    if selected_index >= 0:
                        # 设置为当前播放歌曲
                        self.set_current_song_index(selected_index)
                        
                        # 开始播放选中的歌曲
                        await self.play_current_song()
                        
                        # 更新UI显示
                        self.update_ui()
                    else:
                        logger.info("无法获取选中的歌曲索引")
                else:
                    logger.info("播放列表组件不可用")
        except Exception as e:
            logger.error(f"播放列表选择事件处理失败: {e}")
                
        except Exception as e:
            logger.error(f"播放列表选择失败: {e}")
    
    async def play_current_song(self):
        """播放当前选中的歌曲"""
        try:
            logger.info("开始执行play_current_song")
            current_song = self.get_current_song_entry()
            if not current_song:
                logger.warning("没有当前歌曲可播放")
                return
            
            song_info = current_song["info"]
            song_name = current_song["name"]
            logger.info(f"准备播放歌曲: {song_name}")
            
            # 使用playback_service和music_service检查歌曲
            music_service = self.playback_service.music_service
            if not music_service:
                logger.error("音乐服务不可用")
                self.show_message("音乐服务不可用，请重启应用", "error")
                return
                
            # 尝试多种方法获取本地文件路径
            filepath = music_service.get_local_file_path(song_name)
            logger.info(f"使用music_service查询的路径: {filepath}")
            
            # 如果找到了本地文件，直接播放
            if filepath and os.path.exists(filepath):
                # 重置播放完成标记和相关状态
                self._song_completed = False
                self._last_position = 0
                logger.info("已重置播放完成标记和位置")
                
                # 使用播放服务播放
                logger.info("设置当前歌曲到播放服务")
                self.playback_service.set_current_song(filepath)
                logger.info("开始调用播放服务的play_music")
                await self.playback_service.play_music()
                logger.info("播放服务的play_music调用完成")
                
                # 等待一小段时间确保播放开始
                await asyncio.sleep(0.1)
                
                # 更新播放状态
                self.update_current_song_state(
                    play_count=current_song["state"].get("play_count", 0) + 1
                )
                
                # 立即更新UI显示歌曲信息
                self.update_current_song_info()
                self.update_ui()
                
                # 加载歌词
                if self.lyrics_component:
                    self.lyrics_component.load_lyrics_for_song(song_name)
                
                logger.info(f"开始播放: {song_name}")
            else:
                logger.info(f"本地未找到文件，尝试下载: {song_name}")
                # 尝试下载文件
                await self.download_and_play_song(song_name, song_info)
                
        except Exception as e:
            logger.error(f"播放当前歌曲失败: {e}")
            import traceback
            logger.error(f"play_current_song详细错误信息: {traceback.format_exc()}")
    
    async def download_and_play_song(self, song_name: str, song_info: Dict[str, Any]):
        """下载并播放歌曲"""
        try:
            
            # 显示下载中消息
            self.show_message(f"正在下载歌曲: {song_name}", "info")
            
            # 从歌曲信息获取远程路径
            remote_path = song_info.get('remote_path', song_name)
            
            # 优先使用playback_service的下载和播放功能
            success = await self.playback_service.download_and_play_song(song_name, remote_path)
            
            if success:
                # 下载并播放成功，更新歌曲信息
                updated_info = self.playback_service.get_song_info(song_name)
                if updated_info:
                    current_song = self.get_current_song_entry()
                    if current_song:
                        current_song["info"] = updated_info
                        self.save_current_playlist()
                    
                    # 更新播放状态
                    self.update_current_song_state(
                        play_count=current_song["state"].get("play_count", 0) + 1
                    )
                
                # 立即更新UI显示歌曲信息
                self.update_current_song_info()
                self.update_ui()
                
                # 加载歌词
                if self.lyrics_component:
                    self.lyrics_component.load_lyrics_for_song(song_name)
                
                self.show_message(f"下载并播放成功: {song_name}", "success")
                logger.info(f"下载并开始播放: {song_name}")
            else:
                self.show_message(f"下载失败: {song_name}", "error")
                logger.error(f"下载失败: {song_name}")
                
        except Exception as e:
            logger.error(f"下载并播放歌曲失败: {e}")
            self.show_message(f"下载播放失败: {str(e)}", "error")
    
    # =================================================================
    # 公共接口方法 - 供其他视图调用
    # =================================================================
        
    def handle_add_to_playlist(self, music_files: List[Dict[str, Any]], replace: bool = False):
        """
        处理从文件列表添加歌曲到播放列表的请求
        
        Args:
            music_files: 音乐文件列表，每个元素是包含歌曲信息的字典
            replace: 是否替换当前播放列表（True）还是追加（False）
        """
        try:
            # 提取歌曲名称
            song_names = [file_info.get('name', '') for file_info in music_files if file_info.get('name')]
            
            if not song_names:
                logger.warning("没有有效的歌曲名称")
                return
            
            # 添加到当前播放列表
            self.add_songs_to_current_playlist(song_names, replace=replace)
            
            logger.info(f"已{'替换' if replace else '添加'} {len(song_names)} 首歌曲到播放列表")
            
        except Exception as e:
            logger.error(f"处理添加到播放列表请求失败: {e}")
    
    def add_songs_to_current_playlist(self, song_names: List[str], replace: bool = False):
        """
        添加歌曲到当前播放列表
        
        Args:
            song_names: 歌曲名称列表
            replace: 是否替换当前播放列表（True）还是追加（False）
        """
        try:
            if not song_names:
                logger.warning("没有歌曲可添加")
                return
            
            # 确保当前播放列表存在
            if not self.current_playlist_data:
                self.current_playlist_data = {
                    "id": -1,
                    "name": "临时播放列表",
                    "songs": [],
                    "folder_path": "",
                    "created_at": datetime.now().isoformat(),
                    "last_played": None,
                    "play_count": 0,
                    "current_index": 0
                }
            
            # 如果是替换模式，清空现有歌曲
            if replace:
                self.current_playlist_data["songs"] = []
                self.current_playlist_data["current_index"] = 0
                logger.info("清空现有播放列表")
            
            # 获取当前歌曲数量，用于设置索引
            current_song_count = len(self.current_playlist_data["songs"])
            
            # 添加新歌曲
            added_count = 0
            for song_name in song_names:
                if not song_name:
                    continue
                
                # 检查歌曲是否已存在（避免重复添加）
                existing_song = None
                for existing in self.current_playlist_data["songs"]:
                    if existing.get("name") == song_name:
                        existing_song = existing
                        break
                
                if existing_song:
                    logger.debug(f"歌曲已存在于播放列表: {song_name}")
                    continue
                
                # 从 music_service 获取歌曲信息
                song_info = self.get_song_info_from_music_list(song_name)
                if not song_info:
                    # 如果没有找到歌曲信息，使用基本信息
                    song_info = {
                        'name': song_name,
                        'display_name': song_name,
                        'title': song_name[:-4] if song_name.endswith('.mp3') else song_name,
                        'artist': '未知艺术家',
                        'album': '未知专辑',
                        'is_downloaded': False,
                        'filepath': '',
                        'remote_path': song_name
                    }
                    logger.warning(f"未找到歌曲信息，使用默认信息: {song_name}")
                
                # 创建歌曲条目
                song_entry = {
                    "name": song_name,
                    "info": song_info,
                    "state": {
                        "is_playing": False,
                        "is_paused": False,
                        "position": 0,
                        "duration": 0,
                        "play_count": 0,
                        "last_played": None,
                        "is_favorite": False,
                        "added_at": datetime.now().isoformat()
                    }
                }
                
                # 添加到播放列表
                self.current_playlist_data["songs"].append(song_entry)
                added_count += 1
                logger.debug(f"添加歌曲到播放列表: {song_name}")
            
            # 如果是替换模式且添加了歌曲，设置第一首为当前歌曲
            if replace and added_count > 0:
                self.current_playlist_data["current_index"] = 0
            
            # 保存播放列表更改
            self.save_current_playlist()
            
            # 刷新界面显示
            self.refresh_playlist_display()
            self.update_current_playlist_info()
            
            # 显示成功消息
            action_text = "替换为" if replace else "添加了"
            self.show_message(f"{action_text} {added_count} 首歌曲到播放列表", "success")
            
            logger.info(f"成功{action_text} {added_count} 首歌曲到播放列表")
            
        except Exception as e:
            logger.error(f"添加歌曲到播放列表失败: {e}")
            self.show_message(f"添加歌曲失败: {str(e)}", "error")
    
    def save_current_playlist(self):
        """保存当前播放列表到配置文件"""
        try:
            if not self.current_playlist_data:
                logger.warning("没有当前播放列表可保存")
                return
            
            # 获取播放列表数据
            playlists_data = self.playback_service.load_playlists()
            
            # 如果是临时播放列表（id=-1），直接保存到临时位置
            if self.current_playlist_data.get("id") == -1:
                # 临时播放列表保存到特殊位置
                playlists_data["temp_playlist"] = self.current_playlist_data
            else:
                # 正式播放列表，更新到播放列表数组中
                playlist_id = self.current_playlist_data.get("id")
                playlists = playlists_data.get("playlists", [])
                
                # 查找并更新现有播放列表
                playlist_found = False
                for i, playlist in enumerate(playlists):
                    if playlist.get("id") == playlist_id:
                        playlists[i] = self.current_playlist_data
                        playlist_found = True
                        break
                
                # 如果没找到，添加为新播放列表
                if not playlist_found:
                    # 分配新ID
                    max_id = max([p.get("id", 0) for p in playlists] + [0])
                    self.current_playlist_data["id"] = max_id + 1
                    playlists.append(self.current_playlist_data)
                
                playlists_data["playlists"] = playlists
                
                # 设置为当前播放列表
                playlists_data["current_playlist_id"] = self.current_playlist_data["id"]
            
            # 保存到配置文件
            self.playback_service.save_playlists(playlists_data)
            logger.debug("播放列表已保存")
            
        except Exception as e:
            logger.error(f"保存当前播放列表失败: {e}")
    
    def remove_song_from_playlist(self, index: int):
        """
        从播放列表中移除指定索引的歌曲
        
        Args:
            index: 要移除的歌曲在播放列表中的索引
        """
        try:
            if not self.current_playlist_data or not self.current_playlist_data.get("songs"):
                logger.warning("播放列表为空，无法移除歌曲")
                return
            
            songs = self.current_playlist_data["songs"]
            
            # 检查索引是否有效
            if not (0 <= index < len(songs)):
                logger.warning(f"无效的歌曲索引: {index}")
                return
            
            # 获取要移除的歌曲信息
            removed_song = songs[index]
            song_name = removed_song.get("name", "未知歌曲")
            
            # 移除歌曲
            songs.pop(index)
            
            # 调整当前播放索引
            current_index = self.current_playlist_data.get("current_index", 0)
            
            if index < current_index:
                # 移除的歌曲在当前播放歌曲之前，当前索引需要减1
                self.current_playlist_data["current_index"] = current_index - 1
            elif index == current_index:
                # 移除的是当前播放的歌曲
                if len(songs) == 0:
                    # 播放列表空了
                    self.current_playlist_data["current_index"] = 0
                elif current_index >= len(songs):
                    # 当前索引超出范围，设为最后一首
                    self.current_playlist_data["current_index"] = len(songs) - 1
                # 如果当前索引还在有效范围内，保持不变
            # 如果移除的歌曲在当前播放歌曲之后，当前索引不变
            
            # 保存更改
            self.save_current_playlist()
            
            # 刷新界面
            self.refresh_playlist_display()
            self.update_current_playlist_info()
            self.update_current_song_info()
            
            # 显示成功消息
            self.show_message(f"已移除歌曲: {song_name}", "success")
            logger.info(f"成功移除歌曲: {song_name}")
            
        except Exception as e:
            logger.error(f"移除歌曲失败: {e}")
            self.show_message(f"移除歌曲失败: {str(e)}", "error")
    
    def handle_play_selected(self, music_files: List[Dict[str, Any]], start_index: int = 0):
        """
        处理从文件列表播放选中歌曲的请求
        
        Args:
            music_files: 音乐文件列表
            start_index: 开始播放的索引
        """
        logger.info(f"处理播放选中歌曲请求，文件数: {len(music_files)}, 开始索引: {start_index}")
        try:
            # 创建新播放列表或清空当前播放列表
            if music_files:
                # 获取第一个文件的文件夹路径作为播放列表名称
                first_file = music_files[0]
                folder_path = first_file.get('folder_path', '')
                playlist_name = f"来自文件列表的播放列表"
                
                if folder_path:
                    folder_name = os.path.basename(folder_path)
                    playlist_name = f"来自 {folder_name} 的播放列表"
                
                # 先清空当前播放列表
                self.playlist_manager.clear_current_playlist()
                
                # 添加所有歌曲到播放列表
                for music_file in music_files:
                    self.playlist_component.add_song_to_playlist(music_file)
                
                # 设置播放索引
                current_playlist = self.playlist_manager.get_current_playlist()
                if current_playlist and 0 <= start_index < len(music_files):
                    current_playlist['current_index'] = start_index
                    self.playlist_manager.save_current_playlist(current_playlist)
                
                # 刷新播放列表显示
                self.playlist_component.refresh_display()
                
                # 自动播放第一首歌曲（如果启用了自动播放）
                auto_play = self.app.config_manager.get("player.auto_play_on_select", True)
                if auto_play and music_files:
                    target_song = music_files[start_index] if start_index < len(music_files) else music_files[0]
                    self.app.add_background_task(self.play_selected_song(target_song))
            
            logger.info(f"处理播放选中歌曲请求完成，索引: {start_index}")
            
        except Exception as e:
            logger.error(f"处理播放选中歌曲请求失败: {e}")
    
    def sync_with_app_state(self):
        """
        同步应用的播放状态到播放列表管理系统
        用于在应用状态发生变化时更新播放列表信息
        """
        try:
            # 从播放服务获取当前播放的歌曲
            current_song_name = self.playback_service.get_current_song_name()
            if current_song_name:
                # 在当前播放列表中查找这首歌曲
                if self.current_playlist_data and self.current_playlist_data.get("songs"):
                    for i, song_entry in enumerate(self.current_playlist_data["songs"]):
                        if song_entry["name"] == current_song_name:
                            # 找到了，更新索引
                            self.current_playlist_data["current_index"] = i
                            self.save_current_playlist()
                            break
            
            # 更新界面
            self.refresh_playlist_display()
            self.update_current_song_info()
            
        except Exception as e:
            logger.error(f"同步应用状态失败: {e}")
    

    


    
    def on_seek(self, widget):
        """拖拽进度条"""
        try:
            # 如果是程序自动更新进度条，直接返回
            if hasattr(self, '_updating_progress') and self._updating_progress:
                logger.debug("程序更新进度条，忽略on_change事件")
                return
            
            # iOS特殊处理：添加更强的防抖机制
            from ..platform_audio import is_ios
            if is_ios():
                import time
                current_time = time.time()
                
                # 检查是否在短时间内多次触发
                if hasattr(self, '_last_user_seek_time'):
                    time_diff = current_time - self._last_user_seek_time
                    if time_diff < 0.8:  # 增加到0.8秒的防抖间隔
                        logger.debug(f"iOS: 忽略频繁的用户进度条拖拽 (间隔: {time_diff:.2f}s)")
                        return
                
                # 记录用户操作时间
                self._last_user_seek_time = current_time
                logger.info(f"iOS用户拖拽进度条: {widget.value:.1f}%")
            
            # 如果歌曲已完成播放，忽略UI自动更新导致的跳转尝试
            if self._song_completed:
                logger.debug("歌曲已完成播放，忽略进度条更新")
                return
            
            # 检查是否正在播放，如果没有在播放则不允许跳转
            if not self.playback_service.is_playing():
                logger.warning("当前没有播放音乐，无法跳转")
                # 重置进度条到当前位置
                if hasattr(self, 'position') and hasattr(self, 'duration') and self.duration > 0:
                    current_progress = (self.position / self.duration) * 100
                    self._updating_progress = True
                    widget.value = current_progress
                    self._updating_progress = False
                else:
                    self._updating_progress = True
                    widget.value = 0
                    self._updating_progress = False
                return
            
            # 从音频播放器获取实时时长
            duration = 0
            
            # 首先尝试从播放服务获取时长
            if self.playback_service.audio_player:
                duration = self.playback_service.audio_player.get_duration()
                logger.debug(f"从播放器获取时长: {duration}")
                
            # 如果播放器返回0或无效值，尝试从缓存获取
            if duration <= 0:
                duration = getattr(self, 'duration', 0)
                logger.debug(f"使用缓存的时长: {duration}")
            
            # 如果仍然没有有效时长，尝试从文件信息获取
            if duration <= 0:
                current_song = self.get_current_song_entry()
                if current_song and current_song.get("info"):
                    # 尝试从歌曲信息中获取时长
                    song_info = current_song["info"]
                    if "duration" in song_info and song_info["duration"] > 0:
                        duration = song_info["duration"]
                        logger.debug(f"从歌曲信息获取时长: {duration}")
            
            # 如果还是没有时长，尝试估算一个合理的时长（基于文件大小）
            if duration <= 0:
                current_song = self.get_current_song_entry()
                if current_song and current_song.get("info"):
                    song_info = current_song["info"]
                    file_size = song_info.get("size", 0)
                    if file_size > 0:
                        # 粗略估算：MP3文件约128kbps，即16KB/s
                        # 这只是一个估算，实际可能有很大差异
                        estimated_duration = file_size / (16 * 1024)  # 估算的秒数
                        if 30 <= estimated_duration <= 600:  # 合理范围：30秒到10分钟
                            duration = estimated_duration
                            logger.debug(f"基于文件大小估算时长: {duration:.1f}秒")
                        else:
                            # 如果估算值不合理，使用默认值
                            duration = 180  # 3分钟作为默认值
                            logger.debug(f"估算值不合理({estimated_duration:.1f}s)，使用默认时长: {duration}秒")
                    else:
                        duration = 180  # 3分钟作为默认值
                        logger.debug("没有文件大小信息，使用默认时长: 180秒")
            
            if duration > 0:
                # 计算新的播放位置
                new_position = (widget.value / 100) * duration
                
                # 跳转到新位置
                success = self.playback_service.seek_to_position(new_position)
                if success:
                    # iOS特殊处理：减少日志频率
                    if is_ios():
                        logger.info(f"iOS跳转: {new_position:.2f}秒 ({widget.value:.1f}%)")
                    else:
                        logger.info(f"跳转到位置: {new_position:.2f}秒 ({widget.value:.1f}%)，时长: {duration:.1f}秒")
                    
                    # 重置播放完成标记（手动跳转表示用户还想继续听）
                    if new_position < duration * 0.95:  # 如果跳转到95%之前，重置标记
                        self._song_completed = False
                    
                    # 立即更新位置显示（不等待下次UI更新）
                    self.position = new_position
                    self.duration = duration  # 更新缓存的时长
                    current_min = int(new_position // 60)
                    current_sec = int(new_position % 60)
                    total_min = int(duration // 60)
                    total_sec = int(duration % 60)
                    self.current_time_label.text = f"{current_min:02d}:{current_sec:02d}"
                    self.total_time_label.text = f"{total_min:02d}:{total_sec:02d}"
                    
                    # 强制更新进度条位置（不触发on_change）
                    self._updating_progress = True
                    self.progress_slider.value = widget.value
                    self._updating_progress = False
                    
                else:
                    logger.warning("跳转失败")
                    self.show_message("跳转失败：播放器不支持此功能", "warning")
            else:
                logger.warning("无法跳转：未获取到有效的音频时长")
                # 重置进度条到0
                self._updating_progress = True
                self.progress_slider.value = 0
                self._updating_progress = False
                self.current_time_label.text = "00:00"
                self.total_time_label.text = "00:00"
                
        except Exception as e:
            logger.error(f"拖拽进度条失败: {e}")
            self.show_message(f"跳转失败: {str(e)}", "error")
    

    
    async def on_playlist_select(self, widget, selection=None, **kwargs):
        """播放列表选择"""
        try:                
            # 获取选择的行对象
            if selection is not None:
                selected_row = selection
            elif hasattr(widget, 'selection') and widget.selection is not None:
                selected_row = widget.selection
            else:
                logger.warning("无法获取播放列表选择")
                return
            
            # 检查播放列表是否存在
            if not self.current_playlist_data or not self.current_playlist_data.get("songs"):
                logger.warning("没有可用的播放列表")
                return
                
            # 查找选择项在播放列表中的索引
            selected_index = None
            
            # 方法1：尝试使用 widget 的数据源索引
            try:
                if hasattr(widget, 'data') and widget.data:
                    for i, item in enumerate(widget.data):
                        if item == selected_row:
                            selected_index = i
                            break
            except Exception:
                pass
            
            # 方法2：基于标题匹配
            if selected_index is None and hasattr(selected_row, 'title'):
                selected_title = selected_row.title
                songs = self.current_playlist_data.get("songs", [])
                for i, song_entry in enumerate(songs):
                    song_info = song_entry.get("info", {})
                    song_title = song_info.get('title', song_info.get('display_name', song_entry['name']))
                    if song_title.endswith('.mp3'):
                        song_title = song_title[:-4]
                    if song_title == selected_title:
                        selected_index = i
                        break
            
            if selected_index is None:
                logger.warning("无法确定选择项的索引")
                return
                
            # 设置当前歌曲索引
            self.set_current_song_index(selected_index)
            logger.info(f"选择了歌曲索引: {selected_index}")
            
            # 立即更新UI以显示选择的歌曲
            self.update_ui()
            
            # 如果启用了自动播放
            if self.playback_service.config_manager.get("player.auto_play_on_select", True):
                # 直接使用播放服务播放当前歌曲
                await self.play_current_song()
                    
        except Exception as e:
            logger.error(f"播放列表选择失败: {e}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")

    async def save_playlist_as_new(self, widget):
        """保存当前播放列表为新播放列表"""
        try:
            # 检查当前播放列表是否有歌曲
            if not self.current_playlist_data or not self.current_playlist_data.get("songs"):
                self.show_message("播放列表为空，无法保存", "warning")
                return
            
            # 创建名称输入窗口
            self.create_playlist_name_input_window()
            
        except Exception as e:
            logger.error(f"保存播放列表失败: {e}")
            self.show_message(f"保存播放列表失败: {str(e)}", "error")
    
    def confirm_save_playlist(self, widget):
        """确认保存播放列表"""
        try:
            # 获取输入的播放列表名称
            playlist_name = self.playlist_name_input.value.strip()
            
            if not playlist_name:
                self.show_message("请输入播放列表名称", "warning")
                return
            
            # 检查名称是否已存在
            playlists_data = self.playback_service.load_playlists()
            existing_playlists = playlists_data.get("playlists", [])
            
            for existing in existing_playlists:
                if existing.get("name") == playlist_name:
                    self.show_message(f"播放列表名称 '{playlist_name}' 已存在", "warning")
                    return
            
            # 创建新的播放列表
            max_id = max([p.get("id", 0) for p in existing_playlists] + [0])
            new_playlist = {
                "id": max_id + 1,
                "name": playlist_name,
                "songs": self.current_playlist_data["songs"].copy(),  # 复制歌曲列表
                "folder_path": self.current_playlist_data.get("folder_path", ""),
                "created_at": datetime.now().isoformat(),
                "last_played": None,
                "play_count": 0,
                "current_index": 0
            }
            
            # 添加到播放列表数据
            existing_playlists.append(new_playlist)
            playlists_data["playlists"] = existing_playlists
            
            # 保存播放列表数据
            self.playback_service.save_playlists(playlists_data)
            
            # 关闭输入窗口
            self.close_name_input_window(widget)
            
            # 显示成功消息
            song_count = len(new_playlist["songs"])
            self.show_message(f"播放列表 '{playlist_name}' 保存成功 ({song_count} 首歌曲)", "success")
            logger.info(f"播放列表 '{playlist_name}' 保存成功，包含 {song_count} 首歌曲")
            
        except Exception as e:
            logger.error(f"确认保存播放列表失败: {e}")
            self.show_message(f"保存播放列表失败: {str(e)}", "error")
      
    def create_playlist_name_input_window(self):
        """创建播放列表名称输入窗口"""
        try:
            # 创建新窗口
            self.name_input_window = toga.Window(
                title="保存播放列表",
                size=(400, 200)
            )
            
            # 创建主容器
            main_container = toga.Box(style=Pack(direction=COLUMN, padding=20))
            
            # 标题
            title_label = toga.Label(
                "💾 保存播放列表",
                style=Pack(
                    font_size=16,
                    font_weight="bold",
                    padding=(0, 0, 20, 0),
                    text_align="center"
                )
            )
            
            # 输入提示
            prompt_label = toga.Label(
                "请输入播放列表名称:",
                style=Pack(padding=(0, 0, 10, 0))
            )
            
            # 名称输入框
            self.playlist_name_input = toga.TextInput(
                placeholder="请输入播放列表名称",
                style=Pack(flex=1, padding=(0, 0, 20, 0))
            )
            
            # 按钮容器
            button_container = toga.Box(style=Pack(
                direction=ROW,
                padding=(10, 0, 0, 0),
                alignment="center"
            ))
            
            save_button = toga.Button(
                "💾 保存",
                on_press=self.confirm_save_playlist,
                style=Pack(
                    width=80,
                    height=35,
                    padding=(0, 10),
                    background_color="#28a745",
                    color="white"
                )
            )
            
            cancel_button = toga.Button(
                "❌ 取消",
                on_press=self.cancel_save_playlist,
                style=Pack(
                    width=80,
                    height=35,
                    padding=(0, 10)
                )
            )
            
            button_container.add(save_button)
            button_container.add(cancel_button)
            
            # 组装界面
            main_container.add(title_label)
            main_container.add(prompt_label)
            main_container.add(self.playlist_name_input)
            main_container.add(button_container)
            
            self.name_input_window.content = main_container
            
            # 显示窗口
            self.name_input_window.show()
            
        except Exception as e:
            logger.error(f"创建播放列表名称输入窗口失败: {e}")

    def cancel_save_playlist(self, widget):
        """取消保存播放列表"""
        self.close_name_input_window(widget)

    def close_name_input_window(self, widget):
        """关闭名称输入窗口"""
        try:
            if hasattr(self, 'name_input_window'):
                self.name_input_window.close()
                del self.name_input_window
                del self.playlist_name_input
        except Exception as e:
            logger.error(f"关闭名称输入窗口失败: {e}")

    async def show_playlist_manager(self, widget):
        """显示播放列表管理器"""
        try:
            # 创建播放列表管理窗口
            self.create_playlist_manager_window()
        except Exception as e:
            logger.error(f"显示播放列表管理器失败: {e}")

    def create_playlist_manager_window(self):
        """创建播放列表管理窗口"""
        try:
            # 创建新窗口
            self.playlist_manager_window = toga.Window(
                title="播放列表管理器",
                size=(600, 500)
            )
            
            # 创建主容器
            main_container = toga.Box(style=Pack(direction=COLUMN, padding=20))
            
            # 标题
            title_label = toga.Label(
                "📋 播放列表管理器",
                style=Pack(
                    font_size=18,
                    font_weight="bold",
                    padding=(0, 0, 20, 0),
                    text_align="center"
                )
            )
            
            # 播放列表列表
            self.playlist_manager_table = toga.DetailedList(
                on_select=self.on_manager_playlist_select,
                style=Pack(flex=1, height=300)
            )
            
            # 按钮容器
            button_container = toga.Box(style=Pack(
                direction=ROW,
                padding=(20, 0, 0, 0),
                alignment="center"
            ))
            
            load_button = toga.Button(
                "📂 加载播放列表",
                on_press=self.load_selected_playlist,
                style=Pack(
                    width=120,
                    height=40,
                    padding=(0, 10),
                    background_color="#28a745",
                    color="white"
                )
            )
            
            delete_button = toga.Button(
                "🗑️ 删除播放列表",
                on_press=self.delete_selected_playlist,
                style=Pack(
                    width=120,
                    height=40,
                    padding=(0, 10),
                    background_color="#dc3545",
                    color="white"
                )
            )
            
            close_button = toga.Button(
                "❌ 关闭",
                on_press=self.close_playlist_manager,
                style=Pack(
                    width=80,
                    height=40,
                    padding=(0, 10)
                )
            )
            
            button_container.add(load_button)
            button_container.add(delete_button)
            button_container.add(close_button)
            
            # 组装界面
            main_container.add(title_label)
            main_container.add(self.playlist_manager_table)
            main_container.add(button_container)
            
            self.playlist_manager_window.content = main_container
            
            # 加载播放列表数据
            self.refresh_playlist_manager()
            
            # 显示窗口
            self.playlist_manager_window.show()
            
        except Exception as e:
            logger.error(f"创建播放列表管理窗口失败: {e}")

    def refresh_playlist_manager(self):
        """刷新播放列表管理器数据"""
        try:
            self.playlist_manager_table.data.clear()
            
            playlists_data = self.playback_service.load_playlists()
            playlists = playlists_data.get("playlists", [])
            
            for playlist in playlists:
                # 格式化时间
                created_at = playlist.get("created_at", "")
                if created_at:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(created_at)
                        created_str = dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        created_str = created_at[:16] if len(created_at) > 16 else created_at
                else:
                    created_str = "未知"
                
                last_played = playlist.get("last_played")
                if last_played:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(last_played)
                        played_str = dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        played_str = "未知"
                else:
                    played_str = "从未播放"
                
                song_count = len(playlist.get("songs", []))
                play_count = playlist.get("play_count", 0)
                
                # 添加到表格
                self.playlist_manager_table.data.append({
                    'icon': "🎵",
                    'title': playlist["name"],
                    'subtitle': f"歌曲: {song_count} | 播放: {play_count}次 | 创建: {created_str} | 最后播放: {played_str}"
                })
                
        except Exception as e:
            logger.error(f"刷新播放列表管理器失败: {e}")

    async def on_manager_playlist_select(self, widget, selection=None, **kwargs):
        """播放列表管理器中的选择"""
        try:
            # 获取选择的行对象
            if selection is not None:
                selected_row = selection
            elif hasattr(widget, 'selection') and widget.selection is not None:
                selected_row = widget.selection
            else:
                logger.warning("无法获取播放列表管理器中的选择")
                return
            
            # 保存选择的项目和索引
            self.selected_manager_playlist = selected_row
            
            # 查找选择项在列表中的索引
            selected_index = None
            try:
                if hasattr(widget, 'data') and widget.data:
                    for i, item in enumerate(widget.data):
                        if item == selected_row:
                            selected_index = i
                            break
            except Exception as e:
                logger.error(f"查找选择索引失败: {e}")
            
            # 保存选择的索引
            self.selected_manager_playlist_index = selected_index
            
            logger.info(f"播放列表管理器选择: 索引={selected_index}, 标题={getattr(selected_row, 'title', 'Unknown')}")
            
        except Exception as e:
            logger.error(f"播放列表管理器选择处理失败: {e}")

    async def load_selected_playlist(self, widget):
        """加载选中的播放列表"""
        try:
           
            selected_index = self.selected_manager_playlist_index
            
            # 获取播放列表数据
            playlists_data = self.playback_service.load_playlists()
            playlists = playlists_data.get("playlists", [])
            
            if selected_index >= len(playlists):
                logger.error(f"播放列表索引超出范围")
                return
            
            selected_playlist = playlists[selected_index]
            
            # 将选中的播放列表设为当前播放列表
            self.current_playlist_data = selected_playlist.copy()
            
            # 设置为当前播放列表
            playlists_data["current_playlist_id"] = selected_playlist["id"]
            self.playback_service.save_playlists(playlists_data)
            
            # 更新播放信息
            self.playback_service.config_manager.update_playlist_play_info(selected_playlist["id"])
            
            # 更新UI
            self.refresh_playlist_display()
            self.update_current_playlist_info()
            self.update_ui()
            
            # 关闭管理器窗口
            self.close_playlist_manager(widget)
            
        except Exception as e:
            logger.error(f"加载播放列表失败: {e}")

    async def delete_selected_playlist(self, widget):
        """删除选中的播放列表"""
        try:
            # 检查是否有选中的播放列表
            if not hasattr(self, 'selected_manager_playlist_index') or self.selected_manager_playlist_index is None:
                self.show_message("请先选择要删除的播放列表", "warning")
                return
            
            selected_index = self.selected_manager_playlist_index
            
            # 获取播放列表数据
            playlists_data = self.playback_service.load_playlists()
            playlists = playlists_data.get("playlists", [])
            
            if selected_index >= len(playlists):
                logger.error(f"播放列表索引超出范围")
                self.show_message("选中的播放列表不存在", "error")
                return
            
            selected_playlist = playlists[selected_index]
            playlist_name = selected_playlist.get("name", "未知播放列表")
            playlist_id = selected_playlist.get("id")
            
            # 删除播放列表
            playlists.pop(selected_index)
            playlists_data["playlists"] = playlists
            
            # 如果删除的是当前播放列表，清除当前播放列表ID
            if playlists_data.get("current_playlist_id") == playlist_id:
                playlists_data["current_playlist_id"] = None
                # 清空当前播放列表数据
                self.current_playlist_data = {
                    "id": -1,
                    "name": "临时播放列表",
                    "songs": [],
                    "folder_path": "",
                    "created_at": datetime.now().isoformat(),
                    "last_played": None,
                    "play_count": 0,
                    "current_index": 0
                }
            
            # 保存更改
            self.playback_service.save_playlists(playlists_data)
            
            # 刷新播放列表管理器
            self.refresh_playlist_manager()
            
            # 刷新主界面
            self.refresh_playlist_display()
            self.update_current_playlist_info()
            
            # 显示成功消息
            self.show_message(f"播放列表 '{playlist_name}' 已删除", "success")
            logger.info(f"播放列表 '{playlist_name}' 已删除")
            
            # 清除选择
            self.selected_manager_playlist = None
            self.selected_manager_playlist_index = None
            
        except Exception as e:
            logger.error(f"删除播放列表失败: {e}")
            self.show_message(f"删除播放列表失败: {str(e)}", "error")

    def close_playlist_manager(self, widget):
        """关闭播放列表管理器"""
        try:
            if hasattr(self, 'playlist_manager_window'):
                self.playlist_manager_window.close()
                del self.playlist_manager_window
        except Exception as e:
            logger.error(f"关闭播放列表管理器失败: {e}")
