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
            play_song_callback=self.play_selected_song,
            ui_update_callback=self.on_playback_state_changed
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
            on_playlist_change_callback=self.on_playlist_changed,
            playback_service=self.playback_service
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
        """构建播放界面 - iOS优化版本：播放列表在上，控制区域在下"""
        # 创建主容器，不使用滚动容器以更好地控制布局
        self.container = toga.Box(style=Pack(direction=COLUMN, flex=1))
        
        # 消息显示区域 - 最小化
        self.message_box = toga.Box(style=Pack(
            direction=ROW,
            padding=2,
            visibility="hidden"
        ))
        
        # 精简的标题 - 更小字体和间距
        title = toga.Label(
            "🎵 音乐播放器",
            style=Pack(
                padding=(2, 0, 4, 0),
                font_size=14,
                font_weight="bold",
                text_align="center"
            )
        )
        
        # 当前播放信息区域 - 精简版
        self.create_now_playing_section()
        
        # 视图切换按钮 - 移到顶部
        view_switch_box = toga.Box(style=Pack(
            direction=ROW,
            padding=3,
            alignment="center"
        ))
        
        self.playlist_tab_button = toga.Button(
            "播放列表",
            on_press=self.show_playlist_view,
            style=Pack(
                width=70,
                height=25,
                padding=(0, 2),
                font_size=10,
                background_color="#007bff",
                color="white"
            )
        )
        
        self.lyrics_tab_button = toga.Button(
            "歌词",
            on_press=self.show_lyrics_view,
            style=Pack(
                width=70,
                height=25,
                padding=(0, 2),
                font_size=10
            )
        )
        
        view_switch_box.add(self.playlist_tab_button)
        view_switch_box.add(self.lyrics_tab_button)
        
        # 内容区域容器 - 给予更多flex空间
        self.content_container = toga.Box(style=Pack(
            direction=COLUMN,
            flex=1,
            padding=(0, 5)
        ))
        
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
        
        # 默认显示播放列表
        self.current_view = "playlist"
        self.content_container.add(self.playlist_box)
        
        # 播放控制区域 - 移到最底部，使用播放控制组件的紧凑布局
        self.playback_controls_widget = self.playback_control_component.widget
        
        # 组装界面 - 新的顺序：标题->当前播放->视图切换->内容区域->播放控制
        self.container.add(self.message_box)
        self.container.add(title)
        self.container.add(self.now_playing_box)
        self.container.add(view_switch_box)
        self.container.add(self.content_container)
        self.container.add(self.playback_controls_widget)  # 播放控制移到最底部
        
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
            if change_type in ["song_added", "song_removed", "cleared", "playlist_created", "songs_added_batch"]:
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
    
    def on_playback_state_changed(self, is_playing: bool):
        """播放状态改变回调 - 立即更新播放/暂停按钮"""
        try:
            logger.info(f"播放状态改变为: {'播放中' if is_playing else '暂停'}")
            # 立即更新播放控制组件的按钮状态
            if hasattr(self, 'playback_control_component') and self.playback_control_component:
                self.playback_control_component.update_play_pause_button(is_playing)
                
            # 更新状态标签
            if hasattr(self, 'status_label') and self.status_label:
                if is_playing:
                    self.status_label.text = "播放中 🔊"
                    self.status_label.style.color = "#28a745"  # 绿色表示播放
                else:
                    self.status_label.text = "暂停 ⏸"
                    self.status_label.style.color = "#ffc107"  # 黄色表示暂停
                    
            # 强制刷新UI（如果需要）
            if hasattr(self.app, 'main_window') and self.app.main_window:
                # 在某些平台上可能需要强制刷新
                pass
                    
        except Exception as e:
            logger.error(f"处理播放状态改变失败: {e}")
    
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

    
    def get_song_info_from_music_list(self, song_name: str) -> Dict[str, Any]:
        """从 music_list.json 获取歌曲信息"""
        song_info = self.playback_service.get_song_info(song_name)
        return song_info
       
    
    def set_current_song_index(self, index: int):
        """设置当前播放歌曲索引"""
        try:
            # 直接操作播放列表管理器
            current_playlist = self.playlist_manager.get_current_playlist()
            if not current_playlist or not current_playlist.get("songs"):
                logger.warning("设置播放索引失败：没有当前播放列表")
                return
            
            songs = current_playlist["songs"]
            if 0 <= index < len(songs):
                current_playlist["current_index"] = index
                self.playlist_manager.save_current_playlist(current_playlist)
                
                # 同步更新缓存（保持兼容性）
                self.current_playlist_data = current_playlist
                
                # 更新当前歌曲信息
                self.update_current_song_info()
                
                logger.info(f"设置当前播放索引: {index}")
            else:
                logger.warning(f"播放索引超出范围: {index}, 歌曲总数: {len(songs)}")
                
        except Exception as e:
            logger.error(f"设置播放索引失败: {e}")
    
    def get_current_song_entry(self) -> Optional[Dict[str, Any]]:
        """获取当前播放歌曲条目 - 直接从播放列表管理器获取最新数据"""
        try:
            # 直接从播放列表管理器获取最新的播放列表数据
            current_playlist = self.playlist_manager.get_current_playlist()
            if not current_playlist or not current_playlist.get("songs"):
                logger.debug("get_current_song_entry: 没有当前播放列表或歌曲列表为空")
                return None
            
            current_index = current_playlist.get("current_index", 0)
            songs = current_playlist["songs"]
            
            logger.debug(f"get_current_song_entry: 播放列表有 {len(songs)} 首歌，当前索引: {current_index}")
            
            if 0 <= current_index < len(songs):
                song_entry = songs[current_index]
                logger.debug(f"get_current_song_entry: 返回歌曲: {song_entry.get('name', 'Unknown')}")
                return song_entry
            
            logger.debug("get_current_song_entry: 索引超出范围")
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
                
                # 保存更新后的播放列表
                current_playlist = self.playlist_manager.get_current_playlist()
                if current_playlist:
                    self.playlist_manager.save_current_playlist(current_playlist)
                    
        except Exception as e:
            logger.error(f"更新歌曲状态失败: {e}")
    
    def update_current_song_info(self):
        """更新当前歌曲信息（从music_library获取详细信息）"""
        try:
            # 使用播放列表组件获取当前歌曲信息
            current_song = self.playlist_component.get_current_song_info()
            logger.debug(f"从播放列表组件获取的当前歌曲: {current_song is not None}")
            
            if not current_song:
                self.current_song_info = None
                logger.debug("播放列表组件返回空歌曲，设置为None")
                return
            
            # 获取歌曲名称和信息
            song_info = current_song.get('info', {})
            song_name = current_song.get('name') or song_info.get('name')
            logger.debug(f"歌曲名称: {song_name}")
            
            if not song_name:
                self.current_song_info = None
                logger.debug("歌曲名称为空，设置为None")
                return
            
            # 从music_library获取详细信息（如果可用）
            music_library = getattr(self.app, 'music_library', None)
            if music_library:
                detailed_info = music_library.get_song_info(song_name)
                if detailed_info:
                    # 合并播放列表中的信息和音乐库中的详细信息
                    self.current_song_info = {**song_info, **detailed_info}
                    logger.debug(f"合并音乐库信息，更新歌曲信息: {song_name}")
                else:
                    # 使用播放列表中的信息
                    self.current_song_info = song_info
                    logger.debug(f"使用播放列表信息: {song_name}")
            else:
                # 使用播放列表中的信息
                self.current_song_info = song_info
                logger.debug("music_library不可用，使用播放列表信息")
        
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
        """创建当前播放信息区域 - iOS紧凑版本"""
        self.now_playing_box = toga.Box(style=Pack(
            direction=ROW,  # 改为水平布局
            padding=3,
            background_color="#f8f9fa",
            alignment="center"
        ))
        
        # 当前歌曲信息 - 单行显示
        self.song_title_label = toga.Label(
            "未选择歌曲",
            style=Pack(
                font_size=12,
                font_weight="bold",
                text_align="left",
                padding=(0, 5, 0, 0),
                color="#212529",
                flex=1
            )
        )
        
        # 播放状态 - 紧凑显示
        self.status_label = toga.Label(
            "停止 ●",
            style=Pack(
                font_size=11,  # 增加字体大小以更好显示emoji
                text_align="right",
                padding=(0, 0, 0, 0),
                color="#495057",
                width=80  # 增加宽度以容纳emoji文字
            )
        )
        
        self.now_playing_box.add(self.song_title_label)
        self.now_playing_box.add(self.status_label)
    
    
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
            # 使用播放控制组件来更新进度
            if hasattr(self, 'playback_control_component') and self.playback_control_component:
                self.playback_control_component.update_progress()
            
            # 更新歌词显示位置
            position = 0
            duration = 0
            if hasattr(self, 'playback_control_component') and self.playback_control_component:
                position = self.playback_control_component.get_current_position()
                duration = self.playback_control_component.get_current_duration()
            
            if self.lyrics_component:
                self.lyrics_component.update_lyrics_position(position)
            
            # 检测播放完成并自动播放下一曲的逻辑保持不变
            if duration > 0 and position > 0:
                progress_ratio = position / duration
                # iOS特殊处理：提高完成阈值，避免频繁触发
                from ..platform_audio import is_ios
                completion_threshold = 0.98 if is_ios() else 0.99
                
                # 如果播放进度超过阈值，认为歌曲播放完成
                if progress_ratio >= completion_threshold and not getattr(self, '_song_completed', False):
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
                elif progress_ratio < 0.95 and getattr(self, '_song_completed', False):
                    logger.debug("歌曲位置重置，清除播放完成标记")
                    self._song_completed = False
            
            # 更新播放状态（从播放服务获取实时状态）
            is_playing = self.playback_service.is_playing()
            is_paused = getattr(self.playback_service, 'current_song_state', {}).get('is_paused', False)
            
            if is_playing:
                self.status_label.text = "播放中 🔊"
                self.status_label.style.color = "#28a745"  # 绿色表示播放
                # 更新播放控制组件的播放/暂停按钮
                if hasattr(self, 'playback_control_component') and self.playback_control_component:
                    self.playback_control_component.update_play_pause_button(True)
            elif is_paused:
                self.status_label.text = "暂停 ⏸"
                self.status_label.style.color = "#ffc107"  # 黄色表示暂停
                if hasattr(self, 'playback_control_component') and self.playback_control_component:
                    self.playback_control_component.update_play_pause_button(False)
            else:
                self.status_label.text = "停止 ●"
                self.status_label.style.color = "#6c757d"  # 灰色表示停止
                if hasattr(self, 'playback_control_component') and self.playback_control_component:
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
            logger.debug(f"更新UI - 当前歌曲条目: {current_song is not None}")
            logger.debug(f"更新UI - 当前歌曲信息: {self.current_song_info is not None}")
            
            if current_song and self.current_song_info:
                song_info = self.current_song_info
                
                # 显示歌曲标题和艺术家信息
                display_title = song_info.get('title', song_info.get('display_name', song_info.get('name', '未知歌曲')))
                if display_title.endswith('.mp3'):
                    display_title = display_title[:-4]
                
                # 在标题中包含艺术家信息
                artist = song_info.get('artist', '未知艺术家')
                if artist and artist != '未知艺术家':
                    new_title = f"{display_title} - {artist}"
                else:
                    new_title = display_title
                
                # 只有当标题真正改变时才更新（避免不必要的UI刷新）
                if self.song_title_label.text != new_title:
                    self.song_title_label.text = new_title
                    logger.debug(f"更新歌曲标题: {new_title}")
            else:
                if self.song_title_label.text != "未选择歌曲":
                    self.song_title_label.text = "未选择歌曲"
                    logger.debug("设置为未选择歌曲")
            
            # 更新播放状态（从播放服务获取实时状态）
            is_playing = self.playback_service.is_playing()
            is_paused = getattr(self.playback_service, 'current_song_state', {}).get('is_paused', False)
            
            if is_playing:
                self.status_label.text = "播放中 🔊"
                self.status_label.style.color = "#28a745"  # 绿色表示播放
                # 更新播放控制组件的播放/暂停按钮
                self.playback_control_component.update_play_pause_button(True)
            elif is_paused:
                self.status_label.text = "暂停 ⏸"
                self.status_label.style.color = "#ffc107"  # 黄色表示暂停
                self.playback_control_component.update_play_pause_button(False)
            else:
                self.status_label.text = "停止 ●"
                self.status_label.style.color = "#6c757d"  # 灰色表示停止
                self.playback_control_component.update_play_pause_button(False)
            
            # 更新播放进度 - 使用播放控制组件
            if hasattr(self, 'playback_control_component') and self.playback_control_component:
                self.playback_control_component.update_progress()
                
                # 获取位置信息用于更新歌词
                position = self.playback_control_component.get_current_position()
                
                # 更新歌词显示位置  
                if self.lyrics_component:
                    self.lyrics_component.update_lyrics_position(position)
            
            # 更新音量显示（音量控制现在由播放控制组件处理）
            # 播放控制组件会自己处理音量显示更新
            
            # 更新播放列表 - 由播放列表组件自己处理
            if hasattr(self, 'playlist_component') and self.playlist_component:
                self.playlist_component.update_display()
            
            # 更新播放模式按钮状态
            # 更新播放控制组件的播放模式按钮
            if hasattr(self, 'playback_control_component') and self.playback_control_component:
                self.playback_control_component.update_mode_buttons()
            
            # 强制刷新UI（确保所有更改都被显示）
            try:
                if hasattr(self.app, 'main_window') and self.app.main_window:
                    # 触发UI重绘
                    pass
            except Exception as refresh_error:
                logger.debug(f"UI刷新失败（可忽略）: {refresh_error}")
            
        except Exception as e:
            logger.error(f"更新UI失败: {e}")
    
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
                        # 保存更新后的播放列表
                        current_playlist = self.playlist_manager.get_current_playlist()
                        if current_playlist:
                            self.playlist_manager.save_current_playlist(current_playlist)
                    
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
                
                # 使用批量添加方法，一次性添加所有歌曲
                added_count = self.playlist_component.add_songs_to_playlist_batch(music_files)
                logger.info(f"批量添加完成，实际添加 {added_count} 首歌曲")
                
                # 设置播放索引
                current_playlist = self.playlist_manager.get_current_playlist()
                if current_playlist and 0 <= start_index < len(music_files):
                    current_playlist['current_index'] = start_index
                    self.playlist_manager.save_current_playlist(current_playlist)
                
                # 自动播放第一首歌曲（如果启用了自动播放）
                auto_play = self.app.config_manager.get("player.auto_play_on_select", True)
                if auto_play and music_files:
                    target_song = music_files[start_index] if start_index < len(music_files) else music_files[0]
                    self.app.add_background_task(self.play_selected_song(target_song))
            
            logger.info(f"处理播放选中歌曲请求完成，索引: {start_index}")
            
        except Exception as e:
            logger.error(f"处理播放选中歌曲请求失败: {e}")
            self.show_message(f"播放失败: {str(e)}", "error")
    