"""
连接配置视图 - Flet 版本
"""

import flet as ft
import asyncio
import logging
import threading

from ..utils.theme import Color, Space, FontSize, get_message_style

logger = logging.getLogger(__name__)


class ConnectionView:
    """NextCloud 连接配置视图"""

    def __init__(self, page: ft.Page, app_context: dict, view_manager):
        self.page = page
        self.app_context = app_context
        self.view_manager = view_manager
        self.password_visible = False
        self.is_connected = False
        self._built = False
        self._save_timer = None

    def build(self):
        """构建并返回视图内容"""
        if self._built and hasattr(self, '_container'):
            return self._container

        config_manager = self.app_context['config_manager']
        config = config_manager.get("connection", {})

        # 状态显示
        self.status_text = ft.Text(
            "状态: 未连接",
            size=FontSize.STATUS,
            weight=ft.FontWeight.BOLD,
            color=Color.TEXT_SECONDARY,
        )
        self.status_container = ft.Container(
            content=self.status_text,
            bgcolor=Color.BG_SUBTLE,
            padding=Space.SM,
            border_radius=8,
            width=float("inf"),
        )

        # 表单字段
        self.url_input = ft.TextField(
            label="服务器地址",
            value=config.get("server_url", "http://cloud.home.daozzg.com"),
            hint_text="https://your-nextcloud.com",
            prefix_icon=ft.Icons.CLOUD_OUTLINED,
            border_radius=8,
        )

        self.username_input = ft.TextField(
            label="用户名",
            value=config.get("username", "guest"),
            hint_text="输入用户名",
            prefix_icon=ft.Icons.PERSON_OUTLINED,
            border_radius=8,
        )

        self.password_input = ft.TextField(
            label="密码",
            value=config.get("password", "") if config.get("remember_credentials", True) else "",
            hint_text="输入密码",
            password=True,
            can_reveal_password=True,
            prefix_icon=ft.Icons.LOCK_OUTLINED,
            border_radius=8,
        )

        self.sync_folder_input = ft.TextField(
            label="同步文件夹路径",
            value=config.get("default_sync_folder", "/mp3/音乐/当月抖音热播流行歌曲484首/"),
            hint_text="/Music 或留空表示根目录",
            prefix_icon=ft.Icons.FOLDER_OUTLINED,
            border_radius=8,
            on_change=self._on_sync_folder_changed,
        )

        self.browse_button = ft.ElevatedButton(
            "浏览",
            icon=ft.Icons.FOLDER_OPEN,
            on_click=self._browse_folder,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
        )

        self.remember_password_switch = ft.Switch(
            label="记住密码",
            value=config.get("remember_credentials", True),
            label_position=ft.LabelPosition.RIGHT,
        )

        self.auto_connect_switch = ft.Switch(
            label="启动时自动连接",
            value=config.get("auto_connect", False),
            label_position=ft.LabelPosition.RIGHT,
        )

        # 按钮
        self.connect_button = ft.ElevatedButton(
            "连接",
            icon=ft.Icons.LINK,
            on_click=self._connect_to_nextcloud,
            style=ft.ButtonStyle(
                bgcolor=Color.PRIMARY,
                color=Color.PRIMARY_TEXT,
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
        )

        self.disconnect_button = ft.ElevatedButton(
            "断开",
            icon=ft.Icons.LINK_OFF,
            on_click=self._disconnect_from_nextcloud,
            disabled=True,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
        )

        self.test_button = ft.OutlinedButton(
            "测试",
            icon=ft.Icons.WIFI_FIND,
            on_click=self._test_connection,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
        )

        # 消息区
        self.message_container = ft.Container(visible=False)

        # 组装
        self._container = ft.Column(
            controls=[
                ft.Text("NextCloud 连接配置", size=FontSize.TITLE + 4, weight=ft.FontWeight.BOLD),
                self.status_container,
                self.url_input,
                self.username_input,
                self.password_input,
                ft.Row([self.sync_folder_input, self.browse_button], spacing=Space.XS),
                self.remember_password_switch,
                self.auto_connect_switch,
                ft.Row([self.connect_button, self.disconnect_button, self.test_button], spacing=Space.SM),
                self.message_container,
            ],
            scroll=ft.ScrollMode.AUTO,
            padding=Space.LG,
            spacing=Space.SM,
            expand=True,
        )

        self._built = True

        # 自动连接
        if config.get("auto_connect", False):
            asyncio.create_task(self._auto_connect())

        return self._container

    def _on_sync_folder_changed(self, e):
        """同步文件夹变化时自动保存（带防抖）"""
        if self._save_timer:
            self._save_timer.cancel()
        def delayed_save():
            try:
                new_value = e.control.value.strip()
                self.app_context['config_manager'].set("connection.default_sync_folder", new_value)
                self.app_context['config_manager'].save_config()
                logger.info(f"同步目录已自动保存: {new_value}")
            except Exception as ex:
                logger.error(f"自动保存失败: {ex}")
        self._save_timer = threading.Timer(2.0, delayed_save)
        self._save_timer.start()

    async def _auto_connect(self):
        """自动连接"""
        await asyncio.sleep(1)
        await self._connect_to_nextcloud(None)

    async def _connect_to_nextcloud(self, e):
        """连接到 NextCloud"""
        server_url = self.url_input.value.strip()
        username = self.username_input.value.strip()
        password = self.password_input.value or ""
        sync_folder = self.sync_folder_input.value.strip()

        if not server_url or not username or not password:
            self.show_message("请填写完整的连接信息", "error")
            return

        self.show_message("正在连接...", "info")
        self.connect_button.disabled = True
        self.page.update()

        try:
            from ..nextcloud_client import NextCloudClient
            client = NextCloudClient(server_url, username, password)
            self.app_context['nextcloud_client'] = client

            if self.app_context.get('music_service'):
                self.app_context['music_service'].update_nextcloud_client(client)
            if self.app_context.get('lyrics_service'):
                self.app_context['lyrics_service'].update_clients(nextcloud_client=client)

            success = await client.test_connection()

            if success:
                self.is_connected = True
                self._update_connection_status(True)
                self.show_message("连接成功！", "success")
                self._save_config()
                self.view_manager.switch_to_view("file_list")
            else:
                self.show_message("连接失败，请检查服务器地址和凭据", "error")
                self._update_connection_status(False)
        except Exception as ex:
            logger.error(f"连接失败: {ex}")
            self.show_message(f"连接错误: {str(ex)}", "error")
            self._update_connection_status(False)
        finally:
            self.connect_button.disabled = False
            self.page.update()

    async def _disconnect_from_nextcloud(self, e):
        """断开连接"""
        self.app_context['nextcloud_client'] = None
        if self.app_context.get('music_service'):
            self.app_context['music_service'].update_nextcloud_client(None)
        if self.app_context.get('lyrics_service'):
            self.app_context['lyrics_service'].update_clients(nextcloud_client=None)
        self.is_connected = False
        self._update_connection_status(False)
        self.show_message("已断开连接", "info")

    async def _test_connection(self, e):
        """测试连接"""
        server_url = self.url_input.value.strip()
        username = self.username_input.value.strip()
        password = self.password_input.value or ""

        if not server_url or not username or not password:
            self.show_message("请填写完整的连接信息", "error")
            return

        self.show_message("正在测试连接...", "info")
        self.test_button.disabled = True
        self.page.update()

        try:
            from ..nextcloud_client import NextCloudClient
            temp_client = NextCloudClient(server_url, username, password)
            success = await temp_client.test_connection()
            if success:
                self.show_message("连接测试成功！", "success")
            else:
                self.show_message("连接测试失败", "error")
        except Exception as ex:
            self.show_message(f"测试错误: {str(ex)}", "error")
        finally:
            self.test_button.disabled = False
            self.page.update()

    def _save_config(self):
        """保存连接配置"""
        try:
            cm = self.app_context['config_manager']
            cm.set("connection.server_url", self.url_input.value.strip())
            cm.set("connection.username", self.username_input.value.strip())
            cm.set("connection.default_sync_folder", self.sync_folder_input.value.strip())
            cm.set("connection.auto_connect", self.auto_connect_switch.value)
            cm.set("connection.remember_credentials", self.remember_password_switch.value)
            if self.remember_password_switch.value:
                cm.set("connection.password", self.password_input.value or "")
            else:
                cm.set("connection.password", "")
            cm.save_config()
            logger.info("连接配置已保存")
        except Exception as ex:
            logger.error(f"保存配置失败: {ex}")

    def _update_connection_status(self, connected: bool):
        """更新连接状态显示"""
        if connected:
            self.status_text.value = "状态: 已连接"
            self.status_text.color = Color.SUCCESS
            self.status_container.bgcolor = Color.SUCCESS_LIGHT
            self.connect_button.disabled = True
            self.disconnect_button.disabled = False
        else:
            self.status_text.value = "状态: 未连接"
            self.status_text.color = Color.DANGER
            self.status_container.bgcolor = Color.DANGER_LIGHT
            self.connect_button.disabled = False
            self.disconnect_button.disabled = True
        self.page.update()

    def show_message(self, message: str, message_type: str = "info"):
        """显示消息"""
        bg_color, text_color, icon = get_message_style(message_type)
        self.message_container.content = ft.Row([
            ft.Icon(icon if isinstance(icon, str) else ft.Icons.INFO_OUTLINE, color=text_color, size=18),
            ft.Text(message, color=text_color, size=FontSize.BODY),
        ], spacing=Space.XS)
        self.message_container.bgcolor = bg_color
        self.message_container.padding = Space.SM
        self.message_container.border_radius = 8
        self.message_container.visible = True
        self.page.update()
        logger.info(f"[{message_type.upper()}] {message}")

    def on_view_activated(self):
        """视图激活时检查连接状态"""
        if self.app_context.get('nextcloud_client'):
            self._update_connection_status(True)
        else:
            self._update_connection_status(False)

    def _browse_folder(self, e):
        """浏览文件夹"""
        if not self.app_context.get('nextcloud_client'):
            self.show_message("请先连接到 NextCloud 服务器", "error")
            return

        from .folder_selector import FolderSelector

        current_folder = self.sync_folder_input.value.strip()
        selector = FolderSelector(
            self.page,
            self.app_context['nextcloud_client'],
            current_folder,
        )

        def on_selected(path):
            self.sync_folder_input.value = path
            self.page.update()
            self.show_message(f"已选择文件夹: {path or '/'}", "success")
            self.app_context['config_manager'].set("connection.default_sync_folder", path)
            self.app_context['config_manager'].save_config()

        selector.show_dialog(on_selected)
