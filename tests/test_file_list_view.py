"""
文件列表交互测试：同步进度提示、同步失败反馈、重复点击防抖
"""

import asyncio

from fakes import (
    FakeConfigManager, FakeMusicLibrary, FakeNextcloudClient, FakePage,
    FakeViewManager, add_remote_song, last_notification_text, make_music_service,
)


def make_file_list_view(page, client, library, config, monkeypatch):
    from nextcloud_music_player.views.file_list_view import FileListView
    music_service = make_music_service(library, client, config, monkeypatch)
    app_context = {
        "config_manager": config,
        "music_service": music_service,
        "music_library": library,
        "nextcloud_client": client,
    }
    view = FileListView(page, app_context, FakeViewManager())
    view.build()
    return view, music_service


async def test_sync_shows_progress_and_reloads(tmp_path, monkeypatch):
    """慢网络同步期间显示"正在同步"并禁用按钮，完成后刷新列表"""
    page = FakePage()
    client = FakeNextcloudClient(
        files=[{"name": "a.mp3", "path": "/music/a.mp3", "size": 1},
               {"name": "b.mp3", "path": "/music/b.mp3", "size": 1}],
        list_delay=0.3,
    )
    config = FakeConfigManager({"connection": {"default_sync_folder": "/music"}})
    view, _ = make_file_list_view(
        page, client, FakeMusicLibrary(tmp_path), config, monkeypatch)

    task = asyncio.create_task(view._sync_music_list(None))
    await asyncio.sleep(0.05)

    assert view.sync_button.disabled is True
    assert "正在同步" in last_notification_text(page)

    await task
    assert view.sync_button.disabled is False           # 按钮恢复
    assert len(view.file_list.controls) == 2            # 列表已刷新
    assert {s['name'] for s in view.music_service.get_all_songs()} == {"a.mp3", "b.mp3"}


async def test_sync_failure_shows_error_and_reenables(tmp_path, monkeypatch):
    page = FakePage()
    client = FakeNextcloudClient(list_error=RuntimeError("500 Server Error"))
    config = FakeConfigManager({"connection": {"default_sync_folder": "/music"}})
    view, _ = make_file_list_view(
        page, client, FakeMusicLibrary(tmp_path), config, monkeypatch)

    await view._sync_music_list(None)

    assert view.sync_button.disabled is False
    assert "同步失败" in last_notification_text(page)


async def test_sync_reentry_ignored_while_running(tmp_path, monkeypatch):
    """同步进行中再次点击同步应被忽略，不产生第二次网络请求"""
    page = FakePage()
    client = FakeNextcloudClient(
        files=[{"name": "a.mp3", "path": "/music/a.mp3"}], list_delay=0.2)
    config = FakeConfigManager({"connection": {"default_sync_folder": "/music"}})
    view, _ = make_file_list_view(
        page, client, FakeMusicLibrary(tmp_path), config, monkeypatch)

    first = asyncio.create_task(view._sync_music_list(None))
    await asyncio.sleep(0.02)
    await view._sync_music_list(None)                   # 同步中的重复点击

    await first
    assert len(client.list_calls) == 1


async def test_search_filters_list(tmp_path, monkeypatch):
    page = FakePage()
    client = FakeNextcloudClient()
    config = FakeConfigManager()
    library = FakeMusicLibrary(tmp_path)
    view, _ = make_file_list_view(page, client, library, config, monkeypatch)
    library.add_remote_song("周杰伦-晴天.mp3", "/music/周杰伦-晴天.mp3")
    library.add_remote_song("林俊杰-江南.mp3", "/music/林俊杰-江南.mp3")

    view.search_input.value = "晴天"
    view._search_music(None)

    assert len(view.file_list.controls) == 1


async def test_download_selected_queues_and_drains(tmp_path, monkeypatch):
    """批量下载入队后由 worker 逐首处理，完成后队列清空并提示结果"""
    page = FakePage()
    client = FakeNextcloudClient()
    config = FakeConfigManager()
    library = FakeMusicLibrary(tmp_path)
    library.add_remote_song("a.mp3", "/music/a.mp3")
    library.add_remote_song("b.mp3", "/music/b.mp3")
    view, _ = make_file_list_view(page, client, library, config, monkeypatch)

    view.selected_files = {"a.mp3", "b.mp3"}
    await view._download_selected(None)

    assert view._download_task is not None
    await view._download_task

    assert {name for _, name in client.download_calls} == {"a.mp3", "b.mp3"}
    assert view._pending_downloads == []
    assert "下载完成" in last_notification_text(page)
    assert library.get_song_info("a.mp3")["is_downloaded"] is True


async def test_download_selected_skips_already_downloaded(tmp_path, monkeypatch):
    """选中歌曲均已下载时不启动 worker，直接提示"""
    page = FakePage()
    client = FakeNextcloudClient()
    config = FakeConfigManager()
    library = FakeMusicLibrary(tmp_path)
    add_remote_song(library, "a.mp3", downloaded=True)
    view, _ = make_file_list_view(page, client, library, config, monkeypatch)

    view.selected_files = {"a.mp3"}
    await view._download_selected(None)

    assert view._download_task is None
    assert client.download_calls == []
    assert "均已下载" in last_notification_text(page)


async def test_app_resumed_restarts_dead_download_worker(tmp_path, monkeypatch):
    """队列有剩余且 worker 已死（iOS 后台挂起后）：回前台自动续传"""
    page = FakePage()
    client = FakeNextcloudClient()
    config = FakeConfigManager()
    library = FakeMusicLibrary(tmp_path)
    library.add_remote_song("a.mp3", "/music/a.mp3")
    view, _ = make_file_list_view(page, client, library, config, monkeypatch)

    view._pending_downloads = [("a.mp3", "/music/a.mp3")]
    view._download_task = None

    view.on_app_resumed()
    assert view._download_task is not None
    await view._download_task

    assert client.download_calls == [("/music/a.mp3", "a.mp3")]
    assert view._pending_downloads == []


async def test_app_resumed_does_not_duplicate_running_worker(tmp_path, monkeypatch):
    """worker 存活时回前台不重复拉起"""
    page = FakePage()
    client = FakeNextcloudClient()
    config = FakeConfigManager()
    library = FakeMusicLibrary(tmp_path)
    view, _ = make_file_list_view(page, client, library, config, monkeypatch)

    view._pending_downloads = [("a.mp3", "/music/a.mp3")]
    running = asyncio.create_task(asyncio.sleep(10))
    view._download_task = running

    try:
        view.on_app_resumed()
        assert view._download_task is running
    finally:
        running.cancel()
        view._pending_downloads.clear()
