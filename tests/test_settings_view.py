"""
设置视图测试：日志渲染、级别切换持久化、清空
"""

import logging
from types import SimpleNamespace

import pytest

from fakes import FakeConfigManager, FakePage, FakeViewManager


@pytest.fixture(autouse=True)
def log_env():
    """给 root logger 挂上环形缓冲 handler，并在结束时还原全局日志状态"""
    from nextcloud_music_player.utils.log_buffer import (
        LOG_FORMAT,
        RingBufferHandler,
        clear_buffer,
    )

    clear_buffer()
    handler = RingBufferHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root = logging.getLogger()
    root.addHandler(handler)
    old_level = root.level
    root.setLevel(logging.INFO)
    yield handler
    root.removeHandler(handler)
    root.setLevel(old_level)


def make_settings_view(config=None):
    from nextcloud_music_player.views.settings_view import SettingsView

    page = FakePage()
    config_manager = FakeConfigManager(config)
    app_context = {"config_manager": config_manager}
    view = SettingsView(page, app_context, FakeViewManager())
    view.build()
    return view, page, config_manager


def test_logs_rendered_from_memory_buffer(log_env):
    """当前会话日志渲染到日志列表（FakeConfigManager 无日志目录，走内存兜底）"""
    logging.getLogger("test.settings").info("hello-log-line")
    logging.getLogger("test.settings").warning("warn-log-line")

    view, _, _ = make_settings_view()

    texts = [t.value for t in view.log_list.controls]
    assert any("hello-log-line" in (t or "") for t in texts)
    assert any("warn-log-line" in (t or "") for t in texts)


def test_log_level_change_persists_and_applies(log_env):
    """切换到 DEBUG：立即作用于 root logger 并写入配置"""
    view, _, config = make_settings_view()

    view.level_selector.selected = ["DEBUG"]
    view._on_log_level_change(None)

    assert config.get("app.log_level") == "DEBUG"
    assert logging.getLogger().level == logging.DEBUG


def test_clear_logs(log_env):
    """清空后列表只剩“应用日志已清空”这一条新记录"""
    logging.getLogger("test.settings").info("before-clear")
    view, page, _ = make_settings_view()
    assert len(view.log_list.controls) > 0

    view._clear_logs(None)

    assert len(view.log_list.controls) == 1
    assert "应用日志已清空" in view.log_list.controls[0].value
    notification_texts = [
        control.value
        for control in page.overlay[-1].content.content.controls
        if hasattr(control, "value")
    ]
    assert any("已清空" in text for text in notification_texts)


def test_log_view_initially_renders_only_tail(log_env):
    """打开设置页只创建末尾少量控件，不一次渲染全部日志。"""
    for index in range(70):
        logging.getLogger("test.settings").info("line-%03d", index)

    view, _, _ = make_settings_view()

    assert len(view.log_list.controls) == 40
    assert "line-030" in view.log_list.controls[0].value
    assert "line-069" in view.log_list.controls[-1].value


def test_scrolling_to_top_loads_older_log_page(log_env):
    for index in range(100):
        logging.getLogger("test.settings").info("line-%03d", index)
    view, _, _ = make_settings_view()

    view._on_log_scroll(
        SimpleNamespace(pixels=0, min_scroll_extent=0, scroll_delta=-10)
    )

    assert len(view.log_list.controls) == 90
    assert "line-010" in view.log_list.controls[0].value


def test_tail_diff_returns_only_new_lines():
    from nextcloud_music_player.views.settings_view import SettingsView

    assert SettingsView._new_log_lines(["one", "two"], ["one", "two", "three"]) == [
        "three"
    ]
    assert SettingsView._new_log_lines(["old"], ["new"]) is None


@pytest.mark.asyncio
async def test_copy_uses_clipboard_service_without_adding_it_to_overlay(monkeypatch):
    from nextcloud_music_player.views import settings_view as module

    copied = []

    class FakeClipboard:
        async def set(self, text):
            copied.append(text)

    monkeypatch.setattr(module.ft, "Clipboard", FakeClipboard)
    view, page, _ = make_settings_view()
    view._log_lines = ["line one", "line two"]
    overlay_count = len(page.overlay)

    await view._copy_logs(None)

    assert copied == ["line one\nline two"]
    # 成功提示会新增一个 SnackBar，但 Clipboard 本身不能进入 overlay。
    assert len(page.overlay) == overlay_count + 1
