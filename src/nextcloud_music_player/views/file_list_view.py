"""
文件列表视图 - Flet 版本
"""

import flet as ft
import asyncio
import logging
from typing import List, Dict, Any

from ..utils.theme import Color, Space, FontSize, get_message_style

logger = logging.getLogger(__name__)


class FileListView:
    """文件列表管理视图"""

    def __init__(self, page: ft.Page, app_context: dict, view_manager):
        self.page = page
        self.app_context = app_context
        self.music_service = app_context['music_service']
        self.view_manager = view_manager
        self.music_files = []
        self.selected_files = set()
        self.is_syncing = False
        self._built = False

    def build(self):
        """构建并返回视图内容"""
        if self._built and hasattr(self, '_container'):
            return self._container

        # 操作栏
        self.sync_button = ft.ElevatedButton(
            "同步",
            icon=ft.Icons.SYNC,
            on_click=self._sync_music_list,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
        )

        self.search_input = ft.TextField(
            hint_text="搜索歌曲...",
            prefix_icon=ft.Icons.SEARCH,
            on_submit=self._search_music,
            border_radius=8,
            expand=True,
        )

        self.search_button = ft.IconButton(
            ft.Icons.SEARCH,
            tooltip="搜索",
            on_click=self._search_music,
        )

        # 文件夹路径栏
        self.folder_text = ft.Text(
            "文件夹: 未设置",
            size=FontSize.CAPTION,
            color=ft.Colors.GREY_600,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        self.folder_button = ft.TextButton(
            "去设置",
            icon=ft.Icons.SETTINGS,
            on_click=lambda e: self.view_manager.switch_to_view("connection"),
            style=ft.ButtonStyle(padding=0),
        )

        # 播放操作栏
        self.add_button = ft.ElevatedButton(
            "添加",
            icon=ft.Icons.PLAYLIST_ADD,
            on_click=self._add_to_playlist,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
        )
        self.play_button = ft.ElevatedButton(
            "播放",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._play_selected,
            style=ft.ButtonStyle(bgcolor=Color.PRIMARY, color=Color.PRIMARY_TEXT, shape=ft.RoundedRectangleBorder(radius=8)),
        )
        self.select_all_button = ft.TextButton("全选", on_click=self._select_all)
        self.delete_button = ft.TextButton("删除", on_click=self._delete_selected, style=ft.ButtonStyle(color=Color.DANGER))

        # 统计栏
        self.stats_text = ft.Text("总数: 0 | 已选: 0 | 已下载: 0", size=FontSize.CAPTION, color=ft.Colors.GREY_600)

        # 文件列表
        self.file_list = ft.ListView(expand=True, spacing=4, padding=ft.Padding(left=8, right=8, top=0, bottom=0))

        # 下载栏
        self.download_button = ft.ElevatedButton(
            "下载选中",
            icon=ft.Icons.DOWNLOAD,
            on_click=self._download_selected,
            disabled=True,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
        )
        self.clear_cache_button = ft.OutlinedButton(
            "清除缓存",
            icon=ft.Icons.DELETE_SWEEP,
            on_click=self._clear_cache,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
        )

        # 消息区
        self.message_container = ft.Container(visible=False)

        # 组装
        self._container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("音乐文件", size=FontSize.TITLE + 4, weight=ft.FontWeight.BOLD),
                    ft.Row([self.sync_button, self.search_input, self.search_button], spacing=Space.XS),
                    ft.Row([self.folder_text, self.folder_button], spacing=Space.XS),
                    ft.Row([self.add_button, self.play_button, self.select_all_button, self.delete_button], spacing=Space.XS),
                    ft.Container(content=self.stats_text, bgcolor=Color.BG_SUBTLE, padding=Space.SM, border_radius=6, width=float("inf")),
                    ft.Container(content=self.file_list, expand=True, border_radius=8),
                    ft.Row([self.download_button, self.clear_cache_button], spacing=Space.SM),
                    self.message_container,
                ],
                spacing=Space.SM,
                expand=True,
            ),
            padding=Space.LG,
            expand=True,
        )

        self._built = True
        self.reload_music_list()
        return self._container

    def build_file_item(self, song: Dict[str, Any]) -> ft.Container:
        """构建单个文件项"""
        name = song.get('name', 'Unknown')
        title = song.get('title', name)
        if title.endswith('.mp3'):
            title = title[:-4]
        artist = song.get('artist', '未知艺术家')
        is_downloaded = song.get('is_downloaded', False)
        size = song.get('size', 0)

        size_str = f"{float(size) / 1024 / 1024:.1f}MB" if size else ""
        download_icon = ft.Icons.DOWNLOAD_DONE if is_downloaded else ft.Icons.DOWNLOAD
        download_color = ft.Colors.GREEN_600 if is_downloaded else ft.Colors.GREY_400

        selected = name in self.selected_files
        check_icon = ft.Icon(
            ft.Icons.CHECK_CIRCLE if selected else ft.Icons.RADIO_BUTTON_UNCHECKED,
            color=Color.PRIMARY if selected else ft.Colors.GREY_400,
            size=20,
        )

        return ft.Container(
            content=ft.Row([
                check_icon,
                ft.Icon(download_icon, color=download_color, size=20),
                ft.Column([
                    ft.Text(title, size=FontSize.BODY + 1, weight=ft.FontWeight.W_500, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f"{artist} · {size_str}", size=FontSize.CAPTION, color=ft.Colors.GREY_500, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=2, expand=True),
            ], spacing=Space.SM),
            padding=ft.Padding(left=12, right=12, top=10, bottom=10),
            border_radius=8,
            on_click=lambda e, n=name: self._toggle_select(n),
            bgcolor=ft.Colors.BLUE_50 if selected else None,
        )

    def _toggle_select(self, name: str):
        """切换文件选中状态"""
        if name in self.selected_files:
            self.selected_files.remove(name)
        else:
            self.selected_files.add(name)
        self._update_stats()
        self.reload_music_list(keep_scroll=True)

    def _update_stats(self):
        """更新统计栏"""
        total = len(self.music_files)
        selected = len(self.selected_files)
        downloaded = sum(1 for s in self.music_files if s.get('is_downloaded', False))
        self.stats_text.value = f"总数: {total} | 已选: {selected} | 已下载: {downloaded}"
        self.download_button.disabled = selected == 0
        self.page.update()

    def reload_music_list(self, keep_scroll=False):
        """重新加载音乐列表"""
        try:
            self.music_files = self.music_service.get_all_songs()
            self.file_list.controls.clear()
            for song in self.music_files:
                self.file_list.controls.append(self.build_file_item(song))
            self._update_stats()
            if not keep_scroll:
                self.page.update()
        except Exception as e:
            logger.error(f"加载音乐列表失败: {e}")

    async def _sync_music_list(self, e):
        """同步音乐列表"""
        if self.is_syncing:
            return
        self.is_syncing = True
        self.sync_button.disabled = True
        self.show_message("正在同步...", "info")

        try:
            sync_folder = self.app_context['config_manager'].get("connection.default_sync_folder", "/")
            if not sync_folder:
                self.show_message("请先设置同步文件夹", "error")
                return

            files = await self.music_service.sync_music_files(sync_folder)
            folder_display = self.music_service.music_library.sync_folder or sync_folder
            self.folder_text.value = f"文件夹: {folder_display}"
            self.reload_music_list()
            self.show_message(f"同步完成，共 {len(files)} 首歌曲", "success")
        except Exception as ex:
            self.show_message(f"同步失败: {str(ex)}", "error")
        finally:
            self.is_syncing = False
            self.sync_button.disabled = False
            self.page.update()

    def _search_music(self, e):
        """搜索音乐"""
        query = self.search_input.value.strip() if self.search_input.value else ""
        try:
            self.music_files = self.music_service.search_songs(query)
            self.file_list.controls.clear()
            for song in self.music_files:
                self.file_list.controls.append(self.build_file_item(song))
            self._update_stats()
            self.page.update()
        except Exception as ex:
            logger.error(f"搜索失败: {ex}")

    def _select_all(self, e):
        """全选/取消全选"""
        if len(self.selected_files) == len(self.music_files):
            self.selected_files.clear()
        else:
            self.selected_files = {s.get('name', '') for s in self.music_files}
        self.reload_music_list(keep_scroll=True)

    def _delete_selected(self, e):
        """删除选中的文件"""
        if not self.selected_files:
            self.show_message("请先选择要删除的文件", "warning")
            return
        for name in list(self.selected_files):
            if self.music_service.has_song(name):
                self.music_service.remove_song(name)
        self.selected_files.clear()
        self.reload_music_list()
        self.show_message("删除完成", "success")

    def _add_to_playlist(self, e):
        """添加选中文件到播放列表"""
        if not self.selected_files:
            self.show_message("请先选择文件", "warning")
            return
        playback_view = self.view_manager.get_view("playback")
        selected_files = [s for s in self.music_files if s.get('name') in self.selected_files]
        if playback_view:
            playback_view.handle_play_selected(selected_files)
            self.view_manager.switch_to_view("playback")
            self.show_message(f"已添加 {len(selected_files)} 首歌曲到播放列表", "success")

    def _play_selected(self, e):
        """播放选中文件"""
        if not self.selected_files:
            self.show_message("请先选择文件", "warning")
            return
        playback_view = self.view_manager.get_view("playback")
        selected_files = [s for s in self.music_files if s.get('name') in self.selected_files]
        if playback_view:
            playback_view.handle_play_selected(selected_files, start_index=0)
            self.view_manager.switch_to_view("playback")

    async def _download_selected(self, e):
        """下载选中的文件"""
        if not self.selected_files:
            return
        self.download_button.disabled = True
        self.show_message(f"开始下载 {len(self.selected_files)} 首歌曲...", "info")
        self.page.update()

        success_count = 0
        for name in list(self.selected_files):
            song = next((s for s in self.music_files if s.get('name') == name), None)
            if song and not song.get('is_downloaded', False):
                remote_path = song.get('remote_path', '')
                if remote_path:
                    try:
                        ok = await self.music_service.download_file(remote_path, name)
                        if ok:
                            success_count += 1
                    except Exception as ex:
                        logger.error(f"下载 {name} 失败: {ex}")

        self.selected_files.clear()
        self.reload_music_list()
        self.show_message(f"下载完成，成功 {success_count} 首", "success")

    def _clear_cache(self, e):
        """清除缓存"""
        self.music_service.clear_cache()
        self.selected_files.clear()
        self.reload_music_list()
        self.show_message("缓存已清除", "info")

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
        logger.info(f"[{message_type.upper()}] {message}")

    def on_view_activated(self):
        """视图激活时刷新列表"""
        self.reload_music_list()
        sync_folder = self.app_context['config_manager'].get("connection.default_sync_folder", "")
        if sync_folder:
            self.folder_text.value = f"文件夹: {sync_folder}"
            self.page.update()
