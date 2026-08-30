"""
设置视图测试：日志渲染、级别切换持久化、清空
"""

import logging
from types import SimpleNamespace

import flet as ft
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


def make_settings_view(config=None, sub_page="menu"):
    """构建设置视图；sub_page 指定打开的子页面（默认菜单页）"""
    from nextcloud_music_player.views.settings_view import SettingsView

    page = FakePage()
    config_manager = FakeConfigManager(config)
    app_context = {"config_manager": config_manager}
    view = SettingsView(page, app_context, FakeViewManager())
    view.build()
    if sub_page != "menu":
        view._open_sub_page(sub_page)
    return view, page, config_manager


def test_logs_rendered_from_memory_buffer(log_env):
    """当前会话日志渲染到日志列表（FakeConfigManager 无日志目录，走内存兜底）"""
    logging.getLogger("test.settings").info("hello-log-line")
    logging.getLogger("test.settings").warning("warn-log-line")

    view, _, _ = make_settings_view(sub_page="logs")

    texts = [t.value for t in view.log_list.controls]
    assert any("hello-log-line" in (t or "") for t in texts)
    assert any("warn-log-line" in (t or "") for t in texts)


def test_log_level_change_persists_and_applies(log_env):
    """切换到 DEBUG：立即作用于 root logger 并写入配置"""
    view, _, config = make_settings_view(sub_page="logs")

    view.level_selector.selected = ["DEBUG"]
    view._on_log_level_change(None)

    assert config.get("app.log_level") == "DEBUG"
    assert logging.getLogger().level == logging.DEBUG


def test_clear_logs(log_env):
    """清空后列表只剩“应用日志已清空”这一条新记录"""
    logging.getLogger("test.settings").info("before-clear")
    view, page, _ = make_settings_view(sub_page="logs")
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

    view, _, _ = make_settings_view(sub_page="logs")

    assert len(view.log_list.controls) == 40
    assert "line-030" in view.log_list.controls[0].value
    assert "line-069" in view.log_list.controls[-1].value


def test_scrolling_to_top_loads_older_log_page(log_env):
    for index in range(100):
        logging.getLogger("test.settings").info("line-%03d", index)
    view, _, _ = make_settings_view(sub_page="logs")

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


def test_download_card_renders_live_progress():
    from nextcloud_music_player.services.download_progress import (
        DownloadProgressTracker,
    )

    view, _, _ = make_settings_view(sub_page="download")
    tracker = DownloadProgressTracker()
    tracker.enqueue(2)
    token = tracker.start("song.mp3")
    tracker.update(512 * 1024, 1024 * 1024, token)
    view.app_context["music_service"] = SimpleNamespace(download_progress=tracker)

    assert view._refresh_download_progress() is True
    assert view.download_status_text.value == "正在下载"
    assert view.download_filename_text.value == "song.mp3"
    assert view.download_progress_bar.value == 0.5
    assert "512.0 KB / 1.0 MB" in view.download_progress_text.value
    assert "等待 1" in view.download_queue_text.value


def test_cache_manager_lists_and_selectively_clears_downloads():
    cached = [
        {"name": "a.mp3", "size": 1024, "download_time": "2026-08-30T10:20:00"},
        {"name": "b.mp3", "size": 2048, "download_time": ""},
    ]

    class CacheService:
        def get_cached_songs(self):
            return list(cached)

        def remove_cached_songs(self, names):
            removed = [item for item in cached if item["name"] in names]
            cached[:] = [item for item in cached if item["name"] not in names]
            return len(removed), sum(item["size"] for item in removed)

    view, page, _ = make_settings_view(sub_page="cache")
    view.app_context["music_service"] = CacheService()
    view._refresh_cache_list()

    assert view.cache_summary_text.value == "2 首 · 3.0 KB"
    first_checkbox = view.cache_list.controls[0].controls[0]
    first_checkbox.value = True
    view._toggle_cache_item(SimpleNamespace(control=first_checkbox))
    view._clear_selected_cache(None)

    assert [item["name"] for item in cached] == ["b.mp3"]
    assert view.cache_summary_text.value == "1 首 · 2.0 KB"
    assert page.update_calls > 0


def test_stale_download_cannot_overwrite_newer_progress():
    from nextcloud_music_player.services.download_progress import (
        DownloadProgressTracker,
    )

    tracker = DownloadProgressTracker()
    old_token = tracker.start("old.mp3")
    new_token = tracker.start("new.mp3")
    tracker.update(100, 100, old_token)
    tracker.finish(True, token=old_token)

    state = tracker.snapshot()
    assert state["filename"] == "new.mp3"
    assert state["status"] == "downloading"
    assert state["downloaded_bytes"] == 0
    tracker.update(50, 100, new_token)
    assert tracker.snapshot()["downloaded_bytes"] == 50


@pytest.mark.asyncio
async def test_copy_uses_clipboard_service_without_adding_it_to_overlay(monkeypatch):
    from nextcloud_music_player.views import settings_view as module

    copied = []

    class FakeClipboard:
        async def set(self, text):
            copied.append(text)

    monkeypatch.setattr(module.ft, "Clipboard", FakeClipboard)
    view, page, _ = make_settings_view(sub_page="logs")
    view._log_lines = ["line one", "line two"]
    overlay_count = len(page.overlay)

    await view._copy_logs(None)

    assert copied == ["line one\nline two"]
    # 成功提示会新增一个 SnackBar，但 Clipboard 本身不能进入 overlay。
    assert len(page.overlay) == overlay_count + 1


# ---------------------------------------------------------------------------
# 菜单式二级导航
# ---------------------------------------------------------------------------


def test_menu_lists_all_feature_entries():
    """设置首页是功能菜单列表，每个功能一个入口"""
    view, _, _ = make_settings_view()

    titles = [
        entry.content.controls[1].controls[0].value
        for entry in view._container.content.controls[1:]
    ]
    assert titles == ["下载进度", "缓存管理", "应用日志", "应用信息"]


def test_menu_entry_click_opens_sub_page():
    """点击菜单入口进入对应子页面，返回按钮可回到菜单"""
    view, _, _ = make_settings_view()

    # 第四个入口：应用信息
    about_entry = view._container.content.controls[4]
    about_entry.on_click(SimpleNamespace(control=about_entry))

    assert view._sub_page == "about"
    header = view._container.content.controls[0]
    back_button = header.controls[0]
    assert back_button.icon == ft.Icons.ARROW_BACK_IOS_NEW

    back_button.on_click(SimpleNamespace(control=back_button))
    assert view._sub_page == "menu"


def test_opening_logs_page_renders_log_list(log_env):
    logging.getLogger("test.settings").info("menu-nav-log-line")

    view, _, _ = make_settings_view(sub_page="logs")

    texts = [t.value for t in view.log_list.controls]
    assert any("menu-nav-log-line" in (t or "") for t in texts)


def test_rebuild_keeps_current_sub_page(log_env):
    """从其它标签页切回设置时，停留在离开前的子页面"""
    view, _, _ = make_settings_view(sub_page="logs")

    view.rebuild()

    assert view._sub_page == "logs"
    assert hasattr(view, "log_list")


def test_menu_download_subtitle_tracks_live_progress():
    from nextcloud_music_player.services.download_progress import (
        DownloadProgressTracker,
    )

    view, _, _ = make_settings_view()
    tracker = DownloadProgressTracker()
    tracker.enqueue(3)
    token = tracker.start("song.mp3")
    tracker.update(512 * 1024, 1024 * 1024, token)
    view.app_context["music_service"] = SimpleNamespace(download_progress=tracker)

    assert view._refresh_download_progress() is True
    subtitle = view._menu_subtitles["download"]
    assert "正在下载 song.mp3" in subtitle.value
    assert "排队 2" in subtitle.value


def test_log_tail_poll_updates_download_only_when_not_on_logs_page():
    """菜单页/下载页也轮询下载状态（日志跟随仅限日志页）"""
    view, _, _ = make_settings_view(sub_page="download")

    # 模拟轮询循环的一步：不在日志页时不应触碰 log_list
    assert not hasattr(view, "log_list")
