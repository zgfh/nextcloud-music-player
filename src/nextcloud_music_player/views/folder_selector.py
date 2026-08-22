"""
文件夹选择器 - Flet 版本，使用 AlertDialog
"""

import flet as ft
import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class FolderSelector:
    """NextCloud 文件夹浏览器对话框"""

    def __init__(self, page: ft.Page, nextcloud_client, initial_path: str = "/"):
        self.page = page
        self.nextcloud_client = nextcloud_client
        self.current_path = initial_path or "/"
        self.on_path_selected = None
        self._loading = False

    def show_dialog(self, callback):
        """显示文件夹选择对话框"""
        self.on_path_selected = callback

        self.path_display = ft.Text(
            self.current_path or "/",
            size=13,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.BLUE_700,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        self.folder_list = ft.ListView(
            expand=True,
            spacing=2,
            padding=8,
        )

        self.loading_text = ft.Text("加载中...", size=12, color=ft.Colors.GREY_600, visible=False)

        self.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("选择同步文件夹", size=16, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    ft.Row([self.path_display], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([
                        ft.IconButton(ft.Icons.ARROW_UPWARD, tooltip="上级目录", on_click=self._go_back),
                        ft.IconButton(ft.Icons.HOME, tooltip="根目录", on_click=self._go_root),
                        ft.IconButton(ft.Icons.REFRESH, tooltip="刷新", on_click=self._refresh),
                    ], spacing=4),
                    self.loading_text,
                    ft.Container(content=self.folder_list, height=350),
                ], spacing=8, tight=True),
                width=400,
            ),
            actions=[
                ft.TextButton("取消", on_click=self._cancel),
                ft.ElevatedButton(
                    "选择此文件夹",
                    icon=ft.Icons.CHECK,
                    on_click=self._select_current,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_600, color=ft.Colors.WHITE),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

        asyncio.create_task(self._load_folders())

    async def _load_folders(self):
        """加载当前路径的文件夹列表"""
        self._loading = True
        self.loading_text.visible = True
        self.page.update()

        try:
            folders = await self.nextcloud_client.list_directories(self.current_path)
            self.folder_list.controls.clear()

            if not folders:
                self.folder_list.controls.append(
                    ft.Container(
                        content=ft.Text("没有子文件夹", size=12, color=ft.Colors.GREY_500),
                        padding=16,
                        alignment=ft.Alignment(0, 0),
                    )
                )
            else:
                for folder in folders:
                    folder_name = folder.get('name', folder.get('path', ''))
                    icon = ft.Icons.FOLDER

                    self.folder_list.controls.append(
                        ft.ListTile(
                            leading=ft.Icon(icon, color=ft.Colors.AMBER_700),
                            title=ft.Text(folder_name, size=13),
                            on_click=lambda e, name=folder_name: self._enter_folder(name),
                        )
                    )
        except Exception as e:
            logger.error(f"加载文件夹失败: {e}")
            self.folder_list.controls.clear()
            self.folder_list.controls.append(
                ft.Text(f"加载失败: {e}", size=12, color=ft.Colors.RED_400)
            )
        finally:
            self._loading = False
            self.loading_text.visible = False
            self.page.update()

    def _enter_folder(self, folder_name):
        """进入子文件夹"""
        if self.current_path == "/" or self.current_path == "":
            self.current_path = f"/{folder_name}"
        else:
            self.current_path = f"{self.current_path.rstrip('/')}/{folder_name}"
        self.path_display.value = self.current_path
        asyncio.create_task(self._load_folders())

    def _go_back(self, e):
        """返回上级目录"""
        if self.current_path and self.current_path != "/":
            parent = str(Path(self.current_path).parent)
            self.current_path = parent if parent != "." else "/"
            self.path_display.value = self.current_path
            asyncio.create_task(self._load_folders())

    def _go_root(self, e):
        """返回根目录"""
        self.current_path = "/"
        self.path_display.value = self.current_path
        asyncio.create_task(self._load_folders())

    def _refresh(self, e):
        """刷新当前目录"""
        asyncio.create_task(self._load_folders())

    def _select_current(self, e):
        """选择当前文件夹"""
        self.dialog.open = False
        self.page.update()
        if self.on_path_selected:
            self.on_path_selected(self.current_path)

    def _cancel(self, e):
        """取消选择"""
        self.dialog.open = False
        self.page.update()
