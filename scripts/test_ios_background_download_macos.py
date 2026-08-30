#!/usr/bin/env python3
"""macOS 上验证 iOS 原生后台下载模块（ios_background_download.py）。

Foundation 的 NSURLSession 在 macOS/iOS 行为一致（传输由 nsurlsessiond
执行、跨进程按 identifier 重联），本脚本绕过 is_ios 门禁直接创建真实
后台会话，在桌面端完成端到端验证，覆盖：

  1. 正常下载：进度回调、Basic 认证头送达、文件逐字节一致
  2. HTTP 404：错误页正文被拦截，报告为失败
  3. 强杀恢复：进程 A 提交任务后被 SIGKILL，进程 B 重建同名会话
     接收完成回调（模拟"用户划掉应用后下载继续"）

仅用于开发机验证（需要 macOS + rubicon-objc），不参与 pytest：
    uv run python scripts/test_ios_background_download_macos.py
    NCMP_KILL_PORT=45678 uv run python scripts/test_ios_background_download_macos.py --kill-only
"""

import asyncio
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nextcloud_music_player import ios_background_download as native  # noqa: E402

PAYLOAD = (b"ID3" + bytes(range(256))) * 4096  # ~1MB
KILL_PAYLOAD = (b"ID3" + bytes(range(256))) * 32768  # ~8MB，约 10s 传完，
# 确保 1.2s 的 SIGKILL 窗口稳定落在传输中途


def start_server(handler_cls):
    server = HTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


class SlowOKHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", str(len(PAYLOAD)))
        self.end_headers()
        for off in range(0, len(PAYLOAD), 64 * 1024):
            self.wfile.write(PAYLOAD[off : off + 64 * 1024])
            self.wfile.flush()
            time.sleep(0.002)

    def log_message(self, *a):
        pass


class SlowBigOKHandler(SlowOKHandler):
    payload = KILL_PAYLOAD

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", str(len(KILL_PAYLOAD)))
        self.end_headers()
        for off in range(0, len(KILL_PAYLOAD), 16 * 1024):
            self.wfile.write(KILL_PAYLOAD[off : off + 16 * 1024])
            self.wfile.flush()
            time.sleep(0.02)  # 约 2.6s 传完，给 SIGKILL 留窗口


class NotFoundHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"<html>Not Found</html>"
        self.send_response(404)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def make_state():
    if native._state is not None:  # 幂等：rubicon 不允许重复定义同名类
        return native._state
    state = native._create_native_state()  # 绕过 is_ios 门禁（仅限本脚本）
    assert state is not None, "创建后台 NSURLSession 失败"
    native._state = state
    return state


async def case_normal_download(tmp: Path):
    server = start_server(SlowOKHandler)
    port = server.server_address[1]
    auth_seen = []
    original = SlowOKHandler.do_GET

    def spy_get(self):
        auth_seen.append(self.headers.get("Authorization"))
        original(self)

    SlowOKHandler.do_GET = spy_get

    dest = tmp / "normal.mp3"
    progress = []
    ok, path, error = await native.download(
        f"http://127.0.0.1:{port}/song.mp3",
        {"Authorization": "Basic dXNlcjpwYXNz"},
        dest,
        key="normal.mp3",
        on_progress=lambda done, total: progress.append((done, total)),
    )
    server.shutdown()
    SlowOKHandler.do_GET = original

    assert ok, f"下载失败: {error}"
    assert auth_seen == ["Basic dXNlcjpwYXNz"], auth_seen
    assert len(progress) >= 2, f"进度回调过少: {len(progress)}"
    assert progress[-1][0] == len(PAYLOAD)
    assert dest.read_bytes() == PAYLOAD
    print(f"[1/2] 正常下载 OK（进度回调 {len(progress)} 次，内容一致）")


async def case_http_404(tmp: Path):
    server = start_server(NotFoundHandler)
    port = server.server_address[1]
    dest = tmp / "missing.mp3"

    ok, path, error = await asyncio.wait_for(
        native.download(
            f"http://127.0.0.1:{port}/missing.mp3", None, dest, key="missing.mp3"
        ),
        timeout=15,
    )
    server.shutdown()

    assert ok is False and "404" in (error or ""), (ok, error)
    assert not dest.exists(), "错误页正文不应落盘"
    print("[2/2] HTTP 404 拦截 OK")


async def main_cases():
    make_state()
    tmp = Path("/tmp/ncmp_native_smoke")
    tmp.mkdir(exist_ok=True)
    await case_normal_download(tmp)
    await case_http_404(tmp)
    print("SMOKE OK")


def kill_case():
    """父进程编排：victim 提交后 SIGKILL，recovery 重建会话接收。

    HTTP 服务器常驻父进程——真实场景里 Nextcloud 服务器不会随应用
    死亡；若服务器跟着 victim 死掉，nsurlsessiond 会因连接被拒进入
    退避重试，恢复时机不可控，测不出"任务跨进程存活"本身。
    """
    mode = sys.argv[1] if len(sys.argv) > 1 else "parent"

    # 强杀场景用独立 identifier：一个 identifier 同一时刻只能属于一个
    # 进程，宿主/其它用例若持有同名会话，victim 会拿到 -996
    native.SESSION_IDENTIFIER = native.SESSION_IDENTIFIER + ".killtest"

    if mode == "victim":
        # 服务器与 dest 由父进程通过环境变量提供
        port = int(os.environ["NCMP_KILL_PORT"])
        make_state()
        print("victim: 任务已提交", flush=True)
        result = asyncio.run(
            native.download(
                f"http://127.0.0.1:{port}/killed.mp3",
                None,
                "/tmp/ncmp_native_smoke/killed.mp3",
                key="killed-song.mp3",
            )
        )
        print(f"victim: 不应活着等到下载结束，结果={result}", flush=True)
        raise AssertionError("victim 不应活着等到下载完成")

    if mode == "recovery":

        async def wait_orphan():
            state = make_state()
            seen = []
            state.orphan_callback = lambda key, ok, path, err: seen.append(
                (key, ok, path, err)
            )
            state.main_loop = asyncio.get_running_loop()
            deadline = time.monotonic() + 30
            while not seen and time.monotonic() < deadline:
                await asyncio.sleep(0.3)
            return seen

        seen = asyncio.run(wait_orphan())
        assert seen, "孤儿回调未收到"
        key, ok, path, err = seen[0]
        assert ok and key == "killed-song.mp3", seen
        content = Path("/tmp/ncmp_native_smoke/killed.mp3").read_bytes()
        assert content == KILL_PAYLOAD, f"内容不一致 {len(content)}"
        print("强杀恢复 OK：victim 被 SIGKILL 后下载继续，recovery 落库成功")
        return

    # parent 编排：服务器全程常驻
    Path("/tmp/ncmp_native_smoke").mkdir(exist_ok=True)
    Path("/tmp/ncmp_native_smoke/killed.mp3").unlink(missing_ok=True)
    server = start_server(SlowBigOKHandler)
    port = server.server_address[1]
    env = dict(os.environ, NCMP_KILL_PORT=str(port))

    victim = subprocess.Popen(
        [sys.executable, __file__, "victim"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    line = victim.stdout.readline()
    assert "任务已提交" in line, f"victim 输出异常: {line}"
    time.sleep(1.2)  # 传输进行到约一半
    victim.kill()
    victim.wait()
    if victim.returncode != -9:
        # 提前自行退出的原因（正常应只在 SIGKILL 下死亡）
        print("victim 异常输出:\n" + victim.stdout.read())
        raise AssertionError(f"victim 应被 SIGKILL: {victim.returncode}")
    print(f"victim 已被 SIGKILL（退出码 {victim.returncode}），服务器保持常驻")

    result = subprocess.run(
        [sys.executable, __file__, "recovery"], check=False, env=env
    )
    server.shutdown()
    if result.returncode != 0:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "--kill-only":
        kill_case()
    elif arg in ("victim", "recovery"):
        kill_case()  # 父进程编排的子进程入口
    else:
        asyncio.run(main_cases())
        kill_case()
        print("ALL OK")
