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


def test_library_view_keeps_delete_but_has_no_clear_cache_action(
    tmp_path, monkeypatch
):
    view, _ = make_file_list_view(
        FakePage(), FakeNextcloudClient(), FakeMusicLibrary(tmp_path),
        FakeConfigManager(), monkeypatch,
    )

    assert hasattr(view, "delete_button")
    assert not hasattr(view, "clear_cache_button")


def test_library_toolbar_has_no_add_and_download_follows_select_all(
    tmp_path, monkeypatch
):
    view, _ = make_file_list_view(
        FakePage(), FakeNextcloudClient(), FakeMusicLibrary(tmp_path),
        FakeConfigManager(), monkeypatch,
    )

    assert not hasattr(view, "add_button")
    toolbar = view.selection_action_row
    assert toolbar.controls.index(view.download_button) == (
        toolbar.controls.index(view.select_all_button) + 1
    )


def test_download_button_shows_selected_count(tmp_path, monkeypatch):
    library = FakeMusicLibrary(tmp_path)
    library.add_remote_song("one.mp3", "/one.mp3")
    view, _ = make_file_list_view(
        FakePage(), FakeNextcloudClient(), library, FakeConfigManager(), monkeypatch
    )

    view.selected_files = {"one.mp3"}
    view._update_stats()

    assert view.download_button.text == "下载（1）"
    assert view.select_all_button.text == "取消全选"


def test_song_details_save_custom_title_without_changing_library_key(tmp_path, monkeypatch):
    library = FakeMusicLibrary(tmp_path)
    library.add_remote_song("original.mp3", "/original.mp3")
    page = FakePage()
    view, _ = make_file_list_view(
        page, FakeNextcloudClient(), library, FakeConfigManager(), monkeypatch
    )

    view._show_song_details("original.mp3")
    view.song_title_input.value = "自定义歌名"
    view.song_artist_input.value = "新歌手"
    view._save_song_details(None)

    assert "original.mp3" in library.songs
    assert library.songs["original.mp3"]["custom_title"] == "自定义歌名"
    assert library.songs["original.mp3"]["remote_path"] == "/original.mp3"
    assert page.popped_dialogs == 1


async def test_song_details_query_requires_selection_before_save(tmp_path, monkeypatch):
    library = FakeMusicLibrary(tmp_path)
    library.add_remote_song("周杰伦 - 晴天.mp3", "/song.mp3")
    page = FakePage()
    view, _ = make_file_list_view(
        page, FakeNextcloudClient(), library, FakeConfigManager(), monkeypatch
    )
    view._show_song_details("周杰伦 - 晴天.mp3")

    class SearchService:
        async def search(self, artist, title):
            return [{
                "title": "晴天", "artist": "周杰伦", "album": "叶惠美",
                "year": "2003", "mbid": "mbid-1", "confidence": 99,
            }]

    view._musicbrainz_service = SearchService()
    await view._query_song_metadata()

    # 查询本身不持久化，必须先选择候选再保存。
    assert library.songs["周杰伦 - 晴天.mp3"].get("musicbrainz_mbid") is None
    view._select_song_candidate({
        "title": "晴天", "artist": "周杰伦", "album": "叶惠美",
        "year": "2003", "mbid": "mbid-1",
    })
    view._save_song_details(None)
    assert library.songs["周杰伦 - 晴天.mp3"]["musicbrainz_mbid"] == "mbid-1"


def test_song_details_reparses_legacy_numbered_filename(tmp_path, monkeypatch):
    library = FakeMusicLibrary(tmp_path)
    library.add_remote_song("0172.五月天-倔强.mp3", "/song.mp3")
    library.songs["0172.五月天-倔强.mp3"].update(
        {"title": "0172.五月天-倔强", "artist": "未知艺术家"}
    )
    library.extract_song_info_from_filename = lambda _: {
        "title": "倔强", "artist": "五月天", "album": "未知专辑"
    }
    view, _ = make_file_list_view(
        FakePage(), FakeNextcloudClient(), library, FakeConfigManager(), monkeypatch
    )

    view._show_song_details("0172.五月天-倔强.mp3")

    assert view.song_title_input.value == "倔强"
    assert view.song_artist_input.value == "五月天"


async def test_song_details_keeps_editing_but_disables_online_query(
    tmp_path, monkeypatch
):
    library = FakeMusicLibrary(tmp_path)
    library.add_remote_song("song.mp3", "/song.mp3")
    page = FakePage()
    config = FakeConfigManager(
        {"metadata": {"musicbrainz_enabled": False}}
    )
    view, _ = make_file_list_view(
        page, FakeNextcloudClient(), library, config, monkeypatch
    )

    view._show_song_details("song.mp3")

    assert view.song_query_button.disabled is True
    assert "已在设置中关闭" in view.song_query_status.value
    view.song_title_input.value = "仍可手动编辑"
    view._save_song_details(None)
    assert library.songs["song.mp3"]["custom_title"] == "仍可手动编辑"


def test_remote_song_cloud_icon_reflects_its_source_connection(
    tmp_path, monkeypatch
):
    from nextcloud_music_player.utils.theme import Color

    library = FakeMusicLibrary(tmp_path)
    library.add_remote_song(
        "drive.mp3", "drive-file-id", source_type="gdrive"
    )
    view, service = make_file_list_view(
        FakePage(), FakeNextcloudClient(), library, FakeConfigManager(), monkeypatch
    )
    song = service.get_all_songs()[0]

    offline_item = view.build_file_item(song)
    assert offline_item.content.controls[1].color == Color.TEXT_DISABLED

    service.source_clients["gdrive"] = FakeNextcloudClient()
    online_item = view.build_file_item(song)
    assert online_item.content.controls[1].color == Color.PRIMARY


def test_delete_removes_selected_song_from_library(tmp_path, monkeypatch):
    library = FakeMusicLibrary(tmp_path)
    library.add_remote_song("remove.mp3", "/music/remove.mp3")
    view, _ = make_file_list_view(
        FakePage(), FakeNextcloudClient(), library, FakeConfigManager(), monkeypatch
    )
    view.selected_files = {"remove.mp3"}

    view._delete_selected(None)

    assert library.get_song_info("remove.mp3") is None
    assert view.selected_files == set()


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
    assert view.sync_button.text == "同步中…"
    assert "正在同步" in last_notification_text(page)

    await task
    assert view.sync_button.disabled is False           # 按钮恢复
    assert view.sync_button.text == "同步"
    assert len(view.file_list.controls) == 2            # 列表已刷新
    assert {s['name'] for s in view.music_service.get_all_songs()} == {"a.mp3", "b.mp3"}
    assert all(
        song["source_type"] == "nextcloud"
        for song in view.music_service.get_all_songs()
    )
    assert view.folder_text.value == "同步状态：2/2"
    assert view.music_service.last_sync_report == [{
        "source_type": "nextcloud",
        "folder": "/music",
        "folder_label": "/music",
        "song_count": 2,
        "synced_count": 2,
        "status": "success",
        "error": "",
    }]


async def test_sync_failure_shows_error_and_reenables(tmp_path, monkeypatch):
    page = FakePage()
    client = FakeNextcloudClient(list_error=RuntimeError("500 Server Error"))
    config = FakeConfigManager({"connection": {"default_sync_folder": "/music"}})
    view, _ = make_file_list_view(
        page, client, FakeMusicLibrary(tmp_path), config, monkeypatch)

    await view._sync_music_list(None)

    assert view.sync_button.disabled is False
    assert view.sync_button.text == "同步"
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
