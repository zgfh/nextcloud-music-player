"""
设置视图 - 日志级别切换 / 应用日志查看（iOS 真机排障）/ 应用信息
"""

import asyncio
import logging
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from pathlib import Path

import flet as ft

from ..utils.log_buffer import (
    LOG_FILE_NAME,
    clear_buffer,
    get_buffered_log_count,
    get_recent_logs,
    set_log_level,
)
from ..utils.notify import show_snack_bar
from ..utils.theme import Color, FontSize, Radius, Space, tint

logger = logging.getLogger(__name__)

_LOG_LINE_LIMIT = 300
_LOG_INITIAL_LINES = 40
_LOG_PAGE_LINES = 50


def _package_version(name: str) -> str:
    try:
        return pkg_version(name)
    except PackageNotFoundError:
        return "dev"


class SettingsView:
    """设置视图"""

    def __init__(self, page: ft.Page, app_context: dict, view_manager):
        self.page = page
        self.app_context = app_context
        self.view_manager = view_manager
        self._built = False
        self._log_lines: list[str] = []
        self._log_file: Path | None = None
        self._visible_log_limit = _LOG_INITIAL_LINES
        self._log_tail_task = None
        self._view_active = False
        self._loading_older_logs = False

    def rebuild(self):
        """重建视图（Flet 0.86 控件脱离页面后被冻结且不可复用）"""
        self._cancel_log_tail()
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
                    content=ft.Icon(ft.Icons.TUNE, color=Color.PRIMARY, size=20),
                    width=36,
                    height=36,
                    border_radius=Radius.SM,
                    bgcolor=tint(Color.PRIMARY, "14"),
                    border=ft.Border.all(1, tint(Color.PRIMARY, "33")),
                ),
                ft.Column(
                    [
                        ft.Text(
                            "设置",
                            size=FontSize.TITLE + 4,
                            weight=ft.FontWeight.BOLD,
                            color=Color.TEXT_PRIMARY,
                        ),
                        ft.Text(
                            "SETTINGS · 诊断与日志",
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

        # === 日志级别 ===
        current_level = str(
            self.app_context["config_manager"].get("app.log_level", "INFO")
        ).upper()
        if current_level not in ("INFO", "DEBUG"):
            current_level = "INFO"
        self.level_selector = ft.SegmentedButton(
            selected=[current_level],
            segments=[
                ft.Segment(value="INFO", label="INFO", icon=ft.Icons.INFO_OUTLINED),
                ft.Segment(
                    value="DEBUG", label="DEBUG", icon=ft.Icons.BUG_REPORT_OUTLINED
                ),
            ],
            allow_multiple_selection=False,
            allow_empty_selection=False,
            on_change=self._on_log_level_change,
            style=ft.ButtonStyle(
                bgcolor={
                    ft.ControlState.SELECTED: tint(Color.PRIMARY, "26"),
                    ft.ControlState.DEFAULT: Color.BG_SURFACE_ALT,
                },
                color={
                    ft.ControlState.SELECTED: Color.PRIMARY,
                    ft.ControlState.DEFAULT: Color.TEXT_SECONDARY,
                },
                side=ft.BorderSide(1, Color.BORDER),
                shape=ft.RoundedRectangleBorder(radius=Radius.MD),
            ),
        )

        # === 应用日志 ===
        self.log_path_text = ft.Text(
            "日志文件: -",
            size=FontSize.CAPTION,
            color=Color.TEXT_MUTED,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        self.log_meta_text = ft.Text(
            "0 行",
            size=FontSize.CAPTION,
            color=Color.TEXT_SECONDARY,
        )
        self.log_list = ft.ListView(
            expand=True,
            spacing=0,
            auto_scroll=True,
            auto_scroll_animation=0,
            on_scroll=self._on_log_scroll,
            scroll_interval=100,
            padding=Space.SM,
        )

        self.refresh_button = ft.OutlinedButton(
            "刷新",
            icon=ft.Icons.REFRESH,
            on_click=self._refresh_clicked,
            style=ft.ButtonStyle(
                color=Color.TEXT_SECONDARY,
                icon_color=Color.PRIMARY,
                side=ft.BorderSide(1, Color.BORDER),
                shape=ft.RoundedRectangleBorder(radius=Radius.CIRCLE),
            ),
        )
        self.copy_button = ft.OutlinedButton(
            "复制",
            icon=ft.Icons.CONTENT_COPY,
            on_click=self._copy_logs,
            style=ft.ButtonStyle(
                color=Color.TEXT_SECONDARY,
                icon_color=Color.INFO,
                side=ft.BorderSide(1, Color.BORDER),
                shape=ft.RoundedRectangleBorder(radius=Radius.CIRCLE),
            ),
        )
        self.share_button = ft.OutlinedButton(
            "分享",
            icon=ft.Icons.SHARE,
            on_click=self._share_logs,
            style=ft.ButtonStyle(
                color=Color.TEXT_SECONDARY,
                icon_color=Color.ACCENT,
                side=ft.BorderSide(1, Color.BORDER),
                shape=ft.RoundedRectangleBorder(radius=Radius.CIRCLE),
            ),
        )
        self.clear_button = ft.OutlinedButton(
            "清空",
            icon=ft.Icons.DELETE_SWEEP,
            on_click=self._clear_logs,
            style=ft.ButtonStyle(
                color=Color.DANGER_TEXT,
                icon_color=Color.DANGER,
                side=ft.BorderSide(1, tint(Color.DANGER, "40")),
                shape=ft.RoundedRectangleBorder(radius=Radius.CIRCLE),
            ),
        )

        log_card = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.TERMINAL,
                                size=16,
                                color=Color.SUCCESS,
                            ),
                            ft.Text(
                                "应用日志",
                                size=FontSize.BODY + 1,
                                weight=ft.FontWeight.W_500,
                                color=Color.TEXT_PRIMARY,
                            ),
                        ],
                        spacing=Space.SM,
                    ),
                    self.log_path_text,
                    ft.Container(
                        content=self.log_list,
                        expand=True,
                        bgcolor=Color.BG_APP_ALT,
                        border=ft.Border.all(1, Color.BORDER),
                        border_radius=Radius.MD,
                    ),
                    self.log_meta_text,
                    ft.Row(
                        [
                            self.refresh_button,
                            self.copy_button,
                            self.share_button,
                            self.clear_button,
                        ],
                        spacing=Space.XS,
                        wrap=True,
                    ),
                ],
                spacing=Space.SM,
                expand=True,
            ),
            padding=Space.MD,
            bgcolor=Color.BG_SURFACE,
            border=ft.Border.all(1, Color.BORDER),
            border_radius=Radius.LG,
            expand=True,
        )

        # === 应用信息 ===
        platform_name = str(getattr(self.page, "platform", "") or sys.platform)
        info_rows = ft.Column(
            [
                self._info_row(
                    "平台", f"{platform_name} · Python {sys.version.split()[0]}"
                ),
                self._info_row("Flet 版本", _package_version("flet")),
                self._info_row("应用版本", _package_version("nextcloud-music-player")),
            ],
            spacing=Space.SM,
        )
        info_card = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.INFO_OUTLINED,
                                size=16,
                                color=Color.PRIMARY,
                            ),
                            ft.Text(
                                "应用信息",
                                size=FontSize.BODY + 1,
                                weight=ft.FontWeight.W_500,
                                color=Color.TEXT_PRIMARY,
                            ),
                        ],
                        spacing=Space.SM,
                    ),
                    info_rows,
                ],
                spacing=Space.MD,
            ),
            padding=Space.MD,
            bgcolor=Color.BG_SURFACE,
            border=ft.Border.all(1, Color.BORDER),
            border_radius=Radius.LG,
        )

        # 组装
        self._container = ft.Container(
            content=ft.Column(
                controls=[
                    title_row,
                    ft.Row([self.level_selector], spacing=Space.XS),
                    log_card,
                    info_card,
                ],
                spacing=Space.MD,
                expand=True,
            ),
            padding=Space.LG,
            expand=True,
            bgcolor=Color.BG_APP,
        )

        self._built = True
        self._visible_log_limit = _LOG_INITIAL_LINES
        self._refresh_logs(limit=self._visible_log_limit)
        return self._container

    @staticmethod
    def _info_row(key: str, value: str) -> ft.Row:
        return ft.Row(
            [
                ft.Text(
                    key,
                    size=FontSize.CAPTION,
                    color=Color.TEXT_MUTED,
                    width=80,
                ),
                ft.Text(
                    value,
                    size=FontSize.CAPTION,
                    color=Color.TEXT_SECONDARY,
                    expand=True,
                    selectable=True,
                ),
            ],
            spacing=Space.SM,
        )

    def _log_file_path(self) -> Path | None:
        try:
            log_dir = self.app_context["config_manager"].get_log_directory()
            return Path(log_dir) / LOG_FILE_NAME
        except Exception:
            return None

    def _load_log_lines(self, limit: int) -> list[str]:
        """优先读日志文件（含历史会话），文件不可用时退回内存缓冲"""
        self._log_file = self._log_file_path()
        if self._log_file is not None:
            try:
                if self._log_file.exists():
                    return self._read_file_tail(self._log_file, limit)
            except OSError as ex:
                logger.warning(f"读取日志文件失败: {ex}")
        return get_recent_logs(limit)

    @staticmethod
    def _read_file_tail(path: Path, limit: int) -> list[str]:
        """从文件末尾分块读取，避免日志很大时加载整个文件。"""
        if limit <= 0:
            return []
        chunks: list[bytes] = []
        newline_count = 0
        with path.open("rb") as log_file:
            log_file.seek(0, 2)
            position = log_file.tell()
            while position > 0 and newline_count <= limit:
                chunk_size = min(8192, position)
                position -= chunk_size
                log_file.seek(position)
                chunk = log_file.read(chunk_size)
                chunks.append(chunk)
                newline_count += chunk.count(b"\n")
        content = b"".join(reversed(chunks)).decode("utf-8", errors="replace")
        return content.splitlines()[-limit:]

    @staticmethod
    def _log_text(line: str) -> ft.Text:
        color = Color.TEXT_MUTED
        if " - ERROR - " in line or " - CRITICAL - " in line:
            color = Color.DANGER_TEXT
        elif " - WARNING - " in line:
            color = Color.WARNING_TEXT
        elif " - INFO - " in line:
            color = Color.TEXT_SECONDARY
        return ft.Text(
            line if line.strip() else " ",
            size=FontSize.MICRO + 1,
            color=color,
            font_family="monospace",
            selectable=True,
        )

    def _refresh_logs(self, limit: int | None = None):
        """重新加载日志内容到列表"""
        if limit is None:
            limit = self._visible_log_limit
        self._log_lines = self._load_log_lines(limit)

        self.log_list.controls.clear()
        for line in self._log_lines:
            self.log_list.controls.append(self._log_text(line))

        if self._log_file is not None:
            self.log_path_text.value = f"日志文件: {self._log_file}"
        else:
            self.log_path_text.value = "日志文件不可用，显示内存缓冲（当前会话）"
        self.log_meta_text.value = f"显示最近 {len(self._log_lines)} 行 · 内存缓冲 {get_buffered_log_count()} 条"
        try:
            self.page.update()
        except Exception:
            pass

    def _refresh_clicked(self, e):
        self._refresh_logs(limit=self._visible_log_limit)

    def _on_log_scroll(self, e):
        """上滑到顶部时按页加载更早日志。"""
        if self._loading_older_logs or self._visible_log_limit >= _LOG_LINE_LIMIT:
            return
        pixels = float(getattr(e, "pixels", 1) or 0)
        minimum = float(getattr(e, "min_scroll_extent", 0) or 0)
        delta = getattr(e, "scroll_delta", None)
        if pixels <= minimum + 24 and (delta is None or delta < 0):
            self._loading_older_logs = True
            try:
                self._visible_log_limit = min(
                    _LOG_LINE_LIMIT, self._visible_log_limit + _LOG_PAGE_LINES
                )
                self._refresh_logs(limit=self._visible_log_limit)
            finally:
                self._loading_older_logs = False

    @staticmethod
    def _new_log_lines(
        old_lines: list[str], latest_lines: list[str]
    ) -> list[str] | None:
        """返回旧尾部之后的新增行；找不到旧尾部表示日志已轮转或清空。"""
        if not old_lines:
            return latest_lines
        last_line = old_lines[-1]
        for index in range(len(latest_lines) - 1, -1, -1):
            if latest_lines[index] == last_line:
                return latest_lines[index + 1 :]
        return None

    async def _tail_logs(self):
        """设置页可见时增量追加日志，行为类似 tail -f。"""
        while self._view_active:
            await asyncio.sleep(1.0)
            if not self._view_active or not self._built:
                break
            try:
                latest = self._load_log_lines(_LOG_LINE_LIMIT)
                new_lines = self._new_log_lines(self._log_lines, latest)
                if new_lines is None:
                    self._refresh_logs(limit=self._visible_log_limit)
                    continue
                if not new_lines:
                    continue
                self._log_lines.extend(new_lines)
                if len(self._log_lines) > _LOG_LINE_LIMIT:
                    overflow = len(self._log_lines) - _LOG_LINE_LIMIT
                    del self._log_lines[:overflow]
                    del self.log_list.controls[:overflow]
                self.log_list.controls.extend(
                    self._log_text(line) for line in new_lines
                )
                self.log_meta_text.value = (
                    f"显示最近 {len(self._log_lines)} 行 · "
                    f"内存缓冲 {get_buffered_log_count()} 条"
                )
                self.page.update()
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                if "destroyed session" in str(ex).lower():
                    break
                logger.warning(f"增量刷新日志失败: {ex}")

    def _cancel_log_tail(self):
        self._view_active = False
        if self._log_tail_task and not self._log_tail_task.done():
            self._log_tail_task.cancel()
        self._log_tail_task = None

    def _on_log_level_change(self, e):
        """切换日志级别：立即生效并持久化"""
        try:
            selected = next(iter(self.level_selector.selected), "INFO")
        except Exception:
            selected = "INFO"
        if selected not in ("INFO", "DEBUG"):
            return
        set_log_level(selected, self.app_context["config_manager"])
        self.show_message(f"日志级别已切换为 {selected}", "success")
        self._refresh_logs()

    async def _copy_logs(self, e):
        """复制当前显示的日志到系统剪贴板"""
        if not self._log_lines:
            self.show_message("暂无日志可复制", "warning")
            return
        text = "\n".join(self._log_lines)
        try:
            # Clipboard 是 Service，会在构造时自动注册；放入 overlay 会被
            # Flutter 当作可视控件构建并报 "Unknown control: clipboard"。
            clipboard = ft.Clipboard()
            await clipboard.set(text)
            self.show_message(f"已复制 {len(self._log_lines)} 行日志", "success")
        except Exception as ex:
            logger.error(f"复制日志失败: {ex}")
            self.show_message(f"复制失败: {ex}", "error")

    async def _share_logs(self, e):
        """通过系统分享面板分享日志文本（iOS 可 AirDrop/发送给自己）"""
        if not self._log_lines:
            self.show_message("暂无日志可分享", "warning")
            return
        try:
            share = ft.Share()
            await share.share_text(
                "\n".join(self._log_lines),
                title="分享应用日志",
                subject="NextCloud Music Player 日志",
            )
        except Exception as ex:
            logger.error(f"分享日志失败: {ex}")
            self.show_message(f"分享失败: {ex}", "error")

    def _clear_logs(self, e):
        """清空内存缓冲并截断日志文件"""
        clear_buffer()
        truncated = False
        if self._log_file is None:
            self._log_file = self._log_file_path()
        if self._log_file is not None and self._log_file.exists():
            try:
                self._log_file.write_text("", encoding="utf-8")
                truncated = True
            except OSError as ex:
                logger.warning(f"清空日志文件失败: {ex}")
        logger.info("应用日志已清空")
        self._refresh_logs()
        self.show_message("日志已清空" if truncated else "内存日志已清空", "info")

    def show_message(self, message: str, message_type: str = "info"):
        """在页面顶部显示消息。"""
        show_snack_bar(self.page, message, message_type)

    def on_view_activated(self):
        """视图激活后从当前日志尾部开始增量跟随。"""
        self._view_active = True
        if not self._log_tail_task or self._log_tail_task.done():
            self._log_tail_task = asyncio.create_task(self._tail_logs())

    def on_view_deactivated(self):
        """离开设置页后停止日志轮询。"""
        self._cancel_log_tail()
