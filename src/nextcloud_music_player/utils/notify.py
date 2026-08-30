"""统一的顶部浮层通知。

通知挂到 ``page.overlay``，不参与页面布局，因此不会推动正文或底部导航栏。
同一页面只保留最新一条，3 秒后自动消失。
"""

import asyncio
import logging

import flet as ft

from .theme import get_message_style

logger = logging.getLogger(__name__)

_current_notifications: dict[int, ft.SafeArea | None] = {}


def show_snack_bar(page: ft.Page, message: str, message_type: str = "info"):
    """在页面顶部以 Overlay 显示消息，不改变现有界面布局。"""
    _dismiss_current(page)

    bg_color, text_color, icon = get_message_style(message_type)
    notification = ft.SafeArea(
        content=ft.Container(
            content=ft.Row(
                [
                    ft.Text(icon, size=16),
                    ft.Text(
                        message,
                        color=text_color,
                        max_lines=3,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        expand=True,
                    ),
                ],
                spacing=8,
                tight=True,
            ),
            bgcolor=bg_color,
            border_radius=10,
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            shadow=ft.BoxShadow(
                blur_radius=12,
                color="#55000000",
                offset=ft.Offset(0, 4),
            ),
        ),
        left=12,
        top=0,
        right=12,
        avoid_intrusions_bottom=False,
    )
    try:
        page.overlay.append(notification)
        _current_notifications[id(page)] = notification
        page.update(notification)
        if hasattr(page, "run_task"):
            page.run_task(_auto_dismiss, page, notification)
    except Exception as e:
        logger.warning(f"顶部通知显示失败: {e}")
    logger.info(f"[{message_type.upper()}] {message}")


async def _auto_dismiss(page: ft.Page, notification: ft.SafeArea):
    await asyncio.sleep(3)
    if _current_notifications.get(id(page)) is notification:
        _dismiss_notification(page, notification)


def _dismiss_current(page: ft.Page):
    notification = _current_notifications.get(id(page))
    if notification is not None:
        _dismiss_notification(page, notification)


def _dismiss_notification(page: ft.Page, notification: ft.SafeArea):
    """移除指定浮层；控件已被页面清理时也保持幂等。"""
    if _current_notifications.get(id(page)) is notification:
        _current_notifications[id(page)] = None
    try:
        if notification in page.overlay:
            page.overlay.remove(notification)
        page.update()
    except Exception:
        pass
