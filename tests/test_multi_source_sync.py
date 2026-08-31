"""多来源连接、目录同步与下载路由回归测试。"""

from fakes import FakeConfigManager, FakeMusicLibrary, FakeNextcloudClient


async def test_sync_all_connected_sources_and_folders(tmp_path):
    from nextcloud_music_player.services.music_service import MusicService

    nextcloud = FakeNextcloudClient(files=[{"name": "next.mp3", "path": "/n.mp3"}])
    gdrive = FakeNextcloudClient(files=[{"name": "drive.mp3", "path": "file-id"}])
    config = FakeConfigManager({
        "connection": {
            "sync_folders": ["/Music", "/Live"],
            "gdrive": {"sync_folders": ["folder-a", "folder-b"]},
        }
    })
    library = FakeMusicLibrary(tmp_path)
    service = MusicService(
        library, None, config,
        source_clients={"nextcloud": nextcloud, "gdrive": gdrive},
    )

    files = await service.sync_all_sources()

    assert nextcloud.list_calls == ["/Music", "/Live"]
    assert gdrive.list_calls == ["folder-a", "folder-b"]
    assert len(files) == 4
    assert library.songs["next.mp3"]["source_type"] == "nextcloud"
    assert library.songs["drive.mp3"]["source_type"] == "gdrive"


async def test_download_uses_song_source_client(tmp_path, monkeypatch):
    from nextcloud_music_player.services.music_service import MusicService
    import nextcloud_music_player.utils.audio_normalize as normalize

    monkeypatch.setattr(normalize, "normalize_audio_async", lambda path: _done())
    nextcloud = FakeNextcloudClient()
    gdrive = FakeNextcloudClient()
    library = FakeMusicLibrary(tmp_path)
    library.add_remote_song("drive.mp3", "file-id", source_type="gdrive")
    service = MusicService(
        library, nextcloud, FakeConfigManager(),
        source_clients={"nextcloud": nextcloud, "gdrive": gdrive},
    )

    assert await service._download_one_inner("file-id", "drive.mp3") is True
    assert gdrive.download_calls == [("file-id", "drive.mp3")]
    assert nextcloud.download_calls == []


async def _done():
    return None
