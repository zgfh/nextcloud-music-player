"""
歌词显示组件 - Flet 版本
"""

import asyncio
import logging
from typing import List, Optional

import flet as ft

from ...services.lyrics_service import LyricsService
from ...utils.theme import Color, FontSize, Radius, Space

logger = logging.getLogger(__name__)


class LyricsDisplayComponent:
    """歌词显示组件"""

    def __init__(
        self,
        page: ft.Page,
        app_context: dict,
        config_manager,
        lyrics_service: Optional[LyricsService],
    ):
        self.page = page
        self.app_context = app_context
        self.config_manager = config_manager
        self.lyrics_service = lyrics_service
        self.current_song_name = None
        self.current_position = 0
        self.auto_scroll = True
        self.font_size = (
            config_manager.get("lyrics.font_size", 14) if config_manager else 14
        )
        self._built = False
        self._lyric_items = []  # 用于跟踪歌词行控件

    def build(self):
        """构建并返回组件"""
        if self._built and hasattr(self, "_container"):
            return self._container

        # 标题栏
        self.title_label = ft.Text(
            "歌词",
            size=FontSize.SUBTITLE,
            weight=ft.FontWeight.W_500,
            color=Color.TEXT_SECONDARY,
            expand=True,
            style=ft.TextStyle(letter_spacing=2),
        )
        self.download_button = ft.IconButton(
            ft.Icons.CLOUD_DOWNLOAD_OUTLINED,
            tooltip="下载歌词",
            on_click=self._download_lyrics,
            icon_size=18,
            icon_color=Color.PRIMARY,
            visible=False,
        )

        # 歌词列表
        self.lyrics_list = ft.ListView(
            expand=True,
            spacing=4,
            padding=Space.MD,
        )

        # 无歌词提示
        self.no_lyrics_text = ft.Text(
            "♪ 暂无歌词",
            size=FontSize.BODY + 2,
            color=Color.TEXT_DISABLED,
            text_align=ft.TextAlign.CENTER,
        )

        self._container = ft.Column(
            [
                ft.Row([self.title_label, self.download_button], spacing=4),
                ft.Container(
                    content=self.lyrics_list,
                    expand=True,
                    bgcolor=Color.LYRICS_BG,
                    border=ft.Border.all(1, Color.BORDER),
                    border_radius=Radius.LG,
                ),
            ],
            spacing=Space.XS,
            expand=True,
        )

        self._built = True
        self._show_no_lyrics()
        return self._container

    def _show_no_lyrics(self):
        """显示无歌词提示"""
        self.lyrics_list.controls.clear()
        # 注意：ListView 条目不能带 expand（滚动容器高度无限，
        # flex 子项会触发 "non-zero flex but unbounded constraints" 渲染异常）
        self.lyrics_list.controls.append(
            ft.Container(
                content=self.no_lyrics_text,
                alignment=ft.Alignment(0, 0),
                padding=Space.XL,
            )
        )
        self.page.update()

    def load_lyrics_for_song(self, song_name: str, auto_download: bool = False):
        """加载歌词"""
        if not self.lyrics_service:
            self._show_no_lyrics()
            return

        self.current_song_name = song_name
        try:
            loaded = self.lyrics_service.load_lyrics(
                song_name, auto_download=auto_download
            )
            if loaded:
                self._display_all_lyrics()
                self.download_button.visible = False
            else:
                self._show_no_lyrics()
                self.download_button.visible = True
            self.page.update()
        except Exception as e:
            logger.error(f"加载歌词失败: {e}")
            self._show_no_lyrics()

    def _display_all_lyrics(self):
        """显示所有歌词行"""
        self.lyrics_list.controls.clear()
        self._lyric_items.clear()

        lines = self.lyrics_service.get_all_lyrics_lines()
        if not lines:
            self._show_no_lyrics()
            return

        # 显示元数据
        metadata = self.lyrics_service.get_lyrics_metadata()
        if metadata:
            meta_parts = []
            for key in ["ti", "ar", "al"]:
                if key in metadata:
                    meta_parts.append(metadata[key])
            if meta_parts:
                self.lyrics_list.controls.append(
                    ft.Text(
                        " · ".join(meta_parts),
                        size=FontSize.CAPTION,
                        color=Color.TEXT_MUTED,
                        text_align=ft.TextAlign.CENTER,
                        weight=ft.FontWeight.W_500,
                    )
                )
                self.lyrics_list.controls.append(
                    ft.Divider(height=1, color=Color.BORDER)
                )

        # 显示歌词行
        for i, line in enumerate(lines):
            time_str = self._format_time(line.time_seconds)
            text = f"[{time_str}] {line.text}" if time_str else line.text

            item = ft.Container(
                content=ft.Text(
                    text,
                    size=self.font_size,
                    color=Color.LYRICS_NORMAL,
                    selectable=True,
                ),
                padding=ft.Padding(left=8, right=8, top=4, bottom=4),
                border_radius=Radius.SM,
                key=f"lyric_{i}",
            )
            self._lyric_items.append((item, i, line.time_seconds))
            self.lyrics_list.controls.append(item)

    def update_lyrics_position(self, position_seconds: float):
        """更新歌词高亮位置"""
        if not self.lyrics_service or not self._lyric_items:
            return

        self.current_position = position_seconds
        current_line = self.lyrics_service.get_current_lyric_line(position_seconds)
        if not current_line:
            return

        # 找到当前行索引
        current_index = None
        for item, idx, time_sec in self._lyric_items:
            if abs(time_sec - current_line.time_seconds) < 0.1:
                current_index = idx
                break

        if current_index is None:
            return

        # 更新高亮
        for item, idx, _ in self._lyric_items:
            if idx == current_index:
                item.content.color = Color.LYRICS_HIGHLIGHT
                item.content.weight = ft.FontWeight.BOLD
                item.bgcolor = Color.LYRICS_HIGHLIGHT_BG
            else:
                item.content.color = Color.LYRICS_NORMAL
                item.content.weight = ft.FontWeight.NORMAL
                item.bgcolor = None

        # 自动滚动到当前行
        if self.auto_scroll and current_index < len(self._lyric_items):
            try:
                self.lyrics_list.scroll_to(key=f"lyric_{current_index}", duration=300)
            except:
                pass

        self.page.update()

    async def _download_lyrics(self, e):
        """手动下载歌词"""
        if not self.current_song_name or not self.lyrics_service:
            return

        self.download_button.disabled = True
        self.page.update()

        try:
            song_info = self.app_context.get("music_library")
            remote_path = ""
            if song_info:
                info = song_info.get_song_info(self.current_song_name)
                if info:
                    remote_path = info.get("remote_path", "")

            success = await self.lyrics_service.download_lyrics(
                self.current_song_name, remote_path
            )
            if success:
                self.load_lyrics_for_song(self.current_song_name)
                self.download_button.visible = False
            else:
                self.download_button.visible = True
        except Exception as ex:
            logger.error(f"下载歌词失败: {ex}")
        finally:
            self.download_button.disabled = False
            self.page.update()

    def _format_time(self, seconds: float) -> str:
        """格式化时间"""
        if seconds < 0:
            return ""
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m:02d}:{s:02d}"
