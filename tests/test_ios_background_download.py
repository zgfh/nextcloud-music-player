"""ios_background_download：URL 构造、状态机分发、MusicService 集成与回退。

原生 ObjC 层无法在测试环境运行，这里覆盖的是与 rubicon 解耦的
纯 Python 状态机（_DownloadState），以及 MusicService 对原生下载的
选择逻辑（原生优先、SMB/不可用/提交异常时回退 requests）。
"""

import asyncio
import sys
from pathlib import Path

import pytest

from nextcloud_music_player import ios_background_download as native
from nextcloud_music_player.services.music_service import MusicService
from tests.fakes import FakeConfigManager, FakeMusicLibrary, FakeNextcloudClient

REMOTE_PATH = "/remote.php/dav/files/user/Music/song.mp3"


# ---------------------------------------------------------------------------
# build_webdav_url
# ---------------------------------------------------------------------------


def test_build_webdav_url_keeps_encoded_href_stable():
    # PROPFIND href 本身已百分号编码，二次编码会破坏 URL
    href = "/remote.php/dav/files/user/Music/%E6%AD%8C%E6%9B%B2.mp3"
    assert (
        native.build_webdav_url("https://cloud.example.com/", href)
        == "https://cloud.example.com/remote.php/dav/files/user/Music/%E6%AD%8C%E6%9B%B2.mp3"
    )


def test_build_webdav_url_encodes_raw_unicode_once():
    url = native.build_webdav_url("https://cloud.example.com", "/Music/歌曲.mp3")
    assert url == "https://cloud.example.com/Music/%E6%AD%8C%E6%9B%B2.mp3"


def test_build_webdav_url_adds_leading_slash():
    assert (
        native.build_webdav_url("http://nas.local:8080", "remote.php/dav/f.mp3")
        == "http://nas.local:8080/remote.php/dav/f.mp3"
    )


@pytest.mark.parametrize("server", ["", None, "smb://server/share"])
def test_build_webdav_url_rejects_non_http_source(server):
    assert native.build_webdav_url(server, REMOTE_PATH) is None


# ---------------------------------------------------------------------------
# _DownloadState 状态机
# ---------------------------------------------------------------------------


class FakeNSError:
    """NSError 替身：属性访问与 rubicon 暴露方式一致"""

    domain = "NSURLErrorDomain"
    code = -1009

    def __init__(self, resume_data=None):
        self.userInfo = (
            {"NSURLSessionDownloadTaskResumeData": resume_data}
            if resume_data is not None
            else {}
        )

    def localizedDescription(self):
        return "The Internet connection appears to be offline."


class FakeNativeTask:
    def __init__(self):
        self.description = None
        self.resumed = False

    def setTaskDescription_(self, value):
        self.description = value

    def resume(self):
        self.resumed = True


class FakeResumeSession:
    def __init__(self):
        self.resume_submissions = []

    def downloadTaskWithResumeData_(self, data):
        self.resume_submissions.append(data)
        return FakeNativeTask()


async def test_state_success_flow_moves_file_and_resolves_future(tmp_path):
    state = native._DownloadState()
    progress_seen = []

    fut = state.register(
        "song.mp3", lambda done, total: progress_seen.append((done, total))
    )

    source = tmp_path / "tmp-download"
    source.write_bytes(b"payload")
    dest = tmp_path / "music" / "song.mp3"

    state.handle_progress("song.mp3", 50, 100)
    final_path = state.handle_downloaded(
        "song.mp3", {"key": "song.mp3", "dest": str(dest)}, str(source)
    )
    state.handle_complete("song.mp3", {}, None)

    success, path, error = await fut
    assert success is True
    assert error is None
    assert path == final_path == str(dest)
    assert dest.read_bytes() == b"payload"
    assert not source.exists()
    assert progress_seen == [(50, 100)]
    # 登记已清理，后续同 key 交付按孤儿处理
    assert state.entries == {}


async def test_state_failure_reports_error_without_retry(tmp_path):
    state = native._DownloadState()
    fut = state.register("song.mp3", None)

    state.handle_complete("song.mp3", {}, FakeNSError())

    success, path, error = await fut
    assert success is False
    assert path is None
    assert (
        error
        == "NSURLErrorDomain(-1009): The Internet connection appears to be offline."
    )


async def test_state_retries_once_with_resume_data(tmp_path):
    state = native._DownloadState()
    session = FakeResumeSession()
    fut = state.register("song.mp3", None)
    meta = {"key": "song.mp3", "dest": str(tmp_path / "song.mp3")}

    # 第一次失败携带 resumeData：不结算，原地续传
    state.handle_complete("song.mp3", meta, FakeNSError(resume_data=b"resume"), session)
    assert not fut.done()
    assert len(session.resume_submissions) == 1
    assert state.retried == {"song.mp3"}

    # 第二次失败（无 resumeData）：结算为失败
    state.handle_complete("song.mp3", meta, FakeNSError(), session)
    success, _path, error = await fut
    assert success is False
    assert "offline" in error
    # 只续传过一次
    assert len(session.resume_submissions) == 1


async def test_state_orphan_completion_runs_callback_on_main_loop(tmp_path):
    state = native._DownloadState()
    state.main_loop = asyncio.get_running_loop()
    seen = []

    def orphan(key, success, final_path, error):
        seen.append((key, success, final_path, error))

    state.orphan_callback = orphan

    source = tmp_path / "tmp-download"
    source.write_bytes(b"payload")
    dest = tmp_path / "music" / "song.mp3"

    state.handle_downloaded(
        "song.mp3", {"key": "song.mp3", "dest": str(dest)}, str(source)
    )
    state.handle_complete("song.mp3", {}, None)

    # call_soon_threadsafe 转回主循环执行
    for _ in range(4):
        await asyncio.sleep(0)

    assert seen == [("song.mp3", True, str(dest), None)]


async def test_state_orphan_without_loop_runs_inline(tmp_path):
    state = native._DownloadState()
    seen = []
    state.orphan_callback = lambda *args: seen.append(args)

    state.handle_complete("song.mp3", {}, FakeNSError())

    assert seen == [
        (
            "song.mp3",
            False,
            None,
            "NSURLErrorDomain(-1009): The Internet connection appears to be offline.",
        )
    ]


async def test_state_complete_without_receiver_is_safe():
    state = native._DownloadState()
    state.handle_complete("unknown.mp3", {}, None)  # 不应抛异常


async def test_state_rejects_http_error_status(tmp_path):
    """URLSession 不把 404 当传输错误，错误页正文必须被拦截"""
    state = native._DownloadState()
    fut = state.register("song.mp3", None)

    source = tmp_path / "tmp-download"
    source.write_bytes(b"<html>Not Found</html>")
    dest = tmp_path / "song.mp3"

    state.handle_downloaded(
        "song.mp3",
        {"key": "song.mp3", "dest": str(dest)},
        str(source),
        http_status=404,
    )
    state.handle_complete("song.mp3", {}, None)

    success, path, error = await fut
    assert success is False
    assert error == "HTTP 404"
    assert not dest.exists()  # 错误页不能落盘
    assert not source.exists()  # 临时文件已清理


async def test_state_accepts_2xx_status(tmp_path):
    state = native._DownloadState()
    fut = state.register("song.mp3", None)

    source = tmp_path / "tmp-download"
    source.write_bytes(b"payload")
    dest = tmp_path / "song.mp3"

    state.handle_downloaded(
        "song.mp3",
        {"key": "song.mp3", "dest": str(dest)},
        str(source),
        http_status=206,
    )
    state.handle_complete("song.mp3", {}, None)

    success, path, _error = await fut
    assert success is True and dest.read_bytes() == b"payload"


def test_http_status_helper():
    class FakeResponse:
        statusCode = 403

    assert native._http_status(FakeResponse()) == 403
    assert native._http_status(object()) is None  # 非 HTTP 响应


# ---------------------------------------------------------------------------
# activate 装配
# ---------------------------------------------------------------------------


class FakeService:
    def handle_orphan_native_download(self, *args):
        pass


async def test_activate_wires_orphan_handler_and_loop(monkeypatch):
    state = native._DownloadState()
    monkeypatch.setattr(native, "_ensure_state", lambda: state)
    service = FakeService()

    assert native.activate(service) is True
    assert state.orphan_callback == service.handle_orphan_native_download
    assert state.main_loop is asyncio.get_running_loop()


def test_activate_is_noop_when_unavailable(monkeypatch):
    monkeypatch.setattr(native, "_ensure_state", lambda: None)
    assert native.activate(FakeService()) is False


def test_disable_makes_is_available_false(monkeypatch):
    monkeypatch.setattr(native, "_disabled_reason", None)  # 便于清理
    assert native.is_available() in (True, False)  # 未禁用时由平台决定
    native.disable("测试禁用")
    assert native.is_available() is False


async def test_state_logs_http_error_status(tmp_path, caplog):
    state = native._DownloadState()
    source = tmp_path / "tmp-download"
    source.write_bytes(b"<html>err</html>")

    with caplog.at_level(
        "WARNING", logger="nextcloud_music_player.ios_background_download"
    ):
        state.handle_downloaded(
            "song.mp3",
            {"key": "song.mp3", "dest": str(tmp_path / "s.mp3")},
            str(source),
            http_status=500,
        )

    assert any("HTTP 500" in r.message for r in caplog.records)


def test_handle_orphan_native_download_failure_is_logged(tmp_path, caplog):
    service, _library = make_service(tmp_path, FakeNativeSourceClient())

    with caplog.at_level(
        "ERROR", logger="nextcloud_music_player.services.music_service"
    ):
        service.handle_orphan_native_download(
            "song.mp3", False, None, "NSURLErrorDomain(-1009)"
        )

    assert any(
        "后台遗留下载失败" in r.message and "NSURLErrorDomain(-1009)" in r.message
        for r in caplog.records
    )


# ---------------------------------------------------------------------------
# MusicService 集成
# ---------------------------------------------------------------------------


class FakeNativeSourceClient:
    """带 HTTP 凭据的来源客户端（SMB 客户端没有这些属性）"""

    server_url = "https://cloud.example.com"
    username = "user"
    password = "app-password"

    def __init__(self):
        self.download_calls = []

    async def download_file(
        self, file_path, file_name, local_path=None, progress_callback=None
    ):
        self.download_calls.append((file_path, file_name))
        path = Path(local_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"via-requests")
        return str(path)


def make_service(tmp_path, client):
    library = FakeMusicLibrary(tmp_path)
    library.add_remote_song("song.mp3", REMOTE_PATH)
    service = MusicService(library, client, FakeConfigManager())
    return service, library


def install_native_fake(monkeypatch, result=None, error=None, raise_exc=None):
    """替换原生下载入口（submit：提交即返回 future）；返回调用记录列表"""
    calls = []

    def fake_submit(url, headers, dest, key, on_progress=None):
        calls.append({"url": url, "headers": headers, "dest": str(dest), "key": key})
        if raise_exc is not None:
            raise raise_exc
        fut = asyncio.get_event_loop().create_future()
        if on_progress is not None:
            on_progress(50, 100)
        if result is False:
            fut.set_result((False, None, error))
        else:
            dest_path = Path(dest)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(b"via-native")
            fut.set_result((True, str(dest_path), None))
        return fut

    monkeypatch.setattr(native, "is_available", lambda: True)
    monkeypatch.setattr(native, "submit", fake_submit)
    return calls


async def test_download_file_prefers_native_and_marks_library(tmp_path, monkeypatch):
    client = FakeNativeSourceClient()
    service, library = make_service(tmp_path, client)
    calls = install_native_fake(monkeypatch)

    assert await service.download_file(REMOTE_PATH, "song.mp3") is True

    assert len(calls) == 1
    assert calls[0]["url"] == f"https://cloud.example.com{REMOTE_PATH}"
    assert calls[0]["headers"]["Authorization"].startswith("Basic ")
    assert calls[0]["dest"] == str(library.music_dir / "song.mp3")
    # 原生路径成功后不应触碰 requests 回退
    assert client.download_calls == []
    assert library.songs["song.mp3"]["is_downloaded"] is True
    snapshot = service.download_progress.snapshot()
    assert snapshot["status"] == "completed"
    assert snapshot["completed"] == 1
    assert snapshot["total_bytes"] == 100
    assert snapshot["downloaded_bytes"] == 100  # 完成后补齐到总量


async def test_download_file_skips_native_for_smb_client(tmp_path, monkeypatch):
    client = FakeNextcloudClient()  # 无 server_url/username/password 属性
    service, _library = make_service(tmp_path, client)
    calls = install_native_fake(monkeypatch)

    assert await service.download_file(REMOTE_PATH, "song.mp3")

    assert calls == []  # 原生不适用
    assert len(client.download_calls) == 1


async def test_download_file_falls_back_when_native_unavailable(tmp_path, monkeypatch):
    client = FakeNativeSourceClient()
    service, _library = make_service(tmp_path, client)
    monkeypatch.setattr(native, "is_available", lambda: False)

    assert await service.download_file(REMOTE_PATH, "song.mp3")
    assert len(client.download_calls) == 1


async def test_download_file_falls_back_when_native_submit_fails(tmp_path, monkeypatch):
    client = FakeNativeSourceClient()
    service, _library = make_service(tmp_path, client)
    install_native_fake(monkeypatch, raise_exc=RuntimeError("session gone"))

    assert await service.download_file(REMOTE_PATH, "song.mp3")
    assert len(client.download_calls) == 1


async def test_download_file_native_transfer_failure_returns_false(
    tmp_path, monkeypatch
):
    client = FakeNativeSourceClient()
    service, library = make_service(tmp_path, client)
    install_native_fake(monkeypatch, result=False, error="boom")

    assert await service.download_file(REMOTE_PATH, "song.mp3") is False

    # 传输已由原生会话执行过，不再回退 requests
    assert client.download_calls == []
    assert library.songs["song.mp3"]["is_downloaded"] is False
    assert service.download_progress.snapshot()["status"] == "failed"


async def test_download_file_disables_native_on_ats_error(tmp_path, monkeypatch):
    """ATS 拦截（-1022）是配置级错误：禁用原生路径并回退 requests"""
    monkeypatch.setattr(native, "_disabled_reason", None)  # 便于清理
    client = FakeNativeSourceClient()
    service, library = make_service(tmp_path, client)
    install_native_fake(
        monkeypatch,
        result=False,
        error='Error Domain=NSURLErrorDomain Code=-1022 "App Transport Security policy requires..."',
    )

    assert await service.download_file(REMOTE_PATH, "song.mp3")

    # 当前文件已回退 requests 完成
    assert len(client.download_calls) == 1
    assert library.songs["song.mp3"]["is_downloaded"] is True
    # 原生路径已在本进程内禁用（is_available 已被本测试替换，真实
    # 行为在 test_disable_makes_is_available_false 中验证）
    assert native._disabled_reason is not None


def test_handle_orphan_native_download_marks_library(tmp_path):
    client = FakeNativeSourceClient()
    service, library = make_service(tmp_path, client)

    service.handle_orphan_native_download("song.mp3", True, str(tmp_path / "song.mp3"))

    assert library.songs["song.mp3"]["is_downloaded"] is True
    assert service.download_progress.snapshot()["status"] == "completed"


def test_handle_orphan_native_download_failure_does_not_mark(tmp_path):
    service, library = make_service(tmp_path, FakeNativeSourceClient())

    service.handle_orphan_native_download("song.mp3", False, None, "lost")

    assert library.songs["song.mp3"]["is_downloaded"] is False
    assert service.download_progress.snapshot()["status"] == "failed"


# ---------------------------------------------------------------------------
# download_batch：整批一次性提交（后台/被杀继续的关键）
# ---------------------------------------------------------------------------


async def test_download_batch_submits_all_before_any_completes(tmp_path, monkeypatch):
    """原生批量：整批任务先全部进入系统队列，完成与提交解耦"""
    client = FakeNativeSourceClient()
    service, library = make_service(tmp_path, client)
    for name in ("a.mp3", "b.mp3"):
        library.add_remote_song(name, REMOTE_PATH)

    submitted = []
    pending = {}

    def fake_submit(url, headers, dest, key, on_progress=None):
        submitted.append(key)
        fut = asyncio.get_event_loop().create_future()
        pending[key] = (fut, str(dest))
        return fut

    monkeypatch.setattr(native, "is_available", lambda: True)
    monkeypatch.setattr(native, "submit", fake_submit)

    items = [(REMOTE_PATH, name) for name in ("song.mp3", "a.mp3", "b.mp3")]
    task = asyncio.create_task(service.download_batch(items))
    for _ in range(10):
        await asyncio.sleep(0)

    # 提交全部完成，而没有任何一首需要等上一首完成
    assert sorted(submitted) == ["a.mp3", "b.mp3", "song.mp3"]
    snapshot = service.download_progress.snapshot()
    assert snapshot["downloading"] == 3

    def complete(key, ok):
        fut, dest = pending[key]
        if ok:
            Path(dest).write_bytes(b"via-native")
            fut.set_result((True, dest, None))
        else:
            fut.set_result((False, None, "boom"))

    complete("song.mp3", True)
    complete("a.mp3", True)
    complete("b.mp3", False)

    events = []
    success, failed = await task
    assert (success, failed) == (2, 1)
    assert library.songs["song.mp3"]["is_downloaded"] is True
    assert library.songs["b.mp3"]["is_downloaded"] is False


async def test_download_batch_notifies_each_completion(tmp_path, monkeypatch):
    client = FakeNativeSourceClient()
    service, library = make_service(tmp_path, client)
    library.add_remote_song("a.mp3", REMOTE_PATH)
    monkeypatch.setattr(native, "is_available", lambda: False)

    events = []
    success, failed = await service.download_batch(
        [(REMOTE_PATH, "song.mp3"), (REMOTE_PATH, "a.mp3")],
        on_complete=lambda name, ok: events.append((name, ok)),
    )

    assert (success, failed) == (2, 0)
    # 回退路径逐首执行，顺序保持
    assert client.download_calls[0] == (REMOTE_PATH, "song.mp3")
    assert len(client.download_calls) == 2
    assert events == [("song.mp3", True), ("a.mp3", True)]
