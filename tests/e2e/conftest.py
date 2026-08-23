"""
e2e 测试共享配置。

flet 0.86.5 的 FletTestApp 只保留 Flutter 测试输出最近 256KB（__flutter_output_limit）。
应用启动时会把整棵控件树的增量 patch 逐行打出来（每条可达几十 KB），一次 `testWidgets`
里的异常日志会在该环形缓冲里被冲掉，导致 CI 里只见 "Test failed. See exception logs above."
却看不到真正的 Dart 异常。这里在 fixture 创建前把缓冲放宽，让 teardown 时能把完整异常转储出来。
"""

import flet.testing.flet_test_app as _fta

# 类级常量缺省为 256KB 行裁剪 2048 字节；放宽到足够容纳异常与堆栈。
_fta.FletTestApp._FletTestApp__flutter_output_limit = 200 * 1024 * 1024
_fta.FletTestApp._FletTestApp__flutter_output_line_limit = 512 * 1024