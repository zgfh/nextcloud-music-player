"""
统一顶部 Overlay 通知测试：浮在界面上 + 互斥显示（不叠加）
"""

import flet as ft

from fakes import FakePage


def test_message_uses_top_overlay_without_dialog():
    """提示挂到顶部 Overlay，不使用会推动页面布局的 Banner。"""
    from nextcloud_music_player.utils.notify import show_snack_bar

    page = FakePage()
    show_snack_bar(page, "连接成功！", "success")

    notification = page.overlay[-1]
    assert isinstance(notification, ft.SafeArea)
    assert notification.top == 0
    assert page.dialogs == []
    assert "连接成功！" in notification.content.content.controls[1].value


def test_new_message_replaces_previous_overlay():
    """连续两条消息（如“正在连接...”→“连接成功！”）只显示最新一条"""
    from nextcloud_music_player.utils.notify import show_snack_bar

    page = FakePage()
    show_snack_bar(page, "正在连接...", "info")
    first = page.overlay[-1]

    show_snack_bar(page, "连接成功！", "success")
    second = page.overlay[-1]

    assert second is not first
    assert first not in page.overlay
    assert len(page.overlay) == 1
    assert "连接成功！" in second.content.content.controls[1].value
