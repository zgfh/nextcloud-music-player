"""
e2e 测试共享配置。

flet 0.86.5 的 FletTestApp 只保留 Flutter 测试输出最近 256KB（__flutter_output_limit）。
应用启动时会把整棵控件树的增量 patch 逐行打出来（每条可达几十 KB），一次 `testWidgets`
里的异常日志会在该环形缓冲里被冲掉，导致 CI 里只见 "Test failed. See exception logs above."
却看不到真正的 Dart 异常。这里在 fixture 创建前把缓冲放宽，让 teardown 时能把完整异常转储出来。

mock_nextcloud / mock_gdrive 位于上级 tests/ 目录；tests/e2e 无 __init__.py，
pytest 只会把 tests/e2e 挂进 sys.path，因此这里显式补上 tests/ 与 src/。
"""

import contextlib
import os
import sys
from pathlib import Path

import flet.testing.flet_test_app as _fta
import pytest

_E2E_DIR = Path(__file__).resolve().parent
for _path in (str(_E2E_DIR.parent), str(_E2E_DIR.parents[1] / "src")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from mock_gdrive import MockGdriveServer  # noqa: E402
from mock_nextcloud import MockNextcloudServer  # noqa: E402

# 类级常量缺省为 256KB 行裁剪 2048 字节；放宽到足够容纳异常与堆栈。
_fta.FletTestApp._FletTestApp__flutter_output_limit = 8 * 1024 * 1024
_fta.FletTestApp._FletTestApp__flutter_output_line_limit = 512 * 1024


@contextlib.contextmanager
def _loopback_proxy_bypass():
    """让打包 app 的 requests 直连 127.0.0.1，绕过宿主机代理环境变量。"""
    keys = ("NO_PROXY", "no_proxy")
    old_values = {key: os.environ.get(key) for key in keys}
    for key in keys:
        os.environ[key] = "127.0.0.1,localhost"
    try:
        yield
    finally:
        for key, value in old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.fixture
def mock_nextcloud_server():
    with _loopback_proxy_bypass():
        server = MockNextcloudServer.start()
        try:
            yield server
        finally:
            server.close()


@pytest.fixture
def mock_gdrive_server():
    with _loopback_proxy_bypass():
        server = MockGdriveServer.start()
        try:
            yield server
        finally:
            server.close()
