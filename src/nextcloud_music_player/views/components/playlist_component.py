"""
播放列表视图组件 - Flet 版本
"""

import flet as ft
import logging
from typing import Optional, Dict, List, Any, Callable

from ...utils.theme import Color, Space, FontSize

logger = logging.getLogger(__name__)


class PlaylistViewComponent:
    """播放列表视图组件"""

    def __init__(self, page: ft.Page, app_context: dict, playlist_manager,
                 on_song_select_callback: Callable, on_playlist_change_callback: Callable,
                 playback_service):
        self.page = page
        self.app_context = app_context
        self.playlist_manager = playlist_manager
        self.on_song_select_callback = on_song_select_callback
        self.on_playlist_change_callback = on_playlist_change_callback
        self.playback_service = playback_service
        self._built = False

    def build(self):
        """构建并返回组件"""
        if self._built and hasattr(self, '_container'):
            return self._container

        # 信息栏
        self.info_label = ft.Text("播放列表 (0)", size=FontSize.BODY, weight=ft.FontWeight.W_500, expand=True)
        self.clear_button = ft.IconButton(ft.Icons.DELETE_SWEEP, tooltip="清空", on_click=self._clear_playlist, icon_size=18)
        self.remove_button = ft.IconButton(ft.Icons.REMOVE_CIRCLE, tooltip="移除选中", on_click=self._remove_song, icon_size=18)
        self.refresh_button = ft.IconButton(ft.Icons.REFRESH, tooltip="刷新", on_click=self._refresh_display, icon_size=18)

        # 播放列表
        self.song_list = ft.ListView(expand=True, spacing=2, padding=ft.Padding(left=4, right=4, top=0, bottom=0))

        self._container = ft.Column([
            ft.Row([
                self.info_label,
                self.clear_button,
                self.remove_button,
                self.refresh_button,
            ], spacing=4),
            ft.Container(content=self.song_list, expand=True),
        ], spacing=Space.XS, expand=True)

        self._built = True
        self.refresh_display()
        return self._container

    def build_song_item(self, song_entry: Dict[str, Any], index: int) -> ft.Container:
        """构建单个歌曲项"""
        song_info = song_entry.get('info', {})
        song_name = song_entry.get('name', '')
        title = song_info.get('title', song_name)
        if title.endswith('.mp3'):
            title = title[:-4]
        artist = song_info.get('artist', '未知艺术家')
        state = song_entry.get('state', {})
        play_count = state.get('play_count', 0)
        is_downloaded = song_info.get('is_downloaded', False)

        # 播放状态图标
        is_current = self._is_current_song(index)
        is_playing = is_current and self.playback_service and self.playback_service.is_playing()

        if is_playing:
            status_icon = ft.Icon(ft.Icons.PLAY_CIRCLE_FILLED, color=Color.SUCCESS, size=20)
        elif is_current:
            status_icon = ft.Icon(ft.Icons.PAUSE_CIRCLE_FILLED, color=Color.WARNING, size=20)
        else:
            status_icon = ft.Icon(ft.Icons.MUSIC_NOTE, color=ft.Colors.GREY_400, size=20)

        download_icon = ft.Icon(
            ft.Icons.DOWNLOAD_DONE if is_downloaded else ft.Icons.DOWNLOAD,
            color=ft.Colors.GREEN_600 if is_downloaded else ft.Colors.GREY_400,
            size=16,
        )

        subtitle_parts = []
        subtitle_parts.append(artist)
        if play_count > 0:
            subtitle_parts.append(f"播放{play_count}次")
        subtitle = " · ".join(subtitle_parts)

        return ft.Container(
            content=ft.Row([
                status_icon,
                ft.Column([
                    ft.Text(title, size=FontSize.BODY + 1, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                            weight=ft.FontWeight.W_500 if is_current else ft.FontWeight.NORMAL,
                            color=Color.PRIMARY if is_current else None),
                    ft.Text(subtitle, size=FontSize.CAPTION, color=ft.Colors.GREY_500, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=2, expand=True),
                download_icon,
            ], spacing=Space.SM),
            padding=ft.Padding(left=12, right=12, top=10, bottom=10),
            border_radius=8,
            bgcolor=Color.PRIMARY_LIGHT if is_current else None,
            on_click=lambda e, idx=index, entry=song_entry: self._on_song_selected(idx, entry),
        )

    def _is_current_song(self, index: int) -> bool:
        """检查是否是当前播放歌曲"""
        try:
            playlist = self.playlist_manager.get_current_playlist()
            if not playlist:
                return False
            return playlist.get('current_index', -1) == index
        except:
            return False

    def _on_song_selected(self, index: int, song_entry: Dict[str, Any]):
        """歌曲被选中"""
        try:
            playlist = self.playlist_manager.get_current_playlist()
            if playlist:
                playlist['current_index'] = index
                self.playlist_manager.save_current_playlist(playlist)

            if self.on_song_select_callback:
                self.on_song_select_callback(song_entry, index)

            self.refresh_display()
        except Exception as e:
            logger.error(f"选择歌曲失败: {e}")

    def _clear_playlist(self, e):
        """清空播放列表"""
        self.playlist_manager.clear_current_playlist()
        if self.on_playlist_change_callback:
            self.on_playlist_change_callback("cleared")
        self.refresh_display()

    def _remove_song(self, e):
        """移除当前选中歌曲"""
        try:
            playlist = self.playlist_manager.get_current_playlist()
            if not playlist or not playlist.get('songs'):
                return
            current_index = playlist.get('current_index', 0)
            if 0 <= current_index < len(playlist['songs']):
                self.playlist_manager.remove_song_from_current_playlist(current_index)
                if self.on_playlist_change_callback:
                    self.on_playlist_change_callback("song_removed")
                self.refresh_display()
        except Exception as ex:
            logger.error(f"移除歌曲失败: {ex}")

    def _refresh_display(self, e=None):
        """刷新显示"""
        self.refresh_display()

    def refresh_display(self):
        """刷新播放列表显示"""
        try:
            self.playlist_manager.invalidate_cache()
            playlist = self.playlist_manager.create_default_playlist_if_needed()
            songs = playlist.get('songs', []) if playlist else []
            current_index = playlist.get('current_index', -1) if playlist else -1

            self.info_label.value = f"播放列表 ({len(songs)})"
            self.song_list.controls.clear()

            for i, song_entry in enumerate(songs):
                self.song_list.controls.append(self.build_song_item(song_entry, i))

            self.page.update()
        except Exception as e:
            logger.error(f"刷新播放列表失败: {e}")

    def update_display(self):
        """更新显示（轻量级，只更新状态指示器）"""
        self.refresh_display()

    def update_playing_indicator(self):
        """更新播放状态指示器"""
        self.refresh_display()

    def get_current_song_info(self) -> Optional[Dict[str, Any]]:
        """获取当前歌曲信息"""
        try:
            playlist = self.playlist_manager.get_current_playlist()
            if not playlist or not playlist.get('songs'):
                return None
            current_index = playlist.get('current_index', 0)
            songs = playlist['songs']
            if 0 <= current_index < len(songs):
                return songs[current_index]
            return None
        except Exception as e:
            logger.error(f"获取当前歌曲信息失败: {e}")
            return None

    def add_songs_to_playlist_batch(self, music_files: List[Dict[str, Any]]) -> int:
        """批量添加歌曲到播放列表"""
        added = 0
        for file_info in music_files:
            if self.playlist_manager.add_song_to_current_playlist(file_info):
                added += 1
        if self.on_playlist_change_callback:
            self.on_playlist_change_callback("songs_added_batch")
        self.refresh_display()
        return added

    def get_playlist_name(self) -> str:
        """获取当前播放列表名称"""
        try:
            playlist = self.playlist_manager.get_current_playlist()
            return playlist.get('name', '默认播放列表') if playlist else '默认播放列表'
        except:
            return '默认播放列表'
