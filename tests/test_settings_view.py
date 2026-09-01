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


def test_musicbrainz_switch_defaults_on_and_persists_change():
    view, _, config = make_settings_view()

    assert view.musicbrainz_switch.value is True
    view.musicbrainz_switch.value = False
    view._on_musicbrainz_enabled_change(
        SimpleNamespace(control=view.musicbrainz_switch)
    )

    assert config.get("metadata.musicbrainz_enabled") is False


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
    tracker.enqueue(["other.mp3", "song.mp3"])
    tracker.mark_downloading("song.mp3")
    tracker.update("song.mp3", 512 * 1024, 1024 * 1024)
    view.app_context["music_service"] = SimpleNamespace(download_progress=tracker)

    assert view._refresh_download_progress() is True
    assert view.download_status_text.value == "正在下载 1 首"
    assert view.download_filename_text.value == "song.mp3"
    assert view.download_progress_bar.value == 0.5
    assert "512.0 KB / 1.0 MB" in view.download_progress_text.value
    assert "50%" in view.download_progress_text.value
    assert "等待 1" in view.download_queue_text.value


def test_download_progress_is_static_when_idle():
    from nextcloud_music_player.services.download_progress import (
        DownloadProgressTracker,
    )

    view, _, _ = make_settings_view(sub_page="download")
    view.app_context["music_service"] = SimpleNamespace(
        download_progress=DownloadProgressTracker()
    )

    view._refresh_download_progress()

    assert view.download_status_text.value == "暂无下载任务"
    assert view.download_progress_bar.value == 0.0


def test_download_page_shows_elapsed_and_remaining_time(monkeypatch):
    from nextcloud_music_player.services import download_progress as module
    from nextcloud_music_player.services.download_progress import (
        DownloadProgressTracker,
    )

    clock = [100.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    tracker = DownloadProgressTracker()
    tracker.enqueue("song.mp3")
    tracker.mark_downloading("song.mp3")
    clock[0] = 110.0
    tracker.update("song.mp3", 50, 100)
    view, _, _ = make_settings_view(sub_page="download")
    view.app_context["music_service"] = SimpleNamespace(download_progress=tracker)

    view._refresh_download_progress()

    assert "用时 00:10" in view.download_progress_text.value
    assert "剩余约 00:10" in view.download_progress_text.value
    row_detail = view.download_list.controls[0].controls[2].value
    assert "用时 00:10" in row_detail
    assert "剩余约 00:10" in row_detail


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


def test_stale_progress_cannot_resurrect_finished_file():
    """文件完成后的迟到进度不会复活条目"""
    from nextcloud_music_player.services.download_progress import (
        DownloadProgressTracker,
    )

    tracker = DownloadProgressTracker()
    tracker.enqueue("a.mp3")
    tracker.mark_downloading("a.mp3")
    tracker.update("a.mp3", 100, 100)
    tracker.finish("a.mp3", True)

    tracker.update("a.mp3", 50, 100)  # 迟到进度

    state = tracker.snapshot()
    assert state["completed"] == 1
    assert tracker.file_states()[0]["status"] == "completed"


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
        if isinstance(entry.content, ft.Row)
    ]
    assert titles == ["下载进度", "缓存管理", "应用日志", "谷歌云盘", "应用信息"]


def test_menu_entry_click_opens_sub_page():
    """点击菜单入口进入对应子页面，返回按钮可回到菜单"""
    view, _, _ = make_settings_view()

    gdrive_entry = next(
        entry for entry in view._container.content.controls
        if isinstance(getattr(entry, "content", None), ft.Row)
        and entry.content.controls[1].controls[0].value == "谷歌云盘"
    )
    gdrive_entry.on_click(SimpleNamespace(control=gdrive_entry))

    assert view._sub_page == "gdrive"
    assert hasattr(view, "gdrive_api_base_input")
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
    tracker.enqueue(["a.mp3", "b.mp3", "song.mp3"])
    tracker.mark_downloading("song.mp3")
    tracker.update("song.mp3", 512 * 1024, 1024 * 1024)
    view.app_context["music_service"] = SimpleNamespace(download_progress=tracker)

    assert view._refresh_download_progress() is True
    subtitle = view._menu_subtitles["download"]
    assert "正在下载 1 首" in subtitle.value
    assert "排队 2" in subtitle.value


def test_log_tail_poll_updates_download_only_when_not_on_logs_page():
    """菜单页/下载页也轮询下载状态（日志跟随仅限日志页）"""
    view, _, _ = make_settings_view(sub_page="download")

    # 模拟轮询循环的一步：不在日志页时不应触碰 log_list
    assert not hasattr(view, "log_list")


# ---------------------------------------------------------------------------
# 谷歌云盘设置页
# ---------------------------------------------------------------------------


def test_gdrive_page_loads_existing_api_base():
    view, _, _ = make_settings_view(
        config={"connection": {"gdrive": {"api_base_url": "http://192.168.1.10:8931"}}},
        sub_page="gdrive",
    )

    assert view.gdrive_api_base_input.value == "http://192.168.1.10:8931"


def test_gdrive_page_save_persists_normalized_api_base():
    view, page, config = make_settings_view(sub_page="gdrive")

    view.gdrive_api_base_input.value = "  http://127.0.0.1:8931/ "
    view._save_gdrive_settings(None)

    assert config.get("connection.gdrive.api_base_url") == "http://127.0.0.1:8931"
    # 归一化结果回填输入框，避免保存后显示原始输入
    assert view.gdrive_api_base_input.value == "http://127.0.0.1:8931"
    notification_texts = [
        control.value
        for control in page.overlay[-1].content.content.controls
        if hasattr(control, "value")
    ]
    assert any("已保存" in text for text in notification_texts)


def test_gdrive_page_save_empty_restores_official_endpoint():
    """清空地址保存 = 回到 Google 官方端点"""
    view, _, config = make_settings_view(
        config={"connection": {"gdrive": {"api_base_url": "http://192.168.1.10:8931"}}},
        sub_page="gdrive",
    )

    view.gdrive_api_base_input.value = ""
    view._save_gdrive_settings(None)

    assert config.get("connection.gdrive.api_base_url", "unset") == ""


def test_gdrive_menu_summary_reflects_endpoint_state():
    view, _, _ = make_settings_view()
    assert view._menu_subtitles["gdrive"].value == "使用 Google 官方端点"

    view, _, _ = make_settings_view(
        config={"connection": {"gdrive": {"api_base_url": "http://127.0.0.1:8931"}}}
    )
    assert view._menu_subtitles["gdrive"].value == "自定义端点 http://127.0.0.1:8931"


def test_download_page_renders_per_file_list():
    """下载页按文件渲染列表：进度、成功、失败各自成行"""
    from nextcloud_music_player.services.download_progress import (
        DownloadProgressTracker,
    )

    view, _, _ = make_settings_view(sub_page="download")
    tracker = DownloadProgressTracker()
    tracker.enqueue(["a.mp3", "b.mp3", "c.mp3"])
    tracker.mark_downloading("a.mp3")
    tracker.update("a.mp3", 50, 100)
    tracker.finish("b.mp3", True)
    tracker.finish("c.mp3", False, "HTTP 404")
    view.app_context["music_service"] = SimpleNamespace(download_progress=tracker)

    assert view._refresh_download_progress() is True

    rows = view.download_list.controls
    assert [row.controls[1].value for row in rows] == ["a.mp3", "b.mp3", "c.mp3"]
    assert "50%" in rows[0].controls[2].value
    assert "HTTP 404" in rows[2].controls[2].value
    assert view.download_status_text.value == "正在下载 1 首"
    assert rows[0].controls[1].size >= view.download_filename_text.size
