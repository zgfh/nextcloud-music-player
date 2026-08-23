"""pytest fixtures：把 fakes.py 里的替身组装成各视图可用的测试环境"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# src 布局：保证未 pip install -e 时也能导入
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fakes import (  # noqa: E402
    FakeAudioPlayer,
    FakeConfigManager,
    FakeNextcloudClient,
    FakePage,
    FakeViewManager,
    make_music_service,
)

__all__ = [
    "FakeAudioPlayer", "FakeConfigManager", "FakeNextcloudClient",
    "FakePage", "FakeViewManager", "playback_env",
]


@pytest.fixture
def fake_page():
    return FakePage()


@pytest.fixture
def view_manager():
    return FakeViewManager()


@pytest.fixture
async def playback_env(tmp_path, monkeypatch):
    """完整播放环境：真实 PlaybackView/PlaybackService + 全套替身。

    必须是异步 fixture：view.build() 里会 asyncio.create_task 启动
    UI 定时刷新，需要在事件循环内执行。
    """
    import nextcloud_music_player.services.playback_service as playback_service_module
    from nextcloud_music_player.views.playback_view import PlaybackView

    page = FakePage()
    config_manager = FakeConfigManager()
    library = FakeMusicLibrary(tmp_path)
    client = FakeNextcloudClient()
    player = FakeAudioPlayer()

    monkeypatch.setattr(playback_service_module, "create_audio_player",
                        lambda page=None: player)
    monkeypatch.setattr(playback_service_module, "is_mobile", lambda: True)

    music_service = make_music_service(library, client, config_manager, monkeypatch)

    app_context = {
        "config_manager": config_manager,
        "music_service": music_service,
        "music_library": library,
        "lyrics_service": None,
        "nextcloud_client": client,
    }
    view = PlaybackView(page, app_context, FakeViewManager())
    view.build()

    yield SimpleNamespace(
        page=page, view=view, client=client, library=library,
        player=player, config=config_manager, music_service=music_service,
    )

    view._cancel_ui_timer()  # 结束 UI 定时刷新任务，避免悬挂任务告警


# FakeMusicLibrary 仅在 fixture 内使用，这里补一个便捷导入别名
from fakes import FakeMusicLibrary  # noqa: E402
