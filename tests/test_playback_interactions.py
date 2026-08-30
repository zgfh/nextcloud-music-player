"""
播放交互测试：慢网络下载提示、切歌竞态、失败反馈

直接驱动真实 PlaybackView 的协程入口（play_selected_song），
用 FakeNextcloudClient 模拟慢网络，断言：
- 状态胶囊在每个阶段有明确反馈（切换中/下载中/播放中/下载失败）
- 新点击会让旧的慢下载失效，不会出现"旧歌顶掉新选择"
- 下载/播放失败对用户可见，而不是只写日志
"""

import asyncio

from fakes import add_remote_song


async def test_play_downloaded_song_skips_download(playback_env):
    """已下载的歌曲立即播放，不发起网络请求"""
    info = add_remote_song(playback_env.library, "local.mp3", downloaded=True)

    ok = await playback_env.view.play_selected_song(info)

    assert ok is True
    assert playback_env.client.download_calls == []
    assert playback_env.player.loaded_files[-1].endswith("local.mp3")
    assert playback_env.player.stopped_count == 0
    assert playback_env.view.status_label.value == "播放中"


async def test_undownloaded_song_shows_downloading_status(playback_env):
    """未下载歌曲在慢网络下必须有"下载中"提示，完成后进入播放中"""
    add_remote_song(playback_env.library, "slow.mp3")
    playback_env.client.download_delay = 0.3
    info = playback_env.library.get_song_info("slow.mp3")

    task = asyncio.create_task(playback_env.view.play_selected_song(info))
    await asyncio.sleep(0.1)  # 下载进行中

    assert playback_env.view.status_label.value == "下载中..."
    assert len(playback_env.client.download_calls) == 1

    ok = await task
    assert ok is True
    assert playback_env.player.loaded_files[-1].endswith("slow.mp3")
    assert playback_env.view.status_label.value == "播放中"


async def test_new_click_supersedes_slow_download(playback_env):
    """先点慢歌 A 再点快歌 B：A 的下载结果必须被丢弃，不能顶掉 B。

    这是"切换点击新歌曲后还是播放旧的歌曲"的竞态根因：
    两个并发下载，慢的那个后完成时会把最新选择顶掉。
    """
    add_remote_song(playback_env.library, "A.mp3")
    add_remote_song(playback_env.library, "B.mp3")
    playback_env.client.download_delay = {"A.mp3": 0.5, "B.mp3": 0.05}

    task_a = asyncio.create_task(
        playback_env.view.play_selected_song(playback_env.library.get_song_info("A.mp3")))
    await asyncio.sleep(0.02)  # 让 A 进入下载中

    ok_b = await playback_env.view.play_selected_song(
        playback_env.library.get_song_info("B.mp3"))
    assert ok_b is True
    assert playback_env.player.loaded_files[-1].endswith("B.mp3")

    ok_a = await task_a  # A 的下载此刻才完成
    assert ok_a is False
    # A 全程不应被加载播放
    assert not any(p.endswith("A.mp3") for p in playback_env.player.loaded_files)
    assert playback_env.view.status_label.value == "播放中"


async def test_switching_song_stops_old_playback_immediately(playback_env):
    """点新歌（未下载、下载慢）时旧歌应立刻停止并显示下载中，而不是继续放旧歌"""
    old_info = add_remote_song(playback_env.library, "old.mp3", downloaded=True)
    add_remote_song(playback_env.library, "new.mp3")
    playback_env.client.download_delay = {"new.mp3": 0.3}

    assert await playback_env.view.play_selected_song(old_info) is True
    assert playback_env.player.playing is True

    task = asyncio.create_task(playback_env.view.play_selected_song(
        playback_env.library.get_song_info("new.mp3")))
    await asyncio.sleep(0.05)

    # 旧歌已停、状态明确显示正在下载新歌
    assert playback_env.player.playing is False
    assert playback_env.view.status_label.value == "下载中..."

    ok = await task
    assert ok is True
    assert playback_env.player.loaded_files[-1].endswith("new.mp3")
    assert playback_env.player.playing is True


async def test_download_failure_shows_error_status(playback_env):
    """下载失败必须反馈给用户，而不是静默只写日志"""
    add_remote_song(playback_env.library, "gone.mp3")
    playback_env.client.download_error = RuntimeError("404 Not Found")

    ok = await playback_env.view.play_selected_song(
        playback_env.library.get_song_info("gone.mp3"))

    assert ok is False
    assert playback_env.view.status_label.value == "下载失败"
    assert playback_env.player.loaded_files == []


async def test_download_exception_is_caught(playback_env):
    """下载抛异常（网络中断等）同样反馈且不崩溃"""
    add_remote_song(playback_env.library, "boom.mp3")
    playback_env.client.download_error = ConnectionError("network reset")

    ok = await playback_env.view.play_selected_song(
        playback_env.library.get_song_info("boom.mp3"))

    assert ok is False
    assert playback_env.view.status_label.value == "下载失败"


async def test_play_request_without_remote_path_fails_visibly(playback_env):
    """歌曲缺少远程路径时给出"无法播放"，而不是静默返回"""
    playback_env.library.add_remote_song("stale.mp3", "")
    playback_env.library.songs["stale.mp3"]["filepath"] = ""  # 确保不走本地分支

    ok = await playback_env.view.play_selected_song(
        playback_env.library.get_song_info("stale.mp3"))

    assert ok is False
    assert playback_env.view.status_label.value == "无法播放"
