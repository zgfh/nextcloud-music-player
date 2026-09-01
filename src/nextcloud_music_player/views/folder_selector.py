"""
文件夹选择器 - Flet 版本，使用 AlertDialog
"""

import asyncio
import logging

import flet as ft

from ..utils.theme import Color, Radius

logger = logging.getLogger(__name__)


class FolderSelector:
    """远程文件夹浏览器对话框（Nextcloud/SMB/Google Drive 通用）"""

    def __init__(
        self,
        page: ft.Page,
        nextcloud_client,
        initial_path: str = "/",
        initial_display_path: str = "",
    ):
        self.page = page
        self.nextcloud_client = nextcloud_client
        self.current_path = initial_path or "/"
        self.initial_display_path = initial_display_path
        self.selected_display_path = initial_display_path or self.current_path or "/"
        # 面包屑栈 [(显示名, 路径)]：上级导航与路径展示均基于此。
        # Google Drive 按文件夹 ID 导航，无法用字符串截断求上级目录；
        # Nextcloud/SMB 的根路径 '/' 也会被 Drive 客户端归一化为根目录。
        self._crumbs: list = []
        self.on_path_selected = None
        self._loading = False

    def show_dialog(self, callback):
        """显示文件夹选择对话框"""
        self.on_path_selected = callback

        self.path_display = ft.Text(
            self._display_path(),
            size=13,
            weight=ft.FontWeight.BOLD,
            color=Color.PRIMARY,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        self.folder_list = ft.ListView(
            expand=True,
            spacing=2,
            padding=8,
        )

        self.loading_text = ft.Text(
            "加载中...", size=12, color=Color.TEXT_MUTED, visible=False
        )

        self.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("选择同步文件夹", size=16, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [self.path_display],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Row(
                            [
                                ft.IconButton(
                                    ft.Icons.ARROW_UPWARD,
                                    tooltip="上级目录",
                                    on_click=self._go_back,
                                ),
                                ft.IconButton(
                                    ft.Icons.HOME,
                                    tooltip="根目录",
                                    on_click=self._go_root,
                                ),
                                ft.IconButton(
                                    ft.Icons.REFRESH,
                                    tooltip="刷新",
                                    on_click=self._refresh,
                                ),
                            ],
                            spacing=4,
                        ),
                        self.loading_text,
                        ft.Container(content=self.folder_list, height=350),
                    ],
                    spacing=8,
                    tight=True,
                ),
                width=400,
            ),
            actions=[
                ft.TextButton(
                    "取消",
                    on_click=self._cancel,
                    style=ft.ButtonStyle(color=Color.TEXT_SECONDARY),
                ),
                ft.FilledButton(
                    "选择此文件夹",
                    icon=ft.Icons.CHECK,
                    on_click=self._select_current,
                    style=ft.ButtonStyle(
                        bgcolor=Color.PRIMARY,
                        color=Color.PRIMARY_TEXT,
                        icon_color=Color.PRIMARY_TEXT,
                        shape=ft.RoundedRectangleBorder(radius=Radius.CIRCLE),
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # Flet 0.86：page.open()/page.close() 已移除，改用 show_dialog()/pop_dialog()
        self.page.show_dialog(self.dialog)

        asyncio.create_task(self._load_folders())

    async def _load_folders(self):
        """加载当前路径的文件夹列表（起始目录不存在时自动回退到根目录）"""
        self._loading = True
        self.loading_text.visible = True
        self.page.update()

        try:
            folders = await self.nextcloud_client.list_directories(self.current_path)
            self.folder_list.controls.clear()

            if not folders:
                self.folder_list.controls.append(
                    ft.Container(
                        content=ft.Text(
                            "没有子文件夹", size=12, color=Color.TEXT_MUTED
                        ),
                        padding=16,
                        alignment=ft.Alignment(0, 0),
                    )
                )
            else:
                for folder in folders:
                    folder_name = folder.get("name", folder.get("path", ""))
                    # 优先使用条目自带的完整路径（Google Drive 为文件夹 ID，
                    # Nextcloud/SMB 为共享/WebDAV 内完整路径）；缺失时由
                    # _enter_folder 按名称拼接
                    icon = ft.Icons.FOLDER

                    self.folder_list.controls.append(
                        ft.ListTile(
                            leading=ft.Icon(icon, color=Color.ACCENT),
                            title=ft.Text(
                                folder_name, size=13, color=Color.TEXT_PRIMARY
                            ),
                            on_click=lambda e, name=folder_name, path=folder.get(
                                "path"
                            ): self._enter_folder(name, path),
                        )
                    )
        except Exception as e:
            logger.error(f"加载文件夹失败: {e}")
            # 起始/当前目录不存在（404 等）时回退到根目录重试，仅在根目录仍失败时才报错
            if self.current_path not in ("", "/"):
                logger.info(f"目录不可访问，回退到根目录: {self.current_path}")
                self.current_path = "/"
                self._crumbs.clear()
                self.path_display.value = self._display_path()
                return await self._load_folders()
            self.folder_list.controls.clear()
            self.folder_list.controls.append(
                ft.Text(f"加载失败: {e}", size=12, color=Color.DANGER_TEXT)
            )
        finally:
            self._loading = False
            self.loading_text.visible = False
            self.page.update()

    def _display_path(self) -> str:
        """展示用路径：面包屑名称拼接；栈空时展示原始路径（根为 '/'）"""
        if not self._crumbs:
            return self.initial_display_path or self.current_path or "/"
        return "/" + "/".join(name for name, _ in self._crumbs)

    def _enter_folder(self, folder_name: str, folder_path: str = None):
        """进入子文件夹；优先使用条目自带路径，否则按名称拼接（Nextcloud/SMB）"""
        if folder_path:
            new_path = folder_path
        elif self.current_path in ("", "/"):
            new_path = f"/{folder_name}"
        else:
            new_path = f"{self.current_path.rstrip('/')}/{folder_name}"
        self.current_path = new_path
        self.initial_display_path = ""
        self._crumbs.append((folder_name, new_path))
        self.path_display.value = self._display_path()
        asyncio.create_task(self._load_folders())

    def _go_back(self, e):
        """返回上级目录（面包屑栈出栈；栈空时回根目录）"""
        if not self._crumbs:
            return
        self._crumbs.pop()
        if self._crumbs:
            self.current_path = self._crumbs[-1][1]
        else:
            self.current_path = "/"
        self.initial_display_path = ""
        self.path_display.value = self._display_path()
        asyncio.create_task(self._load_folders())

    def _go_root(self, e):
        """返回根目录"""
        self.current_path = "/"
        self.initial_display_path = ""
        self._crumbs.clear()
        self.path_display.value = self._display_path()
        asyncio.create_task(self._load_folders())

    def _refresh(self, e):
        """刷新当前目录"""
        asyncio.create_task(self._load_folders())

    def _select_current(self, e):
        """选择当前文件夹"""
        self.selected_display_path = self._display_path()
        self.page.pop_dialog()
        if self.on_path_selected:
            self.on_path_selected(self.current_path)

    def _cancel(self, e):
        """取消选择"""
        self.page.pop_dialog()
