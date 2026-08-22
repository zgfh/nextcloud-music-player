"""
播放视图 - Flet 版本
"""

import flet as ft
import asyncio
import logging
import os
from typing import Optional, Dict, List, Any
from datetime import datetime

from ..services.playback_service import PlaybackService
from ..services.playlist_manager import PlaylistManager
from ..services.playback_controller import PlaybackController, PlayMode
from .components.playlist_component import PlaylistViewComponent
from .components.playback_control_component import PlaybackControlComponent
from .components.lyrics_component import LyricsDisplayComponent
from ..utils.theme import Color, Space, FontSize, get_message_style

logger = logging.getLogger(__name__)


class PlaybackView:
    """播放视图"""

    def __init__(self, page: ft.Page, app_context: dict, view_manager):
        self.page = page
        self.app_context = app_context
        self.view_manager = view_manager
        self.play_mode = PlayMode.REPEAT_ONE

        config_manager = app_context['config_manager']
        music_service = app_context.get('music_service')

        # 初始化播放服务
        self.playback_service = PlaybackService(
            config_manager=config_manager,
            music_service=music_service,
            play_music_callback=None,
            add_background_task_callback=lambda task: asyncio.create_task(task) if asyncio.iscoroutine(task) else asyncio.create_task(task()),
        )

        # 播放列表管理器
        self.playlist_manager = PlaylistManager(
            config_manager=config_manager,
            music_service=music_service
        )

        # 播放控制器
        self.playback_controller = PlaybackController(
            playback_service=self.playback_service,
            playlist_manager=self.playlist_manager,
            play_song_callback=self.play_selected_song,
            ui_update_callback=self.on_playback_state_changed
        )

        # 播放控制组件
        self.playback_control_component = PlaybackControlComponent(
            page=page,
            app_context=app_context,
            playback_controller=self.playback_controller,
            on_play_mode_change_callback=self.on_play_mode_changed
        )

        # 播放列表组件
        self.playlist_component = PlaylistViewComponent(
            page=page,
            app_context=app_context,
            playlist_manager=self.playlist_manager,
            on_song_select_callback=self.on_playlist_song_selected,
            on_playlist_change_callback=self.on_playlist_changed,
            playback_service=self.playback_service
        )

        # 歌词组件
        lyrics_service = app_context.get('lyrics_service')
        self.lyrics_component = LyricsDisplayComponent(
            page=page,
            app_context=app_context,
            config_manager=config_manager,
            lyrics_service=lyrics_service
        )

        # 播放列表回调
        self.playback_service.set_playback_callbacks(
            pause_callback=None,
            stop_callback=None,
            get_play_mode_callback=None,
            get_is_playing_callback=None,
            set_volume_callback=lambda v: None,
            seek_to_position_callback=None,
            get_duration_callback=None,
            set_play_mode_callback=None
        )

        self.playback_controller.set_play_mode(PlayMode.REPEAT_ONE)
        self.playback_service.set_play_mode_by_string("repeat_one")

        # 状态
        self.current_song_info = None
        self._song_completed = False
        self._last_position = 0
        self._switching_song = False
        self._built = False

    def build(self):
        """构建并返回视图"""
        if self._built and hasattr(self, '_container'):
            return self._container

        # 当前播放信息
        self.song_title_label = ft.Text(
            "未选择歌曲",
            size=FontSize.SUBTITLE + 2,
            weight=ft.FontWeight.BOLD,
            expand=True,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        self.status_label = ft.Text(
            "停止",
            size=FontSize.STATUS,
            color=Color.TEXT_MUTED,
        )

        now_playing = ft.Container(
            content=ft.Row([self.song_title_label, self.status_label], spacing=Space.SM),
            bgcolor=Color.BG_SURFACE_ALT,
            padding=Space.SM,
            border_radius=8,
        )

        # Tab 切换 - Flet 0.86 Tabs = TabBar + TabBarView
        playlist_view = self.playlist_component.build()
        lyrics_view = self.lyrics_component.build()

        self.tabs = ft.Tabs(
            length=2,
            selected_index=0,
            on_change=self._on_tab_change,
            expand=True,
            content=ft.Column([
                ft.TabBar(
                    tabs=[
                        ft.Tab(label="播放列表"),
                        ft.Tab(label="歌词"),
                    ],
                ),
                ft.TabBarView(
                    expand=True,
                    controls=[
                        playlist_view,
                        lyrics_view,
                    ],
                ),
            ], spacing=0, expand=True),
        )

        # 消息区
        self.message_container = ft.Container(visible=False)

        # 播放控制
        controls = self.playback_control_component.build()

        # 组装
        self._container = ft.Column([
            now_playing,
            self.tabs,
            self.message_container,
            ft.SafeArea(content=controls),
        ], spacing=Space.XS, expand=True)

        self._built = True

        # 初始化模式按钮
        self.playback_control_component.update_mode_buttons()

        # 启动 UI 定时器（在 build 完成后启动）
        asyncio.create_task(self._schedule_ui_update())

        return self._container

    def _on_tab_change(self, e):
        """Tab 切换"""
        pass

    async def on_playlist_song_selected(self, song_entry: Dict[str, Any], index: int):
        """播放列表歌曲选择回调"""
        try:
            song_info = song_entry.get('info', {})
            song_name = song_entry.get('name', '')
            self.current_song_info = song_info
            self._update_current_song_info()

            if self.lyrics_component and song_name:
                self.lyrics_component.load_lyrics_for_song(song_name)

            auto_play = self.app_context['config_manager'].get("player.auto_play_on_select", True)
            if auto_play:
                await self.play_selected_song(song_info)
        except Exception as e:
            logger.error(f"处理播放列表歌曲选择失败: {e}")

    def on_playlist_changed(self, change_type: str):
        """播放列表改变回调"""
        logger.info(f"播放列表发生改变: {change_type}")
        if change_type == "cleared":
            asyncio.create_task(self._stop_music())

    def on_play_mode_changed(self, mode: str):
        """播放模式改变回调"""
        mode_map = {
            "normal": PlayMode.NORMAL,
            "repeat_one": PlayMode.REPEAT_ONE,
            "repeat_all": PlayMode.REPEAT_ALL,
            "shuffle": PlayMode.SHUFFLE,
        }
        self.play_mode = mode_map.get(mode, PlayMode.REPEAT_ONE)

    def on_playback_state_changed(self, is_playing: bool):
        """播放状态改变回调"""
        if self.playback_control_component:
            self.playback_control_component.update_play_pause_button(is_playing)
        if is_playing:
            self.status_label.value = "播放中"
            self.status_label.color = Color.STATUS_PLAYING
        else:
            self.status_label.value = "暂停"
            self.status_label.color = Color.STATUS_PAUSED
        self.page.update()

    async def play_selected_song(self, song_info: Dict[str, Any]):
        """播放选中的歌曲"""
        try:
            if song_info.get('is_downloaded') and song_info.get('filepath'):
                local_path = song_info['filepath']
                if os.path.exists(local_path):
                    await self.play_music_file(local_path)
                    return

            song_name = song_info.get('name', '')
            remote_path = song_info.get('remote_path', '')
            music_service = self.app_context.get('music_service')
            if music_service and remote_path:
                success = await music_service.download_file(remote_path, song_name)
                if success:
                    music_library = self.app_context.get('music_library')
                    updated_info = music_library.get_song_info(song_name) if music_library else None
                    if updated_info and updated_info.get('filepath'):
                        await self.play_music_file(updated_info['filepath'])
        except Exception as e:
            logger.error(f"播放选中歌曲失败: {e}")

    async def play_music_file(self, file_path: str):
        """播放音乐文件"""
        try:
            self.playback_service.set_current_song(file_path)
            try:
                await asyncio.wait_for(self.playback_service.play_music(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.error("播放音乐超时")
                return

            if self.lyrics_component:
                song_name = os.path.basename(file_path)
                self.lyrics_component.load_lyrics_for_song(song_name, auto_download=True)

            self.update_ui()
        except Exception as e:
            logger.error(f"播放音乐文件失败: {e}")

    async def _stop_music(self):
        """停止播放"""
        await self.playback_service.stop_music()
        self.status_label.value = "停止"
        self.status_label.color = Color.STATUS_STOPPED
        self.page.update()

    async def _schedule_ui_update(self):
        """定时更新 UI"""
        from ..platform_audio import is_ios
        update_interval = 2.0 if is_ios() else 0.5

        while True:
            await asyncio.sleep(update_interval)
            try:
                self._update_progress_only()
            except Exception as e:
                logger.error(f"UI更新失败: {e}")

    def _update_progress_only(self):
        """只更新播放进度"""
        if not self._built:
            return
        try:
            if self.playback_control_component:
                self.playback_control_component.update_progress()

            position = self.playback_control_component.get_current_position() if self.playback_control_component else 0
            duration = self.playback_control_component.get_current_duration() if self.playback_control_component else 0

            if self.lyrics_component:
                self.lyrics_component.update_lyrics_position(position)

            # 检测播放完成
            if duration > 0 and position > 0:
                progress_ratio = position / duration
                from ..platform_audio import is_ios
                threshold = 0.98 if is_ios() else 0.99

                if progress_ratio >= threshold and not self._song_completed:
                    self._song_completed = True
                    asyncio.create_task(self._auto_play_next_song())
                elif progress_ratio < 0.95 and self._song_completed:
                    self._song_completed = False

            # 更新状态
            is_playing = self.playback_service.is_playing()
            is_paused = getattr(self.playback_service, 'current_song_state', {}).get('is_paused', False)

            if is_playing:
                self.status_label.value = "播放中"
                self.status_label.color = Color.STATUS_PLAYING
                self.playback_control_component.update_play_pause_button(True)
            elif is_paused:
                self.status_label.value = "暂停"
                self.status_label.color = Color.STATUS_PAUSED
                self.playback_control_component.update_play_pause_button(False)
            else:
                self.status_label.value = "停止"
                self.status_label.color = Color.STATUS_STOPPED
                self.playback_control_component.update_play_pause_button(False)
        except Exception as e:
            logger.error(f"更新播放进度失败: {e}")

    async def _auto_play_next_song(self):
        """自动播放下一曲"""
        if self._switching_song:
            return
        await asyncio.sleep(0.2)
        success = await self.playback_controller.auto_play_next_song()
        if success:
            if self.playlist_component:
                self.playlist_component.refresh_display()
            self.update_ui()

    def update_ui(self):
        """更新 UI 显示"""
        try:
            self._update_current_song_info()
            current_song = self._get_current_song_entry()

            if current_song and self.current_song_info:
                song_info = self.current_song_info
                display_title = song_info.get('title', song_info.get('name', '未知歌曲'))
                if display_title.endswith('.mp3'):
                    display_title = display_title[:-4]
                artist = song_info.get('artist', '未知艺术家')
                if artist and artist != '未知艺术家':
                    new_title = f"{display_title} - {artist}"
                else:
                    new_title = display_title

                if self.song_title_label.value != new_title:
                    self.song_title_label.value = new_title
            else:
                self.song_title_label.value = "未选择歌曲"

            self.page.update()
        except Exception as e:
            logger.error(f"更新UI失败: {e}")

    def _update_current_song_info(self):
        """更新当前歌曲信息"""
        try:
            current_song = self.playlist_component.get_current_song_info()
            if not current_song:
                self.current_song_info = None
                return
            song_info = current_song.get('info', {})
            music_library = self.app_context.get('music_library')
            if music_library:
                song_name = current_song.get('name') or song_info.get('name')
                if song_name:
                    detailed = music_library.get_song_info(song_name)
                    if detailed:
                        self.current_song_info = {**song_info, **detailed}
                    else:
                        self.current_song_info = song_info
            else:
                self.current_song_info = song_info
        except Exception as e:
            logger.error(f"更新当前歌曲信息失败: {e}")

    def _get_current_song_entry(self) -> Optional[Dict[str, Any]]:
        """获取当前播放歌曲条目"""
        try:
            playlist = self.playlist_manager.get_current_playlist()
            if not playlist or not playlist.get('songs'):
                return None
            current_index = playlist.get('current_index', 0)
            songs = playlist['songs']
            if 0 <= current_index < len(songs):
                return songs[current_index]
            return None
        except:
            return None

    def show_message(self, message: str, message_type: str = "info"):
        """显示消息"""
        bg_color, text_color, icon = get_message_style(message_type)
        self.message_container.content = ft.Row([
            ft.Icon(ft.Icons.INFO_OUTLINE, color=text_color, size=18),
            ft.Text(message, color=text_color, size=FontSize.BODY),
        ], spacing=Space.XS)
        self.message_container.bgcolor = bg_color
        self.message_container.padding = Space.SM
        self.message_container.border_radius = 8
        self.message_container.visible = True
        self.page.update()

    def handle_play_selected(self, music_files: List[Dict[str, Any]], start_index: int = 0):
        """处理从文件列表播放选中歌曲"""
        logger.info(f"处理播放选中歌曲请求，文件数: {len(music_files)}, 开始索引: {start_index}")
        try:
            if music_files:
                self.playlist_manager.clear_current_playlist()
                added = self.playlist_component.add_songs_to_playlist_batch(music_files)
                logger.info(f"批量添加 {added} 首歌曲")

                current_playlist = self.playlist_manager.get_current_playlist()
                if current_playlist and 0 <= start_index < len(music_files):
                    current_playlist['current_index'] = start_index
                    self.playlist_manager.save_current_playlist(current_playlist)

                auto_play = self.app_context['config_manager'].get("player.auto_play_on_select", True)
                if auto_play and music_files:
                    target = music_files[start_index] if start_index < len(music_files) else music_files[0]
                    asyncio.create_task(self.play_selected_song(target))
        except Exception as e:
            logger.error(f"处理播放选中歌曲请求失败: {e}")

    def on_view_activated(self):
        """视图激活"""
        if self.playlist_component:
            self.playlist_component.refresh_display()
        self.update_ui()
