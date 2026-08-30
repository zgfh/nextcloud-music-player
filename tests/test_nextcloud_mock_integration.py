"""针对内置 Mock Nextcloud 服务器的真实 HTTP 客户端测试。

正常路径验证 NextCloudClient 的登录/同步/下载；
故障场景（401/404/断线/慢响应）通过 server.set_fault(...) 注入，
验证客户端把服务端异常转换成可判定的结果而不是崩溃。
"""

import time

import pytest
from mock_nextcloud import (
    LRC_BYTES,
    LYRICS_PATH,
    PASSWORD,
    SONG_NAME,
    SONG_PATH,
    USERNAME,
    WAV_BYTES,
    MockNextcloudServer,
)


@pytest.fixture
def mock_server(monkeypatch):
    # 开发机/CI 若配置了 HTTP 代理，requests 会把 127.0.0.1 也送进代理导致连接失败
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    server = MockNextcloudServer.start()
    try:
        yield server
    finally:
        server.clear_fault()
        server.close()


@pytest.fixture
def client(mock_server, tmp_path, monkeypatch):
    from nextcloud_music_player.config_manager import ConfigManager
    from nextcloud_music_player.nextcloud_client import NextCloudClient

    monkeypatch.setattr(ConfigManager, "_get_config_directory", lambda _self: tmp_path)
    return NextCloudClient(mock_server.url, USERNAME, PASSWORD)


async def test_mock_nextcloud_full_client_flow(client, mock_server, tmp_path):
    assert await client.test_connection() is True

    result = await client.sync_files("/music")
    assert result["error"] is None
    assert [item["name"] for item in result["files"]] == [SONG_NAME]
    assert result["files"][0]["path"] == SONG_PATH

    song_path = tmp_path / "downloaded.wav"
    lyrics_path = tmp_path / "downloaded.lrc"
    progress = []
    assert await client.download_file(
        SONG_PATH,
        SONG_NAME,
        str(song_path),
        progress_callback=lambda downloaded, total: progress.append(
            (downloaded, total)
        ),
    )
    assert await client.download_file(LYRICS_PATH, "test-tone.lrc", str(lyrics_path))
    assert song_path.read_bytes() == WAV_BYTES
    assert lyrics_path.read_bytes() == LRC_BYTES
    assert progress
    assert progress[-1] == (len(WAV_BYTES), len(WAV_BYTES))


async def test_wrong_password_is_rejected(mock_server):
    from nextcloud_music_player.config_manager import ConfigManager
    from nextcloud_music_player.nextcloud_client import NextCloudClient

    client = NextCloudClient(mock_server.url, USERNAME, "not-the-password")
    assert await client.test_connection() is False


async def test_server_401_disables_valid_credentials_then_recovers(client, mock_server):
    assert await client.test_connection() is True

    mock_server.set_fault(status=401)
    assert await client.test_connection() is False

    mock_server.clear_fault()
    assert await client.test_connection() is True


async def test_propfind_404_surfaces_sync_error(client, mock_server):
    mock_server.set_fault(status=404)
    result = await client.sync_files("/music")
    assert result["files"] == []
    assert "404" in result["error"]


async def test_dropped_connection_fails_cleanly(client, mock_server):
    mock_server.set_fault(drop=True)
    assert await client.test_connection() is False


async def test_download_404_raises_and_writes_nothing(client, mock_server, tmp_path):
    target = tmp_path / "missing.wav"
    mock_server.set_fault(status=404)
    with pytest.raises(Exception, match="All download methods failed"):
        await client.download_file(SONG_PATH, SONG_NAME, str(target))
    assert not target.exists()


async def test_slow_response_still_succeeds(client, mock_server):
    mock_server.set_fault(delay_seconds=0.3)
    started = time.monotonic()
    assert await client.test_connection() is True
    assert time.monotonic() - started >= 0.3
