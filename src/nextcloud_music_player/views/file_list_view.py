"""
文件列表视图 - Flet 版本
"""

import asyncio
import logging
from typing import Any, Dict, List

import flet as ft

from ..utils.notify import show_snack_bar
from ..utils.theme import (
    Color,
    FontSize,
    Radius,
    Space,
    glow,
    tint,
)

logger = logging.getLogger(__name__)


class FileListView:
    """文件列表管理视图"""

    def __init__(self, page: ft.Page, app_context: dict, view_manager):
        self.page = page
        self.app_context = app_context
        self.music_service = app_context["music_service"]
        self.view_manager = view_manager
        self.music_files = []
        self.selected_files = set()
        self.last_selected_name = None  # 最后点选的歌曲，播放时从它开始
        self.is_syncing = False
        self._built = False
        # 下载队列：iOS 切后台进程挂起会中断下载协程，
        # 未完成项留在 pending，回前台（on_app_resumed）自动续传
        self._pending_downloads: list[tuple[str, str]] = []
        self._download_task: asyncio.Task | None = None

    def rebuild(self):
        """重建视图（Flet 0.86 控件脱离页面后被冻结且不可复用）"""
        self._built = False
        return self.build()

    def build(self):
        """构建并返回视图内容"""
        if self._built and hasattr(self, "_container"):
            return self._container

        # === 标题区 ===
        title_row = ft.Row(
            [
                ft.Container(
                    content=ft.Icon(
                        ft.Icons.LIBRARY_MUSIC_OUTLINED, color=Color.PRIMARY, size=20
                    ),
                    width=36,
                    height=36,
                    border_radius=Radius.SM,
                    bgcolor=tint(Color.PRIMARY, "14"),
                    border=ft.Border.all(1, tint(Color.PRIMARY, "33")),
                ),
                ft.Column(
                    [
                        ft.Text(
                            "音乐库",
                            size=FontSize.TITLE + 4,
                            weight=ft.FontWeight.BOLD,
                            color=Color.TEXT_PRIMARY,
                        ),
                        ft.Text(
                            "LIBRARY · 云端文件",
                            size=FontSize.MICRO,
                            color=Color.TEXT_MUTED,
                            style=ft.TextStyle(letter_spacing=2),
                        ),
                    ],
                    spacing=0,
                ),
            ],
            spacing=Space.MD,
        )

        # 操作栏
        self.sync_button = ft.FilledButton(
            "同步",
            icon=ft.Icons.SYNC,
            on_click=self._sync_music_list,
            style=ft.ButtonStyle(
                bgcolor=Color.BG_ELEVATED,
                color=Color.PRIMARY,
                icon_color=Color.PRIMARY,
                side=ft.BorderSide(1, tint(Color.PRIMARY, "40")),
                shape=ft.RoundedRectangleBorder(radius=Radius.CIRCLE),
            ),
        )

        self.search_input = ft.TextField(
            hint_text="搜索歌曲 / 艺术家...",
            prefix_icon=ft.Icons.SEARCH,
            on_submit=self._search_music,
            bgcolor=Color.BG_SURFACE_ALT,
            border_color=Color.BORDER,
            focused_border_color=Color.PRIMARY,
            border_width=1,
            border_radius=Radius.CIRCLE,
            color=Color.TEXT_PRIMARY,
            hint_style=ft.TextStyle(color=Color.TEXT_DISABLED),
            cursor_color=Color.PRIMARY,
            content_padding=ft.Padding(left=16, right=16, top=10, bottom=10),
            expand=True,
        )

        self.search_button = ft.IconButton(
            ft.Icons.SEARCH,
            tooltip="搜索",
            icon_color=Color.TEXT_SECONDARY,
            on_click=self._search_music,
        )

        # 文件夹路径栏
        self.folder_text = ft.Text(
            "文件夹: 未设置",
            size=FontSize.CAPTION,
            color=Color.TEXT_MUTED,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        self.folder_button = ft.TextButton(
            "去设置",
            icon=ft.Icons.TUNE,
            on_click=lambda e: self.view_manager.switch_to_view("connection"),
            style=ft.ButtonStyle(
                color=Color.PRIMARY,
                icon_color=Color.PRIMARY,
                padding=0,
            ),
        )

        # 播放操作栏
        self.add_button = ft.OutlinedButton(
            "添加",
            icon=ft.Icons.PLAYLIST_ADD,
            on_click=self._add_to_playlist,
            style=ft.ButtonStyle(
                color=Color.TEXT_SECONDARY,
                icon_color=Color.TEXT_SECONDARY,
                side=ft.BorderSide(1, Color.BORDER),
                shape=ft.RoundedRectangleBorder(radius=Radius.CIRCLE),
            ),
        )
        self.play_button = ft.FilledButton(
            "播放",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._play_selected,
            style=ft.ButtonStyle(
                bgcolor={
                    ft.ControlState.DISABLED: Color.BG_ELEVATED,
                    ft.ControlState.DEFAULT: Color.PRIMARY,
                },
                color={
                    ft.ControlState.DISABLED: Color.TEXT_DISABLED,
                    ft.ControlState.DEFAULT: Color.PRIMARY_TEXT,
                },
                icon_color={
                    ft.ControlState.DISABLED: Color.TEXT_DISABLED,
                    ft.ControlState.DEFAULT: Color.PRIMARY_TEXT,
                },
                elevation={ft.ControlState.DEFAULT: 4, ft.ControlState.PRESSED: 1},
                shadow_color=tint(Color.PRIMARY, "59"),
                shape=ft.RoundedRectangleBorder(radius=Radius.CIRCLE),
            ),
        )
        self.select_all_button = ft.TextButton(
            "全选",
            on_click=self._select_all,
            style=ft.ButtonStyle(color=Color.TEXT_SECONDARY),
        )
        self.delete_button = ft.TextButton(
            "删除",
            on_click=self._delete_selected,
            style=ft.ButtonStyle(color=Color.DANGER_TEXT),
        )

        # 统计栏（数据芯片风）
        self.stats_text = ft.Text(
            "总数 0 · 已选 0 · 已下载 0",
            size=FontSize.CAPTION,
            color=Color.TEXT_SECONDARY,
            style=ft.TextStyle(letter_spacing=1),
        )

        # 文件列表
        self.file_list = ft.ListView(
            expand=True,
            spacing=6,
            padding=ft.Padding(left=0, right=0, top=0, bottom=Space.SM),
        )

        # 下载栏
        self.download_button = ft.FilledButton(
            "下载选中",
            icon=ft.Icons.CLOUD_DOWNLOAD,
            on_click=self._download_selected,
            disabled=True,
            style=ft.ButtonStyle(
                bgcolor={
                    ft.ControlState.DISABLED: Color.BG_ELEVATED,
                    ft.ControlState.DEFAULT: Color.BG_ELEVATED,
                },
                color={
                    ft.ControlState.DISABLED: Color.TEXT_DISABLED,
                    ft.ControlState.DEFAULT: Color.SUCCESS_TEXT,
                },
                icon_color={
                    ft.ControlState.DISABLED: Color.TEXT_DISABLED,
                    ft.ControlState.DEFAULT: Color.SUCCESS,
                },
                side=ft.BorderSide(1, tint(Color.SUCCESS, "40")),
                shape=ft.RoundedRectangleBorder(radius=Radius.CIRCLE),
            ),
        )
        self.clear_cache_button = ft.OutlinedButton(
            "清除缓存",
            icon=ft.Icons.DELETE_SWEEP,
            on_click=self._clear_cache,
            style=ft.ButtonStyle(
                color=Color.TEXT_SECONDARY,
                icon_color=Color.TEXT_MUTED,
                side=ft.BorderSide(1, Color.BORDER),
                shape=ft.RoundedRectangleBorder(radius=Radius.CIRCLE),
            ),
        )

        # 组装
        self._container = ft.Container(
            content=ft.Column(
                controls=[
                    title_row,
                    ft.Row(
                        [self.sync_button, self.search_input, self.search_button],
                        spacing=Space.XS,
                    ),
                    ft.Row([self.folder_text, self.folder_button], spacing=Space.XS),
                    ft.Row(
                        [
                            self.add_button,
                            self.play_button,
                            self.select_all_button,
                            self.delete_button,
                        ],
                        spacing=Space.XS,
                    ),
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(
                                    ft.Icons.QUERY_STATS, size=14, color=Color.PRIMARY
                                ),
                                self.stats_text,
                            ],
                            spacing=Space.SM,
                        ),
                        bgcolor=tint(Color.PRIMARY, "0D"),
                        border=ft.Border.all(1, tint(Color.PRIMARY, "26")),
                        padding=ft.Padding(left=12, right=12, top=8, bottom=8),
                        border_radius=Radius.CIRCLE,
                        width=float("inf"),
                    ),
                    ft.Container(
                        content=self.file_list,
                        expand=True,
                        bgcolor=Color.BG_APP_ALT,
                        border=ft.Border.all(1, Color.BORDER),
                        border_radius=Radius.LG,
                        padding=Space.XS,
                    ),
                    ft.Row(
                        [self.download_button, self.clear_cache_button],
                        spacing=Space.SM,
                    ),
                ],
                spacing=Space.MD,
                expand=True,
            ),
            padding=Space.LG,
            expand=True,
            bgcolor=Color.BG_APP,
        )

        self._built = True
        self.reload_music_list()
        return self._container

    def build_file_item(self, song: Dict[str, Any]) -> ft.Container:
        """构建单个文件项（暗色卡片，选中态霓虹发光）"""
        name = song.get("name", "Unknown")
        title = song.get("title", name)
        if title.endswith(".mp3"):
            title = title[:-4]
        artist = song.get("artist", "未知艺术家")
        is_downloaded = song.get("is_downloaded", False)
        size = song.get("size", 0)

        size_str = f"{float(size) / 1024 / 1024:.1f}MB" if size else ""
        download_icon = (
            ft.Icons.TASK_ALT if is_downloaded else ft.Icons.CLOUD_DOWNLOAD_OUTLINED
        )
        download_color = Color.SUCCESS if is_downloaded else Color.TEXT_DISABLED

        selected = name in self.selected_files
        check_icon = ft.Icon(
            ft.Icons.CHECK_CIRCLE if selected else ft.Icons.RADIO_BUTTON_UNCHECKED,
            color=Color.PRIMARY if selected else Color.TEXT_DISABLED,
            size=20,
        )

        return ft.Container(
            key=f"song:{name}",
            content=ft.Row(
                [
                    check_icon,
                    ft.Icon(download_icon, color=download_color, size=18),
                    ft.Column(
                        [
                            ft.Text(
                                title,
                                size=FontSize.BODY + 1,
                                weight=ft.FontWeight.W_500,
                                color=(
                                    Color.TEXT_PRIMARY
                                    if selected
                                    else Color.TEXT_PRIMARY
                                ),
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.Text(
                                f"{artist} · {size_str}",
                                size=FontSize.CAPTION,
                                color=Color.TEXT_MUTED,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                ],
                spacing=Space.SM,
            ),
            padding=ft.Padding(left=12, right=12, top=10, bottom=10),
            border_radius=Radius.MD,
            on_click=lambda e, n=name: self._toggle_select(n),
            bgcolor=tint(Color.PRIMARY, "1A") if selected else Color.BG_SURFACE,
            border=ft.Border.all(
                1, tint(Color.PRIMARY, "66") if selected else Color.BORDER
            ),
            shadow=glow(Color.PRIMARY, radius=12, alpha="26") if selected else None,
        )

    def _toggle_select(self, name: str):
        """切换文件选中状态"""
        if name in self.selected_files:
            self.selected_files.remove(name)
            if self.last_selected_name == name:
                self.last_selected_name = None
        else:
            self.selected_files.add(name)
            self.last_selected_name = name
        self._update_stats()
        self.reload_music_list(keep_scroll=True)

    def _update_stats(self):
        """更新统计栏"""
        total = len(self.music_files)
        selected = len(self.selected_files)
        downloaded = sum(1 for s in self.music_files if s.get("is_downloaded", False))
        self.stats_text.value = f"总数 {total} · 已选 {selected} · 已下载 {downloaded}"
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
            sync_folder = self.music_service.get_default_sync_folder()
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
            self.selected_files = {s.get("name", "") for s in self.music_files}
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

    def _get_selected_start_index(self, selected_files: List[Dict[str, Any]]) -> int:
        """计算播放起始索引：从最后点选的歌曲开始，未命中则回到 0"""
        if self.last_selected_name:
            for i, song in enumerate(selected_files):
                if song.get("name") == self.last_selected_name:
                    return i
        return 0

    def _add_to_playlist(self, e):
        """添加选中文件到播放列表"""
        if not self.selected_files:
            self.show_message("请先选择文件", "warning")
            return
        playback_view = self.view_manager.get_view("playback")
        selected_files = [
            s for s in self.music_files if s.get("name") in self.selected_files
        ]
        if playback_view:
            playback_view.handle_play_selected(
                selected_files,
                start_index=self._get_selected_start_index(selected_files),
            )
            self.view_manager.switch_to_view("playback")
            self.show_message(
                f"已添加 {len(selected_files)} 首歌曲到播放列表", "success"
            )

    def _play_selected(self, e):
        """播放选中文件（从最后点选的歌曲开始）"""
        if not self.selected_files:
            self.show_message("请先选择文件", "warning")
            return
        playback_view = self.view_manager.get_view("playback")
        selected_files = [
            s for s in self.music_files if s.get("name") in self.selected_files
        ]
        if playback_view:
            playback_view.handle_play_selected(
                selected_files,
                start_index=self._get_selected_start_index(selected_files),
            )
            self.view_manager.switch_to_view("playback")

    async def _download_selected(self, e):
        """把选中的文件排入下载队列，由后台 worker 逐首处理"""
        if not self.selected_files:
            return

        added = 0
        for name in list(self.selected_files):
            song = next((s for s in self.music_files if s.get("name") == name), None)
            if song and not song.get("is_downloaded", False):
                remote_path = song.get("remote_path", "")
                if remote_path:
                    self._pending_downloads.append((name, remote_path))
                    added += 1

        self.selected_files.clear()
        self.reload_music_list()

        if not added:
            self.show_message("选中歌曲均已下载", "info")
            return

        self.music_service.download_progress.enqueue(added)
        self.show_message(f"开始下载 {added} 首歌曲...", "info")
        self._start_download_worker()

    def _start_download_worker(self):
        """启动下载 worker；已在运行时不重复启动（新排队项由现有 worker 继续消化）"""
        if self._download_task and not self._download_task.done():
            return
        self._download_task = asyncio.create_task(self._download_worker())

    async def _download_worker(self):
        """逐首处理下载队列。

        iOS 切后台进程挂起可能中断协程：未完成项留在 _pending_downloads，
        回前台由 on_app_resumed() 重新拉起 worker 续传。
        """
        from ..ios_background_task import begin_background_task, end_background_task

        # 申请约 30s 的 iOS 后台宽限，尽量让当前批次在切后台后跑完
        bg_token = begin_background_task("music-download")
        success_count = 0
        failed_count = 0
        try:
            while self._pending_downloads:
                name, remote_path = self._pending_downloads.pop(0)
                try:
                    ok = await self.music_service.download_file(remote_path, name)
                    if ok:
                        success_count += 1
                    else:
                        failed_count += 1
                except asyncio.CancelledError:
                    # 取消时把当前项放回队首，续传时从这里继续
                    self._pending_downloads.insert(0, (name, remote_path))
                    raise
                except Exception as ex:
                    failed_count += 1
                    logger.error(f"下载 {name} 失败: {ex}")
                self.reload_music_list(keep_scroll=True)
        finally:
            end_background_task(bg_token)

        if success_count or failed_count:
            message = f"下载完成，成功 {success_count} 首"
            message_type = "success"
            if failed_count:
                message += f"，失败 {failed_count} 首"
                message_type = "warning"
            self.show_message(message, message_type)
            self.reload_music_list()

    def on_app_resumed(self):
        """应用回到前台：下载队列有剩余且 worker 已死时自动续传"""
        if not self._pending_downloads:
            return
        if self._download_task and not self._download_task.done():
            return
        remaining = len(self._pending_downloads)
        logger.info(f"应用回到前台，续传下载剩余 {remaining} 首")
        self.show_message(f"继续下载剩余 {remaining} 首...", "info")
        self._start_download_worker()

    def _clear_cache(self, e):
        """清除缓存"""
        self.music_service.clear_cache()
        self.selected_files.clear()
        self.reload_music_list()
        self.show_message("缓存已清除", "info")

    def show_message(self, message: str, message_type: str = "info"):
        """在页面顶部显示消息。"""
        show_snack_bar(self.page, message, message_type)

    def on_view_activated(self):
        """视图激活时刷新列表"""
        self.reload_music_list()
        sync_folder = self.music_service.get_default_sync_folder()
        if sync_folder:
            self.folder_text.value = f"文件夹: {sync_folder}"
            self.page.update()
