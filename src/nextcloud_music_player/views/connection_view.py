"""
连接配置视图 - Flet 版本
"""

import asyncio
import logging
import threading
import time

import flet as ft

from ..utils.theme import (
    Color,
    FontSize,
    Gradient,
    Radius,
    Space,
    get_message_style,
    glow,
    tint,
)

logger = logging.getLogger(__name__)


def _dark_input(**kwargs) -> ft.TextField:
    """统一暗色科技风输入框样式"""
    base = dict(
        bgcolor=Color.BG_SURFACE_ALT,
        border_color=Color.BORDER,
        focused_border_color=Color.PRIMARY,
        border_width=1,
        border_radius=Radius.MD,
        color=Color.TEXT_PRIMARY,
        hint_style=ft.TextStyle(color=Color.TEXT_DISABLED),
        label_style=ft.TextStyle(color=Color.TEXT_SECONDARY),
        cursor_color=Color.PRIMARY,
        content_padding=ft.Padding(left=14, right=14, top=12, bottom=12),
    )
    base.update(kwargs)
    return ft.TextField(**base)


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
        self._auto_connect_started = False  # 自动连接每会话只触发一次

    def rebuild(self):
        """重建视图（Flet 0.86 控件脱离页面后被冻结且不可复用）"""
        self._built = False
        return self.build()

    def build(self):
        """构建并返回视图内容"""
        if self._built and hasattr(self, "_container"):
            return self._container

        try:
            return self._do_build()
        except Exception as e:
            logger.error(f"ConnectionView build 失败: {e}", exc_info=True)
            return ft.Container(
                content=ft.Column(
                    [
                        ft.Text(f"构建错误: {e}", color=Color.DANGER_TEXT),
                    ]
                ),
                padding=20,
                bgcolor=Color.BG_APP,
            )

    def _do_build(self):
        config_manager = self.app_context["config_manager"]
        config = config_manager.get("connection", {})
        smb_config = config.get("smb", {})
        source_type = config.get("source_type", "nextcloud")

        # === Hero 头部：渐变徽标 + 标题 ===
        logo = ft.Container(
            content=ft.Icon(ft.Icons.CLOUD_DONE_OUTLINED, color=Color.PRIMARY, size=26),
            width=52,
            height=52,
            border_radius=Radius.LG,
            gradient=Gradient.surface(),
            border=ft.Border.all(1, tint(Color.PRIMARY, "59")),
            shadow=glow(Color.PRIMARY, radius=16, alpha="33"),
        )
        self.title_text = ft.Text(
            "SMB" if source_type == "smb" else "NEXTCLOUD",
            size=FontSize.TITLE + 6,
            weight=ft.FontWeight.BOLD,
            color=Color.TEXT_PRIMARY,
            style=ft.TextStyle(letter_spacing=4),
        )
        subtitle_text = ft.Text(
            "MUSIC · 服务器连接",
            size=FontSize.CAPTION,
            color=Color.TEXT_MUTED,
            style=ft.TextStyle(letter_spacing=2),
        )
        hero = ft.Row(
            [
                logo,
                ft.Column(
                    [self.title_text, subtitle_text],
                    spacing=2,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ],
            spacing=Space.MD,
        )

        # === 来源类型切换：Nextcloud / SMB ===
        # 注意：Flet 0.86 的 selected 类型是 list[str]，
        # 传 set 会在 iOS 首次序列化时崩溃（msgpack 无法打包 set）
        self.source_selector = ft.SegmentedButton(
            key="source_selector",
            selected=[source_type],
            segments=[
                ft.Segment(
                    value="nextcloud", label="Nextcloud", icon=ft.Icons.CLOUD_OUTLINED
                ),
                ft.Segment(value="smb", label="SMB 共享", icon=ft.Icons.LAN_OUTLINED),
            ],
            allow_multiple_selection=False,
            allow_empty_selection=False,
            on_change=self._on_source_type_changed,
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

        # === 状态胶囊 ===
        self.status_dot = ft.Container(
            width=8,
            height=8,
            border_radius=4,
            bgcolor=Color.DANGER,
            shadow=glow(Color.DANGER, radius=8, alpha="80"),
        )
        self.status_text = ft.Text(
            "未连接",
            size=FontSize.STATUS,
            weight=ft.FontWeight.BOLD,
            color=Color.DANGER_TEXT,
            style=ft.TextStyle(letter_spacing=1),
        )
        self.status_container = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.SATELLITE_ALT, size=16, color=Color.TEXT_MUTED),
                    self.status_dot,
                    self.status_text,
                ],
                spacing=Space.SM,
            ),
            bgcolor=tint(Color.DANGER, "1F"),
            border=ft.Border.all(1, tint(Color.DANGER, "40")),
            padding=ft.Padding(left=14, right=14, top=10, bottom=10),
            border_radius=Radius.CIRCLE,
            width=float("inf"),
        )

        # === 表单字段（暗色填充风格） ===
        self.url_input = _dark_input(
            label="服务器地址",
            value=config.get("server_url", "http://cloud.home.daozzg.com"),
            hint_text="https://your-nextcloud.com",
            prefix_icon=ft.Icons.LANGUAGE,
        )

        self.username_input = _dark_input(
            label="用户名",
            value=config.get("username", "guest"),
            hint_text="输入用户名",
            prefix_icon=ft.Icons.PERSON_OUTLINE,
        )

        self.password_input = _dark_input(
            label="密码",
            value=(
                config.get("password", "")
                if config.get("remember_credentials", True)
                else ""
            ),
            hint_text="输入密码",
            password=True,
            can_reveal_password=True,
            prefix_icon=ft.Icons.KEY,
        )

        self.sync_folder_input = _dark_input(
            label="同步文件夹路径",
            value=config.get(
                "default_sync_folder", "/mp3/音乐/当月抖音热播流行歌曲484首/"
            ),
            hint_text="/Music 或留空表示根目录",
            prefix_icon=ft.Icons.FOLDER_OUTLINED,
            on_change=self._on_sync_folder_changed,
            expand=1,
        )

        self.browse_button = ft.OutlinedButton(
            "浏览",
            icon=ft.Icons.FOLDER_OPEN,
            on_click=self._browse_folder,
            style=ft.ButtonStyle(
                bgcolor=Color.BG_SURFACE,
                color=Color.TEXT_SECONDARY,
                icon_color=Color.PRIMARY,
                side=ft.BorderSide(1, Color.BORDER),
                shape=ft.RoundedRectangleBorder(radius=Radius.MD),
            ),
        )

        # === SMB 来源表单字段 ===
        self.smb_host_input = _dark_input(
            key="smb_host",
            label="主机地址 / IP",
            value=smb_config.get("host", ""),
            hint_text="如 192.168.1.100 或 nas.local",
            prefix_icon=ft.Icons.LAN_OUTLINED,
            expand=True,
        )

        # 固定窄宽：端口仅数字，Row 内不设宽度会在窄屏上把输入框挤出屏幕
        self.smb_port_input = _dark_input(
            label="端口",
            value=str(smb_config.get("port", 445)),
            hint_text="445",
            prefix_icon=ft.Icons.NUMBERS,
            keyboard_type=ft.KeyboardType.NUMBER,
            width=110,
        )

        self.smb_share_input = _dark_input(
            key="smb_share",
            label="共享名称",
            value=smb_config.get("share", ""),
            hint_text="如 music",
            prefix_icon=ft.Icons.FOLDER_SHARED_OUTLINED,
        )

        self.smb_username_input = _dark_input(
            label="用户名",
            value=(
                smb_config.get("username", "")
                if config.get("remember_credentials", True)
                else ""
            ),
            hint_text="guest 访问可留空",
            prefix_icon=ft.Icons.PERSON_OUTLINE,
            expand=1,
        )

        self.smb_domain_input = _dark_input(
            label="域（可选）",
            value=smb_config.get("domain", ""),
            hint_text="默认 WORKGROUP",
            prefix_icon=ft.Icons.PUBLIC,
            expand=1,
        )

        self.smb_password_input = _dark_input(
            label="密码",
            value=(
                smb_config.get("password", "")
                if config.get("remember_credentials", True)
                else ""
            ),
            hint_text="guest 访问可留空",
            password=True,
            can_reveal_password=True,
            prefix_icon=ft.Icons.KEY,
        )

        self.smb_sync_folder_input = _dark_input(
            label="同步文件夹路径（共享内）",
            value=smb_config.get("default_sync_folder", "/"),
            hint_text="/ 表示共享根目录",
            prefix_icon=ft.Icons.FOLDER_OUTLINED,
            on_change=self._on_sync_folder_changed,
            expand=1,
        )

        self.smb_browse_button = ft.OutlinedButton(
            "浏览",
            icon=ft.Icons.FOLDER_OPEN,
            on_click=self._browse_folder,
            style=ft.ButtonStyle(
                bgcolor=Color.BG_SURFACE,
                color=Color.TEXT_SECONDARY,
                icon_color=Color.PRIMARY,
                side=ft.BorderSide(1, Color.BORDER),
                shape=ft.RoundedRectangleBorder(radius=Radius.MD),
            ),
        )

        self.remember_password_switch = ft.Switch(
            label="记住密码",
            value=config.get("remember_credentials", True),
            label_position=ft.LabelPosition.RIGHT,
            active_color=Color.PRIMARY,
            label_text_style=ft.TextStyle(color=Color.TEXT_SECONDARY),
        )

        self.auto_connect_switch = ft.Switch(
            label="启动时自动连接",
            value=config.get("auto_connect", False),
            label_position=ft.LabelPosition.RIGHT,
            active_color=Color.PRIMARY,
            label_text_style=ft.TextStyle(color=Color.TEXT_SECONDARY),
        )

        # === 主按钮：霓虹发光 ===
        self.connect_button = ft.FilledButton(
            "建立连接",
            icon=ft.Icons.BOLT,
            on_click=self._connect_to_server,
            expand=2,
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
                elevation={ft.ControlState.DEFAULT: 6, ft.ControlState.PRESSED: 2},
                shadow_color=tint(Color.PRIMARY, "66"),
                shape=ft.RoundedRectangleBorder(radius=Radius.CIRCLE),
            ),
        )

        self.disconnect_button = ft.OutlinedButton(
            "断开",
            icon=ft.Icons.LINK_OFF,
            on_click=self._disconnect_from_nextcloud,
            disabled=True,
            expand=1,
            style=ft.ButtonStyle(
                color={
                    ft.ControlState.DISABLED: Color.TEXT_DISABLED,
                    ft.ControlState.DEFAULT: Color.DANGER_TEXT,
                },
                icon_color={
                    ft.ControlState.DISABLED: Color.TEXT_DISABLED,
                    ft.ControlState.DEFAULT: Color.DANGER,
                },
                side=ft.BorderSide(1, tint(Color.DANGER, "59")),
                shape=ft.RoundedRectangleBorder(radius=Radius.CIRCLE),
            ),
        )

        self.test_button = ft.OutlinedButton(
            "测试",
            icon=ft.Icons.NETWORK_CHECK,
            on_click=self._test_connection,
            expand=1,
            style=ft.ButtonStyle(
                color=Color.TEXT_SECONDARY,
                icon_color=Color.INFO,
                side=ft.BorderSide(1, Color.BORDER),
                shape=ft.RoundedRectangleBorder(radius=Radius.CIRCLE),
            ),
        )

        # 消息 Banner（置顶显示，替代原底部消息条）
        self.message_banner = ft.Banner(
            visible=False,
            leading=ft.Icon(ft.Icons.INFO_OUTLINE),
            content=ft.Text(""),
            actions=[ft.TextButton("知道了", on_click=self._dismiss_banner)],
            content_padding=Space.SM,
            bgcolor=Color.BG_SURFACE,
        )

        # === 组装：表单卡片（按来源类型显示其一） ===
        self.nextcloud_form_card = ft.Container(
            content=ft.Column(
                [
                    self.url_input,
                    self.username_input,
                    self.password_input,
                    ft.Row(
                        [self.sync_folder_input, self.browse_button], spacing=Space.XS
                    ),
                ],
                spacing=Space.SM,
            ),
            bgcolor=Color.BG_SURFACE,
            border=ft.Border.all(1, Color.BORDER),
            border_radius=Radius.LG,
            padding=Space.LG,
            visible=(source_type != "smb"),
        )

        self.smb_form_card = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [self.smb_host_input, self.smb_port_input], spacing=Space.XS
                    ),
                    self.smb_share_input,
                    ft.Row(
                        [self.smb_username_input, self.smb_domain_input],
                        spacing=Space.XS,
                    ),
                    self.smb_password_input,
                    ft.Row(
                        [self.smb_sync_folder_input, self.smb_browse_button],
                        spacing=Space.XS,
                    ),
                ],
                spacing=Space.SM,
            ),
            bgcolor=Color.BG_SURFACE,
            border=ft.Border.all(1, Color.BORDER),
            border_radius=Radius.LG,
            padding=Space.LG,
            visible=(source_type == "smb"),
        )

        self._container = ft.Container(
            content=ft.Column(
                controls=[
                    hero,
                    self.source_selector,
                    self.message_banner,
                    self.status_container,
                    self.nextcloud_form_card,
                    self.smb_form_card,
                    ft.Container(
                        content=ft.Column(
                            [
                                self.remember_password_switch,
                                self.auto_connect_switch,
                            ],
                            spacing=Space.XS,
                        ),
                        padding=ft.Padding(
                            left=Space.XS, top=Space.XS, bottom=Space.XS, right=Space.XS
                        ),
                    ),
                    ft.Row(
                        [
                            self.connect_button,
                            self.disconnect_button,
                            self.test_button,
                        ],
                        spacing=Space.SM,
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
                spacing=Space.MD,
                expand=True,
            ),
            padding=Space.LG,
            expand=True,
            bgcolor=Color.BG_APP,
        )

        self._built = True

        # 自动连接（每会话只触发一次，视图重建不重复连接）
        if config.get("auto_connect", False) and not self._auto_connect_started:
            self._auto_connect_started = True
            asyncio.create_task(self._auto_connect())

        return self._container

    def _on_sync_folder_changed(self, e):
        """同步文件夹变化时自动保存（带防抖，按来源写入对应配置键）"""
        if e.control is self.smb_sync_folder_input:
            config_key = "connection.smb.default_sync_folder"
        else:
            config_key = "connection.default_sync_folder"
        if self._save_timer:
            self._save_timer.cancel()

        def delayed_save():
            try:
                new_value = e.control.value.strip()
                self.app_context["config_manager"].set(config_key, new_value)
                self.app_context["config_manager"].save_config()
                logger.info(f"同步目录已自动保存: {new_value}")
            except Exception as ex:
                logger.error(f"自动保存失败: {ex}")

        self._save_timer = threading.Timer(2.0, delayed_save)
        self._save_timer.start()

    async def _auto_connect(self):
        """自动连接"""
        await asyncio.sleep(1)
        await self._connect_to_server(None)

    def _current_source_type(self) -> str:
        """当前选择的来源类型：nextcloud | smb"""
        try:
            selected = self.source_selector.selected
            return next(iter(selected)) if selected else "nextcloud"
        except Exception:
            return "nextcloud"

    def _on_source_type_changed(self, e):
        """切换来源类型：切换表单与标题，并立即持久化选择"""
        source_type = self._current_source_type()
        is_smb = source_type == "smb"
        self.nextcloud_form_card.visible = not is_smb
        self.smb_form_card.visible = is_smb
        self.title_text.value = "SMB" if is_smb else "NEXTCLOUD"
        try:
            self.app_context["config_manager"].set(
                "connection.source_type", source_type
            )
            self.app_context["config_manager"].save_config()
        except Exception as ex:
            logger.error(f"保存来源类型失败: {ex}")
        self.page.update()

    def _build_client_from_form(self):
        """按当前来源类型从表单构造客户端；表单不完整时抛出带提示的异常"""
        if self._current_source_type() == "smb":
            host = self.smb_host_input.value.strip()
            share = self.smb_share_input.value.strip()
            if not host or not share:
                raise ValueError("请填写 SMB 主机地址和共享名称")
            try:
                port = int(self.smb_port_input.value.strip() or 445)
            except ValueError:
                raise ValueError("SMB 端口必须是数字")
            from ..smb_client import SMBClient

            return SMBClient(
                host=host,
                username=self.smb_username_input.value.strip(),
                password=self.smb_password_input.value or "",
                port=port,
                domain=self.smb_domain_input.value.strip(),
                share=share,
            )

        server_url = self.url_input.value.strip()
        username = self.username_input.value.strip()
        password = self.password_input.value or ""
        if not server_url or not username or not password:
            raise ValueError("请填写完整的连接信息")
        from ..nextcloud_client import NextCloudClient

        return NextCloudClient(server_url, username, password)

    async def _connect_to_server(self, e):
        """连接到当前选择的音乐来源"""
        t_start = time.monotonic()

        try:
            client = self._build_client_from_form()
        except ValueError as ex:
            self.show_message(str(ex), "error")
            return

        self.show_message("正在连接...", "info")
        self._set_connecting_state(True)
        self.connect_button.disabled = True
        self.page.update()

        try:
            # app_context['nextcloud_client'] 槽位承载"当前来源客户端"
            # （NextCloudClient / SMBClient 共用同一事实接口）
            self.app_context["nextcloud_client"] = client

            if self.app_context.get("music_service"):
                self.app_context["music_service"].update_nextcloud_client(client)
            if self.app_context.get("lyrics_service"):
                self.app_context["lyrics_service"].update_clients(
                    nextcloud_client=client
                )

            success = await client.test_connection()

            if success:
                self.is_connected = True
                self._update_connection_status(True)
                self.show_message("连接成功！", "success")
                self._toast("连接成功", "success")
                logger.info(
                    f"✅ 连接成功，点击到完成总耗时 {time.monotonic() - t_start:.1f}s"
                )
                self._save_config()
                self.view_manager.switch_to_view("file_list")
            else:
                self.show_message("连接失败，请检查服务器地址和凭据", "error")
                self._toast("连接失败，请检查服务器地址和凭据", "error")
                self._update_connection_status(False)
                logger.info(f"❌ 连接失败，总耗时 {time.monotonic() - t_start:.1f}s")
        except Exception as ex:
            logger.error(f"连接失败 (总耗时 {time.monotonic() - t_start:.1f}s): {ex}")
            self.show_message(f"连接错误: {str(ex)}", "error")
            self._toast(f"连接错误: {str(ex)[:60]}", "error")
            self._update_connection_status(False)
        finally:
            self.connect_button.disabled = False
            self.page.update()

    async def _disconnect_from_nextcloud(self, e):
        """断开连接"""
        self.app_context["nextcloud_client"] = None
        if self.app_context.get("music_service"):
            self.app_context["music_service"].update_nextcloud_client(None)
        if self.app_context.get("lyrics_service"):
            self.app_context["lyrics_service"].update_clients(nextcloud_client=None)
        self.is_connected = False
        self._update_connection_status(False)
        self.show_message("已断开连接", "info")

    async def _test_connection(self, e):
        """测试连接"""
        try:
            temp_client = self._build_client_from_form()
        except ValueError as ex:
            self.show_message(str(ex), "error")
            return

        self.show_message("正在测试连接...", "info")
        self._set_connecting_state(True)
        self.test_button.disabled = True
        self.page.update()

        try:
            success = await temp_client.test_connection()
            if success:
                self.show_message("连接测试成功！", "success")
                self._toast("连接测试成功！", "success")
            else:
                self.show_message("连接测试失败", "error")
                self._toast("连接测试失败", "error")
        except Exception as ex:
            self.show_message(f"测试错误: {str(ex)}", "error")
            self._toast(f"测试错误: {str(ex)[:60]}", "error")
        finally:
            self.test_button.disabled = False
            self._update_connection_status(self.is_connected)
            self.page.update()

    def _save_config(self):
        """保存连接配置（含来源类型与 SMB 凭据）"""
        try:
            cm = self.app_context["config_manager"]
            source_type = self._current_source_type()
            remember = self.remember_password_switch.value

            cm.set("connection.source_type", source_type)

            # Nextcloud 字段始终保存（保留另一来源的表单内容）
            cm.set("connection.server_url", self.url_input.value.strip())
            cm.set("connection.username", self.username_input.value.strip())
            cm.set(
                "connection.default_sync_folder", self.sync_folder_input.value.strip()
            )
            cm.set("connection.auto_connect", self.auto_connect_switch.value)
            cm.set("connection.remember_credentials", remember)
            cm.set(
                "connection.password",
                self.password_input.value or "" if remember else "",
            )

            # SMB 字段
            cm.set("connection.smb.host", self.smb_host_input.value.strip())
            cm.set("connection.smb.share", self.smb_share_input.value.strip())
            cm.set(
                "connection.smb.default_sync_folder",
                self.smb_sync_folder_input.value.strip() or "/",
            )
            cm.set("connection.smb.username", self.smb_username_input.value.strip())
            cm.set("connection.smb.domain", self.smb_domain_input.value.strip())
            try:
                cm.set(
                    "connection.smb.port", int(self.smb_port_input.value.strip() or 445)
                )
            except ValueError:
                cm.set("connection.smb.port", 445)
            cm.set(
                "connection.smb.password",
                self.smb_password_input.value or "" if remember else "",
            )

            cm.save_config()
            logger.info("连接配置已保存")
        except Exception as ex:
            logger.error(f"保存配置失败: {ex}")

    def _update_connection_status(self, connected: bool):
        """更新连接状态显示（霓虹状态胶囊）"""
        if connected:
            self.status_text.value = "已连接 · ONLINE"
            self.status_text.color = Color.SUCCESS_TEXT
            self.status_dot.bgcolor = Color.SUCCESS
            self.status_dot.shadow = glow(Color.SUCCESS, radius=8, alpha="80")
            self.status_container.bgcolor = tint(Color.SUCCESS, "1F")
            self.status_container.border = ft.Border.all(1, tint(Color.SUCCESS, "40"))
            self.connect_button.disabled = True
            self.disconnect_button.disabled = False
        else:
            self.status_text.value = "未连接 · OFFLINE"
            self.status_text.color = Color.DANGER_TEXT
            self.status_dot.bgcolor = Color.DANGER
            self.status_dot.shadow = glow(Color.DANGER, radius=8, alpha="80")
            self.status_container.bgcolor = tint(Color.DANGER, "1F")
            self.status_container.border = ft.Border.all(1, tint(Color.DANGER, "40"))
            self.connect_button.disabled = False
            self.disconnect_button.disabled = True
        self.page.update()

    def _set_connecting_state(self, connecting: bool):
        """连接过程中在顶部状态条实时反馈（避免提示藏在屏幕底部看不见）"""
        if connecting:
            self.status_text.value = "连接中 · SYNCING"
            self.status_text.color = Color.INFO_TEXT
            self.status_dot.bgcolor = Color.INFO
            self.status_dot.shadow = glow(Color.INFO, radius=8, alpha="80")
            self.status_container.bgcolor = tint(Color.INFO, "1F")
            self.status_container.border = ft.Border.all(1, tint(Color.INFO, "40"))
        self.page.update()

    def _toast(self, message: str, message_type: str = "info"):
        """底部悬浮提示，无需滚动即可看到连接结果"""
        bg_color, text_color, _ = get_message_style(message_type)
        try:
            self.page.show_dialog(
                ft.SnackBar(
                    ft.Text(message, color=text_color),
                    bgcolor=bg_color,
                    duration=3000,
                )
            )
        except Exception as e:
            logger.debug(f"SnackBar 显示失败: {e}")

    def _dismiss_banner(self, e=None):
        """关闭消息 Banner"""
        self.message_banner.visible = False
        self.page.update()

    def show_message(self, message: str, message_type: str = "info"):
        """以顶部 Banner 显示消息（限高 3 行，超长报错不再把页面撑长）"""
        bg_color, text_color, icon = get_message_style(message_type)
        self.message_banner.leading = ft.Icon(
            ft.Icons.INFO_OUTLINE, color=text_color, size=22
        )
        self.message_banner.content = ft.Text(
            message,
            color=text_color,
            size=FontSize.BODY,
            max_lines=3,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        self.message_banner.bgcolor = bg_color
        self.message_banner.visible = True
        self.page.update()
        logger.info(f"[{message_type.upper()}] {message}")

    def on_view_activated(self):
        """视图激活时检查连接状态"""
        if self.app_context.get("nextcloud_client"):
            self._update_connection_status(True)
        else:
            self._update_connection_status(False)

    def _browse_folder(self, e):
        """浏览文件夹（当前来源的远程目录）"""
        if not self.app_context.get("nextcloud_client"):
            self.show_message("请先连接服务器", "error")
            return

        if self._current_source_type() == "smb":
            folder_input = self.smb_sync_folder_input
            config_key = "connection.smb.default_sync_folder"
        else:
            folder_input = self.sync_folder_input
            config_key = "connection.default_sync_folder"

        from .folder_selector import FolderSelector

        current_folder = folder_input.value.strip()
        selector = FolderSelector(
            self.page,
            self.app_context["nextcloud_client"],
            current_folder,
        )

        def on_selected(path):
            folder_input.value = path
            self.page.update()
            self.show_message(f"已选择文件夹: {path or '/'}", "success")
            self.app_context["config_manager"].set(config_key, path)
            self.app_context["config_manager"].save_config()

        selector.show_dialog(on_selected)
