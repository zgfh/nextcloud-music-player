"""
SMB 连接向导 - 像桌面系统一样三步完成连接：

1. 身份验证：选择 访客 / 用户登录（用户登录填写用户名密码，域/端口在高级选项）
2. 选择共享：连接服务器后列出全部可访问共享，点选一个
3. 选择目录：浏览共享内目录，确定同步文件夹

完成后通过 on_complete 回调返回 SMBConnectResult，
由 ConnectionView 负责写入配置、更新客户端与跳转视图。
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import flet as ft

from ...utils.theme import Color, Radius, Space, tint
from ..folder_selector import FolderSelector

logger = logging.getLogger(__name__)


@dataclass
class SMBConnectResult:
    """向导完成结果（含已通过验证的客户端实例）"""

    host: str
    port: int
    domain: str
    username: str
    password: str
    share: str
    sync_folder: str
    client: object  # 已连接且指定了 share 的 SMBClient


class SMBConnectWizard:
    """SMB 三步连接向导（对话框流）"""

    def __init__(self, page: ft.Page, defaults: Optional[dict] = None):
        """
        defaults: 预填项（来自已保存配置），支持
        host/port/domain/username/password/share/sync_folder
        """
        self.page = page
        d = defaults or {}
        self.host = d.get("host", "")
        self.port = int(d.get("port") or 445)
        self.domain = d.get("domain", "") or ""
        self.username = d.get("username", "")
        self.password = d.get("password", "")
        self.share = d.get("share", "")
        self.sync_folder = d.get("sync_folder", "/") or "/"
        self.on_complete = None
        self.on_error = None
        self._client = None  # 认证通过的 SMBClient（未指定 share）
        self._connecting = False

    # === 入口 ===

    def show(self, callback, error_callback=None):
        """打开第一步：身份验证"""
        self.on_complete = callback
        self.on_error = error_callback
        self._show_auth_dialog()

    # === 第一步：身份验证 ===

    def _show_auth_dialog(self):
        is_guest = not self.username

        self.auth_mode = ft.SegmentedButton(
            selected=["guest" if is_guest else "user"],
            segments=[
                ft.Segment(
                    key="smb_auth_guest",
                    value="guest",
                    label="访客",
                    icon=ft.Icons.PERSON_OFF_OUTLINED,
                ),
                ft.Segment(
                    key="smb_auth_user",
                    value="user", label="用户登录", icon=ft.Icons.PERSON_OUTLINED
                ),
            ],
            allow_multiple_selection=False,
            allow_empty_selection=False,
            on_change=lambda e: self._on_auth_mode_changed(),
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

        self.user_input = _wizard_input(
            label="用户名", value=self.username, hint_text="服务器的登录用户名"
        )
        self.password_input = _wizard_input(
            label="密码",
            value=self.password,
            hint_text="输入密码",
            password=True,
            can_reveal_password=True,
        )
        self.domain_input = _wizard_input(
            label="域（可选）", value=self.domain, hint_text="默认 WORKGROUP"
        )
        self.port_input = _wizard_input(
            label="端口",
            value=str(self.port or 445),
            hint_text="445",
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        self.credential_column = ft.Column(
            [self.user_input, self.password_input],
            spacing=Space.SM,
            visible=not is_guest,
        )
        self.advanced_column = ft.Column(
            [self.domain_input, self.port_input],
            spacing=Space.SM,
            visible=False,
        )
        self.advanced_toggle = ft.TextButton(
            "高级选项",
            icon=ft.Icons.TUNE,
            on_click=lambda e: self._toggle_advanced(),
            style=ft.ButtonStyle(color=Color.TEXT_SECONDARY),
        )
        self.auth_error_text = ft.Text(
            "", size=12, color=Color.DANGER_TEXT, visible=False, max_lines=3
        )
        self.connect_btn = ft.FilledButton(
            "连接服务器",
            icon=ft.Icons.BOLT,
            on_click=lambda e: asyncio.create_task(self._do_connect()),
            style=ft.ButtonStyle(
                bgcolor=Color.PRIMARY,
                color=Color.PRIMARY_TEXT,
                icon_color=Color.PRIMARY_TEXT,
                shape=ft.RoundedRectangleBorder(radius=Radius.CIRCLE),
            ),
        )

        self.auth_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(
                f"连接 {self.host}", size=16, weight=ft.FontWeight.BOLD
            ),
            content=ft.Container(
                content=ft.Column(
                    [
                        self.auth_mode,
                        self.credential_column,
                        self.advanced_toggle,
                        self.advanced_column,
                        self.auth_error_text,
                    ],
                    spacing=Space.SM,
                    tight=True,
                ),
                width=340,
            ),
            actions=[
                ft.TextButton(
                    "取消",
                    on_click=lambda e: self._cancel(),
                    style=ft.ButtonStyle(color=Color.TEXT_SECONDARY),
                ),
                self.connect_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        self.page.show_dialog(self.auth_dialog)

    def _on_auth_mode_changed(self):
        selected = self.auth_mode.selected or []
        self.credential_column.visible = "user" in selected
        self.page.update()

    def _toggle_advanced(self):
        self.advanced_column.visible = not self.advanced_column.visible
        self.page.update()

    def _collect_credentials(self):
        """从表单收集凭据（访客模式下清空用户名/密码）"""
        selected = self.auth_mode.selected or []
        if "user" in selected:
            self.username = self.user_input.value.strip()
            self.password = self.password_input.value or ""
        else:
            self.username = ""
            self.password = ""
        self.domain = self.domain_input.value.strip()
        try:
            self.port = int(self.port_input.value.strip() or 445)
        except ValueError:
            self.port = 445

    async def _do_connect(self):
        """用当前凭据连接服务器，成功后进入第二步选共享"""
        if self._connecting:
            return
        self._connecting = True
        self._collect_credentials()
        self._set_auth_busy(True, "正在连接服务器...")

        try:
            from ...smb_client import SMBClient

            client = SMBClient(
                host=self.host,
                username=self.username,
                password=self.password,
                port=self.port,
                domain=self.domain,
            )
            shares = await client.list_shares()
            self._client = client

            # 服务器只有一个普通共享时直接选中，少点一次
            if len(shares) == 1:
                self._choose_share(shares[0]["name"])
                return

            self.page.pop_dialog()
            self._show_share_dialog(shares)
        except Exception as e:
            logger.error(f"SMB 向导连接失败: {e}")
            self._set_auth_busy(False, f"连接失败: {e}")
        finally:
            self._connecting = False

    def _set_auth_busy(self, busy: bool, message: str = ""):
        self.connect_btn.disabled = busy
        if busy:
            self.connect_btn.text = message
        else:
            self.connect_btn.text = "连接服务器"
        self.auth_error_text.visible = not busy and bool(message)
        self.auth_error_text.value = "" if busy else message
        try:
            self.page.update()
        except Exception:
            pass

    # === 第二步：选择共享 ===

    def _show_share_dialog(self, shares):
        share_list = ft.ListView(spacing=2, padding=8, expand=True)
        for share in shares:
            name = share.get("name", "")
            comment = share.get("comment", "")
            share_list.controls.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.FOLDER_SHARED_OUTLINED, color=Color.ACCENT),
                    title=ft.Text(name, size=14, color=Color.TEXT_PRIMARY),
                    subtitle=(
                        ft.Text(comment, size=11, color=Color.TEXT_MUTED)
                        if comment
                        else None
                    ),
                    on_click=lambda e, n=name: self._choose_share(n),
                )
            )

        self.share_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("选择音乐所在的共享", size=16, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            f"{self.host} 上的共享",
                            size=12,
                            color=Color.TEXT_MUTED,
                        ),
                        ft.Container(content=share_list, height=320),
                    ],
                    spacing=Space.SM,
                    tight=True,
                ),
                width=360,
            ),
            actions=[
                ft.TextButton(
                    "上一步",
                    on_click=lambda e: self._back_to_auth(),
                    style=ft.ButtonStyle(color=Color.TEXT_SECONDARY),
                ),
            ],
        )
        self.page.show_dialog(self.share_dialog)

    def _choose_share(self, share_name: str):
        """选定共享：更新客户端的 share 并进入第三步浏览目录"""
        self.share = share_name
        if self._client is not None:
            # SMBClient 的共享字段直接可写；连接已建立，无需重连
            self._client.share = share_name
        try:
            # 关闭当前弹窗（认证弹窗或共享列表弹窗）
            self.page.pop_dialog()
        except Exception:
            pass
        self._show_folder_selector()

    def _back_to_auth(self):
        self.page.pop_dialog()
        self._show_auth_dialog()

    # === 第三步：选择目录 ===

    def _show_folder_selector(self):
        selector = FolderSelector(
            self.page,
            self._client,
            self.sync_folder or "/",
        )

        def on_selected(path):
            self.sync_folder = path or "/"
            self._finish()

        selector.show_dialog(on_selected)

    # === 收尾 ===

    def _finish(self):
        """向导完成：回调结果并清理状态"""
        result = SMBConnectResult(
            host=self.host,
            port=self.port,
            domain=self.domain,
            username=self.username,
            password=self.password,
            share=self.share,
            sync_folder=self.sync_folder,
            client=self._client,
        )
        if self.on_complete:
            self.on_complete(result)

    def _cancel(self):
        try:
            self.page.pop_dialog()
        except Exception:
            pass
        if self.on_error:
            self.on_error("已取消连接")


def _wizard_input(**kwargs) -> ft.TextField:
    """向导对话框内的暗色输入框（与连接页 _dark_input 同风格）"""
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
